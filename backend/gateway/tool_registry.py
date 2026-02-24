"""
Tool registry stub.

All tools (backend tools, MCP wrappers, sandbox tools) are registered here.
This is the SINGLE registry for all tools — never register tools elsewhere.

Populated in Phase 2+ with:
  - required_permissions: checked at Gate 2 (RBAC)
  - sandbox_required: routes to Docker sandbox executor
  - mcp_server / mcp_tool: for MCP-backed tools
"""
from typing import Any

_registry: dict[str, Any] = {}


def register_tool(name: str, definition: dict[str, Any]) -> None:
    """Register a tool with its definition. Called at application startup."""
    _registry[name] = definition


def get_tool(name: str) -> dict[str, Any] | None:
    """Get a tool definition by name. Returns None if not registered."""
    return _registry.get(name)


def list_tools() -> list[str]:
    """Return list of all registered tool names."""
    return list(_registry.keys())
