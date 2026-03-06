"""Test JWKS thundering herd prevention via asyncio.Lock."""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from security.keycloak_config import KeycloakConfig

# Minimal config for JWKS lock tests — only ca_cert_path and jwks_url matter here
_TEST_CONFIG = KeycloakConfig(
    issuer_url="https://kc.test/realms/test",
    client_id="test-client",
    client_secret="test-secret",
    realm="test",
    ca_cert_path="",
    enabled=True,
)


@pytest.mark.asyncio
async def test_concurrent_jwks_refresh_calls_remote_once():
    """Concurrent expired JWKS refreshes fire only one HTTP request."""
    import security.jwt as jwt_module
    # Force cache expiry
    jwt_module._JWKS_CACHE = {}
    jwt_module._jwks_fetched_at = 0.0

    call_count = 0

    async def slow_fetch(config: KeycloakConfig):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)  # simulate network delay
        return {"keys": []}

    with patch("security.jwt._fetch_jwks_from_remote", side_effect=slow_fetch):
        # Fire 5 concurrent requests
        results = await asyncio.gather(*[jwt_module._get_jwks(_TEST_CONFIG) for _ in range(5)])

    # All 5 should get a result, but only 1 remote fetch should have happened
    assert len(results) == 5
    assert call_count == 1
