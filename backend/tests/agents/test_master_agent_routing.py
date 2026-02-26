"""TDD tests for master agent intent routing."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_graph_topology_has_sub_agent_nodes() -> None:
    """Compiled graph has nodes: email_agent, calendar_agent, project_agent, delivery_router."""
    from agents.master_agent import create_master_graph

    g = create_master_graph()
    node_names = list(g.nodes)
    assert "email_agent" in node_names
    assert "calendar_agent" in node_names
    assert "project_agent" in node_names
    assert "delivery_router" in node_names
    assert "master_agent" in node_names


@pytest.mark.asyncio
async def test_pre_route_email_skips_master_llm() -> None:
    """_pre_route returns 'email_agent' for email keyword — no LLM call needed."""
    from langchain_core.messages import HumanMessage
    from agents.master_agent import _pre_route

    state = {"messages": [HumanMessage(content="summarize my unread emails")]}
    with patch("agents.master_agent.async_session") as mock_session:
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=MagicMock(
            execute=AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        ))
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_cm
        result = await _pre_route(state)
    assert result == "email_agent"


@pytest.mark.asyncio
async def test_pre_route_general_goes_to_master_agent() -> None:
    """_pre_route returns 'master_agent' for general intent — no LLM call."""
    from langchain_core.messages import HumanMessage
    from agents.master_agent import _pre_route

    state = {"messages": [HumanMessage(content="write me a haiku")]}
    result = await _pre_route(state)
    assert result == "master_agent"


def test_classify_by_keywords_email() -> None:
    from agents.master_agent import _classify_by_keywords
    assert _classify_by_keywords("summarize my unread emails") == "email"
    assert _classify_by_keywords("check my inbox") == "email"


def test_classify_by_keywords_calendar() -> None:
    from agents.master_agent import _classify_by_keywords
    assert _classify_by_keywords("what's on my calendar today?") == "calendar"
    assert _classify_by_keywords("do I have any meetings?") == "calendar"


def test_classify_by_keywords_project() -> None:
    from agents.master_agent import _classify_by_keywords
    assert _classify_by_keywords("what's the status of Project Alpha?") == "project"
    assert _classify_by_keywords("show me my tasks") == "project"


def test_classify_by_keywords_general() -> None:
    from agents.master_agent import _classify_by_keywords
    assert _classify_by_keywords("write me a haiku") == "general"
    assert _classify_by_keywords("hello how are you") == "general"


@pytest.mark.asyncio
async def test_crm_tools_registered() -> None:
    """CRM tools are registered in the tool registry with correct permissions."""
    from gateway.tool_registry import get_tool

    get_project = get_tool("crm.get_project_status")
    assert get_project is not None
    assert "crm:read" in get_project["required_permissions"]
    assert get_project["mcp_server"] == "crm"
    assert get_project["mcp_tool"] == "get_project_status"

    list_proj = get_tool("crm.list_projects")
    assert list_proj is not None
    assert "crm:read" in list_proj["required_permissions"]

    update_task = get_tool("crm.update_task_status")
    assert update_task is not None
    assert "crm:write" in update_task["required_permissions"]
