"""TDD tests for project sub-agent node."""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from langchain_core.messages import HumanMessage


@pytest.mark.asyncio
async def test_project_agent_calls_mcp_tool() -> None:
    """Verifies call_mcp_tool is called with crm.get_project_status.
    Patched at agents.subagents.project_agent.call_mcp_tool (top-level import).
    """
    user = {
        "user_id": uuid.uuid4(),
        "email": "test@blitz.local",
        "roles": ["employee"],
        "permissions": ["crm:read"],
    }

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("agents.subagents.project_agent.call_mcp_tool", new_callable=AsyncMock) as mock_call,
        patch("agents.subagents.project_agent.current_user_ctx") as mock_ctx,
        patch("agents.subagents.project_agent.get_session", return_value=mock_session),
    ):
        mock_ctx.get.return_value = user
        mock_call.return_value = {
            "success": True,
            "result": {
                "project_name": "Project Alpha",
                "status": "active",
                "owner": "tung@blitz.local",
                "progress_pct": 65,
                "last_update": "2026-02-25",
            },
        }
        from agents.subagents.project_agent import project_agent_node

        state = {
            "messages": [HumanMessage(content="status of Project Alpha?")],
            "delivery_targets": ["WEB_CHAT"],
            "loaded_facts": [],
        }
        result = await project_agent_node(state)

        mock_call.assert_called_once()
        args = mock_call.call_args[0]
        assert args[0] == "crm.get_project_status"


@pytest.mark.asyncio
async def test_project_agent_returns_structured_output() -> None:
    """Result is ProjectStatusResult-compatible dict."""
    user = {
        "user_id": uuid.uuid4(),
        "email": "test@blitz.local",
        "roles": ["employee"],
        "permissions": ["crm:read"],
    }

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("agents.subagents.project_agent.call_mcp_tool", new_callable=AsyncMock) as mock_call,
        patch("agents.subagents.project_agent.current_user_ctx") as mock_ctx,
        patch("agents.subagents.project_agent.get_session", return_value=mock_session),
    ):
        mock_ctx.get.return_value = user
        mock_call.return_value = {
            "success": True,
            "result": {
                "project_name": "Project Alpha",
                "status": "active",
                "owner": "tung@blitz.local",
                "progress_pct": 65,
                "last_update": "2026-02-25",
            },
        }
        from agents.subagents.project_agent import project_agent_node
        from core.schemas.agent_outputs import ProjectStatusResult

        state = {"messages": [], "delivery_targets": ["WEB_CHAT"], "loaded_facts": []}
        result = await project_agent_node(state)
        parsed = json.loads(result["messages"][0].content)
        output = ProjectStatusResult.model_validate(parsed)
        assert output.agent == "project"
        assert output.progress_pct == 65


@pytest.mark.asyncio
async def test_project_agent_returns_friendly_message_on_mcp_failure() -> None:
    """On MCP failure: returns friendly error message, no exception raised."""
    user = {
        "user_id": uuid.uuid4(),
        "email": "test@blitz.local",
        "roles": ["employee"],
        "permissions": [],
    }

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("agents.subagents.project_agent.call_mcp_tool", new_callable=AsyncMock) as mock_call,
        patch("agents.subagents.project_agent.current_user_ctx") as mock_ctx,
        patch("agents.subagents.project_agent.get_session", return_value=mock_session),
    ):
        mock_ctx.get.return_value = user
        mock_call.side_effect = HTTPException(
            status_code=403, detail="Missing permission: crm:read"
        )
        from agents.subagents.project_agent import project_agent_node

        state = {"messages": [], "delivery_targets": ["WEB_CHAT"], "loaded_facts": []}
        result = await project_agent_node(state)
        # Should not raise — returns friendly message
        content = result["messages"][0].content
        assert "couldn't reach" in content or "contact" in content.lower()


@pytest.mark.asyncio
async def test_project_agent_no_user_context_returns_auth_error() -> None:
    """If no user context available, returns authentication error message."""
    with patch("agents.subagents.project_agent.current_user_ctx") as mock_ctx:
        mock_ctx.get.return_value = None
        from agents.subagents.project_agent import project_agent_node

        state = {"messages": [], "delivery_targets": ["WEB_CHAT"], "loaded_facts": []}
        result = await project_agent_node(state)
        content = result["messages"][0].content
        assert "authentication" in content.lower() or "couldn't access" in content.lower()
