"""
Tests for admin skill sharing endpoints:
  POST   /api/admin/skills/{id}/share
  DELETE /api/admin/skills/{id}/share/{user_id}
  GET    /api/admin/skills/{id}/shares

Covers:
  - test_share_skill: POST creates permission row, returns 201 + SkillShareEntry
  - test_share_skill_duplicate_returns_409: POST twice returns 409
  - test_list_shares: POST then GET returns list of 1 entry
  - test_revoke_share: POST then DELETE returns 204; subsequent GET returns []
  - test_revoke_nonexistent_share_returns_404: DELETE non-existent returns 404
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
from security.deps import get_current_user

# The target user that will be granted/revoked skill access
_TARGET_USER_ID = uuid4()
_ADMIN_ID = uuid4()


# ---------------------------------------------------------------------------
# User context helpers
# ---------------------------------------------------------------------------


def make_admin_ctx() -> UserContext:
    """it-admin role has 'registry:manage' permission."""
    return UserContext(
        user_id=_ADMIN_ID,
        email="admin@blitz.local",
        username="admin_user",
        roles=["it-admin"],
        groups=["/it"],
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
def admin_client(sqlite_db):
    """TestClient with admin auth + seeded skill."""
    session_factory = sqlite_db

    async def _seed():
        async with session_factory() as session:
            skill = SkillDefinition(
                name="shared-skill",
                display_name="Shared Skill",
                description="A skill for sharing tests",
                skill_type="instructional",
                instruction_markdown="# Shared Skill\nShared content.",
                status="active",
                is_active=True,
            )
            session.add(skill)
            await session.commit()

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_seed())

    app.dependency_overrides[get_current_user] = make_admin_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client, session_factory
    app.dependency_overrides.pop(get_current_user, None)
    loop.close()


def _get_skill_id(session_factory) -> str:
    """Return the UUID of the seeded shared-skill."""
    from sqlalchemy import select

    async def _fetch():
        async with session_factory() as session:
            result = await session.execute(
                select(SkillDefinition).where(SkillDefinition.name == "shared-skill")
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


def test_share_skill(admin_client) -> None:
    """POST /api/admin/skills/{id}/share creates permission row, returns 201."""
    client, session_factory = admin_client
    skill_id = _get_skill_id(session_factory)

    response = client.post(
        f"/api/admin/skills/{skill_id}/share",
        json={"user_id": str(_TARGET_USER_ID)},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["user_id"] == str(_TARGET_USER_ID)
    assert "created_at" in data


def test_share_skill_duplicate_returns_409(admin_client) -> None:
    """POST /api/admin/skills/{id}/share twice returns 409 on duplicate."""
    client, session_factory = admin_client
    skill_id = _get_skill_id(session_factory)

    # First share: 201
    r1 = client.post(
        f"/api/admin/skills/{skill_id}/share",
        json={"user_id": str(_TARGET_USER_ID)},
    )
    assert r1.status_code == 201, r1.text

    # Duplicate: 409
    r2 = client.post(
        f"/api/admin/skills/{skill_id}/share",
        json={"user_id": str(_TARGET_USER_ID)},
    )
    assert r2.status_code == 409, r2.text


def test_list_shares(admin_client) -> None:
    """GET /api/admin/skills/{id}/shares returns list of 1 after sharing."""
    client, session_factory = admin_client
    skill_id = _get_skill_id(session_factory)

    # Share first
    client.post(
        f"/api/admin/skills/{skill_id}/share",
        json={"user_id": str(_TARGET_USER_ID)},
    )

    # List shares
    response = client.get(f"/api/admin/skills/{skill_id}/shares")
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["user_id"] == str(_TARGET_USER_ID)


def test_revoke_share(admin_client) -> None:
    """DELETE /api/admin/skills/{id}/share/{user_id} returns 204; GET then returns []."""
    client, session_factory = admin_client
    skill_id = _get_skill_id(session_factory)

    # Share first
    client.post(
        f"/api/admin/skills/{skill_id}/share",
        json={"user_id": str(_TARGET_USER_ID)},
    )

    # Revoke
    del_resp = client.delete(
        f"/api/admin/skills/{skill_id}/share/{_TARGET_USER_ID}"
    )
    assert del_resp.status_code == 204, del_resp.text

    # List should be empty
    list_resp = client.get(f"/api/admin/skills/{skill_id}/shares")
    assert list_resp.status_code == 200
    assert list_resp.json() == []


def test_revoke_nonexistent_share_returns_404(admin_client) -> None:
    """DELETE non-existent share returns 404."""
    client, session_factory = admin_client
    skill_id = _get_skill_id(session_factory)

    response = client.delete(
        f"/api/admin/skills/{skill_id}/share/{uuid4()}"
    )
    assert response.status_code == 404, response.text
