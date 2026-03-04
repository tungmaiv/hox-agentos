"""
system.capabilities tool — introspect all registered artifacts for the current user.

Returns a CapabilitiesResponse listing all agents, tools, skills, and MCP servers
that the requesting user is permitted to access, filtered by artifact permissions.

The tool queries four DB tables:
  - agent_definitions (status='active', is_active=True)
  - tool_definitions (status='active', is_active=True)
  - skill_definitions (status='active', is_active=True)
  - mcp_servers (status='active', is_active=True)

Permission filtering is applied for tools and skills using batch_check_artifact_permissions().
Agents and MCP servers use default-allow (no per-artifact permissions applied at this level).

MCP server tool counts are derived from tool_definitions where handler_type='mcp'
and the tool name prefix matches the server name (convention: "server.tool_name").
"""
import uuid
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from capabilities.schemas import (
    AgentInfo,
    CapabilitiesResponse,
    McpServerInfo,
    SkillInfo,
    ToolInfo,
)
from core.context import current_user_ctx
from core.models.agent_definition import AgentDefinition
from core.models.mcp_server import McpServer
from core.models.skill_definition import SkillDefinition
from core.models.tool_definition import ToolDefinition
from security.rbac import batch_check_artifact_permissions

logger = structlog.get_logger(__name__)


async def system_capabilities(
    user_id: UUID,
    session: AsyncSession,
) -> CapabilitiesResponse:
    """
    Return all artifacts available to the requesting user.

    Args:
        user_id: The UUID of the requesting user (from JWT context).
        session: Async SQLAlchemy session.

    Returns:
        CapabilitiesResponse with filtered lists and summary string.
    """
    # Resolve user context for permission checking
    try:
        user_ctx = current_user_ctx.get()
    except LookupError:
        # Fallback for direct invocation (e.g., in tests without gateway context)
        user_ctx = {"user_id": str(user_id), "roles": [], "email": ""}

    # --- 1. Agents (default-allow: all active agents are visible) ---
    agent_result = await session.execute(
        select(AgentDefinition).where(
            AgentDefinition.status == "active",
            AgentDefinition.is_active == True,  # noqa: E712
        )
    )
    all_agents = agent_result.scalars().all()

    agents: list[AgentInfo] = [
        AgentInfo(
            name=a.name,
            display_name=a.display_name,
            description=a.description,
            status=a.status,
        )
        for a in all_agents
    ]

    # --- 2. Tools (permission-filtered) ---
    tool_result = await session.execute(
        select(ToolDefinition).where(
            ToolDefinition.status == "active",
            ToolDefinition.is_active == True,  # noqa: E712
        )
    )
    all_tools = tool_result.scalars().all()

    tool_ids: list[UUID] = [t.id for t in all_tools]
    if tool_ids:
        allowed_tool_ids = await batch_check_artifact_permissions(
            user=user_ctx,
            artifact_type="tool",
            artifact_ids=tool_ids,
            session=session,
        )
    else:
        allowed_tool_ids: set[UUID] = set()

    tools: list[ToolInfo] = [
        ToolInfo(
            name=t.name,
            display_name=t.display_name,
            description=t.description,
            handler_type=t.handler_type,
        )
        for t in all_tools
        if t.id in allowed_tool_ids
    ]

    # --- 3. Skills (permission-filtered) ---
    skill_result = await session.execute(
        select(SkillDefinition).where(
            SkillDefinition.status == "active",
            SkillDefinition.is_active == True,  # noqa: E712
        )
    )
    all_skills = skill_result.scalars().all()

    skill_ids: list[UUID] = [s.id for s in all_skills]
    if skill_ids:
        allowed_skill_ids = await batch_check_artifact_permissions(
            user=user_ctx,
            artifact_type="skill",
            artifact_ids=skill_ids,
            session=session,
        )
    else:
        allowed_skill_ids: set[UUID] = set()

    skills: list[SkillInfo] = [
        SkillInfo(
            name=s.name,
            display_name=s.display_name,
            description=s.description,
            slash_command=s.slash_command,
        )
        for s in all_skills
        if s.id in allowed_skill_ids
    ]

    # --- 4. MCP servers (default-allow: all active servers are visible) ---
    # Count tools per server using the naming convention: "server_name.tool_name"
    mcp_result = await session.execute(
        select(McpServer).where(
            McpServer.status == "active",
            McpServer.is_active == True,  # noqa: E712
        )
    )
    all_mcp_servers = mcp_result.scalars().all()

    # Build per-server tool count from tool_definitions with handler_type='mcp'
    mcp_tools_result = await session.execute(
        select(ToolDefinition.name, ToolDefinition.mcp_server_id).where(
            ToolDefinition.handler_type == "mcp",
            ToolDefinition.status == "active",
            ToolDefinition.is_active == True,  # noqa: E712
        )
    )
    mcp_tool_rows = mcp_tools_result.all()

    # Count tools per mcp_server_id
    tools_by_server_id: dict[uuid.UUID, int] = {}
    for row in mcp_tool_rows:
        srv_id = row[1]
        if srv_id is not None:
            tools_by_server_id[srv_id] = tools_by_server_id.get(srv_id, 0) + 1

    # Also count by name prefix fallback (convention: "server.tool_name")
    tools_by_server_name: dict[str, int] = {}
    for row in mcp_tool_rows:
        tool_name = row[0]
        if "." in tool_name:
            prefix = tool_name.split(".")[0]
            tools_by_server_name[prefix] = tools_by_server_name.get(prefix, 0) + 1

    mcp_servers: list[McpServerInfo] = [
        McpServerInfo(
            name=srv.name,
            display_name=srv.display_name,
            tools_count=(
                tools_by_server_id.get(srv.id, 0)
                or tools_by_server_name.get(srv.name, 0)
            ),
        )
        for srv in all_mcp_servers
    ]

    summary = (
        f"{len(agents)} agent{'s' if len(agents) != 1 else ''}, "
        f"{len(tools)} tool{'s' if len(tools) != 1 else ''}, "
        f"{len(skills)} skill{'s' if len(skills) != 1 else ''}, "
        f"{len(mcp_servers)} MCP server{'s' if len(mcp_servers) != 1 else ''}"
    )

    logger.info(
        "system_capabilities_queried",
        user_id=str(user_id),
        agents=len(agents),
        tools=len(tools),
        skills=len(skills),
        mcp_servers=len(mcp_servers),
    )

    return CapabilitiesResponse(
        agents=agents,
        tools=tools,
        skills=skills,
        mcp_servers=mcp_servers,
        summary=summary,
    )
