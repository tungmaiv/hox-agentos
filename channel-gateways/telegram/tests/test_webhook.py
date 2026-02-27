"""
Tests for the Telegram sidecar /webhook endpoint.

Verifies:
  - Text messages are translated to InternalMessage and forwarded to backend
  - Callback queries are forwarded with callback_data in metadata
  - Group messages with @mention are forwarded
  - Group messages without @mention are ignored
  - Media-only messages are rejected with a text reply
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import main
from telegram_api import TelegramAPI


@pytest.fixture(autouse=True)
def _setup_bot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure bot for all tests."""
    monkeypatch.setattr(main, "BOT_USERNAME", "blitz_bot")
    monkeypatch.setattr(main, "BACKEND_URL", "http://backend:8000")
    # Create a real TelegramAPI instance (methods will be mocked per-test)
    monkeypatch.setattr(main, "telegram_api", TelegramAPI("fake-token"))


@pytest.fixture()
def client() -> TestClient:
    return TestClient(main.app)


def _make_text_message(
    text: str = "Hello bot",
    chat_id: int = 12345,
    user_id: int = 67890,
    chat_type: str = "private",
    entities: list | None = None,
) -> dict:
    """Build a minimal Telegram Update with a text message."""
    msg: dict = {
        "update_id": 1,
        "message": {
            "message_id": 100,
            "from": {
                "id": user_id,
                "first_name": "John",
                "last_name": "Doe",
            },
            "chat": {
                "id": chat_id,
                "type": chat_type,
            },
            "text": text,
        },
    }
    if entities:
        msg["message"]["entities"] = entities
    return msg


def _make_callback_query(
    callback_data: str = "approve_123",
    chat_id: int = 12345,
    user_id: int = 67890,
) -> dict:
    """Build a Telegram Update with a callback_query."""
    return {
        "update_id": 2,
        "callback_query": {
            "id": "cb_1",
            "from": {
                "id": user_id,
                "first_name": "Jane",
                "last_name": "Smith",
            },
            "message": {
                "message_id": 101,
                "chat": {
                    "id": chat_id,
                    "type": "private",
                },
            },
            "data": callback_data,
        },
    }


class TestWebhookTextMessage:
    """Test /webhook with standard text messages."""

    def test_text_message_forwarded(self, client: TestClient) -> None:
        """Private text message is translated to InternalMessage and POSTed to backend."""
        update = _make_text_message(text="Hello agent")

        with (
            patch("main.telegram_api.send_chat_action", new_callable=AsyncMock) as mock_typing,
            patch("main._forward_to_backend", new_callable=AsyncMock) as mock_fwd,
        ):
            resp = client.post("/webhook", json=update)

        assert resp.status_code == 200
        mock_typing.assert_called_once_with(chat_id=12345, action="typing")
        mock_fwd.assert_called_once()

        msg = mock_fwd.call_args[0][0]
        assert msg.direction == "inbound"
        assert msg.channel == "telegram"
        assert msg.external_user_id == "67890"
        assert msg.external_chat_id == "12345"
        assert msg.text == "Hello agent"
        assert msg.is_group is False
        assert msg.metadata["display_name"] == "John Doe"

    def test_empty_update_returns_200(self, client: TestClient) -> None:
        """An update with no message or callback_query returns 200 (ignored)."""
        resp = client.post("/webhook", json={"update_id": 99})
        assert resp.status_code == 200


class TestWebhookCallbackQuery:
    """Test /webhook with callback queries from inline buttons."""

    def test_callback_query_forwarded(self, client: TestClient) -> None:
        """Callback query is translated to InternalMessage with callback_data in metadata."""
        update = _make_callback_query(callback_data="approve_task_42")

        with patch("main._forward_to_backend", new_callable=AsyncMock) as mock_fwd:
            resp = client.post("/webhook", json=update)

        assert resp.status_code == 200
        mock_fwd.assert_called_once()

        msg = mock_fwd.call_args[0][0]
        assert msg.direction == "inbound"
        assert msg.channel == "telegram"
        assert msg.external_user_id == "67890"
        assert msg.text == "approve_task_42"
        assert msg.metadata["callback_data"] == "approve_task_42"
        assert msg.metadata["callback_query_id"] == "cb_1"
        assert msg.metadata["display_name"] == "Jane Smith"


class TestWebhookGroupMessages:
    """Test group message @mention filtering."""

    def test_group_mention_forwarded(self, client: TestClient) -> None:
        """Group message with @blitz_bot mention is forwarded."""
        update = _make_text_message(
            text="@blitz_bot what is the status?",
            chat_type="supergroup",
            entities=[{"type": "mention", "offset": 0, "length": 10}],
        )

        with (
            patch("main.telegram_api.send_chat_action", new_callable=AsyncMock),
            patch("main._forward_to_backend", new_callable=AsyncMock) as mock_fwd,
        ):
            resp = client.post("/webhook", json=update)

        assert resp.status_code == 200
        mock_fwd.assert_called_once()
        msg = mock_fwd.call_args[0][0]
        assert msg.is_group is True

    def test_group_non_mention_ignored(self, client: TestClient) -> None:
        """Group message without bot mention is silently ignored."""
        update = _make_text_message(
            text="Hey team, meeting at 3pm",
            chat_type="group",
        )

        with patch("main._forward_to_backend", new_callable=AsyncMock) as mock_fwd:
            resp = client.post("/webhook", json=update)

        assert resp.status_code == 200
        mock_fwd.assert_not_called()


class TestWebhookAttachments:
    """Test media-only message rejection."""

    def test_attachment_rejected(self, client: TestClient) -> None:
        """Photo-only message gets a text response explaining text-only support."""
        update = {
            "update_id": 3,
            "message": {
                "message_id": 102,
                "from": {"id": 67890, "first_name": "John"},
                "chat": {"id": 12345, "type": "private"},
                "photo": [{"file_id": "abc", "width": 100, "height": 100}],
            },
        }

        with (
            patch("main.telegram_api.send_message", new_callable=AsyncMock) as mock_send,
            patch("main._forward_to_backend", new_callable=AsyncMock) as mock_fwd,
        ):
            resp = client.post("/webhook", json=update)

        assert resp.status_code == 200
        mock_fwd.assert_not_called()
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        assert "text" in call_kwargs.kwargs or len(call_kwargs.args) > 1
