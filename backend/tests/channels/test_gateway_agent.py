"""
Tests for ChannelGateway._invoke_agent() wiring to the master agent graph.

Verifies:
- Successful agent invocation returns AI response text
- Timeout returns error message
- Exception returns error message
- Keycloak failure returns permission error message
"""
import asyncio
import uuid

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from unittest.mock import AsyncMock, MagicMock, patch

from channels.gateway import ChannelGateway
from channels.models import InternalMessage


def _make_inbound_msg(text: str = "Hello") -> InternalMessage:
    """Create a test inbound InternalMessage."""
    return InternalMessage(
        direction="inbound",
        channel="telegram",
        external_user_id="ext_123",
        external_chat_id="chat_456",
        user_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        text=text,
    )


@pytest.mark.asyncio
async def test_invoke_agent_success() -> None:
    """Successful agent invocation extracts AI response from graph result."""
    gateway = ChannelGateway(sidecar_urls={"telegram": "http://telegram:9001"})
    msg = _make_inbound_msg("What is the weather?")

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value={
        "messages": [
            HumanMessage(content="What is the weather?"),
            AIMessage(content="The weather is sunny today."),
        ],
    })

    with patch("agents.master_agent.create_master_graph", return_value=mock_graph), \
         patch("security.keycloak_client.fetch_user_realm_roles", new_callable=AsyncMock, return_value=["employee"]):
        result = await gateway._invoke_agent(msg)

    assert result.direction == "outbound"
    assert result.channel == "telegram"
    assert result.text == "The weather is sunny today."
    assert result.external_user_id == "ext_123"


@pytest.mark.asyncio
async def test_invoke_agent_timeout() -> None:
    """Agent timeout returns error message."""
    gateway = ChannelGateway(sidecar_urls={"telegram": "http://telegram:9001"})
    msg = _make_inbound_msg("Slow question")

    async def slow_invoke(*args, **kwargs):
        await asyncio.sleep(999)
        return {"messages": []}

    mock_graph = MagicMock()
    mock_graph.ainvoke = slow_invoke

    # Patch asyncio.wait_for at module level to simulate timeout
    original_wait_for = asyncio.wait_for

    async def mock_wait_for(coro, *, timeout):
        # Close the coroutine to avoid warning
        coro.close() if hasattr(coro, 'close') else None
        raise asyncio.TimeoutError()

    with patch("agents.master_agent.create_master_graph", return_value=mock_graph), \
         patch("security.keycloak_client.fetch_user_realm_roles", new_callable=AsyncMock, return_value=["employee"]), \
         patch.object(asyncio, "wait_for", side_effect=asyncio.TimeoutError):
        result = await gateway._invoke_agent(msg)

    assert result.direction == "outbound"
    assert "Sorry, I couldn't process your request" in result.text


@pytest.mark.asyncio
async def test_invoke_agent_error() -> None:
    """Agent exception returns error message."""
    gateway = ChannelGateway(sidecar_urls={"telegram": "http://telegram:9001"})
    msg = _make_inbound_msg("Trigger error")

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

    with patch("agents.master_agent.create_master_graph", return_value=mock_graph), \
         patch("security.keycloak_client.fetch_user_realm_roles", new_callable=AsyncMock, return_value=["employee"]):
        result = await gateway._invoke_agent(msg)

    assert result.direction == "outbound"
    assert "Sorry, I couldn't process your request" in result.text


@pytest.mark.asyncio
async def test_invoke_agent_keycloak_failure() -> None:
    """Keycloak unreachable returns permission error message."""
    import httpx

    gateway = ChannelGateway(sidecar_urls={"telegram": "http://telegram:9001"})
    msg = _make_inbound_msg("Hello")

    with patch("security.keycloak_client.fetch_user_realm_roles", new_callable=AsyncMock, side_effect=httpx.ConnectError("unreachable")):
        result = await gateway._invoke_agent(msg)

    assert result.direction == "outbound"
    assert "couldn't verify your permissions" in result.text
