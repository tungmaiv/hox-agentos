"""
Tests for admin SSO health API — Plan 26-01.

Covers:
  - GET /api/admin/sso/health — 200 with categories + circuit breaker (admin)
  - GET /api/admin/sso/health — 403 for non-admin
  - PUT /api/admin/sso/circuit-breaker/config — updates thresholds (admin)
"""
import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
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
from core.models.platform_config import PlatformConfig  # noqa: F401
from core.models.admin_notification import AdminNotification  # noqa: F401
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


@pytest.fixture
def sqlite_db():
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
    app.dependency_overrides[get_current_user] = make_admin_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def employee_client(sqlite_db: None) -> TestClient:
    app.dependency_overrides[get_current_user] = make_employee_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# GET /api/admin/sso/health
# ---------------------------------------------------------------------------


def test_sso_health_returns_categories_and_circuit_breaker(admin_client: TestClient) -> None:
    """GET /api/admin/sso/health returns 200 with all 4 categories + circuit breaker."""
    from security.sso_health import CategoryCheck, SSOHealthStatus
    from datetime import datetime, timezone

    mock_status = SSOHealthStatus(
        overall="healthy",
        categories=[
            CategoryCheck(name="certificate", status="green", detail="OK"),
            CategoryCheck(name="config", status="green", detail="OK"),
            CategoryCheck(name="connectivity", status="green", detail="OK"),
            CategoryCheck(name="performance", status="green", detail="0.3s"),
        ],
        circuit_breaker={"state": "CLOSED", "failure_count": 0},
        checked_at=datetime.now(timezone.utc),
    )

    with patch("api.routes.admin_sso_health.check_sso_health", new_callable=AsyncMock, return_value=mock_status):
        resp = admin_client.get("/api/admin/sso/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["overall"] == "healthy"
    assert len(data["categories"]) == 4
    assert data["circuit_breaker"]["state"] == "CLOSED"


def test_sso_health_403_for_non_admin(employee_client: TestClient) -> None:
    """GET /api/admin/sso/health returns 403 for non-admin."""
    resp = employee_client.get("/api/admin/sso/health")
    assert resp.status_code == 403


def test_update_circuit_breaker_config(admin_client: TestClient) -> None:
    """PUT /api/admin/sso/circuit-breaker/config updates thresholds."""
    resp = admin_client.put(
        "/api/admin/sso/circuit-breaker/config",
        json={
            "failure_threshold": 10,
            "recovery_timeout_seconds": 120,
            "half_open_max_calls": 2,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["failure_threshold"] == 10
    assert data["recovery_timeout_seconds"] == 120
