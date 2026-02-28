"""
Tests for admin agent CRUD API — /api/admin/agents.

Covers:
  - 401 without auth
  - 403 with employee role (no registry:manage)
  - CRUD flow: create -> get -> list -> update -> patch status -> verify
  - Multi-version: create v1.0.0, create v1.1.0, activate v1.1.0, verify v1.0.0 is_active=False
  - Bulk-status: create 3 items, bulk disable 2, verify
  - Graceful removal: status patch returns active_workflow_runs count
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
    """it-admin role has registry:manage permission."""
    return UserContext(
        user_id=uuid4(),
        email="admin@blitz.local",
        username="admin_user",
        roles=["it-admin"],
        groups=["/it"],
    )


def make_employee_ctx() -> UserContext:
    """employee role lacks registry:manage permission."""
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
    yield client
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


def test_list_agents_requires_jwt() -> None:
    """GET /api/admin/agents returns 401 without auth."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/admin/agents")
    assert response.status_code == 401


def test_list_agents_requires_registry_manage(sqlite_db: None) -> None:
    """employee role lacks registry:manage — GET returns 403."""
    app.dependency_overrides[get_current_user] = make_employee_ctx
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/admin/agents")
    app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# CRUD flow
# ---------------------------------------------------------------------------


def test_crud_flow(admin_client: TestClient) -> None:
    """Create -> get -> list -> update -> patch status -> verify."""
    # Create
    create_resp = admin_client.post(
        "/api/admin/agents",
        json={"name": "test_agent", "display_name": "Test Agent"},
    )
    assert create_resp.status_code == 201
    agent = create_resp.json()
    agent_id = agent["id"]
    assert agent["name"] == "test_agent"
    assert agent["version"] == "1.0.0"
    assert agent["is_active"] is True

    # Get
    get_resp = admin_client.get(f"/api/admin/agents/{agent_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "test_agent"

    # List
    list_resp = admin_client.get("/api/admin/agents")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # Update
    update_resp = admin_client.put(
        f"/api/admin/agents/{agent_id}",
        json={"display_name": "Updated Agent", "description": "Updated description"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["display_name"] == "Updated Agent"

    # Patch status
    status_resp = admin_client.patch(
        f"/api/admin/agents/{agent_id}/status",
        json={"status": "disabled"},
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["updated"] is True
    assert status_resp.json()["status"] == "disabled"
    assert "active_workflow_runs" in status_resp.json()

    # Verify status persisted
    get_resp2 = admin_client.get(f"/api/admin/agents/{agent_id}")
    assert get_resp2.json()["status"] == "disabled"


def test_get_agent_not_found(admin_client: TestClient) -> None:
    """GET /api/admin/agents/{id} returns 404 for nonexistent."""
    fake_id = str(uuid4())
    resp = admin_client.get(f"/api/admin/agents/{fake_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Multi-version
# ---------------------------------------------------------------------------


def test_multi_version_activation(admin_client: TestClient) -> None:
    """Create v1.0.0 and v1.1.0, activate v1.1.0 — v1.0.0 becomes inactive."""
    # Create v1.0.0
    r1 = admin_client.post(
        "/api/admin/agents",
        json={"name": "multi_agent", "version": "1.0.0"},
    )
    assert r1.status_code == 201
    id_v1 = r1.json()["id"]

    # Create v1.1.0
    r2 = admin_client.post(
        "/api/admin/agents",
        json={"name": "multi_agent", "version": "1.1.0"},
    )
    assert r2.status_code == 201
    id_v2 = r2.json()["id"]

    # Both are active initially
    assert admin_client.get(f"/api/admin/agents/{id_v1}").json()["is_active"] is True
    assert admin_client.get(f"/api/admin/agents/{id_v2}").json()["is_active"] is True

    # Activate v1.1.0 — should deactivate v1.0.0
    activate_resp = admin_client.patch(f"/api/admin/agents/{id_v2}/activate")
    assert activate_resp.status_code == 200
    assert activate_resp.json()["is_active"] is True

    # v1.0.0 should now be inactive
    assert admin_client.get(f"/api/admin/agents/{id_v1}").json()["is_active"] is False
    # v1.1.0 should remain active
    assert admin_client.get(f"/api/admin/agents/{id_v2}").json()["is_active"] is True


# ---------------------------------------------------------------------------
# Version filter
# ---------------------------------------------------------------------------


def test_list_filter_by_version(admin_client: TestClient) -> None:
    """List agents filtered by version."""
    admin_client.post(
        "/api/admin/agents",
        json={"name": "filter_agent_a", "version": "2.0.0"},
    )
    admin_client.post(
        "/api/admin/agents",
        json={"name": "filter_agent_b", "version": "3.0.0"},
    )

    resp = admin_client.get("/api/admin/agents?version=2.0.0")
    assert resp.status_code == 200
    items = resp.json()
    assert all(a["version"] == "2.0.0" for a in items)
    assert len(items) >= 1


def test_list_filter_by_status(admin_client: TestClient) -> None:
    """List agents filtered by status."""
    r = admin_client.post(
        "/api/admin/agents",
        json={"name": "status_filter_agent"},
    )
    agent_id = r.json()["id"]
    admin_client.patch(
        f"/api/admin/agents/{agent_id}/status",
        json={"status": "deprecated"},
    )

    resp = admin_client.get("/api/admin/agents?status=deprecated")
    assert resp.status_code == 200
    items = resp.json()
    assert any(a["id"] == agent_id for a in items)


# ---------------------------------------------------------------------------
# Bulk status
# ---------------------------------------------------------------------------


def test_bulk_status_update(admin_client: TestClient) -> None:
    """Create 3 agents, bulk disable 2, verify."""
    ids = []
    for i in range(3):
        r = admin_client.post(
            "/api/admin/agents",
            json={"name": f"bulk_agent_{i}"},
        )
        assert r.status_code == 201
        ids.append(r.json()["id"])

    # Bulk disable first 2
    bulk_resp = admin_client.patch(
        "/api/admin/agents/bulk-status",
        json={"ids": ids[:2], "status": "disabled"},
    )
    assert bulk_resp.status_code == 200
    assert bulk_resp.json()["updated"] == 2

    # Verify first 2 are disabled, third is still active
    assert admin_client.get(f"/api/admin/agents/{ids[0]}").json()["status"] == "disabled"
    assert admin_client.get(f"/api/admin/agents/{ids[1]}").json()["status"] == "disabled"
    assert admin_client.get(f"/api/admin/agents/{ids[2]}").json()["status"] == "active"


# ---------------------------------------------------------------------------
# Graceful removal
# ---------------------------------------------------------------------------


def test_graceful_removal_returns_workflow_count(admin_client: TestClient) -> None:
    """Status patch to disabled returns active_workflow_runs count (0 in test DB)."""
    r = admin_client.post(
        "/api/admin/agents",
        json={"name": "removal_agent"},
    )
    agent_id = r.json()["id"]

    resp = admin_client.patch(
        f"/api/admin/agents/{agent_id}/status",
        json={"status": "disabled"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_workflow_runs"] == 0
    assert data["updated"] is True
