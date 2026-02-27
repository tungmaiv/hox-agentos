"""
Tests for the real tool_node handler that calls call_mcp_tool() from mcp/registry.py.

Verifies:
- Unknown tool returns error dict without raising
- Known tool delegates to call_mcp_tool() with correct UserContext
- call_mcp_tool() failure (HTTPException) returns error dict without propagating
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from agents.workflow_state import WorkflowState


def _make_state(user_id: str | None = None) -> WorkflowState:
    return {
        "run_id": uuid4(),
        "user_context": {
            "user_id": user_id or str(uuid4()),
            "email": "test@blitz.local",
            "username": "testuser",
            "roles": ["employee"],
            "groups": [],
        },
        "node_outputs": {},
        "current_output": None,
        "hitl_result": None,
    }


@pytest.mark.asyncio
async def test_tool_node_returns_error_for_unknown_tool():
    """Unknown tool name returns error dict, does not raise."""
    from agents.node_handlers import get_handler
    handler = get_handler("tool_node")
    state = _make_state()
    result = await handler({"tool_name": "nonexistent.tool", "params": {}}, state)
    assert result["success"] is False
    assert "not registered" in result["error"]


@pytest.mark.asyncio
async def test_tool_node_calls_mcp_for_known_tool():
    """Known tool delegates to call_mcp_tool."""
    from agents.node_handlers import get_handler

    mock_result = {"projects": ["Alpha", "Beta"], "count": 2}

    with patch("agents.node_handlers.call_mcp_tool", new_callable=AsyncMock) as mock_call, \
         patch("agents.node_handlers.async_session") as mock_session_factory:

        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_call.return_value = mock_result

        handler = get_handler("tool_node")
        state = _make_state()
        result = await handler(
            {"tool_name": "crm.list_projects", "params": {"limit": 10}},
            state,
        )

    assert result == mock_result
    mock_call.assert_called_once()
    call_kwargs = mock_call.call_args
    assert call_kwargs[1]["tool_name"] == "crm.list_projects"
    assert call_kwargs[1]["arguments"] == {"limit": 10}


@pytest.mark.asyncio
async def test_tool_node_returns_error_on_acl_denial():
    """ACL denial (HTTPException 403) is caught and returned as error dict."""
    from agents.node_handlers import get_handler
    from fastapi import HTTPException

    with patch("agents.node_handlers.call_mcp_tool", new_callable=AsyncMock) as mock_call, \
         patch("agents.node_handlers.async_session") as mock_session_factory:

        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_call.side_effect = HTTPException(status_code=403, detail="Tool call denied by ACL")

        handler = get_handler("tool_node")
        state = _make_state()
        result = await handler({"tool_name": "crm.list_projects", "params": {}}, state)

    assert result["success"] is False
    assert "403" in result["error"] or "denied" in result["error"].lower()
