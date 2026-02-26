"""
MCP Tool Registry — startup discovery + runtime gated execution.

MCPToolRegistry.refresh() is called at FastAPI startup. It loads all active
mcp_servers from the DB, calls tools/list on each, and registers discovered
tools in gateway/tool_registry.py.

call_mcp_tool() executes an MCP tool call through all 3 security gates:
  Gate 1 (JWT): caller's route handler validates the JWT via Depends(get_current_user)
  Gate 2 (RBAC): check required_permissions from tool definition
  Gate 3 (ACL): check tool_acl table for (user_id, tool_name)

After all gates pass, the call is forwarded to the appropriate MCPClient.
Every call attempt is audit-logged regardless of allow/deny outcome.
"""
import time
from typing import Any

import structlog
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_audit_logger
from core.models.user import UserContext
from gateway.tool_registry import get_tool, register_tool
from mcp.client import MCPClient
from security.acl import check_tool_acl
from security.rbac import has_permission

logger = structlog.get_logger(__name__)
audit_logger = get_audit_logger()

# Cache: {server_name: MCPClient}
_clients: dict[str, MCPClient] = {}


class MCPToolRegistry:
    @classmethod
    async def refresh(cls) -> None:
        """
        Called at startup. Loads active mcp_servers from DB, calls tools/list
        on each, registers discovered tools in gateway/tool_registry.py.

        Servers that are unreachable at startup are logged and skipped —
        they can be manually re-registered later without a full restart.
        """
        from core.db import async_session
        from core.models.mcp_server import McpServer
        from security.credentials import decrypt_token

        async with async_session() as session:
            result = await session.execute(
                select(McpServer).where(McpServer.is_active == True)  # noqa: E712
            )
            servers = result.scalars().all()

        for server in servers:
            try:
                auth_token: str | None = None
                if server.auth_token:
                    # auth_token is stored as iv_prefix + ciphertext (12 + n bytes)
                    # decrypt_token expects (ciphertext, iv) separately
                    # For MCP servers we store raw encrypted bytes with embedded IV
                    # Using the simple decrypt pattern from vault
                    raw = server.auth_token
                    iv = raw[:12]
                    ciphertext = raw[12:]
                    auth_token = decrypt_token(ciphertext, iv)

                client = MCPClient(server_url=server.url, auth_token=auth_token)
                _clients[server.name] = client
                tools = await client.list_tools()
                for tool in tools:
                    tool_name = f"{server.name}.{tool['name']}"
                    register_tool(
                        name=tool_name,
                        description=tool.get("description", ""),
                        required_permissions=[f"{server.name}:read"],
                        mcp_server=server.name,
                        mcp_tool=tool["name"],
                    )
                logger.info(
                    "mcp_tools_registered",
                    server=server.name,
                    count=len(tools),
                )
            except Exception as exc:
                logger.warning(
                    "mcp_server_unavailable",
                    server=server.name,
                    error=str(exc),
                )


def _get_client(server_name: str) -> MCPClient:
    client = _clients.get(server_name)
    if client is None:
        raise HTTPException(
            status_code=503,
            detail=f"MCP server '{server_name}' not connected",
        )
    return client


async def call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
    user: UserContext,
    db_session: AsyncSession,
) -> dict[str, Any]:
    """
    Execute an MCP tool call through all 3 security gates.

    Gate 1 (JWT): user already validated by caller's Depends(get_current_user).
    Gate 2 (RBAC): check required_permissions from tool definition.
    Gate 3 (ACL): check tool_acl table for (user_id, tool_name).

    Every call attempt is audit-logged with user_id, tool_name, allowed, duration_ms.
    """
    start_ms = int(time.monotonic() * 1000)
    tool_def = get_tool(tool_name)
    if tool_def is None:
        raise HTTPException(
            status_code=404, detail=f"Tool '{tool_name}' not registered"
        )

    # Gate 2: RBAC — check each required permission
    for permission in tool_def.get("required_permissions", []):
        if not has_permission(user, permission):
            elapsed = int(time.monotonic() * 1000) - start_ms
            audit_logger.info(
                "tool_call",
                tool=tool_name,
                user_id=str(user["user_id"]),
                allowed=False,
                duration_ms=elapsed,
                gate="rbac",
            )
            raise HTTPException(
                status_code=403, detail=f"Missing permission: {permission}"
            )

    # Gate 3: ACL — check per-user override in tool_acl table
    allowed = await check_tool_acl(user["user_id"], tool_name, db_session)
    elapsed = int(time.monotonic() * 1000) - start_ms
    audit_logger.info(
        "tool_call",
        tool=tool_name,
        user_id=str(user["user_id"]),
        allowed=allowed,
        duration_ms=elapsed,
        gate="acl",
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Tool call denied by ACL")

    # All gates passed — call the MCP server
    server_name = tool_def["mcp_server"]
    mcp_tool_name = tool_def["mcp_tool"]
    client = _get_client(server_name)
    return await client.call_tool(mcp_tool_name, arguments)
