"""
MCP server CRUD API -- admin management of MCP server registry.

GET    /api/admin/mcp-servers              -- list all registered MCP servers
POST   /api/admin/mcp-servers              -- register a new MCP server
DELETE /api/admin/mcp-servers/{id}         -- remove a registered MCP server
GET    /api/admin/mcp-servers/{id}/health  -- check MCP server reachability
PATCH  /api/admin/mcp-servers/{id}/status  -- update server status

Security: admin-only via Gate 2 RBAC (tool:admin permission).
Auth tokens are AES-256-GCM encrypted before storage; raw token is never logged.
user_id for audit logging comes from JWT -- never from the request body.
"""
import time
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.mcp_server import McpServer
from core.models.user import UserContext
from core.schemas.registry import McpServerCreate
from mcp.registry import MCPToolRegistry
from security.deps import get_current_user
from security.rbac import has_permission

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin/mcp-servers", tags=["admin"])


async def _require_admin(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2 dependency: deny non-admins with 403."""
    if not await has_permission(user, "tool:admin", session):
        raise HTTPException(status_code=403, detail="Admin permission required")
    return user


class StatusPatch(BaseModel):
    """Request body for updating MCP server status."""

    status: str  # "active", "disabled", "deprecated"


@router.get("")
async def list_mcp_servers(
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return all registered MCP servers. Auth tokens are never returned."""
    result = await session.execute(select(McpServer))
    servers = result.scalars().all()
    logger.info("mcp_servers_listed", user_id=str(user["user_id"]), count=len(servers))
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "url": s.url,
            "is_active": s.is_active,
            "status": s.status,
        }
        for s in servers
    ]


@router.post("")
async def create_mcp_server(
    body: McpServerCreate,
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Register a new MCP server. Encrypts auth_token with AES-256-GCM before storage."""
    from security.credentials import encrypt_token

    auth_token_bytes: bytes | None = None
    if body.auth_token:
        # Embed IV (12 bytes) at the front of the stored blob: iv + ciphertext
        ciphertext, iv = encrypt_token(body.auth_token)
        auth_token_bytes = iv + ciphertext

    server = McpServer(
        name=body.name,
        url=body.url,
        auth_token=auth_token_bytes,
    )
    session.add(server)
    await session.commit()
    await session.refresh(server)

    # Hot-register: make new server's tools immediately callable without restart.
    # refresh() is idempotent -- best-effort; server is already persisted if this fails.
    try:
        await MCPToolRegistry.refresh()
    except Exception as exc:
        logger.warning("mcp_hot_registration_failed", name=body.name, error=str(exc))

    logger.info(
        "mcp_server_registered",
        name=body.name,
        user_id=str(user["user_id"]),
    )
    return {
        "id": str(server.id),
        "name": server.name,
        "url": server.url,
        "is_active": server.is_active,
        "status": server.status,
    }


@router.get("/check-name")
async def check_mcp_server_name(
    name: str = Query(..., min_length=1),
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Returns {"available": true/false} for the given MCP server name (case-insensitive)."""
    count = await session.scalar(
        select(func.count()).where(
            func.lower(McpServer.name) == name.lower(),
        )
    )
    return {"available": (count or 0) == 0}


@router.delete("/{server_id}")
async def delete_mcp_server(
    server_id: UUID,
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Remove a registered MCP server by ID."""
    result = await session.execute(
        select(McpServer).where(McpServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")

    # Evict client before deletion
    MCPToolRegistry.evict_client(server.name)

    await session.delete(server)
    await session.commit()
    logger.info(
        "mcp_server_deleted",
        server_id=str(server_id),
        user_id=str(user["user_id"]),
    )
    return {"status": "deleted"}


@router.get("/{server_id}/health")
async def check_mcp_server_health(
    server_id: UUID,
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Check reachability of an MCP server.

    Makes an HTTP GET to {server_url}/health with a 5s timeout.
    Returns reachable status and latency.
    """
    import httpx

    result = await session.execute(
        select(McpServer).where(McpServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{server.url}/health")
            latency_ms = int((time.monotonic() - start) * 1000)
            reachable = resp.status_code < 500
    except Exception:
        latency_ms = int((time.monotonic() - start) * 1000)
        reachable = False

    return {
        "server_id": str(server_id),
        "name": server.name,
        "reachable": reachable,
        "latency_ms": latency_ms,
    }


@router.patch("/{server_id}/status")
async def patch_mcp_server_status(
    server_id: UUID,
    body: StatusPatch,
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Update an MCP server's status.

    Valid statuses: active, disabled, deprecated.
    Disabling a server evicts its client from the MCPToolRegistry cache
    and invalidates the tool cache.
    """
    from registry.service import invalidate_tool_cache

    valid_statuses = {"active", "disabled", "deprecated"}
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{body.status}'. Must be one of: {', '.join(sorted(valid_statuses))}",
        )

    result = await session.execute(
        select(McpServer).where(McpServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")

    old_status = server.status
    server.status = body.status
    await session.commit()

    # If disabled/deprecated, evict client and invalidate tool cache
    if body.status != "active":
        MCPToolRegistry.evict_client(server.name)
        invalidate_tool_cache()

    logger.info(
        "mcp_server_status_updated",
        server_id=str(server_id),
        name=server.name,
        old_status=old_status,
        new_status=body.status,
        user_id=str(user["user_id"]),
    )
    return {
        "id": str(server_id),
        "name": server.name,
        "status": body.status,
    }
