"""Tests for WhatsApp outbound send endpoint."""

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
from whatsapp_api import WhatsAppAPI  # noqa: E402


@pytest.fixture
def transport() -> ASGITransport:
    return ASGITransport(app=app)


@pytest.fixture
async def client(transport: ASGITransport) -> AsyncClient:
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_send_text_message(client: AsyncClient) -> None:
    """POST /send with no actions calls send_text on WhatsApp API."""
    mock_wa_api = AsyncMock()
    mock_wa_api.send_text = AsyncMock(return_value={"messages": [{"id": "wamid.123"}]})

    with patch("main.get_wa_api", return_value=mock_wa_api):
        response = await client.post(
            "/send",
            json={
                "external_user_id": "84901234567",
                "text": "Hello from Blitz!",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "sent"
    mock_wa_api.send_text.assert_called_once_with("84901234567", "Hello from Blitz!")


@pytest.mark.asyncio
async def test_send_interactive_buttons(client: AsyncClient) -> None:
    """POST /send with actions sends interactive message with buttons."""
    mock_wa_api = AsyncMock()
    mock_wa_api.send_interactive = AsyncMock(
        return_value={"messages": [{"id": "wamid.456"}]}
    )

    with patch("main.get_wa_api", return_value=mock_wa_api):
        response = await client.post(
            "/send",
            json={
                "external_user_id": "84901234567",
                "text": "Choose an option:",
                "actions": [
                    {"label": "Approve", "action_id": "approve_123"},
                    {"label": "Reject", "action_id": "reject_123"},
                ],
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "sent"
    mock_wa_api.send_interactive.assert_called_once()

    # Verify button format
    call_args = mock_wa_api.send_interactive.call_args
    assert call_args[0][0] == "84901234567"
    assert call_args[0][1] == "Choose an option:"
    buttons = call_args[0][2]
    assert len(buttons) == 2
    assert buttons[0]["reply"]["id"] == "approve_123"
    assert buttons[0]["reply"]["title"] == "Approve"


@pytest.mark.asyncio
async def test_buttons_capped_at_3(client: AsyncClient) -> None:
    """POST /send with 5 actions sends only 3 buttons (WhatsApp limit)."""
    mock_wa_api = AsyncMock()
    mock_wa_api.send_interactive = AsyncMock(
        return_value={"messages": [{"id": "wamid.789"}]}
    )

    with patch("main.get_wa_api", return_value=mock_wa_api):
        response = await client.post(
            "/send",
            json={
                "external_user_id": "84901234567",
                "text": "Pick one:",
                "actions": [
                    {"label": f"Option {i}", "action_id": f"opt_{i}"}
                    for i in range(5)
                ],
            },
        )

    assert response.status_code == 200
    # send_interactive receives only 3 buttons
    call_args = mock_wa_api.send_interactive.call_args
    buttons = call_args[0][2]
    assert len(buttons) == 3
    assert buttons[0]["reply"]["title"] == "Option 0"
    assert buttons[2]["reply"]["title"] == "Option 2"


def test_markdown_stripped() -> None:
    """WhatsAppAPI.strip_markdown converts markdown to WhatsApp-compatible format."""
    # **bold** -> *bold*
    assert WhatsAppAPI.strip_markdown("**hello**") == "*hello*"

    # __italic__ -> _italic_
    assert WhatsAppAPI.strip_markdown("__world__") == "_world_"

    # [link](url) -> "link (url)"
    assert WhatsAppAPI.strip_markdown("[Click here](https://example.com)") == (
        "Click here (https://example.com)"
    )

    # Code blocks stripped
    result = WhatsAppAPI.strip_markdown("Before\n```python\nprint('hi')\n```\nAfter")
    assert "```" not in result
    assert "print('hi')" in result

    # Inline code backticks removed
    assert WhatsAppAPI.strip_markdown("Use `npm install`") == "Use npm install"

    # Already-WhatsApp-compatible bold/italic preserved
    assert WhatsAppAPI.strip_markdown("*bold* and _italic_") == "*bold* and _italic_"
