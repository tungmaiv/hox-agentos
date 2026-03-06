"""
JWT validation — Gate 1 of the 3-gate security system.

Responsibilities:
  1. Peek at the `iss` claim (unverified) to dispatch to the correct validator.
  2. Keycloak path: fetch JWKS, decode RS256, verify signature/expiry/issuer.
  3. Local path: decode HS256 with LOCAL_JWT_SECRET, verify issuer + is_active.

Public API:
  validate_token(token: str) -> UserContext   — raises HTTPException on any error
  invalidate_jwks_cache()                     — force JWKS re-fetch after config change
  JWKSCache (module-level state)              — exposed for testing/reset

Security invariants (never break):
  - Credentials / raw tokens are never logged.
  - JWKS is cached in-process for JWKS_TTL_SECONDS (300s) to avoid a Keycloak
    round-trip on every request.
  - ExpiredSignatureError is handled separately so the error message is specific.
  - The issuer peek (get_unverified_claims) is intentionally unverified — the
    actual signature and claims are verified by the dispatched validator.
"""
import asyncio
import time
from typing import Any
from uuid import UUID

import httpx
import structlog
from fastapi import HTTPException
from jose import ExpiredSignatureError, JWTError
from jose import jwt as jose_jwt
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.user import UserContext
from security.keycloak_config import KeycloakConfig, get_keycloak_config

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# In-process JWKS cache (module-level state)
# ---------------------------------------------------------------------------

JWKS_TTL_SECONDS: float = 300.0  # 5 minutes

_JWKS_CACHE: dict[str, Any] = {}  # populated with JWKS dict on first fetch
_jwks_fetched_at: float = 0.0  # monotonic clock timestamp of last fetch
_jwks_refresh_lock: asyncio.Lock = asyncio.Lock()  # prevents thundering herd on concurrent expiry


# ---------------------------------------------------------------------------
# Internal helpers — Keycloak RS256 path
# ---------------------------------------------------------------------------


async def _fetch_jwks_from_remote(config: KeycloakConfig) -> dict[str, Any]:
    """
    Make the actual HTTP request to Keycloak's JWKS endpoint.

    Separated from _get_jwks() so that tests can mock this function alone
    while the in-process cache logic continues to run and be tested.

    Uses config.ca_cert_path for self-signed TLS (local dev).

    Raises:
        HTTPException(503) if the Keycloak endpoint is unreachable.
    """
    # Use the config CA cert for self-signed Keycloak TLS (local dev).
    # Falls back to system default trust store when ca_cert_path is not set.
    ssl_verify: str | bool = config.ca_cert_path or True
    try:
        async with httpx.AsyncClient(verify=ssl_verify) as client:
            resp = await client.get(config.jwks_url, timeout=10.0)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        logger.error("jwks_fetch_failed", url=config.jwks_url, error=str(exc))
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable — JWKS fetch failed",
        ) from exc


async def _get_jwks(config: KeycloakConfig) -> dict[str, Any]:
    """
    Return the Keycloak JWKS, using the in-process cache when still valid.

    Cache TTL: JWKS_TTL_SECONDS (default 300 s).  On first call or after TTL
    expiry, _fetch_jwks_from_remote() is called; subsequent calls within the
    TTL window return the cached dict without any I/O.

    Thundering herd prevention: when multiple coroutines race on an expired
    cache, _jwks_refresh_lock ensures only one HTTP request fires.  All other
    waiters pick up the freshly-populated cache after the lock is released
    (double-checked locking pattern).
    """
    global _jwks_fetched_at, _JWKS_CACHE

    now = time.monotonic()
    # Fast path: cache valid — no lock needed
    if _JWKS_CACHE and (now - _jwks_fetched_at) < JWKS_TTL_SECONDS:
        return _JWKS_CACHE

    # Slow path: acquire lock to prevent thundering herd on concurrent expiry
    async with _jwks_refresh_lock:
        # Double-check after acquiring lock — another coroutine may have refreshed
        now = time.monotonic()
        if _JWKS_CACHE and (now - _jwks_fetched_at) < JWKS_TTL_SECONDS:
            return _JWKS_CACHE

        jwks = await _fetch_jwks_from_remote(config)
        _JWKS_CACHE = jwks
        _jwks_fetched_at = now
        return _JWKS_CACHE


def invalidate_jwks_cache() -> None:
    """Force JWKS re-fetch on next Keycloak token validation. Call after config change."""
    global _jwks_fetched_at, _JWKS_CACHE
    _JWKS_CACHE = {}
    _jwks_fetched_at = 0.0
    logger.info("jwks_cache_invalidated")


async def _validate_keycloak_token(token: str, config: KeycloakConfig) -> UserContext:
    """
    Validate a Keycloak RS256 Bearer token.

    Checks:
      - Signature (RS256, against JWKS public key)
      - Expiry (exp claim)
      - Issuer (iss must equal config.issuer_url)
      - Audience: skipped — blitz-portal tokens carry no aud claim

    Returns:
        UserContext populated from JWT claims.

    Raises:
        HTTPException(401, "Token has expired")   — expired token
        HTTPException(401, "Invalid token")       — any other JWT error
        HTTPException(503, ...)                   — JWKS endpoint unreachable
    """
    jwks = await _get_jwks(config)
    try:
        payload: dict[str, Any] = jose_jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            # Skip audience validation — the blitz-portal access token carries no
            # aud claim (Keycloak default for this realm config).  Signature (RS256)
            # and issuer are still validated so tokens from other issuers are rejected.
            options={"verify_aud": False},
            issuer=config.issuer_url,
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


# ---------------------------------------------------------------------------
# Public API — dual-issuer dispatcher
# ---------------------------------------------------------------------------


async def validate_token(
    token: str,
    session: AsyncSession | None = None,
) -> UserContext:
    """
    Validate a Bearer token, routing to the correct validator by issuer.

    Dispatch logic:
      1. Load current Keycloak config from resolver.
      2. Peek at `iss` claim WITHOUT signature verification.
      3. `iss == config.issuer_url` AND config.enabled → _validate_keycloak_token()
      4. `iss == "blitz-local"` → validate_local_token()
      5. Anything else → HTTPException(401, "Unknown token issuer")

    Args:
        token:   The raw JWT string (no "Bearer " prefix).
        session: Optional DB session for local token is_active check.
                 Required when a local token is expected.
                 If None and the token is local, a temporary session is opened.

    Returns:
        UserContext with user_id, email, username, roles, groups.

    Raises:
        HTTPException(401, "Token has expired")      — expired token (either path)
        HTTPException(401, "Invalid token")          — bad signature / wrong issuer
        HTTPException(401, "Account deactivated")    — local user deactivated
        HTTPException(401, "Unknown token issuer")   — unrecognized iss claim
        HTTPException(503, ...)                      — Keycloak JWKS unreachable
    """
    try:
        unverified = jose_jwt.get_unverified_claims(token)
    except JWTError:
        # Malformed token — can't even peek at claims
        raise HTTPException(status_code=401, detail="Invalid token")

    issuer = unverified.get("iss", "")

    # Load config once per call (cached, cheap after warmup)
    kc_config = await get_keycloak_config()

    if kc_config is not None and kc_config.enabled and issuer == kc_config.issuer_url:
        return await _validate_keycloak_token(token, kc_config)
    elif issuer == "blitz-local":
        # Import here to avoid circular import: local_auth imports from core.models,
        # and some modules may import from security.jwt first.
        from security.local_auth import validate_local_token

        if session is None:
            # No session provided — open one for the is_active check.
            # This path is hit when validate_token is called directly (e.g., tests).
            from core.db import async_session

            async with async_session() as db_session:
                return await validate_local_token(token, db_session)
        return await validate_local_token(token, session)
    else:
        logger.warning("jwt_unknown_issuer", issuer=issuer)
        raise HTTPException(status_code=401, detail="Unknown token issuer")
