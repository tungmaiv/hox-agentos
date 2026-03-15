"""
Tests for MCP server admin routes — /api/admin/mcp-servers.

Covers:
  - POST /test endpoint returns failure for non-reachable URL
  - POST /test endpoint requires admin authentication
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
from core.models.agent_definition import AgentDefinition  # noqa: F401
from core.models.artifact_permission import ArtifactPermission  # noqa: F401
from core.models.role_permission import RolePermission  # noqa: F401
from core.models.skill_definition import SkillDefinition  # noqa: F401
from core.models.tool_definition import ToolDefinition  # noqa: F401
from core.models.user_artifact_permission import UserArtifactPermission  # noqa: F401
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
    """TestClient with admin auth + SQLite DB."""
    app.dependency_overrides[get_current_user] = make_admin_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client  # type: ignore[misc]
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Tests: POST /api/admin/mcp-servers/test
# ---------------------------------------------------------------------------


def test_mcp_test_requires_auth() -> None:
    """POST /api/admin/mcp-servers/test returns 401 without auth."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/admin/mcp-servers/test",
        json={"url": "http://localhost:9999"},
    )
    assert response.status_code == 401


def test_mcp_test_requires_admin(sqlite_db: None) -> None:
    """POST /api/admin/mcp-servers/test returns 403 for non-admin."""
    app.dependency_overrides[get_current_user] = make_employee_ctx
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/admin/mcp-servers/test",
        json={"url": "http://localhost:9999"},
    )
    app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403


def test_mcp_test_unreachable_url(admin_client: TestClient) -> None:
    """POST /api/admin/mcp-servers/test with unreachable URL returns failure."""
    response = admin_client.post(
        "/api/admin/mcp-servers/test",
        json={"url": "http://localhost:19999"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["error"] is not None
    assert data["hint"] is not None
    assert isinstance(data["latency_ms"], int)
