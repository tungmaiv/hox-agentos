"""
RBAC Gate 2 — Role-to-permission mapping and permission checking.

Implements Gate 2 of the 3-gate security system:
  Gate 1: JWT validation (security/jwt.py)
  Gate 2: RBAC permission check (this module) ← you are here
  Gate 3: Tool ACL check (security/acl.py)

ROLE_PERMISSIONS is the single source of truth for what each role can do.
This mapping is locked per CONTEXT.md decisions — do not change without
updating the architecture decision record.

Usage:
    from security.rbac import has_permission
    if not has_permission(user_context, "tool:email"):
        raise HTTPException(
            status_code=403,
            detail={
                "detail": "Permission denied",
                "permission_required": "tool:email",
                "user_roles": user_context["roles"],
                "hint": "Contact IT admin",
            },
        )
"""
from core.models.user import UserContext


# ---------------------------------------------------------------------------
# Role-to-permission mapping (locked per CONTEXT.md Phase 1 design decisions)
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "employee": {
        "chat",
        "tool:email",
        "tool:calendar",
        "tool:project",
    },
    "manager": {
        # All employee permissions
        "chat",
        "tool:email",
        "tool:calendar",
        "tool:project",
        # Manager additions
        "tool:reports",
        "workflow:create",
    },
    "team-lead": {
        # All manager permissions
        "chat",
        "tool:email",
        "tool:calendar",
        "tool:project",
        "tool:reports",
        "workflow:create",
        # Team-lead addition
        "workflow:approve",
    },
    "it-admin": {
        # All permissions — IT admin has full access
        "chat",
        "tool:email",
        "tool:calendar",
        "tool:project",
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


def get_permissions(roles: list[str]) -> set[str]:
    """
    Return the union of all permissions for a list of roles.

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


def has_permission(user_context: UserContext, permission: str) -> bool:
    """
    Gate 2: Check if the authenticated user has the required permission.

    Returns True if ANY of the user's roles grants the requested permission.
    Returns False if no role grants it (deny by default for unknown roles).

    Args:
        user_context: Authenticated user from Gate 1 (JWT validation).
                      user_context["roles"] comes from JWT realm_access.roles.
        permission: The specific permission string to check (e.g. "tool:email").

    Returns:
        True if the user has the permission, False otherwise.

    Example 403 response:
        raise HTTPException(
            status_code=403,
            detail={
                "detail": "Permission denied",
                "permission_required": permission,
                "user_roles": user_context["roles"],
                "hint": "Contact IT admin",
            },
        )
    """
    return permission in get_permissions(user_context["roles"])
