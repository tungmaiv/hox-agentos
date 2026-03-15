"""
Tests for GET /api/auth/config — sso_available field (Plan 26-01).

Covers:
  - sso_available=true when circuit breaker closed and SSO enabled
  - sso_available=false when circuit breaker open (even if SSO enabled)
  - sso_available=false when SSO disabled
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from security.keycloak_config import KeycloakConfig


def _mock_kc(enabled: bool = True) -> KeycloakConfig:
    return KeycloakConfig(
        issuer_url="https://kc.example.com/realms/test",
        client_id="blitz-portal",
        client_secret="s",
        realm="test",
        ca_cert_path="",
        enabled=enabled,
    )


def test_sso_available_true_when_circuit_closed() -> None:
    """GET /api/auth/config returns sso_available=true when circuit breaker is closed."""
    kc = _mock_kc()
    with (
        patch("api.routes.auth_config.get_keycloak_config", new_callable=AsyncMock, return_value=kc),
        patch("api.routes.auth_config.get_circuit_breaker") as mock_cb,
    ):
        mock_cb_instance = mock_cb.return_value
        mock_cb_instance.is_open = AsyncMock(return_value=False)

        client = TestClient(app)
        resp = client.get("/api/auth/config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["sso_enabled"] is True
    assert data["sso_available"] is True


def test_sso_available_false_when_circuit_open() -> None:
    """GET /api/auth/config returns sso_available=false when circuit breaker is open."""
    kc = _mock_kc()
    with (
        patch("api.routes.auth_config.get_keycloak_config", new_callable=AsyncMock, return_value=kc),
        patch("api.routes.auth_config.get_circuit_breaker") as mock_cb,
    ):
        mock_cb_instance = mock_cb.return_value
        mock_cb_instance.is_open = AsyncMock(return_value=True)

        client = TestClient(app)
        resp = client.get("/api/auth/config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["sso_enabled"] is True
    assert data["sso_available"] is False


def test_sso_available_false_when_sso_disabled() -> None:
    """GET /api/auth/config returns sso_available=false when SSO disabled."""
    with patch("api.routes.auth_config.get_keycloak_config", new_callable=AsyncMock, return_value=None):
        client = TestClient(app)
        resp = client.get("/api/auth/config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["sso_enabled"] is False
    assert data["sso_available"] is False
