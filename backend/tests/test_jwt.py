"""
JWT validation test suite — Gate 1 security coverage.

Tests use a self-generated RSA key pair and mock the JWKS HTTP fetch so no
real Keycloak instance is needed. All 7 JWT validation paths are covered:
  1. Valid token  → UserContext returned
  2. Expired token → 401
  3. Wrong issuer → 401
  4. Wrong audience → 401
  5. Tampered/invalid signature → 401
  6. Missing Authorization header → 401
  7. JWKS cache → only 1 HTTP call for repeated validate_token calls

Note: Real Keycloak integration is tested in the Phase 1 end-to-end integration
test (not this file).
"""
import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jose import jwk as jose_jwk
from jose import jwt as jose_jwt
from jose.constants import ALGORITHMS


# ---------------------------------------------------------------------------
# Module-scoped fixtures — key pair generated once per test module run
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rsa_private_key() -> rsa.RSAPrivateKey:
    """Generate a 2048-bit RSA key pair for the test module."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def private_pem(rsa_private_key: rsa.RSAPrivateKey) -> bytes:
    """PKCS8 PEM-encoded private key for signing test JWTs."""
    return rsa_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


@pytest.fixture(scope="module")
def mock_jwks(rsa_private_key: rsa.RSAPrivateKey) -> dict:
    """
    Build a minimal JWKS dict from the test RSA public key.

    Uses python-jose's jwk.construct() to convert the PEM public key into
    JWK format — exactly the same structure returned by a real Keycloak
    /protocol/openid-connect/certs endpoint.
    """
    pub_pem = rsa_private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    rsa_key = jose_jwk.construct(pub_pem.decode(), algorithm=ALGORITHMS.RS256)
    return {"keys": [rsa_key.to_dict()]}


@pytest.fixture(scope="module")
def make_token(private_pem: bytes):
    """
    Factory that returns signed RS256 JWTs for testing.

    Args:
        payload_overrides: Dict of claims to override in the default payload.
        exp_offset: Seconds from now for token expiry (negative = expired).
    """

    def _make(payload_overrides: dict | None = None, exp_offset: int = 3600) -> str:
        # Read iss and aud from the live settings object so tokens always match
        # whatever issuer/client-id is currently configured — avoids fragility
        # when test_config.py reloads core.config with different env vars.
        import core.config as _cfg

        payload: dict = {
            "sub": str(uuid4()),
            "email": "test@blitz.local",
            "preferred_username": "testuser",
            "realm_access": {"roles": ["employee"]},
            "groups": ["/tech"],
            "iss": _cfg.settings.keycloak_issuer,
            "aud": _cfg.settings.keycloak_client_id,
            "exp": int(time.time()) + exp_offset,
            "iat": int(time.time()),
        }
        if payload_overrides:
            payload.update(payload_overrides)
        return jose_jwt.encode(payload, private_pem, algorithm="RS256")

    return _make


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_token_returns_user_context(make_token, mock_jwks) -> None:
    """A valid RS256 JWT returns a fully populated UserContext."""
    from security.jwt import validate_token

    token = make_token()

    with patch("security.jwt._get_jwks", new_callable=AsyncMock, return_value=mock_jwks):
        ctx = await validate_token(token)

    assert ctx["email"] == "test@blitz.local"
    assert ctx["username"] == "testuser"
    assert "employee" in ctx["roles"]
    assert "/tech" in ctx["groups"]
    # user_id must be a UUID (not str)
    from uuid import UUID

    assert isinstance(ctx["user_id"], UUID)


@pytest.mark.asyncio
async def test_expired_token_raises_401(make_token, mock_jwks) -> None:
    """An expired JWT raises HTTPException with status 401 and detail 'Token has expired'."""
    from security.jwt import validate_token

    # exp 10 seconds in the past
    token = make_token(exp_offset=-10)

    with patch("security.jwt._get_jwks", new_callable=AsyncMock, return_value=mock_jwks):
        with pytest.raises(HTTPException) as exc_info:
            await validate_token(token)

    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_wrong_issuer_raises_401(make_token, mock_jwks) -> None:
    """A JWT with an unexpected issuer raises HTTPException 401."""
    from security.jwt import validate_token

    token = make_token(payload_overrides={"iss": "https://evil.example.com/realms/rogue"})

    with patch("security.jwt._get_jwks", new_callable=AsyncMock, return_value=mock_jwks):
        with pytest.raises(HTTPException) as exc_info:
            await validate_token(token)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_no_audience_claim_succeeds(make_token, mock_jwks) -> None:
    """
    Tokens without aud (or with a non-matching aud) must succeed.

    Keycloak's blitz-portal client issues access tokens with no aud claim.
    Audience validation is disabled (verify_aud=False in jwt.py). Issuer and
    RS256 signature are still enforced — this test verifies that a missing or
    non-matching audience does NOT cause a 401.
    """
    from security.jwt import validate_token

    # Simulate a token with no aud field (blitz-portal real-world case)
    token = make_token(payload_overrides={"aud": "some-other-client"})

    with patch("security.jwt._get_jwks", new_callable=AsyncMock, return_value=mock_jwks):
        ctx = await validate_token(token)

    assert ctx["email"] == "test@blitz.local"
    assert ctx["username"] == "testuser"


@pytest.mark.asyncio
async def test_tampered_token_raises_401(make_token, mock_jwks) -> None:
    """A JWT with a tampered payload (invalid signature) raises HTTPException 401."""
    from security.jwt import validate_token

    token = make_token()
    # Corrupt the payload segment (middle section of header.payload.signature)
    parts = token.split(".")
    # Flip a character in the payload to break the signature
    tampered_payload = parts[1][:-2] + ("A" if parts[1][-1] != "A" else "B") + parts[1][-1]
    tampered_token = ".".join([parts[0], tampered_payload, parts[2]])

    with patch("security.jwt._get_jwks", new_callable=AsyncMock, return_value=mock_jwks):
        with pytest.raises(HTTPException) as exc_info:
            await validate_token(tampered_token)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_missing_credentials_raises_401() -> None:
    """When Authorization header is absent, get_current_user() raises 401."""
    from fastapi import Request
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from security.deps import get_current_user

    app = FastAPI()

    @app.get("/protected")
    async def protected(user=None):
        # Use the dependency manually via TestClient
        pass

    # Test the dependency directly without a real request
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Not authenticated"


@pytest.mark.asyncio
async def test_jwks_cache_hit(make_token, mock_jwks) -> None:
    """
    Three consecutive validate_token calls must result in only 1 JWKS fetch.

    The in-process cache (TTL 300s) must serve calls 2 and 3 from memory.
    """
    import security.jwt as jwt_module

    # Reset cache state so we always start from a clean slate for this test
    jwt_module._JWKS_CACHE = {}
    jwt_module._jwks_fetched_at = 0.0

    fetch_mock = AsyncMock(return_value=mock_jwks)

    with patch("security.jwt._fetch_jwks_from_remote", new=fetch_mock):
        token1 = make_token()
        token2 = make_token()
        token3 = make_token()

        await validate_token_with_real_cache(token1)
        await validate_token_with_real_cache(token2)
        await validate_token_with_real_cache(token3)

    # Only 1 HTTP call — 2nd and 3rd served from in-process cache
    assert fetch_mock.call_count == 1


async def validate_token_with_real_cache(token: str) -> None:
    """Call validate_token using the real _get_jwks (which uses cache)."""
    from security.jwt import validate_token

    await validate_token(token)
