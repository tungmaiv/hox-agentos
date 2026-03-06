"""
Tests for KeycloakConfigResolver — TTL cache + resolution order.

Resolution order: platform_config DB (priority) → env vars (fallback) → None (local-only).
"""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_resolver_returns_none_when_no_config():
    """When no DB config and no env vars, resolver returns None (local-only mode)."""
    import security.keycloak_config as kc_mod
    kc_mod._kc_config_cache = None
    kc_mod._kc_config_fetched_at = 0.0
    kc_mod._kc_config_resolved = False

    # Patch env vars to be empty
    with patch("security.keycloak_config.settings") as mock_settings:
        mock_settings.keycloak_url = ""
        mock_settings.keycloak_realm = ""
        mock_settings.keycloak_client_id = ""
        mock_settings.keycloak_client_secret = ""
        mock_settings.keycloak_ca_cert = ""

        with patch("security.keycloak_config._load_from_db", new_callable=AsyncMock, return_value=None):
            result = await kc_mod.get_keycloak_config()

    assert result is None


@pytest.mark.asyncio
async def test_resolver_returns_config_from_env_vars():
    """When env vars are set (no DB override), resolver returns config from settings."""
    import security.keycloak_config as kc_mod
    kc_mod._kc_config_cache = None
    kc_mod._kc_config_fetched_at = 0.0
    kc_mod._kc_config_resolved = False

    with patch("security.keycloak_config.settings") as mock_settings:
        mock_settings.keycloak_url = "https://kc.example.com"
        mock_settings.keycloak_realm = "test-realm"
        mock_settings.keycloak_client_id = "test-client"
        mock_settings.keycloak_client_secret = "test-secret"
        mock_settings.keycloak_ca_cert = ""
        mock_settings.keycloak_issuer = "https://kc.example.com/realms/test-realm"
        mock_settings.keycloak_jwks_url = "https://kc.example.com/realms/test-realm/protocol/openid-connect/certs"

        with patch("security.keycloak_config._load_from_db", new_callable=AsyncMock, return_value=None):
            result = await kc_mod.get_keycloak_config()

    assert result is not None
    assert result.issuer_url == "https://kc.example.com/realms/test-realm"
    assert result.client_id == "test-client"
    assert result.enabled is True


@pytest.mark.asyncio
async def test_resolver_db_config_overrides_env_vars():
    """DB config takes priority over env vars."""
    import security.keycloak_config as kc_mod
    kc_mod._kc_config_cache = None
    kc_mod._kc_config_fetched_at = 0.0
    kc_mod._kc_config_resolved = False

    from security.keycloak_config import KeycloakConfig
    db_config = KeycloakConfig(
        issuer_url="https://db-kc.example.com/realms/db-realm",
        client_id="db-client",
        client_secret="db-secret",
        realm="db-realm",
        ca_cert_path="",
        enabled=True,
    )

    with patch("security.keycloak_config._load_from_db", new_callable=AsyncMock, return_value=db_config):
        result = await kc_mod.get_keycloak_config()

    assert result is not None
    assert result.issuer_url == "https://db-kc.example.com/realms/db-realm"
    assert result.client_id == "db-client"


def test_invalidate_clears_cache():
    """invalidate_keycloak_config_cache() resets the TTL so next call re-fetches."""
    import security.keycloak_config as kc_mod
    kc_mod._kc_config_fetched_at = time.monotonic()  # Simulate warm cache

    kc_mod.invalidate_keycloak_config_cache()

    assert kc_mod._kc_config_fetched_at == 0.0
