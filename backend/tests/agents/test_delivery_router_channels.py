"""
Tests for delivery_router.py channel integration (05-05).

Verifies:
- TELEGRAM deliver() sends outbound via ChannelGateway
- TEAMS deliver() sends outbound via ChannelGateway
- WHATSAPP deliver() sends outbound via ChannelGateway (new enum)
"""
import pytest
from langchain_core.messages import AIMessage
from unittest.mock import AsyncMock, patch

from agents.delivery_router import DeliveryTarget, deliver


@pytest.mark.asyncio
async def test_deliver_telegram_sends_outbound() -> None:
    """deliver(TELEGRAM) creates InternalMessage and sends via gateway."""
    mock_gateway = AsyncMock()
    mock_gateway.send_outbound = AsyncMock()

    with patch("agents.delivery_router._get_gateway", return_value=mock_gateway):
        payload = AIMessage(content="Daily digest report")
        await deliver(DeliveryTarget.TELEGRAM, payload)

    mock_gateway.send_outbound.assert_called_once()
    sent_msg = mock_gateway.send_outbound.call_args[0][0]
    assert sent_msg.channel == "telegram"
    assert sent_msg.direction == "outbound"
    assert "Daily digest report" in sent_msg.text


@pytest.mark.asyncio
async def test_deliver_teams_sends_outbound() -> None:
    """deliver(TEAMS) creates InternalMessage and sends via gateway."""
    mock_gateway = AsyncMock()
    mock_gateway.send_outbound = AsyncMock()

    with patch("agents.delivery_router._get_gateway", return_value=mock_gateway):
        payload = AIMessage(content="Meeting reminder")
        await deliver(DeliveryTarget.TEAMS, payload)

    mock_gateway.send_outbound.assert_called_once()
    sent_msg = mock_gateway.send_outbound.call_args[0][0]
    assert sent_msg.channel == "ms_teams"
    assert sent_msg.direction == "outbound"
    assert "Meeting reminder" in sent_msg.text


@pytest.mark.asyncio
async def test_deliver_whatsapp_sends_outbound() -> None:
    """deliver(WHATSAPP) creates InternalMessage and sends via gateway."""
    mock_gateway = AsyncMock()
    mock_gateway.send_outbound = AsyncMock()

    with patch("agents.delivery_router._get_gateway", return_value=mock_gateway):
        payload = AIMessage(content="Task update")
        await deliver(DeliveryTarget.WHATSAPP, payload)

    mock_gateway.send_outbound.assert_called_once()
    sent_msg = mock_gateway.send_outbound.call_args[0][0]
    assert sent_msg.channel == "whatsapp"
    assert sent_msg.direction == "outbound"
    assert "Task update" in sent_msg.text


@pytest.mark.asyncio
async def test_whatsapp_in_delivery_target_enum() -> None:
    """WHATSAPP is a valid DeliveryTarget enum member."""
    assert DeliveryTarget.WHATSAPP.value == "WHATSAPP"
    assert DeliveryTarget("WHATSAPP") == DeliveryTarget.WHATSAPP
