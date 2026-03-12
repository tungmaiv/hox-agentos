"""
MCP Tool Registry -- startup discovery + runtime gated execution.

MCPToolRegistry.refresh() is called at FastAPI startup. It loads active
mcp_server entries from registry_entries, calls tools/list on each, and upserts
discovered tools back into registry_entries.

call_mcp_tool() executes an MCP tool call through all 3 security gates:
  Gate 1 (JWT): caller's route handler validates the JWT via Depends(get_current_user)
  Gate 2 (RBAC): check required_permissions from tool definition
  Gate 3 (ACL): check tool_acl table for (user_id, tool_name)

After all gates pass, the call is forwarded to the appropriate MCPClient.
Every call attempt is audit-logged regardless of allow/deny outcome.

Phase 24 evolution:
- refresh() now reads from registry_entries (type='mcp_server', status='active')
  instead of the dropped mcp_servers table
- Discovered tools upserted into registry_entries (type='tool')
- get_tool() / update_tool_last_seen() imported from registry.service
"""
import time
from typing import Any

import structlog
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_audit_logger
from core.models.user import UserContext
from mcp.client import MCPClient
from registry.service import get_tool, update_tool_last_seen
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
        Called at startup. Loads active mcp_server entries from registry_entries,
        calls tools/list on each, and upserts discovered tools into registry_entries.

        Servers that are unreachable at startup are logged and skipped —
        they can be manually re-registered later without a full restart.
        """
        from core.db import async_session
        from registry.models import RegistryEntry
        from sqlalchemy import select

        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RegistryEntry).where(
                        RegistryEntry.type == "mcp_server",
                        RegistryEntry.deleted_at.is_(None),
                    )
                )
                all_servers = result.scalars().all()

        # Evict clients for non-active servers
        for server in all_servers:
            if server.status != "active" and server.name in _clients:
                del _clients[server.name]
                logger.info(
                    "mcp_client_evicted",
                    server=server.name,
                    status=server.status,
                )

        active_servers = [s for s in all_servers if s.status == "active"]

        for server in active_servers:
            try:
                cfg = server.config or {}
                url = cfg.get("url")
                if not url:
                    logger.warning(
                        "mcp_server_no_url",
                        server=server.name,
                    )
                    continue

                # Decrypt auth_token_hex if present
                auth_token: str | None = None
                auth_token_hex = cfg.get("auth_token_hex")
                if auth_token_hex:
                    try:
                        from security.credentials import decrypt_token

                        raw = bytes.fromhex(auth_token_hex)
                        iv = raw[:12]
                        ciphertext = raw[12:]
                        auth_token = decrypt_token(ciphertext, iv)
                    except Exception as exc:
                        logger.warning(
                            "mcp_auth_token_decrypt_failed",
                            server=server.name,
                            error=str(exc),
                        )

                client = MCPClient(server_url=url, auth_token=auth_token)
                _clients[server.name] = client
                tools = await client.list_tools()

                # Upsert discovered tools into registry_entries
                async with async_session() as upsert_session:
                    async with upsert_session.begin():
                        from datetime import datetime, timezone
                        from uuid import uuid4

                        for tool in tools:
                            tool_name = f"{server.name}.{tool['name']}"
                            # Check if entry already exists
                            existing_result = await upsert_session.execute(
                                select(RegistryEntry).where(
                                    RegistryEntry.type == "tool",
                                    RegistryEntry.name == tool_name,
                                    RegistryEntry.deleted_at.is_(None),
                                )
                            )
                            existing = existing_result.scalar_one_or_none()

                            tool_config = {
                                "handler_type": "mcp",
                                "mcp_server_id": str(server.id),
                                "mcp_tool_name": tool["name"],
                                "required_permissions": [f"{server.name}:read"],
                                "sandbox_required": False,
                            }

                            if existing is not None:
                                existing.config = tool_config
                                existing.status = "active"
                                existing.description = tool.get("description", "")
                                existing.updated_at = datetime.now(timezone.utc)
                            else:
                                new_tool = RegistryEntry(
                                    id=uuid4(),
                                    type="tool",
                                    name=tool_name,
                                    description=tool.get("description", ""),
                                    config=tool_config,
                                    status="active",
                                    owner_id=server.owner_id,
                                )
                                upsert_session.add(new_tool)

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

    @classmethod
    def evict_client(cls, server_name: str) -> None:
        """Remove a server's client from cache (called when server is disabled)."""
        if server_name in _clients:
            del _clients[server_name]
            logger.info("mcp_client_evicted", server=server_name, reason="status_change")


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
    tool_def = await get_tool(tool_name, db_session)
    if tool_def is None:
        raise HTTPException(
            status_code=404, detail=f"Tool '{tool_name}' not registered"
        )

    # Gate 2: RBAC — check each required permission
    for permission in tool_def.get("required_permissions", []):
        if not await has_permission(user, permission, db_session):
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

    result = await client.call_tool(mcp_tool_name, arguments)

    try:
        await update_tool_last_seen(tool_name, db_session)
    except Exception:
        pass  # best-effort, don't fail the tool call

    return result
