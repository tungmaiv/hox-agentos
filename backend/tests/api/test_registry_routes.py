"""
Tests for unified registry API — /api/registry/*.

Covers:
  - 401 without auth (list, get, create, update, delete)
  - 403 with employee role on mutating endpoints (create, update, delete)
  - 200 with employee role on read endpoints (list, get)
  - CRUD flow: create -> list -> get -> update -> delete
  - 404 on get/update/delete for nonexistent entry
  - Type filter: list?type=tool returns only tool entries
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
from registry.models import RegistryEntry  # noqa: F401 — registers table in Base.metadata
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
    """employee role lacks registry:manage but can read."""
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


@pytest.fixture
def employee_client(sqlite_db: None) -> TestClient:
    """TestClient with employee auth + SQLite DB."""
    app.dependency_overrides[get_current_user] = make_employee_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


def test_list_requires_auth() -> None:
    """GET /api/registry returns 401 without auth."""
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/registry")
    assert resp.status_code == 401


def test_create_requires_auth() -> None:
    """POST /api/registry returns 401 without auth."""
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/registry", json={"type": "tool", "name": "t"})
    assert resp.status_code == 401


def test_update_requires_auth() -> None:
    """PUT /api/registry/{id} returns 401 without auth."""
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.put(f"/api/registry/{uuid4()}", json={"description": "x"})
    assert resp.status_code == 401


def test_delete_requires_auth() -> None:
    """DELETE /api/registry/{id} returns 401 without auth."""
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.delete(f"/api/registry/{uuid4()}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# RBAC tests (employee can read, cannot mutate)
# ---------------------------------------------------------------------------


def test_employee_can_list(employee_client: TestClient) -> None:
    """employee role can GET /api/registry (registry:read)."""
    resp = employee_client.get("/api/registry")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_employee_cannot_create(employee_client: TestClient) -> None:
    """employee role gets 403 on POST /api/registry."""
    resp = employee_client.post(
        "/api/registry",
        json={"type": "tool", "name": "no_perms_tool"},
    )
    assert resp.status_code == 403


def test_employee_cannot_delete(employee_client: TestClient) -> None:
    """employee role gets 403 on DELETE /api/registry/{id}."""
    resp = employee_client.delete(f"/api/registry/{uuid4()}")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# CRUD flow
# ---------------------------------------------------------------------------


def test_crud_flow(admin_client: TestClient) -> None:
    """Create -> list -> get -> update -> delete flow."""
    # Create
    create_resp = admin_client.post(
        "/api/registry",
        json={
            "type": "tool",
            "name": "registry_test_tool",
            "display_name": "Registry Test Tool",
            "description": "A tool for registry tests",
            "config": {"handler_type": "backend", "handler_function": "handle"},
            "status": "active",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    entry = create_resp.json()
    entry_id = entry["id"]
    assert entry["name"] == "registry_test_tool"
    assert entry["type"] == "tool"
    assert entry["status"] == "active"
    assert "owner_id" in entry

    # List — should include our new entry
    list_resp = admin_client.get("/api/registry")
    assert list_resp.status_code == 200
    ids = [e["id"] for e in list_resp.json()]
    assert entry_id in ids

    # Get by id
    get_resp = admin_client.get(f"/api/registry/{entry_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "registry_test_tool"

    # Update
    update_resp = admin_client.put(
        f"/api/registry/{entry_id}",
        json={"description": "updated description"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["description"] == "updated description"

    # Delete (soft delete)
    delete_resp = admin_client.delete(f"/api/registry/{entry_id}")
    assert delete_resp.status_code == 204

    # After soft delete, GET returns 404
    get_after = admin_client.get(f"/api/registry/{entry_id}")
    assert get_after.status_code == 404


# ---------------------------------------------------------------------------
# 404 behavior
# ---------------------------------------------------------------------------


def test_get_not_found(admin_client: TestClient) -> None:
    """GET /api/registry/{id} returns 404 for nonexistent entry."""
    resp = admin_client.get(f"/api/registry/{uuid4()}")
    assert resp.status_code == 404


def test_update_not_found(admin_client: TestClient) -> None:
    """PUT /api/registry/{id} returns 404 for nonexistent entry."""
    resp = admin_client.put(
        f"/api/registry/{uuid4()}",
        json={"description": "ghost"},
    )
    assert resp.status_code == 404


def test_delete_not_found(admin_client: TestClient) -> None:
    """DELETE /api/registry/{id} returns 404 for nonexistent entry."""
    resp = admin_client.delete(f"/api/registry/{uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Type filter
# ---------------------------------------------------------------------------


def test_list_filter_by_type(admin_client: TestClient) -> None:
    """GET /api/registry/?type=tool returns only tool entries."""
    # Create a tool entry
    r1 = admin_client.post(
        "/api/registry",
        json={
            "type": "tool",
            "name": "filter_type_tool",
            "status": "active",
            "config": {"handler_type": "backend", "handler_function": "handle"},
        },
    )
    assert r1.status_code == 201, r1.text
    # Create an agent entry
    r2 = admin_client.post(
        "/api/registry",
        json={"type": "agent", "name": "filter_type_agent", "status": "active"},
    )
    assert r2.status_code == 201, r2.text

    resp = admin_client.get("/api/registry?type=tool")
    assert resp.status_code == 200
    entries = resp.json()
    assert all(e["type"] == "tool" for e in entries)
    names = [e["name"] for e in entries]
    assert "filter_type_tool" in names
    assert "filter_type_agent" not in names
