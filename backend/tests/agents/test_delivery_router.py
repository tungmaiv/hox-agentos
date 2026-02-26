"""TDD tests for DeliveryRouterNode."""
import pytest
from langchain_core.messages import AIMessage
from unittest.mock import patch


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
async def test_delivery_router_telegram_stub_logs_warning() -> None:
    """TELEGRAM stub logs warning and does not raise."""
    from agents.delivery_router import delivery_router_node

    with patch("agents.delivery_router.logger") as mock_logger:
        state = {
            "messages": [AIMessage(content="Hello")],
            "delivery_targets": ["TELEGRAM"],
            "loaded_facts": [],
        }
        result = await delivery_router_node(state)
        assert result == {}
        mock_logger.warning.assert_called_once()


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
async def test_delivery_router_teams_stub_logs_warning() -> None:
    """TEAMS stub logs warning and does not raise."""
    from agents.delivery_router import delivery_router_node

    with patch("agents.delivery_router.logger") as mock_logger:
        state = {
            "messages": [AIMessage(content="Hello")],
            "delivery_targets": ["TEAMS"],
            "loaded_facts": [],
        }
        result = await delivery_router_node(state)
        assert result == {}
        mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_delivery_router_multiple_targets() -> None:
    """Multiple targets: WEB_CHAT + TELEGRAM both processed."""
    from agents.delivery_router import delivery_router_node

    with patch("agents.delivery_router.logger") as mock_logger:
        state = {
            "messages": [AIMessage(content="Hello")],
            "delivery_targets": ["WEB_CHAT", "TELEGRAM"],
            "loaded_facts": [],
        }
        result = await delivery_router_node(state)
        assert result == {}
        # TELEGRAM stub logs warning; WEB_CHAT logs debug
        warning_calls = list(mock_logger.warning.call_args_list)
        assert len(warning_calls) == 1  # only TELEGRAM warning


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
