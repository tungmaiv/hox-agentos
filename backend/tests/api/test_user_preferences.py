"""
Tests for user preferences API — /api/users/me/preferences.

Covers:
  - GET /api/users/me/preferences returns defaults when no row exists
  - GET /api/users/me/preferences returns stored preferences when row exists
  - PUT /api/users/me/preferences creates a new row (upsert)
  - PUT /api/users/me/preferences updates an existing row (upsert)
  - PUT /api/users/me/preferences partial update — only thinking_mode, response_style unchanged
  - PUT /api/users/me/preferences returns 422 for invalid response_style value
  - GET /api/users/me/preferences returns 401 without auth
"""
import asyncio
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.db import Base, get_db
from core.models.user import UserContext
from core.models.user_preferences import UserPreferences  # noqa: F401 — required for metadata
from main import app
from security.deps import get_current_user


# ---------------------------------------------------------------------------
# User context helpers
# ---------------------------------------------------------------------------

_USER_ID = uuid4()


def make_user_ctx() -> UserContext:
    """Standard employee user context."""
    return UserContext(
        user_id=_USER_ID,
        email="user@blitz.local",
        username="test_user",
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
    yield session_factory
    app.dependency_overrides.pop(get_db, None)
    loop.run_until_complete(engine.dispose())
    loop.close()


@pytest.fixture
def auth_client(sqlite_db) -> TestClient:
    """TestClient with employee auth + SQLite DB."""
    app.dependency_overrides[get_current_user] = make_user_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# GET /api/users/me/preferences tests
# ---------------------------------------------------------------------------


def test_get_preferences_requires_jwt() -> None:
    """GET /api/users/me/preferences returns 401 without auth."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/users/me/preferences")
    assert response.status_code == 401


def test_get_preferences_default(auth_client: TestClient) -> None:
    """GET /api/users/me/preferences returns defaults when no row exists."""
    response = auth_client.get("/api/users/me/preferences")
    assert response.status_code == 200
    data = response.json()
    assert data["thinking_mode"] is False
    assert data["response_style"] == "concise"


def test_get_preferences_returns_stored(auth_client: TestClient, sqlite_db) -> None:
    """GET /api/users/me/preferences returns stored preferences when row exists."""
    # First PUT to create a row
    auth_client.put(
        "/api/users/me/preferences",
        json={"thinking_mode": True, "response_style": "detailed"},
    )
    # Now GET should return the stored values
    response = auth_client.get("/api/users/me/preferences")
    assert response.status_code == 200
    data = response.json()
    assert data["thinking_mode"] is True
    assert data["response_style"] == "detailed"


# ---------------------------------------------------------------------------
# PUT /api/users/me/preferences tests
# ---------------------------------------------------------------------------


def test_put_preferences_creates_row(auth_client: TestClient) -> None:
    """PUT /api/users/me/preferences upsert creates a new row when none exists."""
    response = auth_client.put(
        "/api/users/me/preferences",
        json={"thinking_mode": True, "response_style": "conversational"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["thinking_mode"] is True
    assert data["response_style"] == "conversational"


def test_put_preferences_updates_existing(auth_client: TestClient) -> None:
    """PUT /api/users/me/preferences upsert updates an existing row."""
    # Create initial row
    auth_client.put(
        "/api/users/me/preferences",
        json={"thinking_mode": False, "response_style": "concise"},
    )
    # Update it
    response = auth_client.put(
        "/api/users/me/preferences",
        json={"thinking_mode": True, "response_style": "detailed"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["thinking_mode"] is True
    assert data["response_style"] == "detailed"


def test_put_preferences_partial_update(auth_client: TestClient) -> None:
    """PUT with only thinking_mode leaves response_style unchanged."""
    # Set initial state
    auth_client.put(
        "/api/users/me/preferences",
        json={"thinking_mode": False, "response_style": "detailed"},
    )
    # Partial update — only thinking_mode
    response = auth_client.put(
        "/api/users/me/preferences",
        json={"thinking_mode": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["thinking_mode"] is True
    # response_style should remain "detailed" (not reset to default)
    assert data["response_style"] == "detailed"


def test_put_invalid_response_style(auth_client: TestClient) -> None:
    """PUT /api/users/me/preferences returns 422 for invalid response_style value."""
    response = auth_client.put(
        "/api/users/me/preferences",
        json={"thinking_mode": False, "response_style": "verbose"},
    )
    assert response.status_code == 422
