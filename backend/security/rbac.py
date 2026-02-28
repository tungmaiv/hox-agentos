"""
RBAC Gate 2 — Role-to-permission mapping and permission checking.

Implements Gate 2 of the 3-gate security system:
  Gate 1: JWT validation (security/jwt.py)
  Gate 2: RBAC permission check (this module) <- you are here
  Gate 3: Tool ACL check (security/acl.py)

ROLE_PERMISSIONS dict is kept as a fallback for backward compatibility:
- Used when no DB session is provided (session=None).
- Used when the DB returns 0 rows (safety net during migration).

When a session IS provided, permissions are loaded from the role_permissions
table with an in-process cache (60s TTL). Admin changes take effect within
60 seconds without a backend restart, or immediately via invalidate_permission_cache().

Usage (async, DB-backed):
    from security.rbac import has_permission
    if not await has_permission(user_context, "tool:email", session):
        raise HTTPException(status_code=403, ...)

Usage (sync fallback, no DB):
    from security.rbac import has_permission
    result = await has_permission(user_context, "tool:email")
    # Falls back to ROLE_PERMISSIONS dict when session is None.
"""
from __future__ import annotations

import time
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.user import UserContext

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Role-to-permission mapping (fallback — used when DB is empty or no session)
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "employee": {
        "chat",
        "tool:email",
        "tool:calendar",
        "tool:project",
        "crm:read",
    },
    "manager": {
        # All employee permissions
        "chat",
        "tool:email",
        "tool:calendar",
        "tool:project",
        "crm:read",
        # Manager additions
        "crm:write",
        "tool:reports",
        "workflow:create",
    },
    "team-lead": {
        # All manager permissions
        "chat",
        "tool:email",
        "tool:calendar",
        "tool:project",
        "crm:read",
        "crm:write",
        "tool:reports",
        "workflow:create",
        # Team-lead addition
        "workflow:approve",
    },
    "it-admin": {
        # All permissions -- IT admin has full access
        "chat",
        "tool:email",
        "tool:calendar",
        "tool:project",
        "crm:read",
        "crm:write",
        "tool:reports",
        "workflow:create",
        "workflow:approve",
        # Admin-only
        "tool:admin",
        "sandbox:execute",
        "registry:manage",
    },
    "executive": {
        # Read-only access: chat + reports only
        "chat",
        "tool:reports",
    },
}


# ---------------------------------------------------------------------------
# In-process permission cache (refreshed from DB every _CACHE_TTL seconds)
# ---------------------------------------------------------------------------

_permission_cache: dict[str, set[str]] = {}
_cache_timestamp: float = 0.0
_CACHE_TTL: float = 60.0


def invalidate_permission_cache() -> None:
    """
    Reset the permission cache so the next has_permission() call refreshes from DB.

    Call this after admin writes to role_permissions to make changes take effect
    immediately (without waiting for the 60s TTL to expire).
    """
    global _cache_timestamp
    _cache_timestamp = 0.0


async def _refresh_cache(session: AsyncSession) -> dict[str, set[str]]:
    """
    Load all role_permissions from DB and build role -> set[permission] mapping.

    If DB returns 0 rows, falls back to ROLE_PERMISSIONS dict (safety net).
    """
    global _permission_cache, _cache_timestamp

    from core.models.role_permission import RolePermission

    result = await session.execute(select(RolePermission))
    rows = result.scalars().all()

    if not rows:
        # Safety net: DB is empty (e.g. migration not yet applied).
        # Fall back to hardcoded dict.
        _permission_cache = {
            role: set(perms) for role, perms in ROLE_PERMISSIONS.items()
        }
        _cache_timestamp = time.monotonic()
        logger.debug("rbac_cache_fallback", reason="no rows in role_permissions")
        return _permission_cache

    cache: dict[str, set[str]] = {}
    for row in rows:
        cache.setdefault(row.role, set()).add(row.permission)

    _permission_cache = cache
    _cache_timestamp = time.monotonic()
    logger.debug("rbac_cache_refreshed", roles=len(cache))
    return _permission_cache


def get_permissions(roles: list[str]) -> set[str]:
    """
    Return the union of all permissions for a list of roles.

    Uses the hardcoded ROLE_PERMISSIONS dict (sync, no DB).
    Unknown roles contribute no permissions (deny by default).

    Args:
        roles: List of Keycloak realm role names.

    Returns:
        Set of permission strings for all provided roles combined.
    """
    permissions: set[str] = set()
    for role in roles:
        permissions |= ROLE_PERMISSIONS.get(role, set())
    return permissions


async def has_permission(
    user_context: UserContext,
    permission: str,
    session: AsyncSession | None = None,
) -> bool:
    """
    Gate 2: Check if the authenticated user has the required permission.

    When session is provided, reads from the role_permissions table with
    in-process caching (60s TTL). When session is None, falls back to the
    hardcoded ROLE_PERMISSIONS dict for backward compatibility.

    Returns True if ANY of the user's roles grants the requested permission.
    Returns False if no role grants it (deny by default for unknown roles).

    Args:
        user_context: Authenticated user from Gate 1 (JWT validation).
        permission: The specific permission string to check (e.g. "tool:email").
        session: Optional async DB session. When provided, uses DB-backed
                 permissions. When None, uses hardcoded dict.

    Returns:
        True if the user has the permission, False otherwise.
    """
    if session is None:
        # Backward compat: no DB session, use hardcoded dict
        return permission in get_permissions(user_context["roles"])

    # DB-backed path with caching
    global _permission_cache, _cache_timestamp
    now = time.monotonic()
    if not _permission_cache or (now - _cache_timestamp) > _CACHE_TTL:
        await _refresh_cache(session)

    roles = user_context["roles"]
    for role in roles:
        role_perms = _permission_cache.get(role, set())
        if permission in role_perms:
            return True

    return False


async def check_artifact_permission(
    user: UserContext,
    artifact_type: str,
    artifact_id: UUID,
    session: AsyncSession,
) -> bool:
    """
    Gate 2.5: Check per-artifact permission for a user.

    Implements the artifact permission model:
    1. Check user_artifact_permissions first (per-user overrides take precedence).
       - If a user-level override with status='active' exists, return its allowed value.
    2. Check artifact_permissions (per-role).
       - Only rows with status='active' are considered (staged 'pending' rows are ignored).
       - No rows = default ALLOW (same pattern as existing tool_acl).
       - Any row with allowed=False for any of user's roles = DENY.
       - Any row with allowed=True and no denials = ALLOW.

    Args:
        user: Authenticated UserContext from Gate 1.
        artifact_type: One of "agent", "tool", "skill", "mcp_server".
        artifact_id: UUID of the artifact being accessed.
        session: Async SQLAlchemy session.

    Returns:
        True if access is allowed, False if denied.
    """
    from core.models.artifact_permission import ArtifactPermission
    from core.models.user_artifact_permission import UserArtifactPermission

    user_id = user["user_id"]
    roles = user["roles"]

    # 1. Per-user override takes precedence
    user_result = await session.execute(
        select(UserArtifactPermission).where(
            UserArtifactPermission.artifact_type == artifact_type,
            UserArtifactPermission.artifact_id == artifact_id,
            UserArtifactPermission.user_id == user_id,
            UserArtifactPermission.status == "active",
        )
    )
    user_override = user_result.scalar_one_or_none()
    if user_override is not None:
        return user_override.allowed

    # 2. Per-role permissions (only active status)
    if not roles:
        return True  # No roles, no role-level restrictions; default allow

    role_result = await session.execute(
        select(ArtifactPermission).where(
            ArtifactPermission.artifact_type == artifact_type,
            ArtifactPermission.artifact_id == artifact_id,
            ArtifactPermission.role.in_(roles),
            ArtifactPermission.status == "active",
        )
    )
    role_rows = role_result.scalars().all()

    if not role_rows:
        return True  # No explicit permissions = default ALLOW

    # Any denial for any of user's roles = DENY
    for row in role_rows:
        if not row.allowed:
            return False

    # All rows allow
    return True
