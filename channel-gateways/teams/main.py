"""
MS Teams channel sidecar for Blitz AgentOS.

Translates between Bot Framework Activity protocol and InternalMessage format.
Runs as a standalone Docker service on port 9003.

Endpoints:
  POST /webhook  - receives Bot Framework Activity JSON from Teams
  POST /send     - receives InternalMessage from backend, sends to Teams
  GET  /health   - health check
"""
import os
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, Header, Request, Response
from pydantic import BaseModel

from teams_api import TeamsAPI

logger = structlog.get_logger(__name__)

# -- Configuration ----------------------------------------------------------

TEAMS_APP_ID = os.environ.get("TEAMS_APP_ID", "")
TEAMS_APP_PASSWORD = os.environ.get("TEAMS_APP_PASSWORD", "")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")

teams_api = TeamsAPI(app_id=TEAMS_APP_ID, app_password=TEAMS_APP_PASSWORD)

app = FastAPI(title="Blitz Teams Gateway", version="0.1.0")

# -- Message truncation limit -----------------------------------------------

_MAX_MESSAGE_LENGTH = 4096
_TRUNCATION_SUFFIX = "... (response truncated)"


# -- Pydantic models for /send endpoint ------------------------------------

class SendMessage(BaseModel):
    """InternalMessage subset needed for outbound delivery."""

    direction: str
    channel: str
    external_user_id: str
    external_chat_id: str | None = None
    user_id: str | None = None
    conversation_id: str | None = None
    text: str | None = None
    attachments: list[dict[str, Any]] = []
    actions: list[dict[str, str]] = []
    is_group: bool = False
    metadata: dict[str, Any] = {}


# -- Helpers ----------------------------------------------------------------

def _strip_mention(text: str, bot_name: str) -> str:
    """Remove @mention of the bot from message text."""
    # Teams prepends "<at>BotName</at> " to messages
    at_tag = f"<at>{bot_name}</at>"
    stripped = text.replace(at_tag, "").strip()
    return stripped


def _is_bot_mentioned(entities: list[dict[str, Any]], bot_id: str) -> bool:
    """Check if the bot is @mentioned in the activity entities."""
    for entity in entities:
        if entity.get("type") != "mention":
            continue
        mentioned = entity.get("mentioned", {})
        if mentioned.get("id") == bot_id:
            return True
    return False


def _truncate(text: str, max_length: int = _MAX_MESSAGE_LENGTH) -> str:
    """Truncate text to max_length with a suffix indicator."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(_TRUNCATION_SUFFIX)] + _TRUNCATION_SUFFIX


async def _forward_to_backend(internal_message: dict[str, Any]) -> None:
    """POST an InternalMessage to the backend channel incoming endpoint."""
    url = f"{BACKEND_URL}/api/channels/incoming"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=internal_message)
            resp.raise_for_status()
        logger.info(
            "forwarded_to_backend",
            channel="ms_teams",
            external_user_id=internal_message.get("external_user_id"),
        )
    except httpx.HTTPError as exc:
        logger.error(
            "forward_to_backend_failed",
            error=str(exc),
            channel="ms_teams",
        )


# -- Endpoints --------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "teams-gateway"}


@app.post("/webhook")
async def webhook(
    request: Request,
    authorization: str = Header(default=""),
) -> Response:
    """
    Receive Bot Framework Activity JSON from Teams.

    Processes:
      - "message" activities: text messages and attachment-only messages
      - "invoke" activities: Adaptive Card Action.Submit callbacks
    Ignores other activity types (typing, conversationUpdate, etc.).
    """
    # Validate Bot Framework token
    is_valid = await teams_api.validate_token(authorization)
    if not is_valid:
        logger.warning("webhook_unauthorized")
        return Response(status_code=401, content="Unauthorized")

    body: dict[str, Any] = await request.json()
    activity_type = body.get("type", "")

    if activity_type == "message":
        await _handle_message_activity(body)
    elif activity_type == "invoke":
        await _handle_invoke_activity(body)
        # Return invoke response to Bot Framework
        return Response(
            status_code=200,
            content='{"status": 200}',
            media_type="application/json",
        )
    else:
        logger.debug("webhook_ignored_activity", activity_type=activity_type)

    return Response(status_code=200)


async def _handle_message_activity(activity: dict[str, Any]) -> None:
    """Process an inbound message Activity from Teams."""
    from_user = activity.get("from", {})
    conversation = activity.get("conversation", {})
    text = activity.get("text", "") or ""
    service_url = activity.get("serviceUrl", "")
    activity_id = activity.get("id", "")
    channel_data = activity.get("channelData", {})
    entities = activity.get("entities", [])
    attachments = activity.get("attachments", [])

    external_user_id = from_user.get("id", "")
    external_chat_id = conversation.get("id", "")
    display_name = from_user.get("name", "")

    # Channel vs DM detection
    is_group = "team" in channel_data

    # @mention filter for team channels
    if is_group:
        if not _is_bot_mentioned(entities, TEAMS_APP_ID):
            logger.debug(
                "webhook_channel_no_mention",
                conversation_id=external_chat_id,
            )
            return

    # Strip @mention text from message body
    bot_name = ""
    for entity in entities:
        if entity.get("type") == "mention":
            mentioned = entity.get("mentioned", {})
            if mentioned.get("id") == TEAMS_APP_ID:
                bot_name = mentioned.get("name", "")
                break
    if bot_name:
        text = _strip_mention(text, bot_name)

    # Attachment-only messages
    if attachments and not text.strip():
        # Send typing then respond with text-only notice
        await teams_api.send_typing(service_url, external_chat_id)
        reply_activity = {
            "type": "message",
            "text": "I can only process text messages for now.",
            "textFormat": "markdown",
        }
        if is_group and activity_id:
            await teams_api.reply_to_activity(
                service_url, external_chat_id, activity_id, reply_activity
            )
        else:
            await teams_api.send_activity(
                service_url, external_chat_id, reply_activity
            )
        return

    # Send typing indicator
    await teams_api.send_typing(service_url, external_chat_id)

    # Build InternalMessage
    internal_message = {
        "direction": "inbound",
        "channel": "ms_teams",
        "external_user_id": external_user_id,
        "external_chat_id": external_chat_id,
        "text": text,
        "is_group": is_group,
        "metadata": {
            "display_name": display_name,
            "service_url": service_url,
            "reply_to_activity_id": activity_id,
        },
    }

    await _forward_to_backend(internal_message)


async def _handle_invoke_activity(activity: dict[str, Any]) -> None:
    """Process an Adaptive Card Action.Submit invoke Activity."""
    from_user = activity.get("from", {})
    conversation = activity.get("conversation", {})
    value = activity.get("value", {})
    service_url = activity.get("serviceUrl", "")
    activity_id = activity.get("id", "")

    external_user_id = from_user.get("id", "")
    external_chat_id = conversation.get("id", "")
    display_name = from_user.get("name", "")

    # Extract action_id from the submitted value
    action_id = value.get("action_id", "") if isinstance(value, dict) else ""

    internal_message = {
        "direction": "inbound",
        "channel": "ms_teams",
        "external_user_id": external_user_id,
        "external_chat_id": external_chat_id,
        "text": f"[Action: {action_id}]" if action_id else "",
        "is_group": False,
        "metadata": {
            "display_name": display_name,
            "service_url": service_url,
            "reply_to_activity_id": activity_id,
            "callback_data": value,
        },
    }

    await _forward_to_backend(internal_message)


@app.post("/send")
async def send(message: SendMessage) -> dict[str, str]:
    """
    Receive an InternalMessage from the backend and send it to Teams.

    If actions are present, builds an Adaptive Card with Action.Submit buttons.
    Otherwise sends a plain text Activity with markdown formatting.
    Truncates at 4096 chars.
    """
    service_url = message.metadata.get("service_url", "")
    if not service_url:
        logger.warning("send_missing_service_url", external_chat_id=message.external_chat_id)
        return {"status": "error", "reason": "missing_service_url"}

    conversation_id = message.external_chat_id or ""
    reply_to_activity_id = message.metadata.get("reply_to_activity_id")
    text = _truncate(message.text or "")

    if message.actions:
        # Build Adaptive Card with Action.Submit buttons
        activity = TeamsAPI.build_adaptive_card(
            text=text,
            actions=[
                {"label": a.get("label", ""), "action_id": a.get("action_id", "")}
                for a in message.actions
            ],
        )
    else:
        # Plain text Activity with markdown
        activity: dict[str, Any] = {
            "type": "message",
            "text": text,
            "textFormat": "markdown",
        }

    try:
        if reply_to_activity_id:
            await teams_api.reply_to_activity(
                service_url, conversation_id, reply_to_activity_id, activity
            )
        else:
            await teams_api.send_activity(service_url, conversation_id, activity)

        logger.info(
            "send_success",
            channel="ms_teams",
            external_chat_id=conversation_id,
            has_actions=bool(message.actions),
        )
        return {"status": "ok"}

    except httpx.HTTPError as exc:
        logger.error(
            "send_failed",
            error=str(exc),
            channel="ms_teams",
            external_chat_id=conversation_id,
        )
        return {"status": "error", "reason": str(exc)}
