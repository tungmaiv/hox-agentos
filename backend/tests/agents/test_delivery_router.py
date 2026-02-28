"""Tests for DeliveryRouterNode."""
import pytest
from uuid import uuid4
from langchain_core.messages import AIMessage
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_delivery_router_web_chat_does_not_raise() -> None:
    """WEB_CHAT delivery completes without error."""
    from agents.delivery_router import delivery_router_node

    state = {
        "messages": [AIMessage(content='{"agent": "email"}')],
        "delivery_targets": ["WEB_CHAT"],
        "loaded_facts": [],
    }
    result = await delivery_router_node(state)
    assert result == {}  # pure side-effect, no state modification


@pytest.mark.asyncio
async def test_delivery_router_telegram_sends_outbound() -> None:
    """TELEGRAM delivery resolves channel account and sends outbound."""
    from agents.delivery_router import delivery_router_node

    user_id = uuid4()
    mock_gateway = AsyncMock()
    mock_gateway.send_outbound = AsyncMock()

    with patch("agents.delivery_router._get_gateway", return_value=mock_gateway), \
         patch("agents.delivery_router._resolve_channel_account", new_callable=AsyncMock, return_value=("ext_123", "ext_123")):
        state = {
            "messages": [AIMessage(content="Hello from agent")],
            "delivery_targets": ["TELEGRAM"],
            "loaded_facts": [],
            "user_id": user_id,
        }
        result = await delivery_router_node(state)
        assert result == {}
        mock_gateway.send_outbound.assert_called_once()
        sent_msg = mock_gateway.send_outbound.call_args[0][0]
        assert sent_msg.channel == "telegram"
        assert sent_msg.direction == "outbound"
        assert sent_msg.external_chat_id == "ext_123"
        assert sent_msg.external_user_id == "ext_123"


@pytest.mark.asyncio
async def test_delivery_router_email_notify_stub_logs_warning() -> None:
    """EMAIL_NOTIFY stub logs warning and does not raise."""
    from agents.delivery_router import delivery_router_node

    with patch("agents.delivery_router.logger") as mock_logger:
        state = {
            "messages": [AIMessage(content="Hello")],
            "delivery_targets": ["EMAIL_NOTIFY"],
            "loaded_facts": [],
        }
        result = await delivery_router_node(state)
        assert result == {}
        mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_delivery_router_teams_sends_outbound() -> None:
    """TEAMS delivery resolves channel account and sends outbound."""
    from agents.delivery_router import delivery_router_node

    user_id = uuid4()
    mock_gateway = AsyncMock()
    mock_gateway.send_outbound = AsyncMock()

    with patch("agents.delivery_router._get_gateway", return_value=mock_gateway), \
         patch("agents.delivery_router._resolve_channel_account", new_callable=AsyncMock, return_value=("ext_teams", "ext_teams")):
        state = {
            "messages": [AIMessage(content="Hello from agent")],
            "delivery_targets": ["TEAMS"],
            "loaded_facts": [],
            "user_id": user_id,
        }
        result = await delivery_router_node(state)
        assert result == {}
        mock_gateway.send_outbound.assert_called_once()
        sent_msg = mock_gateway.send_outbound.call_args[0][0]
        assert sent_msg.channel == "ms_teams"
        assert sent_msg.direction == "outbound"
        assert sent_msg.external_chat_id == "ext_teams"


@pytest.mark.asyncio
async def test_delivery_router_whatsapp_sends_outbound() -> None:
    """WHATSAPP delivery resolves channel account and sends outbound."""
    from agents.delivery_router import delivery_router_node

    user_id = uuid4()
    mock_gateway = AsyncMock()
    mock_gateway.send_outbound = AsyncMock()

    with patch("agents.delivery_router._get_gateway", return_value=mock_gateway), \
         patch("agents.delivery_router._resolve_channel_account", new_callable=AsyncMock, return_value=("ext_wa", "ext_wa")):
        state = {
            "messages": [AIMessage(content="Hello from agent")],
            "delivery_targets": ["WHATSAPP"],
            "loaded_facts": [],
            "user_id": user_id,
        }
        result = await delivery_router_node(state)
        assert result == {}
        mock_gateway.send_outbound.assert_called_once()
        sent_msg = mock_gateway.send_outbound.call_args[0][0]
        assert sent_msg.channel == "whatsapp"
        assert sent_msg.direction == "outbound"
        assert sent_msg.external_chat_id == "ext_wa"


@pytest.mark.asyncio
async def test_delivery_router_no_channel_account_skips() -> None:
    """Channel delivery without a linked account logs warning and skips."""
    from agents.delivery_router import delivery_router_node

    user_id = uuid4()
    mock_gateway = AsyncMock()

    with patch("agents.delivery_router._get_gateway", return_value=mock_gateway), \
         patch("agents.delivery_router._resolve_channel_account", new_callable=AsyncMock, return_value=("", None)):
        state = {
            "messages": [AIMessage(content="Hello")],
            "delivery_targets": ["TELEGRAM"],
            "loaded_facts": [],
            "user_id": user_id,
        }
        result = await delivery_router_node(state)
        assert result == {}
        mock_gateway.send_outbound.assert_not_called()


@pytest.mark.asyncio
async def test_delivery_router_multiple_targets() -> None:
    """Multiple targets: WEB_CHAT + TELEGRAM both processed."""
    from agents.delivery_router import delivery_router_node

    user_id = uuid4()
    mock_gateway = AsyncMock()
    mock_gateway.send_outbound = AsyncMock()

    with patch("agents.delivery_router._get_gateway", return_value=mock_gateway), \
         patch("agents.delivery_router._resolve_channel_account", new_callable=AsyncMock, return_value=("ext_123", "ext_123")):
        state = {
            "messages": [AIMessage(content="Hello")],
            "delivery_targets": ["WEB_CHAT", "TELEGRAM"],
            "loaded_facts": [],
            "user_id": user_id,
        }
        result = await delivery_router_node(state)
        assert result == {}
        # TELEGRAM sends outbound, WEB_CHAT is no-op
        assert mock_gateway.send_outbound.call_count == 1


@pytest.mark.asyncio
async def test_delivery_router_empty_messages() -> None:
    """Empty messages list: does not raise."""
    from agents.delivery_router import delivery_router_node

    state = {
        "messages": [],
        "delivery_targets": ["WEB_CHAT"],
        "loaded_facts": [],
    }
    result = await delivery_router_node(state)
    assert result == {}


@pytest.mark.asyncio
async def test_delivery_router_invalid_target_logs_error() -> None:
    """Invalid target string logs error and does not raise."""
    from agents.delivery_router import delivery_router_node

    with patch("agents.delivery_router.logger") as mock_logger:
        state = {
            "messages": [AIMessage(content="Hello")],
            "delivery_targets": ["INVALID_TARGET"],
            "loaded_facts": [],
        }
        result = await delivery_router_node(state)
        assert result == {}
        mock_logger.error.assert_called_once()
