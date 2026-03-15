"""
Tests for SSO health checker — Plan 26-01.

Covers:
  - Healthy status when config exists and JWKS reachable
  - Connectivity category when JWKS unreachable
  - Certificate category on TLS errors
  - Config category when no Keycloak config
  - All 4 categories returned
  - Circuit breaker state included in response
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from security.sso_health import (
    SSOHealthStatus,
    check_sso_health,
)


def _mock_kc_config(enabled: bool = True):
    """Create a mock KeycloakConfig."""
    from security.keycloak_config import KeycloakConfig

    return KeycloakConfig(
        issuer_url="https://keycloak.example.com/realms/test",
        client_id="blitz-portal",
        client_secret="secret",
        realm="test",
        ca_cert_path="",
        enabled=enabled,
    )


@pytest.mark.asyncio
async def test_healthy_when_jwks_reachable() -> None:
    """Returns healthy when Keycloak config exists and JWKS is reachable."""
    kc = _mock_kc_config()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"keys": [{"kid": "test-key"}]}
    mock_resp.raise_for_status = MagicMock()

    with (
        patch("security.sso_health.get_keycloak_config", new_callable=AsyncMock, return_value=kc),
        patch("security.sso_health._fetch_jwks_with_timing", new_callable=AsyncMock, return_value=(mock_resp, 0.5)),
        patch("security.sso_health._check_certificate", new_callable=AsyncMock, return_value=("green", "Certificate valid")),
    ):
        result = await check_sso_health()

    assert isinstance(result, SSOHealthStatus)
    assert result.overall in ("healthy", "degraded")
    categories_by_name = {c.name: c for c in result.categories}
    assert "connectivity" in categories_by_name
    assert categories_by_name["connectivity"].status == "green"


@pytest.mark.asyncio
async def test_connectivity_red_when_unreachable() -> None:
    """Returns connectivity=red when JWKS endpoint is unreachable."""
    kc = _mock_kc_config()

    with (
        patch("security.sso_health.get_keycloak_config", new_callable=AsyncMock, return_value=kc),
        patch("security.sso_health._fetch_jwks_with_timing", new_callable=AsyncMock, side_effect=Exception("Connection refused")),
        patch("security.sso_health._check_certificate", new_callable=AsyncMock, return_value=("red", "Connection refused")),
    ):
        result = await check_sso_health()

    categories_by_name = {c.name: c for c in result.categories}
    assert categories_by_name["connectivity"].status == "red"


@pytest.mark.asyncio
async def test_certificate_category_on_tls_error() -> None:
    """Returns certificate=red on TLS certificate error."""
    kc = _mock_kc_config()

    with (
        patch("security.sso_health.get_keycloak_config", new_callable=AsyncMock, return_value=kc),
        patch("security.sso_health._fetch_jwks_with_timing", new_callable=AsyncMock, side_effect=Exception("SSL: CERTIFICATE_VERIFY_FAILED")),
        patch("security.sso_health._check_certificate", new_callable=AsyncMock, return_value=("red", "TLS certificate verification failed")),
    ):
        result = await check_sso_health()

    categories_by_name = {c.name: c for c in result.categories}
    assert categories_by_name["certificate"].status == "red"


@pytest.mark.asyncio
async def test_config_red_when_no_config() -> None:
    """Returns config=red when no Keycloak configuration found."""
    with patch("security.sso_health.get_keycloak_config", new_callable=AsyncMock, return_value=None):
        result = await check_sso_health()

    categories_by_name = {c.name: c for c in result.categories}
    assert categories_by_name["config"].status == "red"
    assert result.overall == "unhealthy"


@pytest.mark.asyncio
async def test_all_four_categories_returned() -> None:
    """Result always contains all 4 category statuses."""
    kc = _mock_kc_config()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"keys": [{"kid": "k1"}]}
    mock_resp.raise_for_status = MagicMock()

    with (
        patch("security.sso_health.get_keycloak_config", new_callable=AsyncMock, return_value=kc),
        patch("security.sso_health._fetch_jwks_with_timing", new_callable=AsyncMock, return_value=(mock_resp, 0.3)),
        patch("security.sso_health._check_certificate", new_callable=AsyncMock, return_value=("green", "OK")),
    ):
        result = await check_sso_health()

    category_names = {c.name for c in result.categories}
    assert category_names == {"certificate", "config", "connectivity", "performance"}


@pytest.mark.asyncio
async def test_circuit_breaker_state_included() -> None:
    """Health response includes circuit breaker state dict."""
    kc = _mock_kc_config()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"keys": []}
    mock_resp.raise_for_status = MagicMock()

    with (
        patch("security.sso_health.get_keycloak_config", new_callable=AsyncMock, return_value=kc),
        patch("security.sso_health._fetch_jwks_with_timing", new_callable=AsyncMock, return_value=(mock_resp, 0.1)),
        patch("security.sso_health._check_certificate", new_callable=AsyncMock, return_value=("green", "OK")),
    ):
        result = await check_sso_health()

    assert result.circuit_breaker is not None
    assert "state" in result.circuit_breaker
    assert "failure_count" in result.circuit_breaker
