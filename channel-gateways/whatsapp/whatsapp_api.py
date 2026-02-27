"""
WhatsApp Cloud API wrapper for Blitz AgentOS WhatsApp sidecar.

Handles outbound text and interactive (button) messages via the
WhatsApp Cloud API v21.0. Provides markdown stripping for
WhatsApp-compatible formatting.

NEVER logs access tokens or sensitive credentials.
"""

import re

import httpx
import structlog

logger = structlog.get_logger(__name__)


class WhatsAppAPI:
    """Wrapper around WhatsApp Cloud API for sending messages."""

    def __init__(self, access_token: str, phone_number_id: str) -> None:
        self._access_token = access_token
        self._phone_number_id = phone_number_id
        self._base_url = (
            f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
        )

    async def send_text(self, to: str, text: str) -> dict:
        """Send a plain text message to a WhatsApp user.

        Args:
            to: Recipient phone number (international format, e.g. "84901234567").
            text: Message text content.

        Returns:
            WhatsApp API response as dict.
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        return await self._send(payload)

    async def send_interactive(
        self, to: str, body_text: str, buttons: list[dict]
    ) -> dict:
        """Send an interactive message with reply buttons.

        WhatsApp allows a maximum of 3 buttons per interactive message.
        If more than 3 buttons are provided, excess buttons are silently dropped.

        Args:
            to: Recipient phone number.
            body_text: Message body text.
            buttons: List of button dicts. Each should have:
                - "type": "reply"
                - "reply": {"id": action_id, "title": label (max 20 chars)}

        Returns:
            WhatsApp API response as dict.
        """
        # Cap at 3 buttons (WhatsApp platform limit)
        capped_buttons = []
        for btn in buttons[:3]:
            # Ensure button format is correct
            if "reply" in btn:
                capped_buttons.append({
                    "type": "reply",
                    "reply": {
                        "id": btn["reply"]["id"],
                        "title": btn["reply"]["title"][:20],
                    },
                })
            else:
                capped_buttons.append({
                    "type": "reply",
                    "reply": {
                        "id": btn.get("id", "unknown"),
                        "title": btn.get("title", "Button")[:20],
                    },
                })

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {"buttons": capped_buttons},
            },
        }
        return await self._send(payload)

    @staticmethod
    def strip_markdown(text: str) -> str:
        """Convert markdown to WhatsApp-compatible format.

        WhatsApp supports *bold* and _italic_ natively.
        This method:
        - Strips code blocks (``` ... ```)
        - Converts **bold** to *bold*
        - Converts [links](url) to plain "links (url)" text
        - Preserves *bold* and _italic_ as-is
        """
        # Strip code blocks (``` ... ```) — replace with content only
        text = re.sub(r"```[\s\S]*?```", lambda m: m.group(0)[3:-3].strip(), text)

        # Strip inline code (`code`) — remove backticks
        text = re.sub(r"`([^`]+)`", r"\1", text)

        # Convert **bold** or __bold__ to *bold* (WhatsApp format)
        text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
        text = re.sub(r"__(.+?)__", r"_\1_", text)

        # Convert [link text](url) to "link text (url)"
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)

        return text

    async def _send(self, payload: dict) -> dict:
        """Send a payload to the WhatsApp Cloud API.

        Args:
            payload: WhatsApp API message payload.

        Returns:
            Response JSON from WhatsApp API.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self._base_url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                logger.info(
                    "whatsapp_message_sent",
                    to=payload.get("to"),
                    message_type=payload.get("type"),
                )
                return result
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "whatsapp_api_error",
                    status_code=exc.response.status_code,
                    detail=exc.response.text,
                    to=payload.get("to"),
                )
                raise
            except httpx.RequestError as exc:
                logger.error(
                    "whatsapp_request_error",
                    error=str(exc),
                    to=payload.get("to"),
                )
                raise
