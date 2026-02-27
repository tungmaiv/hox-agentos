"""
Tests for the Telegram sidecar /send endpoint.

Verifies:
  - Text messages are sent via Telegram API with MarkdownV2 escaping
  - InlineKeyboard buttons are built from InternalMessage actions
  - Long messages are truncated at 4096 chars
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import main
from telegram_api import TelegramAPI


@pytest.fixture(autouse=True)
def _setup_bot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure bot for all tests."""
    monkeypatch.setattr(main, "telegram_api", TelegramAPI("fake-token"))


@pytest.fixture()
def client() -> TestClient:
    return TestClient(main.app)


def _make_internal_message(
    text: str = "Hello from agent",
    actions: list | None = None,
    metadata: dict | None = None,
) -> dict:
    """Build an InternalMessage dict for the /send endpoint."""
    msg = {
        "direction": "outbound",
        "channel": "telegram",
        "external_user_id": "67890",
        "external_chat_id": "12345",
        "text": text,
        "actions": actions or [],
        "metadata": metadata or {},
    }
    return msg


class TestSendTextMessage:
    """Test /send with plain text messages."""

    def test_send_text_message(self, client: TestClient) -> None:
        """Text message is sent via Telegram API with MarkdownV2 escaping."""
        msg = _make_internal_message(text="Task completed successfully!")

        with patch("main.telegram_api.send_message", new_callable=AsyncMock, return_value={"ok": True}) as mock_send:
            resp = client.post("/send", json=msg)

        assert resp.status_code == 200
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["chat_id"] == "12345"
        # MarkdownV2 escapes '!' character
        assert call_kwargs["text"].endswith("\\!")
        assert call_kwargs["reply_to_message_id"] is None
        assert call_kwargs["reply_markup"] is None

    def test_send_with_reply_to(self, client: TestClient) -> None:
        """Message with reply_to_message_id in metadata replies to that message."""
        msg = _make_internal_message(
            text="Reply text",
            metadata={"reply_to_message_id": 42},
        )

        with patch("main.telegram_api.send_message", new_callable=AsyncMock, return_value={"ok": True}) as mock_send:
            resp = client.post("/send", json=msg)

        assert resp.status_code == 200
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["reply_to_message_id"] == 42

    def test_missing_chat_id_returns_400(self, client: TestClient) -> None:
        """Send without external_chat_id returns 400."""
        msg = {
            "direction": "outbound",
            "channel": "telegram",
            "external_user_id": "67890",
            "text": "Hello",
        }
        resp = client.post("/send", json=msg)
        assert resp.status_code == 400


class TestSendWithInlineKeyboard:
    """Test /send with InlineKeyboard buttons from actions."""

    def test_send_with_inline_keyboard(self, client: TestClient) -> None:
        """Actions are converted to InlineKeyboardMarkup."""
        actions = [
            {"label": "Approve", "action_id": "approve_1", "style": "primary"},
            {"label": "Reject", "action_id": "reject_1", "style": "danger"},
        ]
        msg = _make_internal_message(text="Approve this?", actions=actions)

        with patch("main.telegram_api.send_message", new_callable=AsyncMock, return_value={"ok": True}) as mock_send:
            resp = client.post("/send", json=msg)

        assert resp.status_code == 200
        call_kwargs = mock_send.call_args.kwargs
        reply_markup = call_kwargs["reply_markup"]
        assert "inline_keyboard" in reply_markup
        buttons = reply_markup["inline_keyboard"][0]
        assert len(buttons) == 2
        assert buttons[0]["text"] == "Approve"
        assert buttons[0]["callback_data"] == "approve_1"
        assert buttons[1]["text"] == "Reject"
        assert buttons[1]["callback_data"] == "reject_1"


class TestSendLongMessage:
    """Test message truncation at 4096 chars."""

    def test_long_message_truncated(self, client: TestClient) -> None:
        """Messages exceeding 4096 chars are truncated with suffix."""
        # Create a message that will exceed 4096 chars after MarkdownV2 escaping
        # Use chars that won't be escaped to keep length predictable
        long_text = "a" * 5000
        msg = _make_internal_message(text=long_text)

        with patch("main.telegram_api.send_message", new_callable=AsyncMock, return_value={"ok": True}) as mock_send:
            resp = client.post("/send", json=msg)

        assert resp.status_code == 200
        call_kwargs = mock_send.call_args.kwargs
        sent_text = call_kwargs["text"]
        assert len(sent_text) <= 4096
        assert sent_text.endswith("... (response truncated)")
