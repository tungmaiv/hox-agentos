"""
Blitz AgentOS — Telegram Channel Sidecar.

FastAPI service that translates between Telegram Bot API and InternalMessage format.

Endpoints:
  POST /webhook  — receive Telegram Update, translate to InternalMessage, forward to backend
  POST /send     — receive InternalMessage, translate to Telegram sendMessage
  GET  /health   — health check

Environment variables:
  TELEGRAM_BOT_TOKEN   — bot token from @BotFather (required)
  TELEGRAM_WEBHOOK_URL — external URL for webhook registration (optional)
  BACKEND_URL          — backend base URL (default: http://backend:8000)
  BOT_USERNAME         — bot username without @ (optional, auto-detected from token if not set)
"""
import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

from telegram_api import TelegramAPI

logger = structlog.get_logger(__name__)

# -- Configuration ---------------------------------------------------------

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_URL = os.environ.get("TELEGRAM_WEBHOOK_URL", "")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "").lower()

# Telegram API instance (initialized after token is available)
telegram_api: TelegramAPI | None = None

# Max Telegram message length
MAX_MESSAGE_LENGTH = 4096
TRUNCATION_SUFFIX = "... (response truncated)"


# -- Pydantic models matching InternalMessage from backend -----------------


class MessageAction(BaseModel):
    label: str
    action_id: str
    style: str = "primary"


class Attachment(BaseModel):
    type: str
    url: str | None = None
    file_path: str | None = None
    mime_type: str | None = None


class InternalMessage(BaseModel):
    direction: str
    channel: str = "telegram"
    external_user_id: str
    external_chat_id: str | None = None
    user_id: str | None = None
    conversation_id: str | None = None
    text: str | None = None
    attachments: list[Attachment] = []
    actions: list[MessageAction] = []
    is_group: bool = False
    metadata: dict = {}


# -- Lifespan (webhook registration) --------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Register webhook on startup if TELEGRAM_WEBHOOK_URL is set."""
    global telegram_api
    if TELEGRAM_BOT_TOKEN:
        telegram_api = TelegramAPI(TELEGRAM_BOT_TOKEN)
        if TELEGRAM_WEBHOOK_URL:
            await telegram_api.set_webhook(
                TELEGRAM_WEBHOOK_URL,
                allowed_updates=["message", "callback_query"],
            )
            logger.info("webhook_registered", url=TELEGRAM_WEBHOOK_URL)
        else:
            logger.warning("no_webhook_url", hint="Set TELEGRAM_WEBHOOK_URL to register webhook")
    else:
        logger.warning("no_bot_token", hint="Set TELEGRAM_BOT_TOKEN to enable Telegram integration")
    yield


app = FastAPI(title="Blitz Telegram Gateway", lifespan=lifespan)


# -- Helper functions ------------------------------------------------------


def _extract_bot_mention(entities: list[dict], text: str) -> bool:
    """Check if the bot is @mentioned in message entities."""
    if not BOT_USERNAME:
        return False
    for entity in entities:
        if entity.get("type") == "mention":
            offset = entity.get("offset", 0)
            length = entity.get("length", 0)
            mention = text[offset : offset + length].lower()
            if mention == f"@{BOT_USERNAME}":
                return True
        if entity.get("type") == "bot_command":
            return True  # Commands are always directed at us in groups with BotFather privacy
    return False


def _has_media_only(message: dict) -> bool:
    """Check if a message contains media but no text."""
    media_fields = ("photo", "document", "audio", "video", "voice", "sticker", "animation")
    has_media = any(message.get(field) for field in media_fields)
    has_text = bool(message.get("text") or message.get("caption"))
    return has_media and not has_text


def _truncate_text(text: str) -> str:
    """Truncate text to Telegram's 4096 char limit."""
    if len(text) <= MAX_MESSAGE_LENGTH:
        return text
    return text[: MAX_MESSAGE_LENGTH - len(TRUNCATION_SUFFIX)] + TRUNCATION_SUFFIX


# -- Endpoints -------------------------------------------------------------


@app.post("/webhook")
async def webhook(request: Request) -> Response:
    """
    Receive a Telegram Update and forward as InternalMessage to backend.

    Handles:
      - Text messages (private and group)
      - Callback queries (inline button presses)
      - Group @mention filtering
      - Media-only message rejection
    """
    if not telegram_api:
        return Response(content='{"ok":false,"error":"not configured"}', status_code=503)

    update: dict[str, Any] = await request.json()

    # -- Handle callback_query -----------------------------------------------
    callback_query = update.get("callback_query")
    if callback_query:
        from_user = callback_query.get("from", {})
        message = callback_query.get("message", {})
        chat = message.get("chat", {})

        internal_msg = InternalMessage(
            direction="inbound",
            channel="telegram",
            external_user_id=str(from_user.get("id", "")),
            external_chat_id=str(chat.get("id", "")),
            text=callback_query.get("data", ""),
            is_group=chat.get("type", "private") in ("group", "supergroup"),
            metadata={
                "callback_data": callback_query.get("data", ""),
                "callback_query_id": callback_query.get("id", ""),
                "display_name": _build_display_name(from_user),
                "message_id": message.get("message_id"),
            },
        )

        await _forward_to_backend(internal_msg)
        return Response(content='{"ok":true}', status_code=200)

    # -- Handle message ------------------------------------------------------
    message = update.get("message")
    if not message:
        return Response(content='{"ok":true}', status_code=200)

    from_user = message.get("from", {})
    chat = message.get("chat", {})
    chat_type = chat.get("type", "private")
    is_group = chat_type in ("group", "supergroup")
    text = message.get("text") or message.get("caption") or ""
    entities = message.get("entities", [])

    # Group @mention filter: skip if no bot mention
    if is_group and not _extract_bot_mention(entities, text):
        return Response(content='{"ok":true}', status_code=200)

    # Media-only rejection
    if _has_media_only(message):
        await telegram_api.send_message(
            chat_id=chat.get("id"),
            text=TelegramAPI.escape_markdown_v2(
                "I can only process text messages at the moment."
            ),
        )
        return Response(content='{"ok":true}', status_code=200)

    # Send typing indicator
    await telegram_api.send_chat_action(chat_id=chat.get("id"), action="typing")

    # Build InternalMessage
    internal_msg = InternalMessage(
        direction="inbound",
        channel="telegram",
        external_user_id=str(from_user.get("id", "")),
        external_chat_id=str(chat.get("id", "")),
        text=text,
        is_group=is_group,
        metadata={
            "display_name": _build_display_name(from_user),
            "message_id": message.get("message_id"),
        },
    )

    await _forward_to_backend(internal_msg)
    return Response(content='{"ok":true}', status_code=200)


@app.post("/send")
async def send(request: Request) -> Response:
    """
    Receive an InternalMessage and send via Telegram Bot API.

    Handles:
      - Text formatting (MarkdownV2 escaping)
      - Message truncation at 4096 chars
      - InlineKeyboard buttons from actions
      - Reply threading via metadata.reply_to_message_id
    """
    if not telegram_api:
        return Response(content='{"ok":false,"error":"not configured"}', status_code=503)

    body: dict[str, Any] = await request.json()
    msg = InternalMessage.model_validate(body)

    chat_id = msg.external_chat_id
    if not chat_id:
        return Response(
            content='{"ok":false,"error":"missing external_chat_id"}',
            status_code=400,
        )

    text = msg.text or ""
    escaped_text = TelegramAPI.escape_markdown_v2(text)
    escaped_text = _truncate_text(escaped_text)

    # Build reply markup if actions present
    reply_markup = None
    if msg.actions:
        action_dicts = [
            {"label": a.label, "action_id": a.action_id} for a in msg.actions
        ]
        reply_markup = TelegramAPI.build_inline_keyboard(action_dicts)

    # Reply to specific message if metadata has reply_to_message_id
    reply_to = msg.metadata.get("reply_to_message_id")

    result = await telegram_api.send_message(
        chat_id=chat_id,
        text=escaped_text,
        reply_to_message_id=reply_to,
        reply_markup=reply_markup,
    )

    return Response(
        content='{"ok":true}',
        status_code=200,
    )


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "telegram-gateway"}


# -- Internal helpers ------------------------------------------------------


def _build_display_name(from_user: dict) -> str:
    """Build display name from Telegram user object."""
    parts = []
    if from_user.get("first_name"):
        parts.append(from_user["first_name"])
    if from_user.get("last_name"):
        parts.append(from_user["last_name"])
    return " ".join(parts) if parts else str(from_user.get("id", "unknown"))


async def _forward_to_backend(msg: InternalMessage) -> None:
    """POST InternalMessage to backend /api/channels/incoming."""
    url = f"{BACKEND_URL}/api/channels/incoming"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json=msg.model_dump(),
                timeout=30.0,
            )
            if resp.status_code != 200:
                logger.error(
                    "backend_forward_failed",
                    status=resp.status_code,
                    body=resp.text[:200],
                )
            else:
                logger.info(
                    "message_forwarded",
                    external_user_id=msg.external_user_id,
                    channel="telegram",
                    is_group=msg.is_group,
                )
    except httpx.HTTPError as exc:
        logger.error(
            "backend_forward_error",
            error=str(exc),
            external_user_id=msg.external_user_id,
        )
