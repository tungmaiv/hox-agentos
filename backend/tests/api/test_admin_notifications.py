"""
Tests for admin notifications API — Plan 26-01.

Covers:
  - GET /api/admin/notifications — list (admin)
  - GET /api/admin/notifications?unread_only=true — filter unread
  - POST /api/admin/notifications/{id}/read — mark as read
  - POST /api/admin/notifications/read-all — mark all as read
  - GET /api/admin/notifications/count — total + unread counts
  - 403 for non-admin users
"""
import asyncio
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.db import Base, get_db
from core.models.admin_notification import AdminNotification
from core.models.role_permission import RolePermission  # noqa: F401
from core.models.platform_config import PlatformConfig  # noqa: F401
from core.models.user import UserContext
from main import app
from security.deps import get_current_user


# ---------------------------------------------------------------------------
# User context helpers
# ---------------------------------------------------------------------------


def make_admin_ctx() -> UserContext:
    return UserContext(
        user_id=uuid4(),
        email="admin@blitz.local",
        username="admin_user",
        roles=["it-admin"],
        groups=["/it"],
    )


def make_employee_ctx() -> UserContext:
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


_notification_session_factory = None


@pytest.fixture
def sqlite_db():
    global _notification_session_factory
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_setup())

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    _notification_session_factory = session_factory

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session_factory
    _notification_session_factory = None
    app.dependency_overrides.pop(get_db, None)
    loop.run_until_complete(engine.dispose())
    loop.close()


@pytest.fixture
def admin_client(sqlite_db) -> TestClient:
    app.dependency_overrides[get_current_user] = make_admin_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def employee_client(sqlite_db) -> TestClient:
    app.dependency_overrides[get_current_user] = make_employee_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


def _seed_notifications(session_factory, loop) -> list[uuid.UUID]:
    """Seed test notifications, return their IDs."""
    ids: list[uuid.UUID] = []

    async def _seed():
        async with session_factory() as session:
            async with session.begin():
                n1 = AdminNotification(
                    id=uuid4(),
                    category="sso_health",
                    severity="critical",
                    title="SSO Down",
                    message="Circuit breaker opened",
                    is_read=False,
                )
                n2 = AdminNotification(
                    id=uuid4(),
                    category="sso_health",
                    severity="info",
                    title="SSO Recovered",
                    message="Circuit breaker closed",
                    is_read=True,
                )
                session.add(n1)
                session.add(n2)
                ids.extend([n1.id, n2.id])

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_seed())
    loop.close()
    return ids


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_list_notifications(admin_client: TestClient, sqlite_db) -> None:
    """GET /api/admin/notifications returns notifications list."""
    ids = _seed_notifications(sqlite_db, None)
    resp = admin_client.get("/api/admin/notifications")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_list_unread_only(admin_client: TestClient, sqlite_db) -> None:
    """GET /api/admin/notifications?unread_only=true filters to unread."""
    ids = _seed_notifications(sqlite_db, None)
    resp = admin_client.get("/api/admin/notifications?unread_only=true")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["is_read"] is False


def test_mark_single_as_read(admin_client: TestClient, sqlite_db) -> None:
    """POST /api/admin/notifications/{id}/read marks as read."""
    ids = _seed_notifications(sqlite_db, None)
    unread_id = ids[0]
    resp = admin_client.post(f"/api/admin/notifications/{unread_id}/read")
    assert resp.status_code == 200

    # Verify it's now read
    list_resp = admin_client.get("/api/admin/notifications?unread_only=true")
    assert len(list_resp.json()) == 0


def test_mark_all_as_read(admin_client: TestClient, sqlite_db) -> None:
    """POST /api/admin/notifications/read-all marks all as read."""
    _seed_notifications(sqlite_db, None)
    resp = admin_client.post("/api/admin/notifications/read-all")
    assert resp.status_code == 200

    list_resp = admin_client.get("/api/admin/notifications?unread_only=true")
    assert len(list_resp.json()) == 0


def test_notification_count(admin_client: TestClient, sqlite_db) -> None:
    """GET /api/admin/notifications/count returns total + unread."""
    _seed_notifications(sqlite_db, None)
    resp = admin_client.get("/api/admin/notifications/count")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["unread"] == 1


def test_notifications_403_for_non_admin(employee_client: TestClient) -> None:
    """All notification endpoints return 403 for non-admin."""
    assert employee_client.get("/api/admin/notifications").status_code == 403
    assert employee_client.get("/api/admin/notifications/count").status_code == 403
    assert employee_client.post("/api/admin/notifications/read-all").status_code == 403
