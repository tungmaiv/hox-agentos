"""
Tests for GET /health and GET /api/auth/config — no authentication required.

These are integration tests using FastAPI's TestClient.
The health endpoint must always return 200 regardless of auth state.
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_returns_200() -> None:
    """Health check must return 200 OK with {status: ok}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_no_auth_required() -> None:
    """Health check must work without Authorization header."""
    response = client.get("/health", headers={})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_response_schema() -> None:
    """Response must match HealthResponse schema (status + auth fields)."""
    response = client.get("/health")
    data = response.json()
    assert "status" in data
    assert "auth" in data
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_includes_auth_field_local_only():
    """GET /health returns auth='local-only' when no Keycloak config."""
    with patch("api.routes.health.get_keycloak_config", new_callable=AsyncMock, return_value=None):
        client = TestClient(app)
        resp = client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["auth"] == "local-only"


@pytest.mark.asyncio
async def test_health_includes_auth_field_keycloak():
    """GET /health returns auth='local+keycloak' when Keycloak is configured."""
    from security.keycloak_config import KeycloakConfig

    kc = KeycloakConfig(
        issuer_url="https://kc.example.com/realms/test",
        client_id="blitz-portal", client_secret="s", realm="test",
        ca_cert_path="", enabled=True,
    )
    with patch("api.routes.health.get_keycloak_config", new_callable=AsyncMock, return_value=kc):
        client = TestClient(app)
        resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json()["auth"] == "local+keycloak"


def test_auth_config_local_only():
    """GET /api/auth/config returns local-only when no Keycloak config."""
    with patch("api.routes.auth_config.get_keycloak_config", new_callable=AsyncMock, return_value=None):
        client = TestClient(app)
        resp = client.get("/api/auth/config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["auth"] == "local-only"
    assert data.get("sso_enabled") is not True


def test_auth_config_keycloak_enabled():
    """GET /api/auth/config returns sso_enabled=true when Keycloak is active."""
    from security.keycloak_config import KeycloakConfig

    kc = KeycloakConfig(
        issuer_url="https://kc.example.com/realms/test",
        client_id="blitz-portal", client_secret="s", realm="test",
        ca_cert_path="", enabled=True,
    )
    with patch("api.routes.auth_config.get_keycloak_config", new_callable=AsyncMock, return_value=kc):
        client = TestClient(app)
        resp = client.get("/api/auth/config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["auth"] == "local+keycloak"
    assert data["sso_enabled"] is True
