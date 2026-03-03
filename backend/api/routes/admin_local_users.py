"""
Admin CRUD API for local users and groups.

All endpoints require `registry:manage` RBAC permission (same gate as Phase 12 admin routes).

User endpoints:
  POST   /api/admin/local/users              — create user
  GET    /api/admin/local/users              — list users (with resolved roles, group info)
  GET    /api/admin/local/users/{id}         — get user detail
  PUT    /api/admin/local/users/{id}         — update user (password optional)
  DELETE /api/admin/local/users/{id}         — delete user (CASCADE)
  POST   /api/admin/local/users/{id}/groups  — assign groups (GroupAssignment body)
  DELETE /api/admin/local/users/{id}/groups/{group_id} — remove from group
  POST   /api/admin/local/users/{id}/roles   — add direct roles (RoleAssignment body)
  DELETE /api/admin/local/users/{id}/roles/{role}      — remove direct role

Group endpoints:
  POST   /api/admin/local/groups             — create group
  GET    /api/admin/local/groups             — list groups
  PUT    /api/admin/local/groups/{id}        — update group (name, desc, roles — roles replace all)
  DELETE /api/admin/local/groups/{id}        — delete group (CASCADE)

Security: registry:manage RBAC permission required (same as other admin routes).
"""
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.local_auth import (
    LocalGroup,
    LocalGroupRole,
    LocalUser,
    LocalUserGroup,
    LocalUserRole,
)
from core.models.user import UserContext
from core.schemas.local_auth import (
    GroupAssignment,
    GroupBrief,
    LocalGroupCreate,
    LocalGroupResponse,
    LocalGroupUpdate,
    LocalUserCreate,
    LocalUserResponse,
    LocalUserUpdate,
    RoleAssignment,
)
from security.deps import get_current_user
from security.local_auth import hash_password, resolve_user_roles
from security.rbac import has_permission

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin/local", tags=["admin-local-auth"])


# ---------------------------------------------------------------------------
# Shared RBAC gate dependency
# ---------------------------------------------------------------------------


async def _require_registry_manager(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2 dependency: require registry:manage permission."""
    if not await has_permission(user, "registry:manage", session):
        raise HTTPException(status_code=403, detail="Registry manage permission required")
    return user


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _build_user_response(
    user: LocalUser,
    session: AsyncSession,
) -> LocalUserResponse:
    """
    Build a LocalUserResponse from a LocalUser ORM object.

    Loads group memberships and resolves effective roles.
    """
    # Load group memberships
    group_result = await session.execute(
        select(LocalGroup)
        .join(LocalUserGroup, LocalUserGroup.group_id == LocalGroup.id)
        .where(LocalUserGroup.user_id == user.id)
    )
    groups = group_result.scalars().all()
    group_briefs = [GroupBrief(id=g.id, name=g.name) for g in groups]

    # Resolve effective roles
    roles = await resolve_user_roles(session, user.id)

    return LocalUserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        groups=group_briefs,
        roles=roles,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


async def _build_group_response(
    group: LocalGroup,
    session: AsyncSession,
) -> LocalGroupResponse:
    """Build a LocalGroupResponse from a LocalGroup ORM object."""
    # Load roles
    role_result = await session.execute(
        select(LocalGroupRole.role).where(LocalGroupRole.group_id == group.id)
    )
    roles = sorted([row[0] for row in role_result])

    # Count members
    count_result = await session.execute(
        select(func.count()).where(LocalUserGroup.group_id == group.id)
    )
    member_count = count_result.scalar_one()

    return LocalGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        roles=roles,
        member_count=member_count,
        created_at=group.created_at,
    )


# ---------------------------------------------------------------------------
# User endpoints
# ---------------------------------------------------------------------------


@router.post("/users", status_code=201)
async def create_user(
    body: LocalUserCreate,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> LocalUserResponse:
    """Create a new local user. Admin sets the initial password."""
    # Check for duplicate username or email
    existing = await session.execute(
        select(LocalUser).where(
            (LocalUser.username == body.username) | (LocalUser.email == str(body.email))
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username or email already in use")

    # Hash the password
    password_hash = hash_password(body.password)

    new_user = LocalUser(
        username=body.username,
        email=str(body.email),
        password_hash=password_hash,
        is_active=True,
    )
    session.add(new_user)

    try:
        await session.flush()  # get new_user.id before inserting group/role associations

        # Assign groups
        for gid in body.group_ids:
            group_exists = await session.execute(
                select(LocalGroup.id).where(LocalGroup.id == gid)
            )
            if not group_exists.scalar_one_or_none():
                await session.rollback()
                raise HTTPException(status_code=404, detail=f"Group {gid} not found")
            session.add(LocalUserGroup(user_id=new_user.id, group_id=gid))

        # Assign direct roles
        for role in body.role_names:
            session.add(LocalUserRole(user_id=new_user.id, role=role))

        await session.commit()
        await session.refresh(new_user)
    except HTTPException:
        raise
    except Exception as exc:
        await session.rollback()
        logger.error("create_user_failed", error=str(exc), username=body.username)
        raise HTTPException(status_code=500, detail="Failed to create user")

    logger.info("admin_local_user_created", user_id=str(new_user.id), username=new_user.username, by=str(user["user_id"]))
    return await _build_user_response(new_user, session)


@router.get("/users")
async def list_users(
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> list[LocalUserResponse]:
    """List all local users with resolved roles and group info."""
    result = await session.execute(select(LocalUser).order_by(LocalUser.username))
    users = result.scalars().all()
    return [await _build_user_response(u, session) for u in users]


@router.get("/users/{user_id}")
async def get_user(
    user_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> LocalUserResponse:
    """Get a local user by ID."""
    result = await session.execute(select(LocalUser).where(LocalUser.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    return await _build_user_response(target, session)


@router.put("/users/{user_id}")
async def update_user(
    user_id: UUID,
    body: LocalUserUpdate,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> LocalUserResponse:
    """Update a local user. Password change is optional."""
    result = await session.execute(select(LocalUser).where(LocalUser.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if body.username is not None:
        # Check for duplicate username
        dup = await session.execute(
            select(LocalUser.id).where(
                LocalUser.username == body.username, LocalUser.id != user_id
            )
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Username already in use")
        target.username = body.username

    if body.email is not None:
        # Check for duplicate email
        dup = await session.execute(
            select(LocalUser.id).where(
                LocalUser.email == str(body.email), LocalUser.id != user_id
            )
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email already in use")
        target.email = str(body.email)

    if body.password is not None:
        target.password_hash = hash_password(body.password)

    if body.is_active is not None:
        target.is_active = body.is_active

    try:
        await session.commit()
        await session.refresh(target)
    except Exception as exc:
        await session.rollback()
        logger.error("update_user_failed", error=str(exc), user_id=str(user_id))
        raise HTTPException(status_code=500, detail="Failed to update user")

    logger.info("admin_local_user_updated", user_id=str(user_id), by=str(user["user_id"]))
    return await _build_user_response(target, session)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a local user. CASCADE removes group memberships and direct roles."""
    result = await session.execute(select(LocalUser).where(LocalUser.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        await session.delete(target)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.error("delete_user_failed", error=str(exc), user_id=str(user_id))
        raise HTTPException(status_code=500, detail="Failed to delete user")

    logger.info("admin_local_user_deleted", user_id=str(user_id), by=str(user["user_id"]))


@router.post("/users/{user_id}/groups", status_code=204)
async def assign_user_groups(
    user_id: UUID,
    body: GroupAssignment,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Assign one or more groups to a user. Existing memberships are preserved."""
    result = await session.execute(select(LocalUser.id).where(LocalUser.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    try:
        for gid in body.group_ids:
            grp_exists = await session.execute(
                select(LocalGroup.id).where(LocalGroup.id == gid)
            )
            if not grp_exists.scalar_one_or_none():
                raise HTTPException(status_code=404, detail=f"Group {gid} not found")
            # Upsert — ignore if already a member
            existing = await session.execute(
                select(LocalUserGroup).where(
                    LocalUserGroup.user_id == user_id, LocalUserGroup.group_id == gid
                )
            )
            if not existing.scalar_one_or_none():
                session.add(LocalUserGroup(user_id=user_id, group_id=gid))
        await session.commit()
    except HTTPException:
        raise
    except Exception as exc:
        await session.rollback()
        logger.error("assign_groups_failed", error=str(exc), user_id=str(user_id))
        raise HTTPException(status_code=500, detail="Failed to assign groups")


@router.delete("/users/{user_id}/groups/{group_id}", status_code=204)
async def remove_user_from_group(
    user_id: UUID,
    group_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Remove a user from a group."""
    result = await session.execute(
        select(LocalUserGroup).where(
            LocalUserGroup.user_id == user_id, LocalUserGroup.group_id == group_id
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Group membership not found")

    try:
        await session.delete(membership)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to remove group membership") from exc


@router.post("/users/{user_id}/roles", status_code=204)
async def add_user_roles(
    user_id: UUID,
    body: RoleAssignment,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Add direct role assignments to a user. Existing roles are preserved."""
    result = await session.execute(select(LocalUser.id).where(LocalUser.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    try:
        for role in body.roles:
            existing = await session.execute(
                select(LocalUserRole).where(
                    LocalUserRole.user_id == user_id, LocalUserRole.role == role
                )
            )
            if not existing.scalar_one_or_none():
                session.add(LocalUserRole(user_id=user_id, role=role))
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to add roles") from exc


@router.delete("/users/{user_id}/roles/{role}", status_code=204)
async def remove_user_role(
    user_id: UUID,
    role: str,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Remove a direct role from a user."""
    result = await session.execute(
        select(LocalUserRole).where(
            LocalUserRole.user_id == user_id, LocalUserRole.role == role
        )
    )
    user_role = result.scalar_one_or_none()
    if not user_role:
        raise HTTPException(status_code=404, detail="Role assignment not found")

    try:
        await session.delete(user_role)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to remove role") from exc


# ---------------------------------------------------------------------------
# Group endpoints
# ---------------------------------------------------------------------------


@router.post("/groups", status_code=201)
async def create_group(
    body: LocalGroupCreate,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> LocalGroupResponse:
    """Create a new local group with optional roles."""
    existing = await session.execute(
        select(LocalGroup).where(LocalGroup.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Group name already in use")

    new_group = LocalGroup(name=body.name, description=body.description)
    session.add(new_group)

    try:
        await session.flush()  # get new_group.id
        for role in body.roles:
            session.add(LocalGroupRole(group_id=new_group.id, role=role))
        await session.commit()
        await session.refresh(new_group)
    except HTTPException:
        raise
    except Exception as exc:
        await session.rollback()
        logger.error("create_group_failed", error=str(exc), name=body.name)
        raise HTTPException(status_code=500, detail="Failed to create group")

    logger.info("admin_local_group_created", group_id=str(new_group.id), name=new_group.name, by=str(user["user_id"]))
    return await _build_group_response(new_group, session)


@router.get("/groups")
async def list_groups(
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> list[LocalGroupResponse]:
    """List all local groups with roles and member counts."""
    result = await session.execute(select(LocalGroup).order_by(LocalGroup.name))
    groups = result.scalars().all()
    return [await _build_group_response(g, session) for g in groups]


@router.put("/groups/{group_id}")
async def update_group(
    group_id: UUID,
    body: LocalGroupUpdate,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> LocalGroupResponse:
    """Update a group. When roles is provided, it REPLACES the entire role set."""
    result = await session.execute(select(LocalGroup).where(LocalGroup.id == group_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Group not found")

    if body.name is not None:
        dup = await session.execute(
            select(LocalGroup.id).where(
                LocalGroup.name == body.name, LocalGroup.id != group_id
            )
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Group name already in use")
        target.name = body.name

    if body.description is not None:
        target.description = body.description

    try:
        if body.roles is not None:
            # Replace the entire role set
            await session.execute(
                delete(LocalGroupRole).where(LocalGroupRole.group_id == group_id)
            )
            for role in body.roles:
                session.add(LocalGroupRole(group_id=group_id, role=role))

        await session.commit()
        await session.refresh(target)
    except Exception as exc:
        await session.rollback()
        logger.error("update_group_failed", error=str(exc), group_id=str(group_id))
        raise HTTPException(status_code=500, detail="Failed to update group")

    logger.info("admin_local_group_updated", group_id=str(group_id), by=str(user["user_id"]))
    return await _build_group_response(target, session)


@router.delete("/groups/{group_id}", status_code=204)
async def delete_group(
    group_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a group. CASCADE removes role assignments and user memberships."""
    result = await session.execute(select(LocalGroup).where(LocalGroup.id == group_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Group not found")

    try:
        await session.delete(target)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.error("delete_group_failed", error=str(exc), group_id=str(group_id))
        raise HTTPException(status_code=500, detail="Failed to delete group")

    logger.info("admin_local_group_deleted", group_id=str(group_id), by=str(user["user_id"]))
