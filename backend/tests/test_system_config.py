"""
Tests for GET /api/admin/config and PUT /api/admin/config/{key}.

Tests cover:
  - 401 when Authorization header is absent (Gate 1)
  - 403 when user lacks "tool:admin" permission (Gate 2 RBAC)
  - 200 + seeded values for admin user
  - PUT updates the value; subsequent GET returns updated value

DB dependency is overridden with an in-memory SQLite async session so tests
run without a live PostgreSQL instance.

Note: SQLite does not support JSONB natively. The in-memory session creates
tables from the ORM metadata using JSON column type for SQLite compatibility.
The SystemConfig.value column is JSONB in PostgreSQL but stores/retrieves
any JSON-serializable Python value regardless.
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
from core.models.system_config import SystemConfig  # noqa: F401 — registers in metadata
from core.models.user import UserContext
from main import app
from security.deps import get_current_user


# ---------------------------------------------------------------------------
# User context helpers
# ---------------------------------------------------------------------------


def make_admin_ctx() -> UserContext:
    """it-admin role has "tool:admin" permission — can access admin config."""
    return UserContext(
        user_id=uuid4(),
        email="admin@blitz.local",
        username="admin_user",
        roles=["it-admin"],
        groups=["/it"],
    )


def make_employee_ctx() -> UserContext:
    """employee role lacks "tool:admin" permission — blocked at Gate 2."""
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
def sqlite_db_with_seed():
    """
    Override get_db with an in-memory SQLite async session pre-seeded
    with two system_config rows matching migration 007 seed data.

    The fixture seeds a subset of the real rows — enough for tests to assert
    on key presence without depending on the full PostgreSQL schema.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # Seed a few rows for the GET test
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add(SystemConfig(key="agent.email.enabled", value=True))
            session.add(SystemConfig(key="agent.calendar.enabled", value=True))
            session.add(SystemConfig(key="agent.project.enabled", value=True))
            await session.commit()

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
def sqlite_db_empty():
    """Override get_db with empty in-memory SQLite session (no seed data)."""
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_get_config_requires_jwt() -> None:
    """GET /api/admin/config returns 401 without Authorization header."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/admin/config")
    assert response.status_code == 401


def test_get_config_requires_admin_role(sqlite_db_empty: None) -> None:
    """employee role lacks tool:admin permission — GET returns 403."""
    app.dependency_overrides[get_current_user] = make_employee_ctx
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/admin/config")
    app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403


def test_get_config_returns_seeded_values(sqlite_db_with_seed: None) -> None:
    """Admin user gets 200 with all seeded config keys present."""
    app.dependency_overrides[get_current_user] = make_admin_ctx
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/admin/config")
    app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    data = response.json()
    assert "agent.email.enabled" in data
    assert "agent.calendar.enabled" in data
    assert "agent.project.enabled" in data
    assert data["agent.email.enabled"] is True


def test_put_config_updates_value(sqlite_db_with_seed: None) -> None:
    """PUT /api/admin/config/{key} updates value; subsequent GET returns new value."""
    app.dependency_overrides[get_current_user] = make_admin_ctx
    client = TestClient(app, raise_server_exceptions=False)

    # Disable email agent
    put_response = client.put(
        "/api/admin/config/agent.email.enabled",
        json={"value": False},
    )
    assert put_response.status_code == 200
    assert put_response.json()["value"] is False

    # Verify the change persists in the same session
    get_response = client.get("/api/admin/config")
    app.dependency_overrides.pop(get_current_user, None)

    assert get_response.status_code == 200
    data = get_response.json()
    assert data["agent.email.enabled"] is False


def test_put_config_returns_422_for_missing_value() -> None:
    """PUT /api/admin/config/{key} with missing 'value' field returns 422."""
    app.dependency_overrides[get_current_user] = make_admin_ctx
    client = TestClient(app, raise_server_exceptions=False)
    # Send empty body — missing required 'value' field
    response = client.put("/api/admin/config/agent.email.enabled", json={})
    app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 422
