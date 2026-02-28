"""
Tests for admin permission management API — /api/admin/permissions.

Covers:
  - 401 without auth
  - 403 with employee role
  - Role permission listing and setting
  - Artifact permission CRUD with staged model (pending -> apply -> active)
  - Per-user override CRUD
  - Cache invalidation timing (only on apply, not on staged writes)
"""
import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import patch
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
    """
    Override get_db with an in-memory SQLite async session.

    Seeds role_permissions with it-admin's registry:manage permission
    so that after cache invalidation, the DB still resolves correctly.
    Also resets the RBAC cache on teardown to avoid cross-test contamination.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # Seed it-admin role permissions so DB-backed RBAC works after cache invalidation
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            for perm in ["tool:admin", "registry:manage", "chat", "sandbox:execute"]:
                session.add(RolePermission(role="it-admin", permission=perm))
            await session.commit()

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_setup())

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    # Reset RBAC cache to avoid cross-test contamination
    from security.rbac import invalidate_permission_cache
    invalidate_permission_cache()
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


def test_list_roles_requires_jwt() -> None:
    """GET /api/admin/permissions/roles returns 401 without auth."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/admin/permissions/roles")
    assert response.status_code == 401


def test_list_roles_requires_registry_manage(sqlite_db: None) -> None:
    """employee role lacks registry:manage — GET returns 403."""
    app.dependency_overrides[get_current_user] = make_employee_ctx
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/admin/permissions/roles")
    app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Role permission tests
# ---------------------------------------------------------------------------


def test_role_permission_listing(admin_client: TestClient) -> None:
    """GET /api/admin/permissions/roles returns empty dict initially."""
    resp = admin_client.get("/api/admin/permissions/roles")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


def test_set_role_permissions(admin_client: TestClient) -> None:
    """PUT /api/admin/permissions/roles/{role} replaces permissions."""
    resp = admin_client.put(
        "/api/admin/permissions/roles/test-role",
        json={"permissions": ["chat", "tool:email", "tool:calendar"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "test-role"
    assert set(data["permissions"]) == {"chat", "tool:email", "tool:calendar"}

    # Verify listing now includes this role
    list_resp = admin_client.get("/api/admin/permissions/roles")
    assert "test-role" in list_resp.json()
    assert set(list_resp.json()["test-role"]) == {"chat", "tool:email", "tool:calendar"}


def test_set_role_permissions_replaces(admin_client: TestClient) -> None:
    """PUT replaces existing permissions, not appends."""
    # Set initial
    admin_client.put(
        "/api/admin/permissions/roles/replace-role",
        json={"permissions": ["chat", "tool:email"]},
    )
    # Replace
    admin_client.put(
        "/api/admin/permissions/roles/replace-role",
        json={"permissions": ["tool:calendar"]},
    )

    list_resp = admin_client.get("/api/admin/permissions/roles")
    assert list_resp.json()["replace-role"] == ["tool:calendar"]


def test_set_role_permissions_invalidates_cache(admin_client: TestClient) -> None:
    """PUT /api/admin/permissions/roles/{role} calls invalidate_permission_cache."""
    with patch(
        "api.routes.admin_permissions.invalidate_permission_cache"
    ) as mock_invalidate:
        admin_client.put(
            "/api/admin/permissions/roles/cache-role",
            json={"permissions": ["chat"]},
        )
        mock_invalidate.assert_called_once()


# ---------------------------------------------------------------------------
# Artifact permission tests (staged model)
# ---------------------------------------------------------------------------


def test_artifact_permission_crud(admin_client: TestClient) -> None:
    """PUT creates pending, GET returns both active and pending."""
    artifact_id = str(uuid4())

    # Set artifact permissions (staged as pending)
    put_resp = admin_client.put(
        f"/api/admin/permissions/artifacts/tool/{artifact_id}",
        json={
            "artifact_type": "tool",
            "roles": [
                {"role": "employee", "allowed": True},
                {"role": "executive", "allowed": False},
            ],
        },
    )
    assert put_resp.status_code == 200
    items = put_resp.json()
    assert len(items) == 2
    assert all(i["status"] == "pending" for i in items)

    # GET returns all permissions
    get_resp = admin_client.get(
        f"/api/admin/permissions/artifacts/tool/{artifact_id}"
    )
    assert get_resp.status_code == 200
    assert len(get_resp.json()) == 2


def test_staged_model_pending_to_active(admin_client: TestClient) -> None:
    """Write permission -> pending -> apply -> active -> cache invalidated."""
    artifact_id = str(uuid4())

    # Set permissions (pending)
    put_resp = admin_client.put(
        f"/api/admin/permissions/artifacts/agent/{artifact_id}",
        json={
            "artifact_type": "agent",
            "roles": [{"role": "employee", "allowed": True}],
        },
    )
    perm_ids = [item["id"] for item in put_resp.json()]
    assert all(item["status"] == "pending" for item in put_resp.json())

    # Apply
    with patch(
        "api.routes.admin_permissions.invalidate_permission_cache"
    ) as mock_invalidate:
        apply_resp = admin_client.post(
            "/api/admin/permissions/apply",
            json={"ids": perm_ids},
        )
        assert apply_resp.status_code == 200
        assert apply_resp.json()["applied"] == 1
        mock_invalidate.assert_called_once()

    # Verify now active
    get_resp = admin_client.get(
        f"/api/admin/permissions/artifacts/agent/{artifact_id}"
    )
    items = get_resp.json()
    assert len(items) == 1
    assert items[0]["status"] == "active"


def test_staged_write_does_not_invalidate_cache(admin_client: TestClient) -> None:
    """PUT /artifacts creates pending rows WITHOUT invalidating cache."""
    artifact_id = str(uuid4())

    with patch(
        "api.routes.admin_permissions.invalidate_permission_cache"
    ) as mock_invalidate:
        admin_client.put(
            f"/api/admin/permissions/artifacts/tool/{artifact_id}",
            json={
                "artifact_type": "tool",
                "roles": [{"role": "employee", "allowed": True}],
            },
        )
        mock_invalidate.assert_not_called()


# ---------------------------------------------------------------------------
# Per-user override tests
# ---------------------------------------------------------------------------


def test_user_permission_crud(admin_client: TestClient) -> None:
    """PUT creates pending user overrides, GET returns them."""
    artifact_id = str(uuid4())
    target_user_id = str(uuid4())

    # Set user-level permissions (pending)
    put_resp = admin_client.put(
        f"/api/admin/permissions/users/tool/{artifact_id}",
        json=[
            {
                "artifact_type": "tool",
                "user_id": target_user_id,
                "allowed": False,
            },
        ],
    )
    assert put_resp.status_code == 200
    items = put_resp.json()
    assert len(items) == 1
    assert items[0]["status"] == "pending"
    assert items[0]["user_id"] == target_user_id

    # GET returns user-level permissions
    get_resp = admin_client.get(
        f"/api/admin/permissions/users/tool/{artifact_id}"
    )
    assert get_resp.status_code == 200
    assert len(get_resp.json()) == 1


def test_user_permission_apply(admin_client: TestClient) -> None:
    """User overrides also applied via POST /apply."""
    artifact_id = str(uuid4())
    target_user_id = str(uuid4())

    # Set user-level permission (pending)
    put_resp = admin_client.put(
        f"/api/admin/permissions/users/agent/{artifact_id}",
        json=[
            {
                "artifact_type": "agent",
                "user_id": target_user_id,
                "allowed": True,
            },
        ],
    )
    perm_ids = [item["id"] for item in put_resp.json()]

    # Apply
    apply_resp = admin_client.post(
        "/api/admin/permissions/apply",
        json={"ids": perm_ids},
    )
    assert apply_resp.status_code == 200
    assert apply_resp.json()["applied"] == 1

    # Verify now active
    get_resp = admin_client.get(
        f"/api/admin/permissions/users/agent/{artifact_id}"
    )
    items = get_resp.json()
    assert len(items) == 1
    assert items[0]["status"] == "active"


def test_user_permission_replaces_on_put(admin_client: TestClient) -> None:
    """PUT /users replaces existing entries, not appends."""
    artifact_id = str(uuid4())
    user_a = str(uuid4())
    user_b = str(uuid4())

    # Set user_a
    admin_client.put(
        f"/api/admin/permissions/users/tool/{artifact_id}",
        json=[{"artifact_type": "tool", "user_id": user_a, "allowed": True}],
    )

    # Replace with user_b
    admin_client.put(
        f"/api/admin/permissions/users/tool/{artifact_id}",
        json=[{"artifact_type": "tool", "user_id": user_b, "allowed": False}],
    )

    # Only user_b should remain
    get_resp = admin_client.get(
        f"/api/admin/permissions/users/tool/{artifact_id}"
    )
    items = get_resp.json()
    assert len(items) == 1
    assert items[0]["user_id"] == user_b


# ---------------------------------------------------------------------------
# Empty apply
# ---------------------------------------------------------------------------


def test_apply_empty_ids(admin_client: TestClient) -> None:
    """POST /apply with empty IDs list returns 0 applied."""
    resp = admin_client.post(
        "/api/admin/permissions/apply",
        json={"ids": []},
    )
    assert resp.status_code == 200
    assert resp.json()["applied"] == 0
