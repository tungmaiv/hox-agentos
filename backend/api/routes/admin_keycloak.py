"""
Admin Keycloak configuration API — Plan 18-02.

Endpoints:
  GET  /api/admin/keycloak/config           — read current config (has_secret: bool, never raw secret)
  POST /api/admin/keycloak/config           — save config + invalidate caches + restart frontend
  POST /api/admin/keycloak/test-connection  — validate JWKS endpoint reachability
  POST /api/admin/keycloak/disable          — set enabled=false + restart frontend
  GET  /api/internal/keycloak/provider-config — serve config to Next.js at startup (X-Internal-Key)

Storage: platform_config table (single-row, id=1) — NOT system_config key/value store.
  Decision: IDCFG-06 — typed columns for type safety and migration tractability.

Security:
  - All admin endpoints require 'tool:admin' permission (it-admin role).
  - Internal endpoint requires X-Internal-Key header (shared secret).
  - client_secret is NEVER logged. Stored AES-256-GCM encrypted in platform_config.
  - GET config response never includes client_secret or masked string — only has_secret: bool.
"""

import asyncio
import base64
import json
import os
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from sqlalchemy import select

from core.db import async_session, get_db
from core.logging import get_audit_logger
from core.models.local_auth import LocalUser
from core.models.platform_config import PlatformConfig
from core.models.user import UserContext
from security.deps import get_current_user
from security.jwt import invalidate_jwks_cache
from security.keycloak_config import (
    get_keycloak_config,
    invalidate_keycloak_config_cache,
)
from security.rbac import has_permission

logger = structlog.get_logger(__name__)
audit_logger = get_audit_logger()
router = APIRouter(tags=["admin-keycloak"])

# ---------------------------------------------------------------------------
# Security gate
# ---------------------------------------------------------------------------


async def _require_admin(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    if not await has_permission(user, "tool:admin", session):
        raise HTTPException(status_code=403, detail="Admin permission required")
    return user


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class KeycloakConfigInput(BaseModel):
    issuer_url: str
    client_id: str
    client_secret: str | None = (
        None  # None or "" means "keep existing secret if one is stored"
    )
    realm: str
    ca_cert_path: str = ""


class KeycloakConfigResponse(BaseModel):
    """
    Admin read response for Keycloak config.

    Decision (Sensitive field display policy):
      has_secret: bool — true if a client secret is stored in platform_config.
      The raw secret (or any masked representation like "*****") is NEVER included.
    """

    configured: bool = True
    issuer_url: str = ""
    client_id: str = ""
    has_secret: bool = (
        False  # true if client_secret_encrypted is set; never raw/masked string
    )
    realm: str = ""
    ca_cert_path: str = ""
    enabled: bool = True


class SaveConfigResponse(BaseModel):
    saved: bool
    frontend_restarting: bool


class TestConnectionInput(BaseModel):
    issuer_url: str
    ca_cert_path: str = ""


class TestConnectionResponse(BaseModel):
    reachable: bool
    keys_found: int = 0
    error: str | None = None


class DisableResponse(BaseModel):
    disabled: bool
    frontend_restarting: bool


class EnableResponse(BaseModel):
    enabled: bool
    frontend_restarting: bool


class InternalProviderConfig(BaseModel):
    enabled: bool
    client_id: str = ""
    client_secret: str = ""
    issuer: str = ""


class KeycloakUserEntry(BaseModel):
    id: str
    username: str
    email: str


# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------


def _encrypt_secret(plaintext: str) -> str:
    """
    Encrypt client_secret using AES-256-GCM.
    Returns JSON string {"iv_b64": ..., "ct_b64": ...} for storage in
    platform_config.keycloak_client_secret_encrypted (Text column).
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    hex_key = settings.credential_encryption_key
    if not hex_key:
        raise HTTPException(
            status_code=500,
            detail="CREDENTIAL_ENCRYPTION_KEY is not set — cannot encrypt Keycloak client secret",
        )
    key = bytes.fromhex(hex_key)
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    enc_dict = {
        "iv_b64": base64.b64encode(iv).decode(),
        "ct_b64": base64.b64encode(ciphertext).decode(),
    }
    return json.dumps(enc_dict)


# ---------------------------------------------------------------------------
# DB helpers — operate on platform_config (single-row, id=1)
# ---------------------------------------------------------------------------


async def _save_keycloak_config_to_db(config: KeycloakConfigInput) -> None:
    """
    Persist Keycloak config to platform_config table (single-row upsert, id=1).

    Extracts keycloak_url from issuer_url by stripping /realms/<realm>.
    Encrypts client_secret before storing.

    Secret update policy:
      - config.client_secret is None or "" AND existing row already has a secret
        → keep the existing encrypted secret unchanged
      - config.client_secret is a non-empty string
        → encrypt and overwrite the stored secret
    """
    from sqlalchemy import select

    # Derive keycloak_url from issuer_url
    # issuer_url = "https://host/realms/realm" → keycloak_url = "https://host"
    issuer = config.issuer_url.rstrip("/")
    if f"/realms/{config.realm}" in issuer:
        keycloak_url = issuer[: issuer.index(f"/realms/{config.realm}")]
    else:
        keycloak_url = issuer  # Fallback: store issuer_url directly

    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(PlatformConfig).where(PlatformConfig.id == 1)
            )
            existing = result.scalar_one_or_none()

            # Determine whether to update the secret column.
            # If the caller sent an empty/None secret AND a secret is already stored,
            # preserve the existing encrypted value (frontend "keep current secret" path).
            new_secret = config.client_secret  # str | None
            if not new_secret:
                # Empty or None — only encrypt and store if no existing secret
                encrypted_secret = (
                    None
                    if (existing and existing.keycloak_client_secret_encrypted)
                    else None  # No existing row either: leave as None, caller must provide secret
                )
                should_update_secret = not (
                    existing and existing.keycloak_client_secret_encrypted is not None
                )
            else:
                encrypted_secret = _encrypt_secret(new_secret)
                should_update_secret = True

            if existing:
                existing.keycloak_url = keycloak_url
                existing.keycloak_realm = config.realm
                existing.keycloak_client_id = config.client_id
                if should_update_secret:
                    existing.keycloak_client_secret_encrypted = encrypted_secret
                # else: leave existing.keycloak_client_secret_encrypted unchanged
                existing.keycloak_ca_cert = config.ca_cert_path or None
                # Do NOT touch existing.enabled — preserve whatever the admin last set.
                # Use POST /api/admin/keycloak/disable to change the enabled state.
            else:
                session.add(
                    PlatformConfig(
                        id=1,
                        keycloak_url=keycloak_url,
                        keycloak_realm=config.realm,
                        keycloak_client_id=config.client_id,
                        keycloak_client_secret_encrypted=encrypted_secret,
                        keycloak_ca_cert=config.ca_cert_path or None,
                        enabled=True,
                    )
                )


async def _set_keycloak_enabled(enabled: bool) -> None:
    """Set platform_config.enabled (single-row, id=1)."""
    from sqlalchemy import select

    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(PlatformConfig).where(PlatformConfig.id == 1)
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.enabled = enabled
            else:
                # No config row yet — nothing to disable
                logger.warning("keycloak_disable_no_config_row")


# ---------------------------------------------------------------------------
# JWKS test helper
# ---------------------------------------------------------------------------


async def _test_jwks_endpoint(issuer_url: str, ca_cert_path: str) -> dict[str, Any]:
    """
    Attempt to fetch JWKS from the given issuer. Returns dict with reachable/keys_found/error.

    Security note: issuer_url is validated to be an https:// URL before use.
    Only it-admin role can reach this code path (enforced by _require_admin dependency).
    """
    if not issuer_url.startswith("https://"):
        return {
            "reachable": False,
            "keys_found": 0,
            "error": "issuer_url must use https://",
        }
    jwks_url = f"{issuer_url}/protocol/openid-connect/certs"
    ssl_verify: str | bool = ca_cert_path or True
    try:
        async with httpx.AsyncClient(verify=ssl_verify, timeout=10.0) as client:
            resp = await client.get(jwks_url)
            resp.raise_for_status()
            data = resp.json()
            keys_found = len(data.get("keys", []))
            return {"reachable": True, "keys_found": keys_found, "error": None}
    except Exception as exc:
        return {"reachable": False, "keys_found": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# Docker restart helper
# ---------------------------------------------------------------------------


def _restart_frontend_container() -> None:
    """
    Restart the Next.js frontend Docker container using the Docker SDK.

    Uses compose service label to find the container (robust across project names).
    Runs synchronously in a thread (Docker SDK is sync).
    Logs a warning if Docker is unavailable — never raises.
    """
    try:
        import docker
        import docker.errors

        client = docker.from_env()
        containers = client.containers.list(
            filters={"label": "com.docker.compose.service=frontend"}
        )
        if not containers:
            logger.warning("frontend_container_not_found_for_restart")
            return
        for container in containers:
            container.restart(timeout=10)
            logger.info("frontend_container_restarted", container_id=container.short_id)
    except Exception as exc:
        logger.warning("frontend_restart_failed", error=str(exc))


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.get("/api/admin/keycloak/config", response_model=None)
async def get_admin_keycloak_config(
    user: UserContext = Depends(_require_admin),
) -> dict[str, Any]:
    """
    Return current Keycloak config for the admin UI.

    has_secret: bool indicates whether a client secret is stored.
    The secret itself (raw or masked) is NEVER returned.
    """
    kc = await get_keycloak_config()
    if kc is None:
        return {"configured": False}

    return {
        "configured": True,
        "issuer_url": kc.issuer_url,
        "client_id": kc.client_id,
        "has_secret": bool(kc.client_secret),  # true if secret exists, never the value
        "realm": kc.realm,
        "ca_cert_path": kc.ca_cert_path,
        "enabled": kc.enabled,
    }


@router.post("/api/admin/keycloak/config", response_model=SaveConfigResponse)
async def save_keycloak_config(
    body: KeycloakConfigInput,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(_require_admin),
) -> SaveConfigResponse:
    """
    Save Keycloak configuration to platform_config table.

    Invalidates the resolver cache and JWKS cache so the backend
    picks up the new config within seconds without restart.
    Triggers a frontend container restart so Next.js auth.ts
    fetches the new credentials on next boot.
    """
    await _save_keycloak_config_to_db(body)

    # Invalidate caches — backend uses new config on next request
    invalidate_keycloak_config_cache()
    invalidate_jwks_cache()

    # Restart frontend AFTER response is sent — BackgroundTasks fires post-response.
    # Do NOT await here: the frontend container is the one making this request,
    # so killing it before returning would drop the connection → "Failed to fetch".
    background_tasks.add_task(_restart_frontend_container)

    audit_logger.info(
        "keycloak_config_saved",
        issuer_url=body.issuer_url,
        client_id=body.client_id,
        admin_user=str(user["user_id"]),
    )
    return SaveConfigResponse(saved=True, frontend_restarting=True)


@router.post(
    "/api/admin/keycloak/test-connection", response_model=TestConnectionResponse
)
async def test_keycloak_connection(
    body: TestConnectionInput,
    user: UserContext = Depends(_require_admin),
) -> TestConnectionResponse:
    """
    Test JWKS endpoint reachability without saving config.

    Constructs JWKS URL from issuer_url and attempts HTTP GET.
    Returns reachable=true/false so admin can verify before saving.
    """
    result = await _test_jwks_endpoint(body.issuer_url, body.ca_cert_path)
    audit_logger.info(
        "keycloak_connection_test",
        issuer_url=body.issuer_url,
        reachable=result["reachable"],
        admin_user=str(user["user_id"]),
    )
    return TestConnectionResponse(**result)


@router.post("/api/admin/keycloak/enable", response_model=EnableResponse)
async def enable_sso(
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(_require_admin),
) -> EnableResponse:
    """
    Enable SSO (re-enable after being disabled).

    Sets platform_config.enabled=True, invalidates caches,
    and restarts frontend so Next.js loads the Keycloak provider.
    """
    await _set_keycloak_enabled(True)
    invalidate_keycloak_config_cache()
    invalidate_jwks_cache()
    background_tasks.add_task(_restart_frontend_container)

    audit_logger.info("keycloak_sso_enabled", admin_user=str(user["user_id"]))
    return EnableResponse(enabled=True, frontend_restarting=True)


@router.post("/api/admin/keycloak/disable", response_model=DisableResponse)
async def disable_sso(
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(_require_admin),
) -> DisableResponse:
    """
    Disable SSO without removing config.

    Sets platform_config.enabled=False, invalidates caches,
    and restarts frontend so Next.js drops the Keycloak provider.
    """
    await _set_keycloak_enabled(False)
    invalidate_keycloak_config_cache()
    invalidate_jwks_cache()
    background_tasks.add_task(_restart_frontend_container)

    audit_logger.info("keycloak_sso_disabled", admin_user=str(user["user_id"]))
    return DisableResponse(disabled=True, frontend_restarting=True)


# ---------------------------------------------------------------------------
# Internal endpoint — Next.js startup
# ---------------------------------------------------------------------------


@router.get(
    "/api/internal/keycloak/provider-config", response_model=InternalProviderConfig
)
async def internal_provider_config(
    x_internal_key: str | None = Header(default=None, alias="X-Internal-Key"),
) -> InternalProviderConfig:
    """
    Serve Keycloak provider credentials to Next.js on startup.

    Called by auth.ts during Next.js initialization. Protected by X-Internal-Key
    shared secret. Never exposed through Next.js to the browser.

    Returns: {"enabled": false} when Keycloak is not configured.
             {"enabled": true, "client_id": ..., "client_secret": ..., "issuer": ...} when configured.
    """
    expected_key = settings.internal_api_key
    if not expected_key or x_internal_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Internal-Key")

    kc = await get_keycloak_config()
    if kc is None or not kc.enabled:
        return InternalProviderConfig(enabled=False)

    return InternalProviderConfig(
        enabled=True,
        client_id=kc.client_id,
        client_secret=kc.client_secret,
        issuer=kc.issuer_url,
    )


@router.get("/api/admin/keycloak/users")
async def search_keycloak_users(
    q: str = "",
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> list[KeycloakUserEntry]:
    """Search all users (local DB + Keycloak) by username or email.

    Always queries local_users table. If Keycloak is enabled, also queries
    Keycloak admin API. Results are merged and deduplicated by email — when
    the same email appears in both sources, the Keycloak entry takes precedence
    (its ID matches the JWT sub claim used for authentication).

    Used by the admin skill share dialog so the stored user_id always matches
    the target user's JWT sub, regardless of which auth method they use.
    """
    lower = q.strip().lower()

    # --- 1. Local DB users ---
    local_stmt = select(LocalUser)
    if lower:
        from sqlalchemy import or_
        local_stmt = local_stmt.where(
            or_(
                LocalUser.username.ilike(f"%{lower}%"),
                LocalUser.email.ilike(f"%{lower}%"),
            )
        )
    local_result = await session.execute(local_stmt)
    local_users = local_result.scalars().all()

    # Build result map keyed by email (lowercase) — local entries first
    # {email: KeycloakUserEntry}
    by_email: dict[str, KeycloakUserEntry] = {
        lu.email.lower(): KeycloakUserEntry(
            id=str(lu.id),
            username=lu.username,
            email=lu.email,
        )
        for lu in local_users
    }

    # --- 2. Keycloak users (if configured) — override local entries by email ---
    kc = await get_keycloak_config()
    if kc is not None and kc.enabled:
        base_url = kc.issuer_url.split("/realms/")[0]
        ca_cert: str | bool = kc.ca_cert_path if kc.ca_cert_path else False
        try:
            async with httpx.AsyncClient(verify=ca_cert, timeout=10.0) as client:
                token_resp = await client.post(
                    f"{base_url}/realms/master/protocol/openid-connect/token",
                    data={
                        "grant_type": "password",
                        "client_id": "admin-cli",
                        "username": settings.keycloak_admin_username,
                        "password": settings.keycloak_admin_password,
                    },
                )
                if token_resp.status_code == 200:
                    admin_token = token_resp.json()["access_token"]
                    params: dict[str, str | int] = {"max": 50}
                    if lower:
                        params["search"] = lower
                    users_resp = await client.get(
                        f"{base_url}/admin/realms/{kc.realm}/users",
                        headers={"Authorization": f"Bearer {admin_token}"},
                        params=params,
                    )
                    if users_resp.status_code == 200:
                        for u in users_resp.json():
                            email = u.get("email", "").lower()
                            username = u.get("username", "")
                            # Client-side filter (Keycloak search is broad)
                            if lower and lower not in username.lower() and lower not in email:
                                continue
                            # Keycloak entry overrides local entry for same email
                            by_email[email] = KeycloakUserEntry(
                                id=u["id"],
                                username=username,
                                email=u.get("email", ""),
                            )
                else:
                    logger.warning("keycloak_admin_token_failed", status=token_resp.status_code)
        except Exception as exc:
            logger.warning("keycloak_user_search_error", error=str(exc))

    return list(by_email.values())
