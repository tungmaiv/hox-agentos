# backend/tests/test_user_instructions.py
"""Tests for GET /api/user/instructions and PUT /api/user/instructions."""
from uuid import uuid4

from fastapi.testclient import TestClient

from main import app
from core.models.user import UserContext
from security.deps import get_current_user


def _make_user(roles: list[str] | None = None) -> UserContext:
    return UserContext(
        user_id=uuid4(),
        email="test@blitz.local",
        username="testuser",
        roles=roles or ["employee"],
        groups=[],
    )


def test_get_instructions_requires_jwt() -> None:
    """GET /api/user/instructions returns 401 without JWT."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/user/instructions/")
    assert response.status_code == 401


def test_put_instructions_requires_jwt() -> None:
    """PUT /api/user/instructions returns 401 without JWT."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.put("/api/user/instructions/", json={"instructions": "test"})
    assert response.status_code == 401


def test_get_instructions_route_exists() -> None:
    """GET /api/user/instructions/ is registered (not 404)."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/user/instructions/")
    assert response.status_code != 404


def test_put_instructions_route_exists() -> None:
    """PUT /api/user/instructions/ is registered (not 404)."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.put("/api/user/instructions/", json={"instructions": "test"})
    assert response.status_code != 404
