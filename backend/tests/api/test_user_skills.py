"""
Tests for user-facing skill API — /api/skills.

Covers:
  - GET /api/skills returns only active skills with is_active=True
  - GET /api/skills excludes skills denied by artifact_permissions for user's role
  - POST /api/skills/{name}/run executes a procedural skill with mocked tool calls
  - POST /api/skills/{name}/run executes an instructional skill and returns markdown
  - POST /api/skills/nonexistent/run returns 404
  - POST /api/skills/{disabled_name}/run returns 404 (disabled skill)
  - POST /api/skills/{denied_name}/run returns 403 (denied by artifact permission)
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
from core.models.agent_definition import AgentDefinition  # noqa: F401
from core.models.artifact_permission import ArtifactPermission
from core.models.role_permission import RolePermission  # noqa: F401
from core.models.skill_definition import SkillDefinition
from core.models.tool_definition import ToolDefinition  # noqa: F401
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
def employee_client(sqlite_db) -> TestClient:
    """TestClient with employee auth + SQLite DB."""
    app.dependency_overrides[get_current_user] = make_employee_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def seeded_client(sqlite_db):
    """TestClient with employee auth + pre-seeded skills."""
    session_factory = sqlite_db

    async def _seed():
        async with session_factory() as session:
            # Active instructional skill
            s1 = SkillDefinition(
                name="morning_digest",
                display_name="Morning Digest",
                description="Get your morning briefing",
                skill_type="instructional",
                instruction_markdown="# Morning Digest\nCheck your emails and calendar.",
                slash_command="/morning_digest",
                status="active",
                is_active=True,
            )
            # Active procedural skill
            s2 = SkillDefinition(
                name="proc_skill",
                display_name="Procedural Skill",
                description="A procedural skill",
                skill_type="procedural",
                procedure_json={
                    "schema_version": "1.0",
                    "steps": [
                        {"id": "s1", "type": "tool", "tool": "email.send", "params": {}},
                    ],
                },
                slash_command="/proc_test",
                status="active",
                is_active=True,
            )
            # Disabled skill
            s3 = SkillDefinition(
                name="disabled_skill",
                display_name="Disabled Skill",
                description="This skill is disabled",
                skill_type="instructional",
                instruction_markdown="# Disabled",
                status="disabled",
                is_active=False,
            )
            # Inactive skill (active status but not activated version)
            s4 = SkillDefinition(
                name="inactive_skill",
                display_name="Inactive Skill",
                description="Not activated version",
                skill_type="instructional",
                instruction_markdown="# Inactive",
                status="active",
                is_active=False,
            )
            session.add_all([s1, s2, s3, s4])
            await session.commit()

    loop = asyncio.get_event_loop_policy().new_event_loop()
    loop.run_until_complete(_seed())

    app.dependency_overrides[get_current_user] = make_employee_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client, session_factory
    app.dependency_overrides.pop(get_current_user, None)
    loop.close()


# ---------------------------------------------------------------------------
# GET /api/skills tests
# ---------------------------------------------------------------------------


def test_list_skills_requires_jwt() -> None:
    """GET /api/skills returns 401 without auth."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/skills")
    assert response.status_code == 401


def test_list_skills_returns_active_only(seeded_client) -> None:
    """GET /api/skills returns only active skills with is_active=True."""
    client, _ = seeded_client
    response = client.get("/api/skills")
    assert response.status_code == 200
    data = response.json()
    # Should include morning_digest and proc_skill (active + is_active)
    # Should NOT include disabled_skill or inactive_skill
    names = [s["name"] for s in data]
    assert "morning_digest" in names
    assert "proc_skill" in names
    assert "disabled_skill" not in names
    assert "inactive_skill" not in names


def test_list_skills_shows_all_active_regardless_of_acl(seeded_client) -> None:
    """GET /api/skills returns ALL active skills without ACL join (SKCAT-03 decision).

    The user catalog shows all active skills so users can discover and request access.
    ACL enforcement is only applied at run time (POST /api/skills/{name}/run).
    """
    client, session_factory = seeded_client

    async def _deny_skill():
        async with session_factory() as session:
            # Find morning_digest
            from sqlalchemy import select

            result = await session.execute(
                select(SkillDefinition).where(SkillDefinition.name == "morning_digest")
            )
            skill = result.scalar_one()
            # Deny for employee role — should NOT hide the skill from the list
            perm = ArtifactPermission(
                artifact_type="skill",
                artifact_id=skill.id,
                role="employee",
                allowed=False,
                status="active",
            )
            session.add(perm)
            await session.commit()

    loop = asyncio.get_event_loop_policy().new_event_loop()
    loop.run_until_complete(_deny_skill())

    response = client.get("/api/skills")
    assert response.status_code == 200
    names = [s["name"] for s in response.json()]
    # All active skills are visible — ACL denial does NOT hide from catalog
    assert "morning_digest" in names
    assert "proc_skill" in names
    loop.close()


def test_list_skills_shape(seeded_client) -> None:
    """Skills list items have the correct SkillListItem shape."""
    client, _ = seeded_client
    response = client.get("/api/skills")
    assert response.status_code == 200
    items = response.json()
    for item in items:
        assert "id" in item
        assert "name" in item
        assert "display_name" in item
        assert "description" in item
        assert "slash_command" in item


# ---------------------------------------------------------------------------
# POST /api/skills/{name}/run tests
# ---------------------------------------------------------------------------


def test_run_nonexistent_skill(employee_client) -> None:
    """POST /api/skills/nonexistent/run returns 404."""
    response = employee_client.post("/api/skills/nonexistent/run")
    assert response.status_code == 404


def test_run_disabled_skill(seeded_client) -> None:
    """POST /api/skills/{disabled_name}/run returns 404 (disabled skill)."""
    client, _ = seeded_client
    response = client.post("/api/skills/disabled_skill/run")
    assert response.status_code == 404


def test_run_instructional_skill(seeded_client) -> None:
    """POST /api/skills/morning_digest/run returns instruction markdown."""
    client, _ = seeded_client
    response = client.post("/api/skills/morning_digest/run")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Morning Digest" in data["output"]


def test_run_denied_skill(seeded_client) -> None:
    """POST /api/skills/{name}/run returns 403 when artifact permission denies."""
    client, session_factory = seeded_client

    async def _deny_proc():
        async with session_factory() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(SkillDefinition).where(SkillDefinition.name == "proc_skill")
            )
            skill = result.scalar_one()
            perm = ArtifactPermission(
                artifact_type="skill",
                artifact_id=skill.id,
                role="employee",
                allowed=False,
                status="active",
            )
            session.add(perm)
            await session.commit()

    loop = asyncio.get_event_loop_policy().new_event_loop()
    loop.run_until_complete(_deny_proc())

    response = client.post("/api/skills/proc_skill/run")
    assert response.status_code == 403
    loop.close()


def test_run_procedural_skill_with_mock(seeded_client) -> None:
    """POST /api/skills/{name}/run with procedural skill + mocked executor."""
    client, _ = seeded_client

    mock_result = MagicMock()
    mock_result.success = True
    mock_result.output = "Skill executed successfully"
    mock_result.step_outputs = {"s1": "email sent"}
    mock_result.failed_step = None

    with patch("api.routes.user_skills.SkillExecutor") as MockExecutor:
        instance = MockExecutor.return_value
        instance.run = AsyncMock(return_value=mock_result)

        response = client.post(
            "/api/skills/proc_skill/run",
            json={"user_input": {"to": "test@example.com"}},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["output"] == "Skill executed successfully"
