"""
Tests for PATCH /api/admin/skills/{id}/promote endpoint.

Covers:
  - test_promote_skill: PATCH toggles is_promoted False → True, returns 200
  - test_unpromote_skill: PATCH twice toggles True → False, returns 200
  - test_promote_not_found: PATCH with unknown UUID returns 404
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
from core.models.tool_definition import ToolDefinition  # noqa: F401
from core.models.user_artifact_permission import UserArtifactPermission  # noqa: F401
from core.models.user import UserContext
from main import app
from registry.models import RegistryEntry
from security.deps import get_current_user


# ---------------------------------------------------------------------------
# User context helpers
# ---------------------------------------------------------------------------

_ADMIN_ID = uuid4()


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
            skill = RegistryEntry(
                type="skill",
                name="test-skill",
                display_name="Test Skill",
                description="A test skill for promote tests",
                config={
                    "skill_type": "instructional",
                    "instruction_markdown": "# Test\nSome instructions.",
                    "is_promoted": False,
                },
                status="active",
                owner_id=_ADMIN_ID,
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


# ---------------------------------------------------------------------------
# Helper to get skill ID
# ---------------------------------------------------------------------------


def _get_skill_id(session_factory) -> str:
    """Return the UUID of the seeded skill."""
    import asyncio
    from sqlalchemy import select

    async def _fetch():
        async with session_factory() as session:
            result = await session.execute(
                select(RegistryEntry).where(
                    RegistryEntry.name == "test-skill",
                    RegistryEntry.type == "skill",
                )
            )
            entry = result.scalar_one()
            return str(entry.id)

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch())
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_promote_skill(admin_client) -> None:
    """PATCH /api/admin/skills/{id}/promote toggles False → True, returns 200."""
    client, session_factory = admin_client
    skill_id = _get_skill_id(session_factory)

    response = client.patch(f"/api/admin/skills/{skill_id}/promote")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["is_promoted"] is True
    assert data["id"] == skill_id


def test_unpromote_skill(admin_client) -> None:
    """PATCH twice toggles True → False, returns 200."""
    client, session_factory = admin_client
    skill_id = _get_skill_id(session_factory)

    # First PATCH: False → True
    r1 = client.patch(f"/api/admin/skills/{skill_id}/promote")
    assert r1.status_code == 200
    assert r1.json()["is_promoted"] is True

    # Second PATCH: True → False
    r2 = client.patch(f"/api/admin/skills/{skill_id}/promote")
    assert r2.status_code == 200
    assert r2.json()["is_promoted"] is False


def test_promote_not_found(admin_client) -> None:
    """PATCH /api/admin/skills/{unknown_uuid}/promote returns 404."""
    client, _ = admin_client
    response = client.patch(f"/api/admin/skills/{uuid4()}/promote")
    assert response.status_code == 404
