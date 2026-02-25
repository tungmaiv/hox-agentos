# backend/tests/test_runtime.py
"""
TDD tests for gateway/runtime.py CopilotKit endpoint.

Tests verify:
- Route is registered (not 404)
- JWT gate: 401 without Authorization header
- Permission gate: 403 for role lacking 'chat' permission
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4

from main import app
from security.deps import get_current_user
from core.models.user import UserContext


def _make_user_ctx(roles: list[str]) -> UserContext:
    return UserContext(
        user_id=uuid4(),
        email="user@blitz.local",
        username="testuser",
        roles=roles,
        groups=[],
    )


def test_copilotkit_endpoint_exists_not_404():
    """POST /api/copilotkit must be registered as a route (not return 404)."""
    client = TestClient(app, raise_server_exceptions=False)
    # Without auth we expect 401 — not 404 (which means route is missing)
    response = client.post("/api/copilotkit", json={})
    assert response.status_code != 404, (
        f"POST /api/copilotkit returned 404 — route not registered in main.py. "
        f"Add: app.include_router(runtime.router)"
    )


def test_copilotkit_endpoint_returns_401_without_jwt():
    """POST /api/copilotkit returns 401 when Authorization header is absent."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/copilotkit", json={})
    assert response.status_code == 401, (
        f"Expected 401 without JWT, got {response.status_code}"
    )


def test_copilotkit_endpoint_returns_403_for_no_permission():
    """POST /api/copilotkit returns 403 for a role with no 'chat' permission."""
    def mock_no_perm_user():
        return _make_user_ctx(roles=["unknown_role_with_no_permissions"])

    app.dependency_overrides[get_current_user] = mock_no_perm_user
    client = TestClient(app, raise_server_exceptions=False)
    try:
        response = client.post("/api/copilotkit", json={})
        assert response.status_code == 403, (
            f"Expected 403 for user with no 'chat' permission, got {response.status_code}"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
