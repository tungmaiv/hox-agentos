"""TDD tests for master agent intent routing."""
import pytest


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
