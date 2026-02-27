"""
Tests for the Teams sidecar /send endpoint.

Covers:
  - Plain text Activity sent to Teams
  - Adaptive Card with Action.Submit buttons sent
  - Threaded reply using reply_to_activity_id metadata
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from main import app
    return TestClient(app)


def _make_send_payload(
    text: str = "Hello from Blitz",
    actions: list | None = None,
    service_url: str = "https://smba.trafficmanager.net/teams/",
    external_chat_id: str = "conv456",
    reply_to_activity_id: str | None = None,
) -> dict:
    """Build an InternalMessage payload for the /send endpoint."""
    metadata: dict = {"service_url": service_url}
    if reply_to_activity_id:
        metadata["reply_to_activity_id"] = reply_to_activity_id

    return {
        "direction": "outbound",
        "channel": "ms_teams",
        "external_user_id": "user123",
        "external_chat_id": external_chat_id,
        "text": text,
        "actions": actions or [],
        "metadata": metadata,
    }


class TestSendTextActivity:
    """POST /send with plain text sends a markdown Activity."""

    def test_send_text_activity(self, client):
        payload = _make_send_payload(text="Here is your summary.")

        with patch(
            "main.teams_api.send_activity",
            new_callable=AsyncMock,
            return_value={"id": "resp123"},
        ) as mock_send:
            resp = client.post("/send", json=payload)

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        mock_send.assert_called_once()
        service_url, conv_id, activity = mock_send.call_args[0]
        assert service_url == "https://smba.trafficmanager.net/teams/"
        assert conv_id == "conv456"
        assert activity["type"] == "message"
        assert activity["text"] == "Here is your summary."
        assert activity["textFormat"] == "markdown"


class TestSendAdaptiveCard:
    """POST /send with actions builds and sends an Adaptive Card."""

    def test_send_adaptive_card(self, client):
        payload = _make_send_payload(
            text="Choose an option:",
            actions=[
                {"label": "Approve", "action_id": "approve"},
                {"label": "Reject", "action_id": "reject"},
            ],
        )

        with patch(
            "main.teams_api.send_activity",
            new_callable=AsyncMock,
            return_value={"id": "resp123"},
        ) as mock_send:
            resp = client.post("/send", json=payload)

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        mock_send.assert_called_once()
        _, _, activity = mock_send.call_args[0]
        # Should be an Adaptive Card activity
        assert "attachments" in activity
        card_attachment = activity["attachments"][0]
        assert card_attachment["contentType"] == "application/vnd.microsoft.card.adaptive"
        card = card_attachment["content"]
        assert card["type"] == "AdaptiveCard"
        assert len(card["body"]) == 1
        assert card["body"][0]["text"] == "Choose an option:"
        assert len(card["actions"]) == 2
        assert card["actions"][0]["title"] == "Approve"
        assert card["actions"][0]["data"]["action_id"] == "approve"
        assert card["actions"][1]["title"] == "Reject"


class TestThreadedReply:
    """POST /send with reply_to_activity_id uses reply_to_activity."""

    def test_threaded_reply(self, client):
        payload = _make_send_payload(
            text="Threaded response.",
            reply_to_activity_id="original-activity-123",
        )

        with patch(
            "main.teams_api.reply_to_activity",
            new_callable=AsyncMock,
            return_value={"id": "resp123"},
        ) as mock_reply:
            resp = client.post("/send", json=payload)

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        mock_reply.assert_called_once()
        service_url, conv_id, act_id, activity = mock_reply.call_args[0]
        assert service_url == "https://smba.trafficmanager.net/teams/"
        assert conv_id == "conv456"
        assert act_id == "original-activity-123"
        assert activity["text"] == "Threaded response."
