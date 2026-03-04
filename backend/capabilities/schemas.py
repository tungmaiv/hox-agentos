"""
Pydantic v2 response schemas for the system.capabilities tool.

These models define the structure returned when agents or users ask
"what can you do?" or request a capabilities listing.

Each schema maps to one of the four artifact types in the system:
  - AgentInfo: registered agent definitions
  - ToolInfo: registered tool definitions (backend, MCP, sandbox)
  - SkillInfo: registered skill definitions (instructional, procedural)
  - McpServerInfo: registered MCP server connections

CapabilitiesResponse bundles all four with a human-readable summary string.
"""
from pydantic import BaseModel


class AgentInfo(BaseModel):
    """Summary info for a single registered agent."""

    name: str
    display_name: str | None
    description: str | None
    status: str


class ToolInfo(BaseModel):
    """Summary info for a single registered tool."""

    name: str
    display_name: str | None
    description: str | None
    handler_type: str


class SkillInfo(BaseModel):
    """Summary info for a single registered skill."""

    name: str
    display_name: str | None
    description: str | None
    slash_command: str | None


class McpServerInfo(BaseModel):
    """Summary info for a single registered MCP server."""

    name: str
    display_name: str | None
    tools_count: int


class CapabilitiesResponse(BaseModel):
    """
    Full capabilities response bundling all four artifact registries.

    The summary field provides a human-readable count string,
    e.g. "3 agents, 12 tools, 5 skills, 2 MCP servers".
    """

    agents: list[AgentInfo]
    tools: list[ToolInfo]
    skills: list[SkillInfo]
    mcp_servers: list[McpServerInfo]
    summary: str
