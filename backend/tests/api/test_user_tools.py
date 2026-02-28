"""
Tests for user-facing tool API — /api/tools (GET /).

Covers:
  - GET /api/tools returns only active tools with is_active=True
  - GET /api/tools excludes tools denied by artifact_permissions for user's role
  - GET /api/tools returns ToolListItem shape
  - 401 without auth
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
from core.models.artifact_permission import ArtifactPermission
from core.models.role_permission import RolePermission  # noqa: F401
from core.models.skill_definition import SkillDefinition  # noqa: F401
from core.models.tool_definition import ToolDefinition
from core.models.user_artifact_permission import UserArtifactPermission  # noqa: F401
from core.models.user import UserContext
from main import app
from security.deps import get_current_user


# ---------------------------------------------------------------------------
# User context helpers
# ---------------------------------------------------------------------------

_EMPLOYEE_ID = uuid4()


def make_employee_ctx() -> UserContext:
    """Employee role has 'chat' permission."""
    return UserContext(
        user_id=_EMPLOYEE_ID,
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
    yield session_factory
    app.dependency_overrides.pop(get_db, None)
    loop.run_until_complete(engine.dispose())
    loop.close()


@pytest.fixture
def seeded_client(sqlite_db):
    """TestClient with employee auth + pre-seeded tools."""
    session_factory = sqlite_db

    async def _seed():
        async with session_factory() as session:
            # Active tool
            t1 = ToolDefinition(
                name="email.fetch",
                display_name="Fetch Emails",
                description="Fetch recent emails",
                handler_type="backend",
                status="active",
                is_active=True,
            )
            # Active MCP tool
            t2 = ToolDefinition(
                name="crm.get_tasks",
                display_name="Get CRM Tasks",
                description="Get tasks from CRM",
                handler_type="mcp",
                status="active",
                is_active=True,
            )
            # Disabled tool
            t3 = ToolDefinition(
                name="disabled_tool",
                display_name="Disabled Tool",
                description="Not available",
                handler_type="backend",
                status="disabled",
                is_active=False,
            )
            # Active status but not activated version
            t4 = ToolDefinition(
                name="inactive_tool",
                display_name="Inactive Tool",
                description="Not activated",
                handler_type="backend",
                status="active",
                is_active=False,
            )
            session.add_all([t1, t2, t3, t4])
            await session.commit()

    loop = asyncio.get_event_loop_policy().new_event_loop()
    loop.run_until_complete(_seed())

    app.dependency_overrides[get_current_user] = make_employee_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client, session_factory
    app.dependency_overrides.pop(get_current_user, None)
    loop.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_list_tools_requires_jwt() -> None:
    """GET /api/tools returns 401 without auth."""
    client = TestClient(app, raise_server_exceptions=False)
    # GET /api/tools is the user listing route (not /api/tools/call which is POST)
    response = client.get("/api/tools")
    assert response.status_code == 401


def test_list_tools_returns_active_only(seeded_client) -> None:
    """GET /api/tools returns only active tools with is_active=True."""
    client, _ = seeded_client
    response = client.get("/api/tools")
    assert response.status_code == 200
    data = response.json()
    names = [t["name"] for t in data]
    assert "email.fetch" in names
    assert "crm.get_tasks" in names
    assert "disabled_tool" not in names
    assert "inactive_tool" not in names


def test_list_tools_excludes_denied(seeded_client) -> None:
    """GET /api/tools excludes tools denied by artifact_permissions."""
    client, session_factory = seeded_client

    async def _deny_tool():
        async with session_factory() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(ToolDefinition).where(ToolDefinition.name == "email.fetch")
            )
            tool = result.scalar_one()
            perm = ArtifactPermission(
                artifact_type="tool",
                artifact_id=tool.id,
                role="employee",
                allowed=False,
                status="active",
            )
            session.add(perm)
            await session.commit()

    loop = asyncio.get_event_loop_policy().new_event_loop()
    loop.run_until_complete(_deny_tool())

    response = client.get("/api/tools")
    assert response.status_code == 200
    names = [t["name"] for t in response.json()]
    assert "email.fetch" not in names
    assert "crm.get_tasks" in names
    loop.close()


def test_list_tools_shape(seeded_client) -> None:
    """Tools list items have the correct ToolListItem shape."""
    client, _ = seeded_client
    response = client.get("/api/tools")
    assert response.status_code == 200
    items = response.json()
    for item in items:
        assert "id" in item
        assert "name" in item
        assert "display_name" in item
        assert "description" in item
        assert "handler_type" in item
