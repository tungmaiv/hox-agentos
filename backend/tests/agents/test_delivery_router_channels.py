"""
Tests for delivery_router.py channel integration (05-05).

Verifies:
- TELEGRAM deliver() resolves channel account and sends outbound via ChannelGateway
- TEAMS deliver() resolves channel account and sends outbound via ChannelGateway
- WHATSAPP deliver() resolves channel account and sends outbound via ChannelGateway
- deliver() without user_id skips delivery (no account to resolve)
"""
import pytest
from uuid import uuid4
from langchain_core.messages import AIMessage
from unittest.mock import AsyncMock, patch

from agents.delivery_router import DeliveryTarget, deliver


@pytest.mark.asyncio
async def test_deliver_telegram_sends_outbound() -> None:
    """deliver(TELEGRAM) resolves channel account and sends via gateway."""
    user_id = uuid4()
    mock_gateway = AsyncMock()
    mock_gateway.send_outbound = AsyncMock()

    with patch("agents.delivery_router._get_gateway", return_value=mock_gateway), \
         patch("agents.delivery_router._resolve_channel_account", new_callable=AsyncMock, return_value=("ext_tg", "ext_tg")):
        payload = AIMessage(content="Daily digest report")
        await deliver(DeliveryTarget.TELEGRAM, payload, user_id=user_id)

    mock_gateway.send_outbound.assert_called_once()
    sent_msg = mock_gateway.send_outbound.call_args[0][0]
    assert sent_msg.channel == "telegram"
    assert sent_msg.direction == "outbound"
    assert sent_msg.external_chat_id == "ext_tg"
    assert "Daily digest report" in sent_msg.text


@pytest.mark.asyncio
async def test_deliver_teams_sends_outbound() -> None:
    """deliver(TEAMS) resolves channel account and sends via gateway."""
    user_id = uuid4()
    mock_gateway = AsyncMock()
    mock_gateway.send_outbound = AsyncMock()

    with patch("agents.delivery_router._get_gateway", return_value=mock_gateway), \
         patch("agents.delivery_router._resolve_channel_account", new_callable=AsyncMock, return_value=("ext_teams", "ext_teams")):
        payload = AIMessage(content="Meeting reminder")
        await deliver(DeliveryTarget.TEAMS, payload, user_id=user_id)

    mock_gateway.send_outbound.assert_called_once()
    sent_msg = mock_gateway.send_outbound.call_args[0][0]
    assert sent_msg.channel == "ms_teams"
    assert sent_msg.direction == "outbound"
    assert sent_msg.external_chat_id == "ext_teams"
    assert "Meeting reminder" in sent_msg.text


@pytest.mark.asyncio
async def test_deliver_whatsapp_sends_outbound() -> None:
    """deliver(WHATSAPP) resolves channel account and sends via gateway."""
    user_id = uuid4()
    mock_gateway = AsyncMock()
    mock_gateway.send_outbound = AsyncMock()

    with patch("agents.delivery_router._get_gateway", return_value=mock_gateway), \
         patch("agents.delivery_router._resolve_channel_account", new_callable=AsyncMock, return_value=("ext_wa", "ext_wa")):
        payload = AIMessage(content="Task update")
        await deliver(DeliveryTarget.WHATSAPP, payload, user_id=user_id)

    mock_gateway.send_outbound.assert_called_once()
    sent_msg = mock_gateway.send_outbound.call_args[0][0]
    assert sent_msg.channel == "whatsapp"
    assert sent_msg.direction == "outbound"
    assert sent_msg.external_chat_id == "ext_wa"
    assert "Task update" in sent_msg.text


@pytest.mark.asyncio
async def test_deliver_channel_no_account_skips() -> None:
    """deliver() without linked channel account logs warning and skips."""
    user_id = uuid4()
    mock_gateway = AsyncMock()

    with patch("agents.delivery_router._get_gateway", return_value=mock_gateway), \
         patch("agents.delivery_router._resolve_channel_account", new_callable=AsyncMock, return_value=("", None)):
        payload = AIMessage(content="Hello")
        await deliver(DeliveryTarget.TELEGRAM, payload, user_id=user_id)

    mock_gateway.send_outbound.assert_not_called()


@pytest.mark.asyncio
async def test_whatsapp_in_delivery_target_enum() -> None:
    """WHATSAPP is a valid DeliveryTarget enum member."""
    assert DeliveryTarget.WHATSAPP.value == "WHATSAPP"
    assert DeliveryTarget("WHATSAPP") == DeliveryTarget.WHATSAPP
