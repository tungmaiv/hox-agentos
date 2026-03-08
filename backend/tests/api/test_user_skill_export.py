"""
Tests for GET /api/skills/{id}/export endpoint.

Covers:
  - test_user_export_skill_returns_zip: authenticated user gets ZIP file for active skill
  - test_user_export_skill_not_found: 404 for unknown skill UUID
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
from core.models.skill_definition import SkillDefinition
from core.models.tool_definition import ToolDefinition  # noqa: F401
from core.models.user_artifact_permission import UserArtifactPermission  # noqa: F401
from core.models.user import UserContext
from main import app
from security.deps import get_current_user, get_user_db


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
    """Override get_db and get_user_db with an in-memory SQLite async session."""
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
    app.dependency_overrides[get_user_db] = override_get_db
    yield session_factory
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_user_db, None)
    loop.run_until_complete(engine.dispose())
    loop.close()


@pytest.fixture
def employee_client(sqlite_db):
    """TestClient with employee auth + seeded active skill."""
    session_factory = sqlite_db

    async def _seed():
        async with session_factory() as session:
            skill = SkillDefinition(
                name="export-skill",
                display_name="Export Skill",
                description="A skill for export testing",
                skill_type="instructional",
                instruction_markdown="# Export Skill\nDo something useful.",
                status="active",
                is_active=True,
            )
            session.add(skill)
            await session.commit()

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_seed())

    app.dependency_overrides[get_current_user] = make_employee_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client, session_factory
    app.dependency_overrides.pop(get_current_user, None)
    loop.close()


def _get_skill_id(session_factory) -> str:
    """Return the UUID of the seeded export-skill."""
    from sqlalchemy import select

    async def _fetch():
        async with session_factory() as session:
            result = await session.execute(
                select(SkillDefinition).where(SkillDefinition.name == "export-skill")
            )
            skill = result.scalar_one()
            return str(skill.id)

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch())
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_user_export_skill_returns_zip(employee_client) -> None:
    """GET /api/skills/{id}/export returns 200 with application/zip content."""
    client, session_factory = employee_client
    skill_id = _get_skill_id(session_factory)

    response = client.get(f"/api/skills/{skill_id}/export")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    # Content-Disposition header should mention "export-skill"
    content_disp = response.headers.get("content-disposition", "")
    assert "export-skill" in content_disp


def test_user_export_skill_not_found(employee_client) -> None:
    """GET /api/skills/{unknown_uuid}/export returns 404."""
    client, _ = employee_client
    response = client.get(f"/api/skills/{uuid4()}/export")
    assert response.status_code == 404
