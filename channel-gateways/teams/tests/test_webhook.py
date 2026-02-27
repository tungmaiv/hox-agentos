"""
Tests for the Teams sidecar /webhook endpoint.

Covers:
  - Message activity forwarded to backend
  - Invoke activity (Adaptive Card Action.Submit) forwarded
  - Channel @mention message forwarded
  - Channel non-mention message ignored
  - Attachment-only message rejected with text-only notice
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _mock_token_validation():
    """Always validate tokens in tests."""
    with patch("main.teams_api.validate_token", new_callable=AsyncMock, return_value=True):
        yield


@pytest.fixture()
def client():
    from main import app
    return TestClient(app)


def _make_message_activity(
    text: str = "Hello bot",
    from_id: str = "user123",
    from_name: str = "Test User",
    conversation_id: str = "conv456",
    activity_id: str = "act789",
    service_url: str = "https://smba.trafficmanager.net/teams/",
    channel_data: dict | None = None,
    entities: list | None = None,
    attachments: list | None = None,
) -> dict:
    """Build a minimal Bot Framework message Activity."""
    activity = {
        "type": "message",
        "id": activity_id,
        "text": text,
        "from": {"id": from_id, "name": from_name},
        "conversation": {"id": conversation_id},
        "serviceUrl": service_url,
        "channelData": channel_data or {},
        "entities": entities or [],
    }
    if attachments is not None:
        activity["attachments"] = attachments
    return activity


def _make_invoke_activity(
    value: dict | None = None,
    from_id: str = "user123",
    from_name: str = "Test User",
    conversation_id: str = "conv456",
    activity_id: str = "act789",
    service_url: str = "https://smba.trafficmanager.net/teams/",
) -> dict:
    """Build a minimal Bot Framework invoke Activity."""
    return {
        "type": "invoke",
        "id": activity_id,
        "value": value or {"action_id": "approve"},
        "from": {"id": from_id, "name": from_name},
        "conversation": {"id": conversation_id},
        "serviceUrl": service_url,
        "channelData": {},
        "entities": [],
    }


class TestMessageActivityForwarded:
    """POST /webhook with a message activity forwards InternalMessage to backend."""

    def test_message_activity_forwarded(self, client):
        activity = _make_message_activity(text="Hello Blitz")

        with (
            patch("main._forward_to_backend", new_callable=AsyncMock) as mock_forward,
            patch("main.teams_api.send_typing", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/webhook",
                json=activity,
                headers={"Authorization": "Bearer fake-token"},
            )

        assert resp.status_code == 200
        mock_forward.assert_called_once()
        msg = mock_forward.call_args[0][0]
        assert msg["direction"] == "inbound"
        assert msg["channel"] == "ms_teams"
        assert msg["text"] == "Hello Blitz"
        assert msg["external_user_id"] == "user123"
        assert msg["external_chat_id"] == "conv456"
        assert msg["metadata"]["display_name"] == "Test User"
        assert msg["metadata"]["service_url"] == "https://smba.trafficmanager.net/teams/"
        assert msg["metadata"]["reply_to_activity_id"] == "act789"


class TestInvokeActivityForwarded:
    """POST /webhook with an invoke activity (Adaptive Card Action.Submit)."""

    def test_invoke_activity_forwarded(self, client):
        activity = _make_invoke_activity(value={"action_id": "approve_task"})

        with patch("main._forward_to_backend", new_callable=AsyncMock) as mock_forward:
            resp = client.post(
                "/webhook",
                json=activity,
                headers={"Authorization": "Bearer fake-token"},
            )

        assert resp.status_code == 200
        mock_forward.assert_called_once()
        msg = mock_forward.call_args[0][0]
        assert msg["channel"] == "ms_teams"
        assert msg["text"] == "[Action: approve_task]"
        assert msg["metadata"]["callback_data"] == {"action_id": "approve_task"}


class TestChannelMentionForwarded:
    """POST /webhook with a team channel message mentioning the bot."""

    def test_channel_mention_forwarded(self, client):
        # Simulate a channel message with @mention of the bot
        bot_id = ""  # TEAMS_APP_ID defaults to ""
        activity = _make_message_activity(
            text="<at>BlitzBot</at> What is the status?",
            channel_data={"team": {"id": "team123"}},
            entities=[
                {
                    "type": "mention",
                    "mentioned": {"id": bot_id, "name": "BlitzBot"},
                    "text": "<at>BlitzBot</at>",
                }
            ],
        )

        with (
            patch("main._forward_to_backend", new_callable=AsyncMock) as mock_forward,
            patch("main.teams_api.send_typing", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/webhook",
                json=activity,
                headers={"Authorization": "Bearer fake-token"},
            )

        assert resp.status_code == 200
        mock_forward.assert_called_once()
        msg = mock_forward.call_args[0][0]
        assert msg["text"] == "What is the status?"
        assert msg["is_group"] is True


class TestChannelNonMentionIgnored:
    """POST /webhook with a team channel message NOT mentioning the bot."""

    def test_channel_non_mention_ignored(self, client):
        activity = _make_message_activity(
            text="Hey everyone, meeting at 3pm",
            channel_data={"team": {"id": "team123"}},
            entities=[],  # No @mention of bot
        )

        with (
            patch("main._forward_to_backend", new_callable=AsyncMock) as mock_forward,
            patch("main.teams_api.send_typing", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/webhook",
                json=activity,
                headers={"Authorization": "Bearer fake-token"},
            )

        assert resp.status_code == 200
        mock_forward.assert_not_called()


class TestAttachmentRejected:
    """POST /webhook with attachment-only message returns text-only notice."""

    def test_attachment_rejected(self, client):
        activity = _make_message_activity(
            text="",
            attachments=[{"contentType": "image/png", "contentUrl": "https://example.com/img.png"}],
        )

        with (
            patch("main.teams_api.send_typing", new_callable=AsyncMock),
            patch("main.teams_api.send_activity", new_callable=AsyncMock) as mock_send,
            patch("main._forward_to_backend", new_callable=AsyncMock) as mock_forward,
        ):
            resp = client.post(
                "/webhook",
                json=activity,
                headers={"Authorization": "Bearer fake-token"},
            )

        assert resp.status_code == 200
        # Should NOT forward to backend
        mock_forward.assert_not_called()
        # Should send a rejection message to the user
        mock_send.assert_called_once()
        sent_activity = mock_send.call_args[0][2]
        assert "text messages" in sent_activity["text"].lower()
