"""
JWT validation — Gate 1 of the 3-gate security system.

Responsibilities:
  1. Fetch Keycloak's JWKS endpoint (with in-process TTL cache).
  2. Decode and validate an RS256 JWT (signature, expiry, issuer, audience).
  3. Extract claims into a UserContext for use by the rest of the system.

Public API:
  validate_token(token: str) -> UserContext   — raises HTTPException on any error
  JWKSCache (module-level state)              — exposed for testing/reset

Security invariants (never break):
  - Credentials / raw tokens are never logged.
  - JWKS is cached in-process for JWKS_TTL_SECONDS (300s) to avoid a Keycloak
    round-trip on every request.
  - ExpiredSignatureError is handled separately so the error message is specific.
"""
import time
from typing import Any
from uuid import UUID

import httpx
import structlog
from fastapi import HTTPException
from jose import ExpiredSignatureError, JWTError
from jose import jwt as jose_jwt

from core.config import settings
from core.models.user import UserContext

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# In-process JWKS cache (module-level state)
# ---------------------------------------------------------------------------

JWKS_TTL_SECONDS: float = 300.0  # 5 minutes

_JWKS_CACHE: dict[str, Any] = {}  # populated with JWKS dict on first fetch
_jwks_fetched_at: float = 0.0  # monotonic clock timestamp of last fetch


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _fetch_jwks_from_remote() -> dict[str, Any]:
    """
    Make the actual HTTP request to Keycloak's JWKS endpoint.

    Separated from _get_jwks() so that tests can mock this function alone
    while the in-process cache logic continues to run and be tested.

    Raises:
        HTTPException(503) if the Keycloak endpoint is unreachable.
    """
    # Use the project CA cert for self-signed Keycloak TLS (local dev).
    # Falls back to system default trust store when keycloak_ca_cert is not set.
    ssl_verify: str | bool = settings.keycloak_ca_cert or True
    try:
        async with httpx.AsyncClient(verify=ssl_verify) as client:
            resp = await client.get(settings.keycloak_jwks_url, timeout=10.0)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        logger.error("jwks_fetch_failed", url=settings.keycloak_jwks_url, error=str(exc))
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable — JWKS fetch failed",
        ) from exc


async def _get_jwks() -> dict[str, Any]:
    """
    Return the Keycloak JWKS, using the in-process cache when still valid.

    Cache TTL: JWKS_TTL_SECONDS (default 300 s).  On first call or after TTL
    expiry, _fetch_jwks_from_remote() is called; subsequent calls within the
    TTL window return the cached dict without any I/O.
    """
    global _jwks_fetched_at, _JWKS_CACHE

    now = time.monotonic()
    if _JWKS_CACHE and (now - _jwks_fetched_at) < JWKS_TTL_SECONDS:
        return _JWKS_CACHE

    jwks = await _fetch_jwks_from_remote()
    _JWKS_CACHE = jwks
    _jwks_fetched_at = now
    return _JWKS_CACHE


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def validate_token(token: str) -> UserContext:
    """
    Validate an RS256 Bearer token against Keycloak's JWKS.

    Checks:
      - Signature (RS256, against JWKS public key)
      - Expiry (exp claim)
      - Issuer (iss must equal settings.keycloak_issuer)
      - Audience: skipped — blitz-portal tokens carry no aud claim (issuer is sufficient)

    Returns:
        UserContext populated from JWT claims.

    Raises:
        HTTPException(401, "Token has expired")   — expired token
        HTTPException(401, "Invalid token")       — any other JWT error
        HTTPException(503, ...)                   — JWKS endpoint unreachable
    """
    jwks = await _get_jwks()
    try:
        payload: dict[str, Any] = jose_jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            # Skip audience validation — the blitz-portal access token carries no
            # aud claim (Keycloak default for this realm config).  Signature (RS256)
            # and issuer are still validated so tokens from other issuers are rejected.
            options={"verify_aud": False},
            issuer=settings.keycloak_issuer,
        )
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError as exc:
        # Never log the raw token — only the error class name
        logger.warning("jwt_validation_failed", error_type=type(exc).__name__, error=str(exc))
        raise HTTPException(status_code=401, detail="Invalid token")

    # Keycloak realm has a custom "roles" scope mapper that emits a flat
    # realm_roles claim instead of the standard realm_access.roles nesting.
    # Try the flat key first; fall back to standard path for forward-compat.
    roles: list[str] = payload.get("realm_roles") or payload.get("realm_access", {}).get("roles", [])
    return UserContext(
        user_id=UUID(payload["sub"]),
        email=payload.get("email", ""),
        username=payload.get("preferred_username", ""),
        roles=roles,
        groups=payload.get("groups", []),
    )
