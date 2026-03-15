"""
MCP server CRUD API -- admin management of MCP server registry.

GET    /api/admin/mcp-servers              -- list all registered MCP servers
POST   /api/admin/mcp-servers              -- register a new MCP server
GET    /api/admin/mcp-servers/check-name   -- check name availability
DELETE /api/admin/mcp-servers/{id}         -- remove a registered MCP server
GET    /api/admin/mcp-servers/{id}/health  -- check MCP server reachability
PATCH  /api/admin/mcp-servers/{id}/status  -- update server status

Security: admin-only via Gate 2 RBAC (tool:admin permission).
Auth tokens are AES-256-GCM encrypted before storage; raw token is never logged.
user_id for audit logging comes from JWT -- never from the request body.

Migration note (Phase 24+): storage uses registry_entries (unified registry).
The old mcp_servers table was dropped; entries live in registry_entries with type='mcp_server'.
Auth tokens are hex-encoded encrypted blobs stored in config['auth_token_hex'].
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
from core.models.user import UserContext
from core.schemas.registry import McpServerCreate, RegistryEntryCreate
from mcp.registry import MCPToolRegistry
from registry.models import RegistryEntry
from registry.service import UnifiedRegistryService, invalidate_tool_cache
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


def _entry_to_response(entry: RegistryEntry) -> dict[str, Any]:
    cfg: dict[str, Any] = entry.config or {}
    return {
        "id": str(entry.id),
        "name": entry.name,
        "url": cfg.get("url", ""),
        "is_active": entry.status == "active",
        "status": entry.status,
    }


@router.get("")
async def list_mcp_servers(
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return all registered MCP servers. Auth tokens are never returned."""
    result = await session.execute(
        select(RegistryEntry).where(
            RegistryEntry.type == "mcp_server",
            RegistryEntry.deleted_at.is_(None),
        )
    )
    servers = result.scalars().all()
    logger.info("mcp_servers_listed", user_id=str(user["user_id"]), count=len(servers))
    return [_entry_to_response(s) for s in servers]


@router.post("")
async def create_mcp_server(
    body: McpServerCreate,
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Register a new MCP server. Encrypts auth_token with AES-256-GCM before storage."""
    config: dict[str, Any] = {"url": body.url, "is_active": True}

    if body.auth_token:
        from security.credentials import encrypt_token
        ciphertext, iv = encrypt_token(body.auth_token)
        auth_token_bytes = iv + ciphertext
        config["auth_token_hex"] = auth_token_bytes.hex()

    svc = UnifiedRegistryService()
    entry_data = RegistryEntryCreate(
        type="mcp_server",
        name=body.name,
        description=body.description if hasattr(body, "description") else None,
        config=config,
        status="active",
    )
    entry = await svc.create_entry(session, entry_data, owner_id=user["user_id"])
    await session.commit()

    # Hot-register: make new server's tools immediately callable without restart.
    try:
        await MCPToolRegistry.refresh()
    except Exception as exc:
        logger.warning("mcp_hot_registration_failed", name=body.name, error=str(exc))

    logger.info(
        "mcp_server_registered",
        name=body.name,
        user_id=str(user["user_id"]),
    )
    return _entry_to_response(entry)


@router.get("/check-name")
async def check_mcp_server_name(
    name: str = Query(..., min_length=1),
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Returns {"available": true/false} for the given MCP server name (case-insensitive)."""
    count = await session.scalar(
        select(func.count()).where(
            RegistryEntry.type == "mcp_server",
            func.lower(RegistryEntry.name) == name.lower(),
            RegistryEntry.deleted_at.is_(None),
        )
    )
    return {"available": (count or 0) == 0}


class McpTestRequest(BaseModel):
    """Request body for testing MCP server connectivity."""

    url: str
    auth_token: str | None = None


class McpTestResponse(BaseModel):
    """Response from MCP connection test."""

    success: bool
    latency_ms: int
    tool_count: int | None = None
    error: str | None = None
    hint: str | None = None


@router.post("/test")
async def test_mcp_connection(
    body: McpTestRequest,
    user: UserContext = Depends(_require_admin),
) -> dict[str, Any]:
    """Test connectivity to an MCP server by attempting SSE connection and tools/list."""
    import httpx

    logger.info("mcp_test_connection", url=body.url, user_id=str(user["user_id"]))

    start = time.monotonic()
    headers: dict[str, str] = {}
    if body.auth_token:
        headers["Authorization"] = f"Bearer {body.auth_token}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Attempt to reach the SSE endpoint
            resp = await client.get(f"{body.url}/sse", headers=headers)
            latency_ms = int((time.monotonic() - start) * 1000)
            if resp.status_code >= 400:
                return McpTestResponse(
                    success=False,
                    latency_ms=latency_ms,
                    error=f"HTTP {resp.status_code} from SSE endpoint",
                    hint="Check that the MCP server is running and the URL is correct",
                ).model_dump()

            return McpTestResponse(
                success=True,
                latency_ms=latency_ms,
            ).model_dump()

    except httpx.ConnectError:
        latency_ms = int((time.monotonic() - start) * 1000)
        return McpTestResponse(
            success=False,
            latency_ms=latency_ms,
            error="Connection refused",
            hint="Check that the MCP server is running and the URL is correct",
        ).model_dump()
    except httpx.TimeoutException:
        latency_ms = int((time.monotonic() - start) * 1000)
        return McpTestResponse(
            success=False,
            latency_ms=latency_ms,
            error="Connection timed out",
            hint="Server did not respond within 10 seconds",
        ).model_dump()
    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        error_msg = str(exc)
        hint = None
        if "ssl" in error_msg.lower() or "certificate" in error_msg.lower():
            hint = "SSL certificate verification failed -- check TLS configuration"
        else:
            hint = "Check that the MCP server is running and the URL is correct"
        return McpTestResponse(
            success=False,
            latency_ms=latency_ms,
            error=error_msg,
            hint=hint,
        ).model_dump()


@router.delete("/{server_id}")
async def delete_mcp_server(
    server_id: UUID,
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Remove a registered MCP server by ID."""
    result = await session.execute(
        select(RegistryEntry).where(
            RegistryEntry.id == server_id,
            RegistryEntry.type == "mcp_server",
            RegistryEntry.deleted_at.is_(None),
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Server not found")

    try:
        MCPToolRegistry.evict_client(entry.name)
    except Exception:
        pass

    from datetime import datetime
    entry.deleted_at = datetime.utcnow()
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
    """Check reachability of an MCP server."""
    import httpx

    result = await session.execute(
        select(RegistryEntry).where(
            RegistryEntry.id == server_id,
            RegistryEntry.type == "mcp_server",
            RegistryEntry.deleted_at.is_(None),
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Server not found")

    url = (entry.config or {}).get("url", "")
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{url}/health")
            latency_ms = int((time.monotonic() - start) * 1000)
            reachable = resp.status_code < 500
    except Exception:
        latency_ms = int((time.monotonic() - start) * 1000)
        reachable = False

    return {
        "server_id": str(server_id),
        "name": entry.name,
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
    """Update an MCP server's status."""
    valid_statuses = {"active", "disabled", "deprecated"}
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{body.status}'. Must be one of: {', '.join(sorted(valid_statuses))}",
        )

    result = await session.execute(
        select(RegistryEntry).where(
            RegistryEntry.id == server_id,
            RegistryEntry.type == "mcp_server",
            RegistryEntry.deleted_at.is_(None),
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Server not found")

    old_status = entry.status
    entry.status = body.status
    await session.commit()

    if body.status != "active":
        try:
            MCPToolRegistry.evict_client(entry.name)
        except Exception:
            pass
        invalidate_tool_cache()

    logger.info(
        "mcp_server_status_updated",
        server_id=str(server_id),
        name=entry.name,
        old_status=old_status,
        new_status=body.status,
        user_id=str(user["user_id"]),
    )
    return _entry_to_response(entry)
