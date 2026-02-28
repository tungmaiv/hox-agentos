"""
Admin permission management API — role-level, artifact-level, per-user overrides.

Role permissions:
  GET  /api/admin/permissions/roles             — all role-permission mappings
  PUT  /api/admin/permissions/roles/{role}      — replace all permissions for a role

Artifact permissions (staged model):
  GET  /api/admin/permissions/artifacts/{artifact_type}/{artifact_id}
  PUT  /api/admin/permissions/artifacts/{artifact_type}/{artifact_id}

Per-user overrides:
  GET  /api/admin/permissions/users/{artifact_type}/{artifact_id}
  PUT  /api/admin/permissions/users/{artifact_type}/{artifact_id}

Apply:
  POST /api/admin/permissions/apply — move pending -> active, invalidate cache

Security: requires `registry:manage` permission (Gate 2 RBAC).
"""
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.artifact_permission import ArtifactPermission
from core.models.role_permission import RolePermission
from core.models.user import UserContext
from core.models.user_artifact_permission import UserArtifactPermission
from core.schemas.registry import (
    ArtifactPermissionResponse,
    ArtifactPermissionSet,
    PermissionApplyRequest,
    RolePermissionResponse,
    RolePermissionSet,
    UserArtifactPermissionResponse,
    UserArtifactPermissionSet,
)
from security.deps import get_current_user
from security.rbac import has_permission, invalidate_permission_cache

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin/permissions", tags=["admin-permissions"])


async def _require_registry_manager(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2 dependency: require registry:manage permission."""
    if not await has_permission(user, "registry:manage", session):
        raise HTTPException(status_code=403, detail="Registry manage permission required")
    return user


# ---------------------------------------------------------------------------
# Role permissions
# ---------------------------------------------------------------------------


@router.get("/roles")
async def list_role_permissions(
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> dict[str, list[str]]:
    """
    Return all role-permission mappings grouped by role.

    Returns a dict like: {"it-admin": ["tool:admin", "registry:manage", ...], ...}
    """
    result = await session.execute(select(RolePermission))
    rows = result.scalars().all()

    grouped: dict[str, list[str]] = {}
    for row in rows:
        grouped.setdefault(row.role, []).append(row.permission)

    logger.info(
        "admin_role_permissions_listed",
        user_id=str(user["user_id"]),
        roles=len(grouped),
    )
    return grouped


@router.put("/roles/{role}")
async def set_role_permissions(
    role: str,
    body: RolePermissionSet,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> RolePermissionResponse:
    """
    Replace all permissions for a role.

    Deletes existing rows for the role, inserts new rows from the request body.
    Invalidates permission cache immediately.
    """
    # Delete existing permissions for this role
    await session.execute(
        delete(RolePermission).where(RolePermission.role == role)
    )

    # Insert new permissions
    for perm in body.permissions:
        session.add(RolePermission(role=role, permission=perm))

    await session.commit()

    # Invalidate cache so changes take effect immediately
    invalidate_permission_cache()

    logger.info(
        "admin_role_permissions_set",
        role=role,
        count=len(body.permissions),
        user_id=str(user["user_id"]),
    )
    return RolePermissionResponse(role=role, permissions=body.permissions)


# ---------------------------------------------------------------------------
# Artifact permissions (staged model)
# ---------------------------------------------------------------------------


@router.get("/artifacts/{artifact_type}/{artifact_id}")
async def get_artifact_permissions(
    artifact_type: str,
    artifact_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> list[ArtifactPermissionResponse]:
    """
    Return all permission overrides for an artifact (both active and pending).
    """
    result = await session.execute(
        select(ArtifactPermission).where(
            ArtifactPermission.artifact_type == artifact_type,
            ArtifactPermission.artifact_id == artifact_id,
        )
    )
    rows = result.scalars().all()
    return [ArtifactPermissionResponse.model_validate(r) for r in rows]


@router.put("/artifacts/{artifact_type}/{artifact_id}")
async def set_artifact_permissions(
    artifact_type: str,
    artifact_id: UUID,
    body: ArtifactPermissionSet,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> list[ArtifactPermissionResponse]:
    """
    Set per-role permissions for an artifact (staged as pending).

    Deletes existing rows for this artifact, inserts new rows with status='pending'.
    Does NOT invalidate permission cache — call POST /apply to make them active.
    """
    # Delete existing permissions for this artifact
    await session.execute(
        delete(ArtifactPermission).where(
            ArtifactPermission.artifact_type == artifact_type,
            ArtifactPermission.artifact_id == artifact_id,
        )
    )

    # Insert new permissions with status='pending'
    new_rows: list[ArtifactPermission] = []
    for entry in body.roles:
        row = ArtifactPermission(
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            role=entry.role,
            allowed=entry.allowed,
            status="pending",
        )
        session.add(row)
        new_rows.append(row)

    await session.commit()

    # Refresh to get generated IDs
    for row in new_rows:
        await session.refresh(row)

    logger.info(
        "admin_artifact_permissions_set",
        artifact_type=artifact_type,
        artifact_id=str(artifact_id),
        count=len(new_rows),
        user_id=str(user["user_id"]),
    )
    return [ArtifactPermissionResponse.model_validate(r) for r in new_rows]


# ---------------------------------------------------------------------------
# Per-user overrides
# ---------------------------------------------------------------------------


@router.get("/users/{artifact_type}/{artifact_id}")
async def get_user_permissions(
    artifact_type: str,
    artifact_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> list[UserArtifactPermissionResponse]:
    """Return user-level permission overrides for an artifact."""
    result = await session.execute(
        select(UserArtifactPermission).where(
            UserArtifactPermission.artifact_type == artifact_type,
            UserArtifactPermission.artifact_id == artifact_id,
        )
    )
    rows = result.scalars().all()
    return [UserArtifactPermissionResponse.model_validate(r) for r in rows]


@router.put("/users/{artifact_type}/{artifact_id}")
async def set_user_permissions(
    artifact_type: str,
    artifact_id: UUID,
    body: list[UserArtifactPermissionSet],
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> list[UserArtifactPermissionResponse]:
    """
    Set per-user permissions for an artifact (staged as pending).

    Deletes existing user-level rows for this artifact, inserts new with status='pending'.
    Applied via POST /apply (same as artifact permissions).
    """
    # Delete existing user-level permissions for this artifact
    await session.execute(
        delete(UserArtifactPermission).where(
            UserArtifactPermission.artifact_type == artifact_type,
            UserArtifactPermission.artifact_id == artifact_id,
        )
    )

    # Insert new user-level permissions with status='pending'
    new_rows: list[UserArtifactPermission] = []
    for entry in body:
        row = UserArtifactPermission(
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            user_id=entry.user_id,
            allowed=entry.allowed,
            status="pending",
        )
        session.add(row)
        new_rows.append(row)

    await session.commit()

    for row in new_rows:
        await session.refresh(row)

    logger.info(
        "admin_user_permissions_set",
        artifact_type=artifact_type,
        artifact_id=str(artifact_id),
        count=len(new_rows),
        user_id=str(user["user_id"]),
    )
    return [UserArtifactPermissionResponse.model_validate(r) for r in new_rows]


# ---------------------------------------------------------------------------
# Apply pending permissions
# ---------------------------------------------------------------------------


@router.post("/apply")
async def apply_permissions(
    body: PermissionApplyRequest,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Apply pending permissions by their IDs — sets status from 'pending' to 'active'.

    Handles both artifact_permissions and user_artifact_permissions tables.
    Invalidates permission cache after applying.
    """
    applied_count = 0

    # Apply artifact permissions
    result_artifact = await session.execute(
        update(ArtifactPermission)
        .where(
            ArtifactPermission.id.in_(body.ids),
            ArtifactPermission.status == "pending",
        )
        .values(status="active")
    )
    applied_count += result_artifact.rowcount

    # Apply user artifact permissions
    result_user = await session.execute(
        update(UserArtifactPermission)
        .where(
            UserArtifactPermission.id.in_(body.ids),
            UserArtifactPermission.status == "pending",
        )
        .values(status="active")
    )
    applied_count += result_user.rowcount

    await session.commit()

    # Invalidate cache only on apply — not on staged writes
    invalidate_permission_cache()

    logger.info(
        "admin_permissions_applied",
        applied=applied_count,
        user_id=str(user["user_id"]),
    )
    return {"applied": applied_count}
