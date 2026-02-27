"""
Telegram Bot API wrapper for Blitz AgentOS Telegram sidecar.

Handles:
  - sendMessage with MarkdownV2 formatting and InlineKeyboard
  - sendChatAction (typing indicator)
  - setWebhook registration on startup

Security: NEVER logs the bot token.
"""
import re

import httpx
import structlog

logger = structlog.get_logger(__name__)

# Characters that must be escaped in Telegram MarkdownV2
_MARKDOWN_V2_SPECIAL = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")


class TelegramAPI:
    """Async wrapper around the Telegram Bot API."""

    def __init__(self, bot_token: str) -> None:
        self._bot_token = bot_token
        self._base_url = f"https://api.telegram.org/bot{bot_token}"

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: str = "MarkdownV2",
        reply_to_message_id: int | None = None,
        reply_markup: dict | None = None,
    ) -> dict:
        """Send a text message via Telegram Bot API."""
        payload: dict = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/sendMessage",
                json=payload,
                timeout=10.0,
            )
            if resp.status_code != 200:
                logger.error(
                    "telegram_send_message_failed",
                    status=resp.status_code,
                    body=resp.text,
                    chat_id=chat_id,
                )
            return resp.json()

    async def send_chat_action(
        self,
        chat_id: int | str,
        action: str = "typing",
    ) -> dict:
        """Send a chat action (e.g., typing indicator)."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/sendChatAction",
                json={"chat_id": chat_id, "action": action},
                timeout=10.0,
            )
            return resp.json()

    async def set_webhook(
        self,
        url: str,
        allowed_updates: list[str] | None = None,
    ) -> dict:
        """Register a webhook URL with Telegram."""
        payload: dict = {"url": url}
        if allowed_updates is not None:
            payload["allowed_updates"] = allowed_updates

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/setWebhook",
                json=payload,
                timeout=10.0,
            )
            if resp.status_code == 200:
                logger.info("telegram_webhook_set", url=url)
            else:
                logger.error(
                    "telegram_set_webhook_failed",
                    status=resp.status_code,
                    body=resp.text,
                )
            return resp.json()

    @staticmethod
    def escape_markdown_v2(text: str) -> str:
        """Escape special characters for Telegram MarkdownV2 format."""
        return _MARKDOWN_V2_SPECIAL.sub(r"\\\1", text)

    @staticmethod
    def build_inline_keyboard(actions: list[dict]) -> dict:
        """
        Build an InlineKeyboardMarkup from MessageAction-like dicts.

        Each action dict should have:
          - label: str (button text)
          - action_id: str (callback_data)

        Returns Telegram InlineKeyboardMarkup JSON structure.
        Telegram limit: up to ~100 buttons. Excess silently dropped.
        """
        buttons = []
        for action in actions[:100]:  # Telegram button limit
            buttons.append({
                "text": action.get("label", ""),
                "callback_data": action.get("action_id", ""),
            })

        # Arrange buttons in rows of up to 3
        rows = []
        for i in range(0, len(buttons), 3):
            rows.append(buttons[i : i + 3])

        return {"inline_keyboard": rows}
