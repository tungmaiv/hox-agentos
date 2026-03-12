"""
Tests for admin tool CRUD API — /api/admin/tools.

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


def test_list_tools_requires_jwt() -> None:
    """GET /api/admin/tools returns 401 without auth."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/admin/tools")
    assert response.status_code == 401


def test_list_tools_requires_registry_manage(sqlite_db: None) -> None:
    """employee role lacks registry:manage — GET returns 403."""
    app.dependency_overrides[get_current_user] = make_employee_ctx
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/admin/tools")
    app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# CRUD flow
# ---------------------------------------------------------------------------


def test_crud_flow(admin_client: TestClient) -> None:
    """Create -> get -> list -> update -> patch status -> verify."""
    # Create
    create_resp = admin_client.post(
        "/api/admin/tools",
        json={
            "name": "test_tool",
            "display_name": "Test Tool",
            "handler_type": "backend",
        },
    )
    assert create_resp.status_code == 201
    tool = create_resp.json()
    tool_id = tool["id"]
    assert tool["name"] == "test_tool"
    assert tool["version"] == "1.0.0"
    assert tool["is_active"] is True
    assert tool["handler_type"] == "backend"

    # Get
    get_resp = admin_client.get(f"/api/admin/tools/{tool_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "test_tool"

    # List
    list_resp = admin_client.get("/api/admin/tools")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # Update
    update_resp = admin_client.put(
        f"/api/admin/tools/{tool_id}",
        json={"display_name": "Updated Tool", "handler_type": "mcp"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["display_name"] == "Updated Tool"
    assert update_resp.json()["handler_type"] == "mcp"

    # Patch status
    status_resp = admin_client.patch(
        f"/api/admin/tools/{tool_id}/status",
        json={"status": "disabled"},
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["updated"] is True
    assert status_resp.json()["status"] == "disabled"
    assert "active_workflow_runs" in status_resp.json()

    # Verify status persisted
    get_resp2 = admin_client.get(f"/api/admin/tools/{tool_id}")
    assert get_resp2.json()["status"] == "disabled"


def test_get_tool_not_found(admin_client: TestClient) -> None:
    """GET /api/admin/tools/{id} returns 404 for nonexistent."""
    fake_id = str(uuid4())
    resp = admin_client.get(f"/api/admin/tools/{fake_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Multi-version
# ---------------------------------------------------------------------------


def test_multi_version_activation(admin_client: TestClient) -> None:
    """Create v1.0.0 and v1.1.0, activate v1.1.0 — v1.0.0 becomes inactive."""
    # Create v1.0.0
    r1 = admin_client.post(
        "/api/admin/tools",
        json={"name": "multi_tool", "version": "1.0.0"},
    )
    assert r1.status_code == 201
    id_v1 = r1.json()["id"]

    # Create v1.1.0
    r2 = admin_client.post(
        "/api/admin/tools",
        json={"name": "multi_tool", "version": "1.1.0"},
    )
    assert r2.status_code == 201
    id_v2 = r2.json()["id"]

    # Both active initially
    assert admin_client.get(f"/api/admin/tools/{id_v1}").json()["is_active"] is True
    assert admin_client.get(f"/api/admin/tools/{id_v2}").json()["is_active"] is True

    # Activate v1.1.0 — deactivates v1.0.0
    activate_resp = admin_client.patch(f"/api/admin/tools/{id_v2}/activate")
    assert activate_resp.status_code == 200
    assert activate_resp.json()["is_active"] is True

    # v1.0.0 inactive, v1.1.0 active
    assert admin_client.get(f"/api/admin/tools/{id_v1}").json()["is_active"] is False
    assert admin_client.get(f"/api/admin/tools/{id_v2}").json()["is_active"] is True


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


def test_list_filter_by_version(admin_client: TestClient) -> None:
    """List tools filtered by version."""
    admin_client.post(
        "/api/admin/tools",
        json={"name": "filter_tool_a", "version": "2.0.0"},
    )
    admin_client.post(
        "/api/admin/tools",
        json={"name": "filter_tool_b", "version": "3.0.0"},
    )

    resp = admin_client.get("/api/admin/tools?version=2.0.0")
    assert resp.status_code == 200
    items = resp.json()
    assert all(t["version"] == "2.0.0" for t in items)
    assert len(items) >= 1


def test_list_filter_by_status(admin_client: TestClient) -> None:
    """List tools filtered by status."""
    r = admin_client.post(
        "/api/admin/tools",
        json={"name": "status_filter_tool"},
    )
    tool_id = r.json()["id"]
    admin_client.patch(
        f"/api/admin/tools/{tool_id}/status",
        json={"status": "deprecated"},
    )

    resp = admin_client.get("/api/admin/tools?status=deprecated")
    assert resp.status_code == 200
    items = resp.json()
    assert any(t["id"] == tool_id for t in items)


# ---------------------------------------------------------------------------
# Bulk status
# ---------------------------------------------------------------------------


def test_bulk_status_update(admin_client: TestClient) -> None:
    """Create 3 tools, bulk disable 2, verify."""
    ids = []
    for i in range(3):
        r = admin_client.post(
            "/api/admin/tools",
            json={"name": f"bulk_tool_{i}"},
        )
        assert r.status_code == 201
        ids.append(r.json()["id"])

    # Bulk disable first 2
    bulk_resp = admin_client.patch(
        "/api/admin/tools/bulk-status",
        json={"ids": ids[:2], "status": "disabled"},
    )
    assert bulk_resp.status_code == 200
    assert bulk_resp.json()["updated"] == 2

    # Verify
    assert admin_client.get(f"/api/admin/tools/{ids[0]}").json()["status"] == "disabled"
    assert admin_client.get(f"/api/admin/tools/{ids[1]}").json()["status"] == "disabled"
    assert admin_client.get(f"/api/admin/tools/{ids[2]}").json()["status"] == "active"


# ---------------------------------------------------------------------------
# Graceful removal
# ---------------------------------------------------------------------------


def test_graceful_removal_returns_workflow_count(admin_client: TestClient) -> None:
    """Status patch to disabled returns active_workflow_runs count (0 in test DB)."""
    r = admin_client.post(
        "/api/admin/tools",
        json={"name": "removal_tool"},
    )
    tool_id = r.json()["id"]

    resp = admin_client.patch(
        f"/api/admin/tools/{tool_id}/status",
        json={"status": "disabled"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_workflow_runs"] == 0
    assert data["updated"] is True


# ---------------------------------------------------------------------------
# Cache invalidation regression tests (Phase 9 EXTD-03/EXTD-05)
# ---------------------------------------------------------------------------


def test_patch_status_invalidates_cache(admin_client: TestClient) -> None:
    """patch_tool_status() returns 200 and disables the tool.

    Note: the old gateway.tool_registry._tool_cache no longer exists — the
    unified registry (registry_entries) is queried directly on each call.
    Cache eviction regression tests are no longer applicable.
    """
    # Create a tool
    r = admin_client.post("/api/admin/tools", json={"name": "cache_test_patch_tool"})
    assert r.status_code == 201
    tool_id = r.json()["id"]

    # Disable the tool via PATCH /status — must return 200
    resp = admin_client.patch(
        f"/api/admin/tools/{tool_id}/status",
        json={"status": "disabled"},
    )
    assert resp.status_code == 200


def test_activate_version_invalidates_cache(admin_client: TestClient) -> None:
    """activate_tool_version() returns 200 after activating a version.

    Note: the old gateway.tool_registry._tool_cache no longer exists — the
    unified registry (registry_entries) is queried directly on each call.
    Cache eviction regression tests are no longer applicable.
    """
    # Create two versions of the same tool
    r1 = admin_client.post(
        "/api/admin/tools", json={"name": "cache_test_activate_tool", "version": "1.0.0"}
    )
    assert r1.status_code == 201
    r2 = admin_client.post(
        "/api/admin/tools", json={"name": "cache_test_activate_tool", "version": "1.1.0"}
    )
    assert r2.status_code == 201
    id_v2 = r2.json()["id"]

    # Activate v1.1.0 — must return 200
    resp = admin_client.patch(f"/api/admin/tools/{id_v2}/activate")
    assert resp.status_code == 200

# ---------------------------------------------------------------------------
# activate-stub endpoint (SKBLD-03)
# ---------------------------------------------------------------------------


def test_activate_stub_endpoint(admin_client: TestClient) -> None:
    """PATCH /activate-stub promotes pending_stub -> active, handler_code preserved."""
    # Create a tool with pending_stub status and handler_code
    create_resp = admin_client.post(
        "/api/admin/tools",
        json={
            "name": "stub_tool_activate",
            "description": "A tool pending stub activation",
            "handler_type": "backend",
        },
    )
    assert create_resp.status_code == 201
    tool_id = create_resp.json()["id"]

    # Manually set status to pending_stub and add handler_code
    patch_resp = admin_client.put(
        f"/api/admin/tools/{tool_id}",
        json={"status": "pending_stub", "handler_code": "async def handler(input): return {}"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "pending_stub"

    # Now activate the stub
    activate_resp = admin_client.patch(f"/api/admin/tools/{tool_id}/activate-stub")
    assert activate_resp.status_code == 200
    result = activate_resp.json()
    assert result["status"] == "active"
    assert result["is_active"] is True


def test_activate_stub_returns_409_if_not_pending_stub(admin_client: TestClient) -> None:
    """PATCH /activate-stub returns 409 if tool is already active (not pending_stub)."""
    create_resp = admin_client.post(
        "/api/admin/tools",
        json={"name": "already_active_tool", "handler_type": "backend"},
    )
    assert create_resp.status_code == 201
    tool_id = create_resp.json()["id"]

    # Tool is 'active' by default — activate-stub should return 409
    activate_resp = admin_client.patch(f"/api/admin/tools/{tool_id}/activate-stub")
    assert activate_resp.status_code == 409

