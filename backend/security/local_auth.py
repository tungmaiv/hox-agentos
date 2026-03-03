"""
Local authentication utilities — password hashing and HS256 JWT lifecycle.

This module handles the local username/password auth path, parallel to
Keycloak SSO. Local JWTs use HS256 (symmetric) signing with LOCAL_JWT_SECRET.

Public API:
  hash_password(plain)                         — bcrypt hash via passlib
  verify_password(plain, hashed)               — bcrypt verify via passlib
  create_local_token(user_id, email, username, roles) — issue HS256 JWT
  validate_local_token(token)                  — verify HS256 JWT + is_active DB check
  resolve_user_roles(session, user_id)         — union of group + direct roles

Security invariants (never break):
  - Passwords are never logged, stored in plaintext, or returned in responses.
  - LOCAL_JWT_SECRET is only used for signing — never included in token claims.
  - is_active check on every validate_local_token call ensures deactivated users
    are blocked without a token blocklist.
  - resolve_user_roles returns a sorted, deduplicated list for deterministic JWTs.
"""
import re
import time
from uuid import UUID

import bcrypt as _bcrypt
import structlog
from fastapi import HTTPException
from jose import ExpiredSignatureError, JWTError
from jose import jwt as jose_jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.models.local_auth import LocalGroupRole, LocalUser, LocalUserGroup, LocalUserRole
from core.models.user import UserContext

logger = structlog.get_logger(__name__)

_ISSUER = "blitz-local"

# Password complexity: min 8 chars, at least 1 uppercase, 1 lowercase, 1 digit.
# Sensible for ~100 internal users per design decision in CONTEXT.md.
_PASSWORD_MIN_LEN = 8
_PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$")


def _validate_password_complexity(plain: str) -> None:
    """
    Raise ValueError if the password does not meet complexity requirements.

    Requirements:
      - At least 8 characters
      - At least one uppercase letter
      - At least one lowercase letter
      - At least one digit

    Raises:
        ValueError with a human-readable message.
    """
    if len(plain) < _PASSWORD_MIN_LEN:
        raise ValueError(f"Password must be at least {_PASSWORD_MIN_LEN} characters long")
    if not _PASSWORD_RE.match(plain):
        raise ValueError(
            "Password must contain at least one uppercase letter, "
            "one lowercase letter, and one digit"
        )


def hash_password(plain: str) -> str:
    """
    Hash a plaintext password using bcrypt.

    Uses the bcrypt library directly (not passlib) for Python 3.12 + bcrypt 5.x compatibility.

    Args:
        plain: The plaintext password to hash.

    Returns:
        A bcrypt hash string suitable for storage in local_users.password_hash.

    Note:
        Does NOT validate password complexity — callers that create passwords
        (admin user create/update) should call _validate_password_complexity() first.
        validate_local_token() only calls verify_password(), not this.
    """
    return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plaintext password against a stored bcrypt hash.

    Args:
        plain:  The plaintext password from the login request.
        hashed: The bcrypt hash from local_users.password_hash.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        # Catches invalid hash format (e.g., dummy hash during timing attack prevention)
        return False


# ---------------------------------------------------------------------------
# JWT creation
# ---------------------------------------------------------------------------


def create_local_token(
    user_id: UUID,
    email: str,
    username: str,
    roles: list[str],
) -> str:
    """
    Create a signed HS256 JWT for a local user.

    Claims mirror Keycloak JWT structure exactly so RBAC and Tool ACL work
    identically for local and Keycloak-authenticated users:
      - sub:                str(user_id)
      - iss:                "blitz-local"
      - exp / iat:          Unix timestamps
      - email:              user's email
      - preferred_username: user's username
      - realm_roles:        resolved role list (same claim name as Keycloak custom mapper)

    Args:
        user_id:  LocalUser.id (UUID)
        email:    LocalUser.email
        username: LocalUser.username
        roles:    Resolved role list from resolve_user_roles()

    Returns:
        Signed HS256 JWT string.

    Raises:
        HTTPException(500) if LOCAL_JWT_SECRET is not configured.
    """
    if not settings.local_jwt_secret:
        logger.error("local_jwt_secret_not_configured")
        raise HTTPException(
            status_code=500,
            detail="Local auth is not configured — LOCAL_JWT_SECRET is missing",
        )

    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "iss": _ISSUER,
        "iat": now,
        "exp": now + settings.local_jwt_expires_hours * 3600,
        "email": email,
        "preferred_username": username,
        "realm_roles": roles,
    }
    return jose_jwt.encode(payload, settings.local_jwt_secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# JWT validation
# ---------------------------------------------------------------------------


async def validate_local_token(token: str, session: AsyncSession) -> UserContext:
    """
    Validate a local HS256 JWT and return a UserContext.

    Validation steps:
      1. Decode and verify HS256 signature using LOCAL_JWT_SECRET.
      2. Verify issuer == "blitz-local" and token is not expired.
      3. Look up LocalUser in DB to confirm is_active=True.

    Args:
        token:   The raw HS256 JWT string (no "Bearer " prefix).
        session: Async DB session for the is_active check.

    Returns:
        UserContext populated from JWT claims.

    Raises:
        HTTPException(401, "Token has expired")  — expired token
        HTTPException(401, "Invalid token")       — bad signature / wrong issuer
        HTTPException(401, "Account deactivated") — user.is_active is False
        HTTPException(500)                        — LOCAL_JWT_SECRET not configured
    """
    if not settings.local_jwt_secret:
        logger.error("local_jwt_secret_not_configured")
        raise HTTPException(
            status_code=500,
            detail="Local auth is not configured — LOCAL_JWT_SECRET is missing",
        )

    try:
        payload = jose_jwt.decode(
            token,
            settings.local_jwt_secret,
            algorithms=["HS256"],
            issuer=_ISSUER,
        )
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError as exc:
        logger.warning("local_jwt_validation_failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=401, detail="Invalid token")

    # Verify the user is still active in the DB.
    # This allows deactivation to take effect on the next request without
    # needing a token blocklist.
    user_id = UUID(payload["sub"])
    result = await session.execute(
        select(LocalUser.is_active).where(LocalUser.id == user_id)
    )
    is_active = result.scalar_one_or_none()

    if is_active is None:
        # User was deleted after token was issued
        logger.warning("local_jwt_user_not_found", user_id=str(user_id))
        raise HTTPException(status_code=401, detail="Invalid token")

    if not is_active:
        logger.info("local_jwt_account_deactivated", user_id=str(user_id))
        raise HTTPException(status_code=401, detail="Account deactivated")

    roles: list[str] = payload.get("realm_roles", [])
    return UserContext(
        user_id=user_id,
        email=payload.get("email", ""),
        username=payload.get("preferred_username", ""),
        roles=roles,
        groups=[],  # Local users don't have path-style groups like Keycloak
    )


# ---------------------------------------------------------------------------
# Role resolution
# ---------------------------------------------------------------------------


async def resolve_user_roles(session: AsyncSession, user_id: UUID) -> list[str]:
    """
    Compute the effective role list for a local user.

    Effective roles = union(group roles, direct user roles).
    This mirrors Keycloak's realm_roles claim behavior where a user's roles
    are the union of all their group roles.

    SQL approach: two separate queries joined in Python (simpler than a UNION
    query for this scale — ~100 users means negligible overhead).

    The caller is responsible for transaction management. This function runs
    queries directly on the session without starting a new transaction, so
    it works correctly whether called inside or outside a begin() block.

    Args:
        session: Async DB session (any transaction state).
        user_id: LocalUser.id to resolve roles for.

    Returns:
        Sorted, deduplicated list of role strings.
        Empty list if user has no role assignments.
    """
    roles: set[str] = set()

    # Group roles: roles inherited through group membership
    group_role_result = await session.execute(
        select(LocalGroupRole.role)
        .join(LocalUserGroup, LocalUserGroup.group_id == LocalGroupRole.group_id)
        .where(LocalUserGroup.user_id == user_id)
    )
    for row in group_role_result:
        roles.add(row[0])

    # Direct user roles: roles assigned directly to the user
    direct_role_result = await session.execute(
        select(LocalUserRole.role).where(LocalUserRole.user_id == user_id)
    )
    for row in direct_role_result:
        roles.add(row[0])

    return sorted(roles)
