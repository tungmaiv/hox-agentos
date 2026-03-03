import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from agents.node_handlers import HANDLER_REGISTRY, get_handler


def test_all_node_types_registered():
    required = {
        "trigger_node",
        "agent_node",
        "tool_node",
        "condition_node",
        "hitl_approval_node",
        "channel_output_node",
    }
    assert required.issubset(set(HANDLER_REGISTRY.keys()))


def test_get_handler_returns_callable():
    handler = get_handler("tool_node")
    assert callable(handler)


def test_get_handler_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown node type"):
        get_handler("unknown_node_xyz")


@pytest.mark.asyncio
async def test_trigger_handler_is_passthrough():
    """Trigger node returns current_output unchanged."""
    from agents.node_handlers import HANDLER_REGISTRY
    from agents.workflow_state import WorkflowState

    state: WorkflowState = {
        "run_id": None,
        "user_context": None,
        "node_outputs": {},
        "current_output": {"payload": "webhook_data"},
        "hitl_result": None,
    }
    handler = HANDLER_REGISTRY["trigger_node"]
    result = await handler({}, state)
    assert result == {"payload": "webhook_data"}


@pytest.mark.asyncio
async def test_condition_handler_evaluates_expression():
    """Condition handler returns True/False by evaluating expression."""
    from agents.workflow_state import WorkflowState

    state: WorkflowState = {
        "run_id": None,
        "user_context": None,
        "node_outputs": {},
        "current_output": {"count": 5},
        "hitl_result": None,
    }
    handler = get_handler("condition_node")
    result = await handler({"expression": "output.count > 0"}, state)
    assert result is True


@pytest.mark.asyncio
async def test_condition_handler_false():
    from agents.workflow_state import WorkflowState

    state: WorkflowState = {
        "run_id": None,
        "user_context": None,
        "node_outputs": {},
        "current_output": {"count": 0},
        "hitl_result": None,
    }
    handler = get_handler("condition_node")
    result = await handler({"expression": "output.count > 0"}, state)
    assert result is False


# ── Channel output node tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_channel_output_node_web_passthrough():
    """Web channel returns result without DB query or send_outbound call."""
    handler = get_handler("channel_output_node")
    state = {
        "run_id": None,
        "user_context": {"user_id": str(uuid4())},
        "node_outputs": {},
        "current_output": "Hello world",
        "hitl_result": None,
        "workflow_name": "Test Workflow",
    }
    result = await handler({"channel": "web", "template": "{output}"}, state)
    assert result["channel"] == "web"
    assert result["sent"] is True
    assert "[Test Workflow]" in result["message"]


@pytest.mark.asyncio
async def test_channel_output_node_telegram_delivery():
    """Telegram delivery resolves external_chat_id from channel_accounts."""
    user_id = uuid4()
    handler = get_handler("channel_output_node")
    state = {
        "run_id": None,
        "user_context": {"user_id": str(user_id)},
        "node_outputs": {},
        "current_output": "Digest content",
        "hitl_result": None,
        "workflow_name": "Morning Digest",
    }

    # Mock channel account
    mock_account = MagicMock()
    mock_account.external_user_id = "12345"

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_account))
    )
    mock_begin_ctx = AsyncMock()
    mock_begin_ctx.__aenter__ = AsyncMock(return_value=None)
    mock_begin_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = MagicMock(return_value=mock_begin_ctx)

    mock_gateway = MagicMock()
    mock_gateway.send_outbound = AsyncMock()

    with patch("agents.node_handlers.async_session") as mock_sf, \
         patch("api.routes.channels.get_channel_gateway", return_value=mock_gateway):
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await handler({"channel": "telegram", "template": "{output}"}, state)

    assert result["sent"] is True
    mock_gateway.send_outbound.assert_called_once()

    # Verify InternalMessage has correct external IDs
    sent_msg = mock_gateway.send_outbound.call_args[0][0]
    assert sent_msg.external_user_id == "12345"
    assert sent_msg.external_chat_id == "12345"

    # Verify message is prefixed with workflow name
    assert sent_msg.text.startswith("[Morning Digest]")


@pytest.mark.asyncio
async def test_channel_output_node_no_linked_account():
    """No paired channel account raises ValueError."""
    user_id = uuid4()
    handler = get_handler("channel_output_node")
    state = {
        "run_id": None,
        "user_context": {"user_id": str(user_id)},
        "node_outputs": {},
        "current_output": "test",
        "hitl_result": None,
        "workflow_name": "",
    }

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    mock_begin_ctx = AsyncMock()
    mock_begin_ctx.__aenter__ = AsyncMock(return_value=None)
    mock_begin_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = MagicMock(return_value=mock_begin_ctx)

    with patch("agents.node_handlers.async_session") as mock_sf:
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(ValueError, match="No linked telegram account"):
            await handler({"channel": "telegram", "template": "{output}"}, state)


@pytest.mark.asyncio
async def test_channel_output_node_no_user_id():
    """No user_id in user_context raises ValueError."""
    handler = get_handler("channel_output_node")
    state = {
        "run_id": None,
        "user_context": {},
        "node_outputs": {},
        "current_output": "test",
        "hitl_result": None,
        "workflow_name": "",
    }

    with pytest.raises(ValueError, match="No user_id"):
        await handler({"channel": "telegram", "template": "{output}"}, state)


# ── Agent node tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_agent_node_dispatches_email_agent():
    """Agent node dispatches to email_agent_node and returns formatted output."""
    from langchain_core.messages import AIMessage

    handler = get_handler("agent_node")
    state = {
        "run_id": None,
        "user_context": {"user_id": str(uuid4())},
        "node_outputs": {},
        "current_output": None,
        "hitl_result": None,
        "workflow_name": "",
    }

    mock_result = {"messages": [AIMessage(content='{"agent":"email","items":[]}')]}

    with patch("agents.subagents.email_agent.email_agent_node", new_callable=AsyncMock, return_value=mock_result), \
         patch("channels.gateway.format_for_channel", return_value="formatted text"):
        result = await handler({"agent": "email_agent", "instruction": "fetch my emails"}, state)

    assert result["success"] is True
    assert result["agent"] == "email_agent"
    assert result["result"] == "formatted text"


@pytest.mark.asyncio
async def test_agent_node_dispatches_calendar_agent():
    """Agent node dispatches to calendar_agent_node."""
    from langchain_core.messages import AIMessage

    handler = get_handler("agent_node")
    state = {
        "run_id": None,
        "user_context": {"user_id": str(uuid4())},
        "node_outputs": {},
        "current_output": None,
        "hitl_result": None,
        "workflow_name": "",
    }

    mock_result = {"messages": [AIMessage(content='{"agent":"calendar","events":[]}')]}

    with patch("agents.subagents.calendar_agent.calendar_agent_node", new_callable=AsyncMock, return_value=mock_result), \
         patch("channels.gateway.format_for_channel", return_value="calendar formatted"):
        result = await handler({"agent": "calendar_agent", "instruction": "show my calendar"}, state)

    assert result["success"] is True
    assert result["agent"] == "calendar_agent"
    assert result["result"] == "calendar formatted"


@pytest.mark.asyncio
async def test_agent_node_unknown_agent():
    """Unknown agent name returns error dict with success=False."""
    handler = get_handler("agent_node")
    state = {
        "run_id": None,
        "user_context": {"user_id": str(uuid4())},
        "node_outputs": {},
        "current_output": None,
        "hitl_result": None,
        "workflow_name": "",
    }

    result = await handler({"agent": "unknown_agent"}, state)

    assert result["success"] is False
    assert "Unknown agent" in result["error"]
    assert result["agent"] == "unknown_agent"


@pytest.mark.asyncio
async def test_agent_node_subagent_failure():
    """Sub-agent exception returns error dict with success=False."""
    handler = get_handler("agent_node")
    state = {
        "run_id": None,
        "user_context": {"user_id": str(uuid4())},
        "node_outputs": {},
        "current_output": None,
        "hitl_result": None,
        "workflow_name": "",
    }

    with patch("agents.subagents.email_agent.email_agent_node", new_callable=AsyncMock, side_effect=Exception("LLM timeout")):
        result = await handler({"agent": "email_agent", "instruction": "fetch emails"}, state)

    assert result["success"] is False
    assert "LLM timeout" in result["error"]
