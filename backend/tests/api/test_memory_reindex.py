"""Tests for POST /api/admin/memory/reindex endpoint."""
import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.db import Base, get_db
from core.models.role_permission import RolePermission  # noqa: F401
from core.models.user import UserContext
from main import app
from security.deps import get_current_user


# ---------------------------------------------------------------------------
# User context helpers
# ---------------------------------------------------------------------------


def make_admin_ctx() -> UserContext:
    """it-admin role has tool:admin permission."""
    return UserContext(
        user_id=uuid4(),
        email="admin@blitz.local",
        username="admin_user",
        roles=["it-admin"],
        groups=["/it"],
    )


def make_employee_ctx() -> UserContext:
    """employee role lacks tool:admin permission."""
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
    yield
    app.dependency_overrides.pop(get_db, None)
    loop.run_until_complete(engine.dispose())
    loop.close()


@pytest.fixture
def admin_client(sqlite_db: None) -> TestClient:
    """TestClient with admin (it-admin) auth + SQLite DB."""
    app.dependency_overrides[get_current_user] = make_admin_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def employee_client(sqlite_db: None) -> TestClient:
    """TestClient with employee role (no tool:admin) + SQLite DB."""
    app.dependency_overrides[get_current_user] = make_employee_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_reindex_requires_admin(employee_client: TestClient) -> None:
    """Non-admin users get 403."""
    resp = employee_client.post(
        "/api/admin/memory/reindex",
        json={"confirm": True},
    )
    assert resp.status_code == 403


def test_reindex_requires_confirm(admin_client: TestClient) -> None:
    """Missing confirm=true returns 422."""
    resp = admin_client.post(
        "/api/admin/memory/reindex",
        json={"confirm": False},
    )
    assert resp.status_code == 422


def test_reindex_enqueues_task(admin_client: TestClient) -> None:
    """confirm=true returns 202 with job_id and enqueues Celery task."""
    with patch("api.routes.admin_memory.reindex_memory_task") as mock_task:
        mock_task.delay.return_value = MagicMock(id="test-job-123")
        resp = admin_client.post(
            "/api/admin/memory/reindex",
            json={"confirm": True},
        )
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    mock_task.delay.assert_called_once()
