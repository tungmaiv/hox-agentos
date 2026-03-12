"""
Unified Registry API — /api/registry/* CRUD endpoints.

GET    /api/registry/          — list entries; query params: type, status (registry:read)
GET    /api/registry/{id}      — get one entry (registry:read)
POST   /api/registry/          — create entry (registry:manage)
PUT    /api/registry/{id}      — update entry (registry:manage)
DELETE /api/registry/{id}      — soft delete (registry:manage)

Security: Gates 1+2.
  - GET endpoints: require any authenticated user (registry:read via ROLE_PERMISSIONS)
  - Mutating endpoints: require registry:manage (it-admin role)
"""
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.user import UserContext
from core.schemas.registry import (
    RegistryEntryCreate,
    RegistryEntryResponse,
    RegistryEntryUpdate,
)
from registry.service import UnifiedRegistryService
from security.deps import get_current_user
from security.rbac import has_permission

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
