"""
Tests for Keycloak Admin API role fetching.

Verifies:
- Successful role fetch via client_credentials grant
- Keycloak unreachable (ConnectError propagates to caller)
- Role endpoint returns 403 (HTTPStatusError propagates)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx


@pytest.mark.asyncio
async def test_fetch_user_realm_roles_success():
    """Mock token + roles endpoints, assert correct role list returned."""
    user_id = "test-user-uuid-1234"

    mock_token_response = MagicMock()
    mock_token_response.json.return_value = {"access_token": "fake-admin-token"}
    mock_token_response.raise_for_status = MagicMock()

    mock_roles_response = MagicMock()
    mock_roles_response.json.return_value = [
        {"name": "employee"},
        {"name": "it-admin"},
    ]
    mock_roles_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_token_response)
    mock_client.get = AsyncMock(return_value=mock_roles_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("security.keycloak_client.httpx.AsyncClient", return_value=mock_client):
        from security.keycloak_client import fetch_user_realm_roles

        roles = await fetch_user_realm_roles(user_id)

    assert roles == ["employee", "it-admin"]
    mock_client.post.assert_called_once()
    mock_client.get.assert_called_once()

    # Verify the get call includes the Bearer token
    get_call_kwargs = mock_client.get.call_args
    assert "Authorization" in get_call_kwargs.kwargs.get("headers", {})
    assert get_call_kwargs.kwargs["headers"]["Authorization"] == "Bearer fake-admin-token"


@pytest.mark.asyncio
async def test_fetch_user_realm_roles_keycloak_unreachable():
    """ConnectError from token endpoint propagates (not caught)."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("security.keycloak_client.httpx.AsyncClient", return_value=mock_client):
        from security.keycloak_client import fetch_user_realm_roles

        with pytest.raises(httpx.ConnectError):
            await fetch_user_realm_roles("some-user-id")


@pytest.mark.asyncio
async def test_fetch_user_realm_roles_403_forbidden():
    """Roles endpoint returns 403 — raises HTTPStatusError."""
    mock_token_response = MagicMock()
    mock_token_response.json.return_value = {"access_token": "fake-admin-token"}
    mock_token_response.raise_for_status = MagicMock()

    # Build a realistic HTTPStatusError for the 403 response
    mock_request = httpx.Request("GET", "https://keycloak.test/admin/realms/test/users/uid/role-mappings/realm")
    mock_response = httpx.Response(403, request=mock_request)

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_token_response)
    mock_client.get = AsyncMock(return_value=MagicMock(
        raise_for_status=MagicMock(
            side_effect=httpx.HTTPStatusError("Forbidden", request=mock_request, response=mock_response)
        ),
    ))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("security.keycloak_client.httpx.AsyncClient", return_value=mock_client):
        from security.keycloak_client import fetch_user_realm_roles

        with pytest.raises(httpx.HTTPStatusError):
            await fetch_user_realm_roles("some-user-id")
