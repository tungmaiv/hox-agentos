"""
KeycloakConfig resolver — single source of truth for runtime Keycloak configuration.

Resolution order (higher priority first):
  1. platform_config DB table — typed columns, single-row (admin-configured at runtime)
  2. Settings / env vars — keycloak_url, keycloak_realm, etc. (fallback)
  3. None — no configuration found → local-only mode

Decision (IDCFG-06): platform_config table used, NOT system_config key/value store.

Cache: 60-second TTL (same pattern as JWKS cache in jwt.py).
Call invalidate_keycloak_config_cache() after admin config save to force re-read.

Security invariants:
  - client_secret is NEVER logged.
  - The resolver never raises — returns None on any read failure (safe fallback).
"""
import asyncio
import base64
import json
import time
from dataclasses import dataclass

import structlog
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.config import settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Cache state (module-level, same pattern as jwt.py JWKS cache)
# ---------------------------------------------------------------------------

KC_CONFIG_TTL_SECONDS: float = 60.0

_kc_config_cache: "KeycloakConfig | None" = None
_kc_config_fetched_at: float = 0.0
# Sentinel to distinguish "not yet fetched" from "fetched and got None"
_kc_config_resolved: bool = False
_kc_config_refresh_lock: asyncio.Lock = asyncio.Lock()  # thundering herd guard


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KeycloakConfig:
    """Runtime Keycloak configuration. Immutable once constructed."""

    issuer_url: str       # e.g. https://keycloak.blitz.local/realms/blitz-internal
    client_id: str        # e.g. blitz-portal
    client_secret: str    # plaintext (decrypted from DB or from env) — never log
    realm: str            # e.g. blitz-internal
    ca_cert_path: str     # optional path to CA cert for self-signed TLS
    enabled: bool         # admin can disable SSO without removing config

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer_url}/protocol/openid-connect/certs"


# ---------------------------------------------------------------------------
# DB loader — reads from platform_config typed-column table
# ---------------------------------------------------------------------------


async def _load_from_db() -> "KeycloakConfig | None":
    """
    Read Keycloak config from platform_config table (single-row, id=1).

    Returns None if no row exists or keycloak_url is not set, or on any error.
    """
    try:
        from sqlalchemy import select
        from core.db import async_session
        from core.models.platform_config import PlatformConfig

        async with async_session() as session:
            result = await session.execute(
                select(PlatformConfig).where(PlatformConfig.id == 1)
            )
            row = result.scalar_one_or_none()

        if row is None or not row.keycloak_url:
            return None  # Not configured in DB

        # Derive issuer URL from url + realm
        issuer_url = f"{row.keycloak_url}/realms/{row.keycloak_realm}"

        # Decrypt client secret
        client_secret = ""
        if row.keycloak_client_secret_encrypted:
            try:
                enc = json.loads(row.keycloak_client_secret_encrypted)
                client_secret = _decrypt_client_secret(enc)
            except Exception as exc:
                logger.error("keycloak_config_decrypt_failed", error=str(exc))
                return None

        if not row.keycloak_client_id:
            return None

        return KeycloakConfig(
            issuer_url=issuer_url,
            client_id=row.keycloak_client_id,
            client_secret=client_secret,
            realm=row.keycloak_realm or "",
            ca_cert_path=row.keycloak_ca_cert or "",
            enabled=row.enabled,
        )
    except Exception as exc:
        logger.warning("keycloak_config_db_read_failed", error=str(exc))
        return None


def _decrypt_client_secret(enc: object) -> str:
    """Decrypt AES-256-GCM encrypted client secret from platform_config value."""
    if not isinstance(enc, dict):
        raise ValueError(f"Expected dict for encrypted secret, got {type(enc)}")

    iv_b64 = enc.get("iv_b64", "")
    ct_b64 = enc.get("ct_b64", "")
    if not iv_b64 or not ct_b64:
        raise ValueError("Missing iv_b64 or ct_b64 in encrypted secret")

    hex_key = settings.credential_encryption_key
    if not hex_key:
        raise RuntimeError("CREDENTIAL_ENCRYPTION_KEY not set — cannot decrypt Keycloak client secret")

    key = bytes.fromhex(hex_key)
    iv = base64.b64decode(iv_b64)
    ct = base64.b64decode(ct_b64)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, ct, None).decode("utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_keycloak_config() -> "KeycloakConfig | None":
    """
    Return current Keycloak config, using TTL cache.

    Resolution order: platform_config DB → env vars → None (local-only).
    Returns None if no Keycloak config is found anywhere.
    Cache TTL: KC_CONFIG_TTL_SECONDS (60s). Force refresh: invalidate_keycloak_config_cache().
    """
    global _kc_config_cache, _kc_config_fetched_at, _kc_config_resolved

    now = time.monotonic()
    # Fast path: cache valid — no lock needed
    if _kc_config_resolved and (now - _kc_config_fetched_at) < KC_CONFIG_TTL_SECONDS:
        return _kc_config_cache

    # Slow path: acquire lock to prevent thundering herd on concurrent cache expiry
    async with _kc_config_refresh_lock:
        # Double-check after acquiring lock — another coroutine may have refreshed
        now = time.monotonic()
        if _kc_config_resolved and (now - _kc_config_fetched_at) < KC_CONFIG_TTL_SECONDS:
            return _kc_config_cache

        # Try DB first
        db_config = await _load_from_db()
        if db_config is not None:
            _kc_config_cache = db_config
            _kc_config_fetched_at = now
            _kc_config_resolved = True
            logger.debug("keycloak_config_loaded_from_db", issuer_url=db_config.issuer_url)
            return db_config

        # Fallback: env vars / settings
        if settings.keycloak_url and settings.keycloak_client_id:
            env_config = KeycloakConfig(
                issuer_url=settings.keycloak_issuer or f"{settings.keycloak_url}/realms/{settings.keycloak_realm}",
                client_id=settings.keycloak_client_id,
                client_secret=settings.keycloak_client_secret,
                realm=settings.keycloak_realm,
                ca_cert_path=settings.keycloak_ca_cert,
                enabled=True,
            )
            _kc_config_cache = env_config
            _kc_config_fetched_at = now
            _kc_config_resolved = True
            logger.debug("keycloak_config_loaded_from_env", issuer_url=env_config.issuer_url)
            return env_config

        # No config → local-only mode
        _kc_config_cache = None
        _kc_config_fetched_at = now
        _kc_config_resolved = True
        logger.debug("keycloak_config_none_local_only")
        return None


def invalidate_keycloak_config_cache() -> None:
    """
    Force the next call to get_keycloak_config() to re-read from DB.
    Call after admin saves or disables Keycloak config.
    """
    global _kc_config_fetched_at, _kc_config_resolved
    _kc_config_fetched_at = 0.0
    _kc_config_resolved = False
    logger.info("keycloak_config_cache_invalidated")
