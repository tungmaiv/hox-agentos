"""
Local authentication endpoint.

POST /api/auth/local/token — issue a HS256 JWT for a local user.

No auth required — this IS the authentication endpoint.
The login flow:
  1. Look up user by username (case-sensitive — consistent with most identity systems)
  2. Verify bcrypt password
  3. Check is_active
  4. Resolve roles (union of group roles + direct user roles)
  5. Issue HS256 JWT with claims mirroring Keycloak structure

Security notes:
  - Invalid username and wrong password return the same 401 to prevent username enumeration.
  - Deactivated users are rejected after password verification (so they get the same 401,
    not a special "account disabled" message that reveals account existence).
  - No rate limiting for MVP (on-premise ~100 users, low brute-force risk per CONTEXT.md).
"""
import bcrypt as _bcrypt
import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.local_auth import LocalUser
from core.schemas.local_auth import LocalLoginRequest, LocalLoginResponse
from security.local_auth import create_local_token, resolve_user_roles, verify_password

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/auth/local", tags=["local-auth"])

# Pre-computed hash of a random string — provides real bcrypt timing for username-not-found path.
# Generated once at module load; cost factor 12 matches hash_password() in security/local_auth.py.
_DUMMY_HASH: str = _bcrypt.hashpw(b"dummy-timing-placeholder", _bcrypt.gensalt(rounds=12)).decode("utf-8")


@router.post("/token")
async def local_login(
    body: LocalLoginRequest,
    session: AsyncSession = Depends(get_db),
) -> LocalLoginResponse:
    """
    Authenticate a local user and issue a HS256 JWT.

    Returns the same 401 for invalid username, wrong password, or deactivated
    account to prevent username enumeration.

    Returns:
        LocalLoginResponse with access_token and token_type="bearer".

    Raises:
        HTTPException(401) — invalid credentials or deactivated account.
        HTTPException(500) — LOCAL_JWT_SECRET is not configured.
    """
    # Look up user by username
    result = await session.execute(
        select(LocalUser).where(LocalUser.username == body.username)
    )
    user = result.scalar_one_or_none()

    # Always run bcrypt verify for constant-time behavior (prevents username enumeration).
    stored_hash = user.password_hash if user else _DUMMY_HASH
    password_ok = verify_password(body.password, stored_hash)

    if not password_ok or user is None:
        logger.info("local_login_failed", username=body.username, reason="invalid_credentials")
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not user.is_active:
        logger.info("local_login_failed", username=body.username, reason="invalid_credentials")
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Resolve effective roles: union(group roles, direct user roles)
    roles = await resolve_user_roles(session, user.id)

    token = create_local_token(
        user_id=user.id,
        email=user.email,
        username=user.username,
        roles=roles,
    )

    logger.info("local_login_success", user_id=str(user.id), username=user.username)
    return LocalLoginResponse(access_token=token)
