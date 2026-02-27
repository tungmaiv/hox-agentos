"""Tests for WhatsApp webhook endpoints (GET verification + POST inbound)."""

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Set env vars before importing app
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test-token")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123456789")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "my-verify-token")
os.environ.setdefault("BACKEND_URL", "http://backend:8000")

from main import app  # noqa: E402


@pytest.fixture
def transport() -> ASGITransport:
    return ASGITransport(app=app)


@pytest.fixture
async def client(transport: ASGITransport) -> AsyncClient:
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_verification_challenge_success(client: AsyncClient) -> None:
    """GET /webhook with correct verify_token returns hub.challenge as plain text."""
    response = await client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "my-verify-token",
            "hub.challenge": "challenge_abc123",
        },
    )
    assert response.status_code == 200
    assert response.text == "challenge_abc123"
    assert response.headers["content-type"] == "text/plain; charset=utf-8"


@pytest.mark.asyncio
async def test_verification_challenge_wrong_token(client: AsyncClient) -> None:
    """GET /webhook with wrong verify_token returns 403."""
    response = await client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "challenge_abc123",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_text_message_forwarded(client: AsyncClient) -> None:
    """POST /webhook with text message forwards InternalMessage to backend."""
    webhook_payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "84901234567",
                                    "type": "text",
                                    "text": {"body": "Hello from WhatsApp"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    with patch("main.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        response = await client.post("/webhook", json=webhook_payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify backend was called with InternalMessage
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "http://backend:8000/api/channels/incoming"
    forwarded = call_args[1]["json"]
    assert forwarded["direction"] == "inbound"
    assert forwarded["channel"] == "whatsapp"
    assert forwarded["external_user_id"] == "84901234567"
    assert forwarded["text"] == "Hello from WhatsApp"
    assert forwarded["is_group"] is False


@pytest.mark.asyncio
async def test_interactive_reply_forwarded(client: AsyncClient) -> None:
    """POST /webhook with interactive button reply includes callback_data in metadata."""
    webhook_payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "84901234567",
                                    "type": "interactive",
                                    "interactive": {
                                        "button_reply": {
                                            "id": "approve_task_123",
                                            "title": "Approve",
                                        }
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    with patch("main.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        response = await client.post("/webhook", json=webhook_payload)

    assert response.status_code == 200
    forwarded = mock_client.post.call_args[1]["json"]
    assert forwarded["text"] == "Approve"
    assert forwarded["metadata"]["callback_data"] == "approve_task_123"


@pytest.mark.asyncio
async def test_attachment_rejected(client: AsyncClient) -> None:
    """POST /webhook with image message sends rejection and does not forward to backend."""
    webhook_payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "84901234567",
                                    "type": "image",
                                    "image": {
                                        "id": "img123",
                                        "mime_type": "image/jpeg",
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    mock_wa_api = AsyncMock()
    mock_wa_api.send_text = AsyncMock()

    with patch("main.get_wa_api", return_value=mock_wa_api):
        response = await client.post("/webhook", json=webhook_payload)

    assert response.status_code == 200
    mock_wa_api.send_text.assert_called_once()
    call_args = mock_wa_api.send_text.call_args
    assert call_args[0][0] == "84901234567"
    assert "text messages" in call_args[0][1]
