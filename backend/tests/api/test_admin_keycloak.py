"""
Tests for admin Keycloak config API — Plan 18-02.

Covers:
  - GET /api/admin/keycloak/config (admin only; has_secret: bool — never raw secret)
  - POST /api/admin/keycloak/config (saves to platform_config, triggers cache invalidation)
  - POST /api/admin/keycloak/test-connection (validates JWKS endpoint)
  - POST /api/admin/keycloak/disable (sets enabled=false in platform_config)
  - GET /api/internal/keycloak/provider-config (X-Internal-Key required)
"""
import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.db import Base, get_db
from core.models.role_permission import RolePermission  # noqa: F401
from core.models.user import UserContext
from main import app
from security.deps import get_current_user


# ---------------------------------------------------------------------------
# User context helpers
# ---------------------------------------------------------------------------


def make_admin_ctx() -> UserContext:
    """it-admin role has tool:admin permission."""
    return UserContext(
        user_id=uuid4(),
        email="admin@blitz.local",
        username="admin_user",
        roles=["it-admin"],
        groups=["/it"],
    )


def make_employee_ctx() -> UserContext:
    """employee role lacks tool:admin permission."""
    return UserContext(
        user_id=uuid4(),
        email="employee@blitz.local",
        username="emp_user",
        roles=["employee"],
        groups=["/tech"],
    )


# ---------------------------------------------------------------------------
# SQLite in-memory fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_db():
    """Override get_db with an in-memory SQLite async session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_setup())

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    loop.run_until_complete(engine.dispose())
    loop.close()


@pytest.fixture
def admin_client(sqlite_db: None) -> TestClient:
    """TestClient with admin (it-admin) auth + SQLite DB."""
    app.dependency_overrides[get_current_user] = make_admin_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def employee_client(sqlite_db: None) -> TestClient:
    """TestClient with employee role (no tool:admin) + SQLite DB."""
    app.dependency_overrides[get_current_user] = make_employee_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# GET /api/admin/keycloak/config
# ---------------------------------------------------------------------------


def test_get_keycloak_config_returns_has_secret_true(admin_client: TestClient) -> None:
    """GET config returns has_secret=true when a secret is stored; never the secret string."""
    from security.keycloak_config import KeycloakConfig

    kc = KeycloakConfig(
        issuer_url="https://kc.example.com/realms/test",
        client_id="blitz-portal",
        client_secret="super-secret",  # only in resolver; must NOT appear in response
        realm="test",
        ca_cert_path="",
        enabled=True,
    )

    with patch("api.routes.admin_keycloak.get_keycloak_config", new_callable=AsyncMock, return_value=kc):
        resp = admin_client.get("/api/admin/keycloak/config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["issuer_url"] == "https://kc.example.com/realms/test"
    assert data["client_id"] == "blitz-portal"
    # has_secret: true — never a masked string like "*****"
    assert data["has_secret"] is True
    assert "client_secret" not in data
    assert data["enabled"] is True


def test_get_keycloak_config_returns_has_secret_false_when_no_secret(admin_client: TestClient) -> None:
    """GET config returns has_secret=false when no secret is stored."""
    from security.keycloak_config import KeycloakConfig

    kc = KeycloakConfig(
        issuer_url="https://kc.example.com/realms/test",
        client_id="blitz-portal",
        client_secret="",  # empty = no secret stored
        realm="test",
        ca_cert_path="",
        enabled=True,
    )

    with patch("api.routes.admin_keycloak.get_keycloak_config", new_callable=AsyncMock, return_value=kc):
        resp = admin_client.get("/api/admin/keycloak/config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_secret"] is False


def test_get_keycloak_config_returns_not_configured(admin_client: TestClient) -> None:
    """GET config returns not_configured when no Keycloak config exists."""
    with patch("api.routes.admin_keycloak.get_keycloak_config", new_callable=AsyncMock, return_value=None):
        resp = admin_client.get("/api/admin/keycloak/config")

    assert resp.status_code == 200
    assert resp.json()["configured"] is False


def test_get_keycloak_config_forbidden_for_non_admin(employee_client: TestClient) -> None:
    """Non-admin users get 403."""
    resp = employee_client.get("/api/admin/keycloak/config")
    assert resp.status_code == 403


def test_post_keycloak_config_forbidden_for_non_admin(employee_client: TestClient) -> None:
    """POST config returns 403 for non-admin users."""
    payload = {
        "issuer_url": "https://kc.example.com/realms/test",
        "client_id": "blitz-portal",
        "client_secret": "secret",
        "realm": "test",
        "ca_cert_path": "",
    }
    resp = employee_client.post("/api/admin/keycloak/config", json=payload)
    assert resp.status_code == 403


def test_disable_sso_forbidden_for_non_admin(employee_client: TestClient) -> None:
    """POST disable returns 403 for non-admin users."""
    resp = employee_client.post("/api/admin/keycloak/disable")
    assert resp.status_code == 403


def test_test_connection_forbidden_for_non_admin(employee_client: TestClient) -> None:
    """POST test-connection returns 403 for non-admin users."""
    resp = employee_client.post(
        "/api/admin/keycloak/test-connection",
        json={"issuer_url": "https://kc.example.com/realms/test", "ca_cert_path": ""},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/admin/keycloak/config
# ---------------------------------------------------------------------------


def test_post_keycloak_config_saves_and_invalidates_cache(admin_client: TestClient) -> None:
    """POST config saves to platform_config, invalidates caches, triggers restart."""
    with patch("api.routes.admin_keycloak._save_keycloak_config_to_db", new_callable=AsyncMock), \
         patch("api.routes.admin_keycloak.invalidate_keycloak_config_cache") as mock_kc_inv, \
         patch("api.routes.admin_keycloak.invalidate_jwks_cache") as mock_jwks_inv, \
         patch("api.routes.admin_keycloak._restart_frontend_container") as mock_restart:

        payload = {
            "issuer_url": "https://kc.example.com/realms/test",
            "client_id": "blitz-portal",
            "client_secret": "new-secret",
            "realm": "test",
            "ca_cert_path": "",
        }
        resp = admin_client.post("/api/admin/keycloak/config", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["saved"] is True
    assert data["frontend_restarting"] is True
    mock_kc_inv.assert_called_once()
    mock_jwks_inv.assert_called_once()
    mock_restart.assert_called_once()


# ---------------------------------------------------------------------------
# POST /api/admin/keycloak/test-connection
# ---------------------------------------------------------------------------


def test_test_connection_reachable(admin_client: TestClient) -> None:
    """test-connection returns reachable=true when JWKS endpoint responds."""
    with patch("api.routes.admin_keycloak._test_jwks_endpoint", new_callable=AsyncMock,
               return_value={"reachable": True, "keys_found": 3, "error": None}):
        resp = admin_client.post(
            "/api/admin/keycloak/test-connection",
            json={"issuer_url": "https://kc.example.com/realms/test", "ca_cert_path": ""},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["reachable"] is True
    assert data["keys_found"] == 3


def test_test_connection_unreachable(admin_client: TestClient) -> None:
    """test-connection returns reachable=false when JWKS endpoint is unreachable."""
    with patch("api.routes.admin_keycloak._test_jwks_endpoint", new_callable=AsyncMock,
               return_value={"reachable": False, "keys_found": 0, "error": "Connection refused"}):
        resp = admin_client.post(
            "/api/admin/keycloak/test-connection",
            json={"issuer_url": "https://bad.example.com/realms/test", "ca_cert_path": ""},
        )

    assert resp.status_code == 200
    assert resp.json()["reachable"] is False


# ---------------------------------------------------------------------------
# POST /api/admin/keycloak/disable
# ---------------------------------------------------------------------------


def test_disable_sso_sets_enabled_false(admin_client: TestClient) -> None:
    """POST /disable saves enabled=false and triggers cache invalidation."""
    with patch("api.routes.admin_keycloak._set_keycloak_enabled", new_callable=AsyncMock), \
         patch("api.routes.admin_keycloak.invalidate_keycloak_config_cache") as mock_inv, \
         patch("api.routes.admin_keycloak.invalidate_jwks_cache"), \
         patch("api.routes.admin_keycloak._restart_frontend_container"):
        resp = admin_client.post("/api/admin/keycloak/disable")

    assert resp.status_code == 200
    assert resp.json()["disabled"] is True
    mock_inv.assert_called_once()


# ---------------------------------------------------------------------------
# GET /api/internal/keycloak/provider-config
# ---------------------------------------------------------------------------


def test_internal_provider_config_requires_key() -> None:
    """Missing X-Internal-Key header returns 401."""
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/internal/keycloak/provider-config")
    assert resp.status_code == 401


def test_internal_provider_config_wrong_key() -> None:
    """Wrong X-Internal-Key returns 401."""
    # Patch settings at the router module level (where it's imported and used)
    with patch("api.routes.admin_keycloak.settings") as mock_settings:
        mock_settings.internal_api_key = "correct-key"
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/internal/keycloak/provider-config",
            headers={"X-Internal-Key": "wrong-key"},
        )
    assert resp.status_code == 401


def test_internal_provider_config_no_keycloak() -> None:
    """Returns enabled=false when no Keycloak config."""
    with patch("api.routes.admin_keycloak.settings") as mock_settings, \
         patch("api.routes.admin_keycloak.get_keycloak_config", new_callable=AsyncMock, return_value=None):
        mock_settings.internal_api_key = "test-key"
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/internal/keycloak/provider-config",
            headers={"X-Internal-Key": "test-key"},
        )

    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


# ---------------------------------------------------------------------------
# Encryption roundtrip
# ---------------------------------------------------------------------------


def test_encrypt_secret_roundtrip() -> None:
    """Encrypted client_secret can be decrypted back to original value."""
    import json

    # Use a test key (64 hex chars = 32 bytes)
    test_key = "a" * 64

    # Patch settings at both call sites:
    #   _encrypt_secret        → api.routes.admin_keycloak.settings
    #   _decrypt_client_secret → security.keycloak_config.settings
    with patch("api.routes.admin_keycloak.settings") as mock_enc_settings, \
         patch("security.keycloak_config.settings") as mock_dec_settings:
        mock_enc_settings.credential_encryption_key = test_key
        mock_dec_settings.credential_encryption_key = test_key

        from api.routes.admin_keycloak import _encrypt_secret
        from security.keycloak_config import _decrypt_client_secret

        original = "my-super-secret-keycloak-client-secret"
        encrypted_json = _encrypt_secret(original)

        # _encrypt_secret returns a JSON string; parse it before passing to _decrypt_client_secret
        encrypted_dict = json.loads(encrypted_json)
        assert "iv_b64" in encrypted_dict
        assert "ct_b64" in encrypted_dict

        decrypted = _decrypt_client_secret(encrypted_dict)
        assert decrypted == original


@pytest.mark.asyncio
async def test_post_keycloak_config_keeps_existing_secret_when_empty_sent() -> None:
    """
    POST config with client_secret='' and an existing row that has a secret
    must NOT overwrite keycloak_client_secret_encrypted.

    This covers the frontend 'Keep current secret' path where the toggle is
    not expanded and an empty string is sent to the backend.
    """
    from unittest.mock import AsyncMock, MagicMock, patch, call
    from sqlalchemy.ext.asyncio import AsyncSession

    # Simulate an existing platform_config row that already has an encrypted secret
    existing_row = MagicMock()
    existing_row.keycloak_client_secret_encrypted = '{"iv_b64": "abc", "ct_b64": "def"}'
    existing_row.keycloak_url = "https://old.example.com"
    existing_row.keycloak_realm = "old-realm"
    existing_row.keycloak_client_id = "old-client"
    existing_row.enabled = True

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_row

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=None),
        __aexit__=AsyncMock(return_value=False),
    ))

    with patch("api.routes.admin_keycloak.async_session", return_value=mock_session):
        from api.routes.admin_keycloak import _save_keycloak_config_to_db, KeycloakConfigInput

        config = KeycloakConfigInput(
            issuer_url="https://new.example.com/realms/new-realm",
            client_id="new-client",
            client_secret="",   # Empty string → should keep existing secret
            realm="new-realm",
            ca_cert_path="",
        )
        await _save_keycloak_config_to_db(config)

    # The existing encrypted secret must not have been overwritten
    assert existing_row.keycloak_client_secret_encrypted == '{"iv_b64": "abc", "ct_b64": "def"}'
    # Other fields should have been updated
    assert existing_row.keycloak_client_id == "new-client"


def test_internal_provider_config_returns_credentials() -> None:
    """Returns credentials when Keycloak is configured and enabled."""
    from security.keycloak_config import KeycloakConfig
    kc = KeycloakConfig(
        issuer_url="https://kc.example.com/realms/test",
        client_id="blitz-portal",
        client_secret="secret123",
        realm="test",
        ca_cert_path="",
        enabled=True,
    )

    with patch("api.routes.admin_keycloak.settings") as mock_settings, \
         patch("api.routes.admin_keycloak.get_keycloak_config", new_callable=AsyncMock, return_value=kc):
        mock_settings.internal_api_key = "test-key"
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/internal/keycloak/provider-config",
            headers={"X-Internal-Key": "test-key"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert data["client_id"] == "blitz-portal"
    assert data["client_secret"] == "secret123"
    assert data["issuer"] == "https://kc.example.com/realms/test"
