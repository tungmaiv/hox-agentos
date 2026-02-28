"""
WhatsApp Cloud API sidecar for Blitz AgentOS.

Handles:
- GET  /webhook  — WhatsApp verification challenge (hub.verify_token handshake)
- POST /webhook  — Inbound Cloud API message events -> InternalMessage -> backend
- POST /send     — Outbound InternalMessage -> WhatsApp Cloud API
- GET  /health   — Service health check

DM-only for MVP (no group support).
Text-only for MVP (attachment messages get a rejection response).
"""

import os
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

from whatsapp_api import WhatsAppAPI

logger = structlog.get_logger(__name__)

app = FastAPI(title="Blitz WhatsApp Gateway", version="0.1.0")

# --- Configuration from environment ---
WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")

# --- WhatsApp API client (lazy init to allow test override) ---
_wa_api: WhatsAppAPI | None = None

MAX_MESSAGE_LENGTH = 4096
TRUNCATION_SUFFIX = "... (response truncated)"


def get_wa_api() -> WhatsAppAPI:
    """Get or create the WhatsApp API client singleton."""
    global _wa_api
    if _wa_api is None:
        _wa_api = WhatsAppAPI(WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID)
    return _wa_api


# --- Pydantic models for send endpoint ---
class MessageAction(BaseModel):
    label: str
    action_id: str
    style: str = "primary"


class SendRequest(BaseModel):
    direction: str = "outbound"
    channel: str = "whatsapp"
    external_user_id: str
    external_chat_id: str | None = None
    text: str | None = None
    actions: list[MessageAction] = []
    metadata: dict[str, Any] = {}


# --- Routes ---


@app.get("/webhook")
async def webhook_verify(
    request: Request,
) -> Response:
    """WhatsApp webhook verification challenge.

    WhatsApp sends GET with hub.mode, hub.verify_token, hub.challenge.
    If mode is "subscribe" and token matches, return challenge as plain text.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        logger.info("webhook_verified")
        return Response(content=challenge, media_type="text/plain")

    logger.warning("webhook_verification_failed", mode=mode)
    return Response(content="Forbidden", status_code=403)


@app.post("/webhook")
async def webhook_receive(request: Request) -> dict:
    """Receive inbound WhatsApp Cloud API webhook events.

    Parses the event, extracts message details, translates to InternalMessage,
    and forwards to the backend channel incoming endpoint.

    Returns 200 immediately (WhatsApp requires fast response).
    """
    body = await request.json()

    try:
        entry = body.get("entry", [])
        if not entry:
            return {"status": "ok"}

        changes = entry[0].get("changes", [])
        if not changes:
            return {"status": "ok"}

        value = changes[0].get("value", {})
        messages = value.get("messages", [])
        if not messages:
            return {"status": "ok"}

        message = messages[0]
        from_number = message.get("from", "")
        message_type = message.get("type", "")

        # Attachment detection: text-only MVP
        if message_type in ("image", "document", "audio", "video"):
            wa_api = get_wa_api()
            await wa_api.send_text(
                from_number,
                "I can only process text messages for now. "
                "Please send your request as text.",
            )
            logger.info(
                "attachment_rejected",
                from_number=from_number,
                message_type=message_type,
            )
            return {"status": "ok"}

        # Extract text content
        text = ""
        metadata: dict[str, Any] = {}

        if message_type == "text":
            text = message.get("text", {}).get("body", "")
        elif message_type == "interactive":
            # Button reply
            interactive = message.get("interactive", {})
            button_reply = interactive.get("button_reply", {})
            text = button_reply.get("title", "")
            metadata["callback_data"] = button_reply.get("id", "")
        else:
            # Unknown type, try to extract text
            text = message.get("text", {}).get("body", "")

        # Build InternalMessage
        internal_message = {
            "direction": "inbound",
            "channel": "whatsapp",
            "external_user_id": from_number,
            "external_chat_id": from_number,  # DM-only, same as user
            "text": text,
            "is_group": False,
            "metadata": metadata,
        }

        # Forward to backend
        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    f"{BACKEND_URL}/api/channels/incoming",
                    json=internal_message,
                    timeout=10.0,
                )
                logger.info(
                    "message_forwarded",
                    from_number=from_number,
                    message_type=message_type,
                )
            except httpx.RequestError as exc:
                logger.error(
                    "backend_forward_error",
                    error=str(exc),
                    from_number=from_number,
                )

    except Exception as exc:
        logger.error("webhook_parse_error", error=str(exc))

    return {"status": "ok"}


@app.post("/send")
async def send_message(msg: SendRequest) -> dict:
    """Send an outbound message to a WhatsApp user.

    Receives InternalMessage format. If actions are present, sends
    interactive message with buttons (max 3). Otherwise sends plain text.

    Applies markdown stripping and message truncation (4096 chars).
    """
    wa_api = get_wa_api()

    text = msg.text or ""

    # Apply markdown stripping
    text = WhatsAppAPI.strip_markdown(text)

    # Truncate at 4096 chars
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[: MAX_MESSAGE_LENGTH - len(TRUNCATION_SUFFIX)] + TRUNCATION_SUFFIX

    to = msg.external_user_id

    try:
        if msg.actions and len(msg.actions) > 0:
            # Build WhatsApp button format (cap at 3 — WhatsApp platform limit)
            buttons = [
                {
                    "type": "reply",
                    "reply": {
                        "id": action.action_id,
                        "title": action.label[:20],
                    },
                }
                for action in msg.actions[:3]
            ]
            result = await wa_api.send_interactive(to, text, buttons)
        else:
            result = await wa_api.send_text(to, text)

        logger.info("message_sent", to=to, has_actions=bool(msg.actions))
        return {"status": "sent", "result": result}

    except Exception as exc:
        logger.error("send_error", error=str(exc), to=to)
        return {"status": "error", "detail": str(exc)}


@app.get("/health")
async def health() -> dict:
    """Service health check."""
    return {"status": "ok", "service": "whatsapp-gateway"}
