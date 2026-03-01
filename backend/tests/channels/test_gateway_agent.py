"""
Tests for ChannelGateway._invoke_agent() wiring to the master agent graph.

Verifies the refactored contract (Phase 10-01):
- _invoke_agent() returns None; response is delivered via delivery_router_node -> send_outbound()
- Timeout calls send_outbound() with error reply, returns None
- Exception calls send_outbound() with error reply, returns None
- Keycloak failure calls send_outbound() with permission error, returns None
- delivery_targets is set to [msg.channel.upper()] in initial_state
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
async def test_invoke_agent_returns_none_on_success() -> None:
    """_invoke_agent() returns None; delivery happens via delivery_router_node."""
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

    # New contract: _invoke_agent() returns None; delivery handled by graph
    assert result is None


@pytest.mark.asyncio
async def test_invoke_agent_sets_delivery_targets() -> None:
    """_invoke_agent() passes delivery_targets=[channel.upper()] to graph initial_state."""
    gateway = ChannelGateway(sidecar_urls={"telegram": "http://telegram:9001"})
    msg = _make_inbound_msg("Hello")

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value={"messages": []})

    captured_state: dict = {}

    async def capture_state(state, config=None, **kwargs):
        captured_state.update(state)
        return {"messages": []}

    mock_graph.ainvoke = capture_state

    with patch("agents.master_agent.create_master_graph", return_value=mock_graph), \
         patch("security.keycloak_client.fetch_user_realm_roles", new_callable=AsyncMock, return_value=["employee"]):
        await gateway._invoke_agent(msg)

    assert captured_state.get("delivery_targets") == ["TELEGRAM"]


@pytest.mark.asyncio
async def test_invoke_agent_timeout_sends_error_reply() -> None:
    """Agent timeout calls send_outbound() with error reply and returns None."""
    gateway = ChannelGateway(sidecar_urls={"telegram": "http://telegram:9001"})
    msg = _make_inbound_msg("Slow question")

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"messages": []})

    sent_messages: list[InternalMessage] = []

    async def capture_outbound(out_msg: InternalMessage) -> None:
        sent_messages.append(out_msg)

    gateway.send_outbound = capture_outbound

    with patch("agents.master_agent.create_master_graph", return_value=mock_graph), \
         patch("security.keycloak_client.fetch_user_realm_roles", new_callable=AsyncMock, return_value=["employee"]), \
         patch.object(asyncio, "wait_for", side_effect=asyncio.TimeoutError):
        result = await gateway._invoke_agent(msg)

    assert result is None
    assert len(sent_messages) == 1
    assert sent_messages[0].direction == "outbound"
    assert "Sorry, I couldn't process your request" in sent_messages[0].text


@pytest.mark.asyncio
async def test_invoke_agent_error_sends_error_reply() -> None:
    """Agent exception calls send_outbound() with error reply and returns None."""
    gateway = ChannelGateway(sidecar_urls={"telegram": "http://telegram:9001"})
    msg = _make_inbound_msg("Trigger error")

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

    sent_messages: list[InternalMessage] = []

    async def capture_outbound(out_msg: InternalMessage) -> None:
        sent_messages.append(out_msg)

    gateway.send_outbound = capture_outbound

    with patch("agents.master_agent.create_master_graph", return_value=mock_graph), \
         patch("security.keycloak_client.fetch_user_realm_roles", new_callable=AsyncMock, return_value=["employee"]):
        result = await gateway._invoke_agent(msg)

    assert result is None
    assert len(sent_messages) == 1
    assert sent_messages[0].direction == "outbound"
    assert "Sorry, I couldn't process your request" in sent_messages[0].text


@pytest.mark.asyncio
async def test_invoke_agent_keycloak_failure_sends_permission_error() -> None:
    """Keycloak unreachable calls send_outbound() with permission error and returns None."""
    import httpx

    gateway = ChannelGateway(sidecar_urls={"telegram": "http://telegram:9001"})
    msg = _make_inbound_msg("Hello")

    sent_messages: list[InternalMessage] = []

    async def capture_outbound(out_msg: InternalMessage) -> None:
        sent_messages.append(out_msg)

    gateway.send_outbound = capture_outbound

    with patch("security.keycloak_client.fetch_user_realm_roles", new_callable=AsyncMock, side_effect=httpx.ConnectError("unreachable")):
        result = await gateway._invoke_agent(msg)

    assert result is None
    assert len(sent_messages) == 1
    assert sent_messages[0].direction == "outbound"
    assert "couldn't verify your permissions" in sent_messages[0].text
