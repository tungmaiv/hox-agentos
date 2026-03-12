"""
Unified Registry API — /api/registry/* CRUD endpoints.

GET    /api/registry/          — list entries; query params: type, status (registry:read)
GET    /api/registry/{id}      — get one entry (registry:read)
POST   /api/registry/          — create entry (registry:manage)
POST   /api/registry/import    — import skill from external source (registry:manage)
PUT    /api/registry/{id}      — update entry (registry:manage)
DELETE /api/registry/{id}      — soft delete (registry:manage)

Security: Gates 1+2.
  - GET endpoints: require any authenticated user (registry:read via ROLE_PERMISSIONS)
  - Mutating endpoints: require registry:manage (it-admin role)
"""
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.user import UserContext
from core.schemas.registry import (
    RegistryEntryCreate,
    RegistryEntryResponse,
    RegistryEntryUpdate,
)
from registry.models import McpServerCatalog
from registry.service import UnifiedRegistryService
from security.deps import get_current_user
from security.rbac import has_permission
from skills.importer import SkillImportError
from skills.import_service import UnifiedImportService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/registry", tags=["registry"])

_registry_service = UnifiedRegistryService()


# ── Permission helpers ────────────────────────────────────────────────────


async def _require_read(
    user: UserContext = Depends(get_current_user),
) -> UserContext:
    """Gate 2: require authenticated user (any role can read the registry)."""
    return user


async def _require_manage(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2: require registry:manage permission (it-admin role)."""
    if not await has_permission(user, "registry:manage", session):
        raise HTTPException(
            status_code=403,
            detail="Registry manage permission required",
        )
    return user


# ── List entries ─────────────────────────────────────────────────────────


@router.get("")
async def list_entries(
    type: str | None = Query(None, description="Filter by entry type"),
    status: str | None = Query(None, description="Filter by status"),
    user: UserContext = Depends(_require_read),
    session: AsyncSession = Depends(get_db),
) -> list[RegistryEntryResponse]:
    """List registry entries with optional type and status filters."""
    entries = await _registry_service.list_entries(
        session,
        type=type,
        status=status,
    )
    logger.info(
        "registry_entries_listed",
        user_id=str(user["user_id"]),
        type=type,
        count=len(entries),
    )
    return [RegistryEntryResponse.model_validate(e) for e in entries]


# ── MCP server catalog ───────────────────────────────────────────────────


@router.get("/mcp-catalog")
async def list_mcp_catalog(
    user: UserContext = Depends(_require_read),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all pre-built MCP server catalog entries (ordered by name).

    Returns the catalog of known installable MCP servers. These are not yet
    installed — installation creates a registry_entries row.
    """
    result = await session.execute(
        select(McpServerCatalog).order_by(McpServerCatalog.name)
    )
    entries = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "name": e.name,
            "display_name": e.display_name,
            "description": e.description,
            "package_manager": e.package_manager,
            "package_name": e.package_name,
            "command": e.command,
            "args": e.args,
            "env_vars": e.env_vars,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]


# ── Import skill from external source ────────────────────────────────────


class ImportSkillRequest(BaseModel):
    """Request body for importing a skill from an external URL or URI."""

    source: str  # URL or claude-market:// URI
    source_type: str | None = None  # optional hint (not used currently)


class ImportSkillResponse(BaseModel):
    """Response after successfully importing a skill."""

    id: UUID
    name: str
    status: str
    security_score: int | None = None


_import_service = UnifiedImportService()


@router.post("/import", status_code=201, response_model=ImportSkillResponse)
async def import_skill(
    request: ImportSkillRequest,
    user: UserContext = Depends(_require_manage),
    session: AsyncSession = Depends(get_db),
) -> ImportSkillResponse:
    """Import a skill from an external source (URL, GitHub, claude-market://).

    Detects the appropriate adapter, validates source, fetches and normalizes
    the skill, runs a security scan (if available), and creates a registry entry.

    Requires registry:manage permission (it-admin role).
    """
    try:
        entry = await _import_service.import_skill(
            source=request.source,
            session=session,
            owner_id=user["user_id"],
        )
        await session.commit()
    except SkillImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc

    logger.info(
        "registry_skill_imported_api",
        user_id=str(user["user_id"]),
        entry_id=str(entry.id),
        source=request.source,
    )
    return ImportSkillResponse(
        id=entry.id,
        name=entry.name,
        status=entry.status,
        security_score=entry.config.get("security_score") if entry.config else None,
    )


# ── Get one entry ─────────────────────────────────────────────────────────


@router.get("/{entry_id}")
async def get_entry(
    entry_id: UUID,
    user: UserContext = Depends(_require_read),
    session: AsyncSession = Depends(get_db),
) -> RegistryEntryResponse:
    """Get a single registry entry by id."""
    entry = await _registry_service.get_entry(session, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Registry entry not found")
    return RegistryEntryResponse.model_validate(entry)


# ── Create entry ──────────────────────────────────────────────────────────


@router.post("", status_code=201)
async def create_entry(
    body: RegistryEntryCreate,
    user: UserContext = Depends(_require_manage),
    session: AsyncSession = Depends(get_db),
) -> RegistryEntryResponse:
    """Create a new registry entry. Requires registry:manage permission."""
    try:
        entry = await _registry_service.create_entry(
            session,
            data=body,
            owner_id=user["user_id"],
        )
        await session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    logger.info(
        "registry_entry_created_api",
        user_id=str(user["user_id"]),
        entry_id=str(entry.id),
        type=entry.type,
        name=entry.name,
    )
    return RegistryEntryResponse.model_validate(entry)


# ── Update entry ──────────────────────────────────────────────────────────


@router.put("/{entry_id}")
async def update_entry(
    entry_id: UUID,
    body: RegistryEntryUpdate,
    user: UserContext = Depends(_require_manage),
    session: AsyncSession = Depends(get_db),
) -> RegistryEntryResponse:
    """Update an existing registry entry. Requires registry:manage permission."""
    # Gate: prevent activation when skill has unresolved tool_gaps
    if body.status == "active":
        existing = await _registry_service.get_entry(session, entry_id)
        if existing and (existing.config or {}).get("tool_gaps"):
            raise HTTPException(
                status_code=422,
                detail="Skill has unresolved tool gaps. Create missing tools first.",
            )

    try:
        entry = await _registry_service.update_entry(session, entry_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if entry is None:
        raise HTTPException(status_code=404, detail="Registry entry not found")

    await session.commit()

    logger.info(
        "registry_entry_updated_api",
        user_id=str(user["user_id"]),
        entry_id=str(entry_id),
    )
    return RegistryEntryResponse.model_validate(entry)


# ── Delete (soft) entry ───────────────────────────────────────────────────


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: UUID,
    user: UserContext = Depends(_require_manage),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a registry entry (sets deleted_at). Requires registry:manage permission."""
    deleted = await _registry_service.delete_entry(session, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Registry entry not found")

    await session.commit()

    logger.info(
        "registry_entry_deleted_api",
        user_id=str(user["user_id"]),
        entry_id=str(entry_id),
    )
