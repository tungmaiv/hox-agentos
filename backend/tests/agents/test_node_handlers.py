import pytest
from unittest.mock import AsyncMock, patch
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
