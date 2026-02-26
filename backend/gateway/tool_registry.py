"""
Tool registry — single source of truth for all registered tools.

All tools (backend tools, MCP wrappers, sandbox tools) are registered here.
This is the SINGLE registry for all tools — never register tools elsewhere.

Tool definition fields:
  - name: str — unique tool identifier (e.g. "email.fetch", "crm.list_projects")
  - description: str — human-readable description
  - required_permissions: list[str] — checked at Gate 2 (RBAC)
  - sandbox_required: bool — routes to Docker sandbox executor
  - mcp_server: str | None — for MCP-backed tools (server name in mcp_servers table)
  - mcp_tool: str | None — for MCP-backed tools (tool name on the MCP server)
"""
from typing import Any

_registry: dict[str, Any] = {}


def register_tool(
    name: str,
    description: str = "",
    required_permissions: list[str] | None = None,
    sandbox_required: bool = False,
    mcp_server: str | None = None,
    mcp_tool: str | None = None,
) -> None:
    """
    Register a tool with its definition.

    Called at application startup (for static tools) or during MCPToolRegistry.refresh()
    (for dynamically discovered MCP tools).

    Args:
        name: Unique tool identifier. For MCP tools: "{server_name}.{tool_name}".
        description: Human-readable description of what the tool does.
        required_permissions: List of permission strings checked at Gate 2 (RBAC).
                              Empty list = no permission restriction.
        sandbox_required: True if the tool must run inside a Docker sandbox.
        mcp_server: Name of the MCP server (from mcp_servers table) for MCP-backed tools.
        mcp_tool: Name of the tool on the remote MCP server for MCP-backed tools.
    """
    _registry[name] = {
        "name": name,
        "description": description,
        "required_permissions": required_permissions or [],
        "sandbox_required": sandbox_required,
        "mcp_server": mcp_server,
        "mcp_tool": mcp_tool,
    }


def get_tool(name: str) -> dict[str, Any] | None:
    """Get a tool definition by name. Returns None if not registered."""
    return _registry.get(name)


def list_tools() -> list[str]:
    """Return list of all registered tool names."""
    return list(_registry.keys())


# CRM tools — registered at module load for static discovery.
# Dynamic discovery via MCPToolRegistry.refresh() at startup may overwrite these
# with the same definitions (idempotent). Pre-registering here ensures tests and
# sub-agents can look up these tools before the MCP server connects at startup.
register_tool(
    name="crm.get_project_status",
    description="Get project status from CRM",
    required_permissions=["crm:read"],
    mcp_server="crm",
    mcp_tool="get_project_status",
)
register_tool(
    name="crm.list_projects",
    description="List all CRM projects",
    required_permissions=["crm:read"],
    mcp_server="crm",
    mcp_tool="list_projects",
)
register_tool(
    name="crm.update_task_status",
    description="Update task status in CRM kanban",
    required_permissions=["crm:write"],
    mcp_server="crm",
    mcp_tool="update_task_status",
)
