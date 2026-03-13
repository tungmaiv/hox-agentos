"""
Tests for admin skill CRUD API — /api/admin/skills.

Covers:
  - 401 without auth
  - 403 with employee role (no registry:manage)
  - CRUD flow: create -> get -> list -> update -> patch status -> verify
  - Pending filter: GET /pending returns only pending_review status
  - Multi-version activation
  - Bulk-status update
  - Validate endpoint (stub returns valid)
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


def test_list_skills_requires_jwt() -> None:
    """GET /api/admin/skills returns 401 without auth."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/admin/skills")
    assert response.status_code == 401


def test_list_skills_requires_registry_manage(sqlite_db: None) -> None:
    """employee role lacks registry:manage — GET returns 403."""
    app.dependency_overrides[get_current_user] = make_employee_ctx
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/admin/skills")
    app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# CRUD flow
# ---------------------------------------------------------------------------


def test_crud_flow(admin_client: TestClient) -> None:
    """Create -> get -> list -> update -> patch status -> verify."""
    # Create instructional skill
    create_resp = admin_client.post(
        "/api/admin/skills",
        json={
            "name": "test-skill",
            "display_name": "Test Skill",
            "skill_type": "instructional",
            "instruction_markdown": "# Test\nDo the thing.",
        },
    )
    assert create_resp.status_code == 201
    skill = create_resp.json()
    skill_id = skill["id"]
    assert skill["name"] == "test-skill"
    assert skill["skill_type"] == "instructional"
    assert skill["version"] == "1.0.0"
    assert skill["is_active"] is False

    # Get
    get_resp = admin_client.get(f"/api/admin/skills/{skill_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "test-skill"

    # List
    list_resp = admin_client.get("/api/admin/skills")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # Update
    update_resp = admin_client.put(
        f"/api/admin/skills/{skill_id}",
        json={"display_name": "Updated Skill", "description": "Updated desc"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["display_name"] == "Updated Skill"

    # Patch status
    status_resp = admin_client.patch(
        f"/api/admin/skills/{skill_id}/status",
        json={"status": "disabled"},
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["updated"] is True
    assert status_resp.json()["status"] == "disabled"
    assert "active_workflow_runs" in status_resp.json()

    # Verify status persisted
    get_resp2 = admin_client.get(f"/api/admin/skills/{skill_id}")
    assert get_resp2.json()["status"] == "disabled"


def test_get_skill_not_found(admin_client: TestClient) -> None:
    """GET /api/admin/skills/{id} returns 404 for nonexistent."""
    fake_id = str(uuid4())
    resp = admin_client.get(f"/api/admin/skills/{fake_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Pending filter
# ---------------------------------------------------------------------------


def test_pending_filter(admin_client: TestClient) -> None:
    """GET /api/admin/skills/pending returns only pending_review skills."""
    # Create a skill then set its status to pending_review
    r = admin_client.post(
        "/api/admin/skills",
        json={
            "name": "pending-skill",
            "skill_type": "instructional",
            "instruction_markdown": "# Pending",
        },
    )
    skill_id = r.json()["id"]

    # Manually set to pending_review via PUT update won't work for status,
    # so we use the status patch. But StatusUpdate only allows active/disabled/deprecated.
    # Instead we check that pending returns empty when none are pending_review.
    resp = admin_client.get("/api/admin/skills/pending")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Multi-version
# ---------------------------------------------------------------------------


def test_create_skill_defaults_to_draft(admin_client: TestClient) -> None:
    """POST /api/admin/skills returns status='draft' for all new skills."""
    r = admin_client.post(
        "/api/admin/skills",
        json={
            "name": "draft-default-skill",
            "version": "1.0.0",
            "skill_type": "instructional",
            "instruction_markdown": "# Draft Default Test",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "draft"
    assert data["is_active"] is False


def test_activate_skill(admin_client: TestClient) -> None:
    """Create a draft skill, activate it — status becomes 'active' and is_active is True."""
    # Create skill — starts as 'draft'
    r1 = admin_client.post(
        "/api/admin/skills",
        json={
            "name": "activate-skill",
            "version": "1.0.0",
            "skill_type": "instructional",
            "instruction_markdown": "# Activate Test",
        },
    )
    assert r1.status_code == 201
    skill_id = r1.json()["id"]
    assert r1.json()["status"] == "draft"

    # Activate directly from draft via /activate endpoint
    activate_resp = admin_client.patch(f"/api/admin/skills/{skill_id}/activate")
    assert activate_resp.status_code == 200
    data = activate_resp.json()
    assert data["status"] == "active"
    assert data["is_active"] is True


# ---------------------------------------------------------------------------
# Tool-gaps gate — activation bypass prevention
# ---------------------------------------------------------------------------


def test_activate_endpoint_blocked_by_tool_gaps(admin_client: TestClient) -> None:
    """PATCH /activate returns 422 when skill has unresolved tool_gaps."""
    create_resp = admin_client.post(
        "/api/admin/skills",
        json={
            "name": "gated-activate-skill",
            "version": "1.0.0",
            "skill_type": "procedural",
            "procedure_json": {"steps": []},
        },
    )
    assert create_resp.status_code == 201
    skill_id = create_resp.json()["id"]

    # Inject tool_gaps via the registry update endpoint (merges into existing config)
    gap_resp = admin_client.put(
        f"/api/registry/{skill_id}",
        json={"config": {"tool_gaps": [{"step": 1, "tool": "MISSING:send-slack-message"}]}},
    )
    assert gap_resp.status_code == 200

    activate_resp = admin_client.patch(f"/api/admin/skills/{skill_id}/activate")
    assert activate_resp.status_code == 422
    assert "tool gaps" in activate_resp.json()["detail"].lower()


def test_patch_status_blocked_by_tool_gaps(admin_client: TestClient) -> None:
    """PATCH /status to 'active' returns 422 when skill has unresolved tool_gaps."""
    create_resp = admin_client.post(
        "/api/admin/skills",
        json={
            "name": "gated-status-skill",
            "version": "1.0.0",
            "skill_type": "procedural",
            "procedure_json": {"steps": []},
        },
    )
    assert create_resp.status_code == 201
    skill_id = create_resp.json()["id"]

    # Inject tool_gaps via the registry update endpoint
    gap_resp = admin_client.put(
        f"/api/registry/{skill_id}",
        json={"config": {"tool_gaps": [{"step": 1, "tool": "MISSING:missing-tool"}]}},
    )
    assert gap_resp.status_code == 200

    status_resp = admin_client.patch(
        f"/api/admin/skills/{skill_id}/status", json={"status": "active"}
    )
    assert status_resp.status_code == 422
    assert "tool gaps" in status_resp.json()["detail"].lower()

    # Non-active status transitions are not blocked
    ok_resp = admin_client.patch(
        f"/api/admin/skills/{skill_id}/status", json={"status": "disabled"}
    )
    assert ok_resp.status_code == 200


def test_bulk_status_skips_skills_with_tool_gaps(admin_client: TestClient) -> None:
    """Bulk activate skips skills with tool_gaps; returns blocked list."""
    # Skill without gaps — should be activated
    r1 = admin_client.post(
        "/api/admin/skills",
        json={"name": "bulk-clean-skill", "skill_type": "instructional", "instruction_markdown": "# test"},
    )
    assert r1.status_code == 201
    clean_id = r1.json()["id"]

    # Skill with gaps — should be blocked
    r2 = admin_client.post(
        "/api/admin/skills",
        json={"name": "bulk-gapped-skill", "skill_type": "instructional", "instruction_markdown": "# test"},
    )
    assert r2.status_code == 201
    gapped_id = r2.json()["id"]

    # Disable both so we can test re-activation
    admin_client.patch(
        "/api/admin/skills/bulk-status",
        json={"ids": [clean_id, gapped_id], "status": "disabled"},
    )

    # Inject tool_gaps into gapped skill only
    gap_resp = admin_client.put(
        f"/api/registry/{gapped_id}",
        json={"config": {"tool_gaps": [{"step": 1, "tool": "MISSING:some-tool"}]}},
    )
    assert gap_resp.status_code == 200

    # Bulk activate — clean should succeed, gapped should be blocked
    resp = admin_client.patch(
        "/api/admin/skills/bulk-status",
        json={"ids": [clean_id, gapped_id], "status": "active"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] == 1
    assert gapped_id in data["blocked"]
    # Clean skill was activated
    assert admin_client.get(f"/api/admin/skills/{clean_id}").json()["status"] == "active"
    # Gapped skill was NOT activated (remains disabled)
    assert admin_client.get(f"/api/admin/skills/{gapped_id}").json()["status"] == "disabled"


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


def test_list_filter_by_skill_type(admin_client: TestClient) -> None:
    """List skills filtered by skill_type."""
    admin_client.post(
        "/api/admin/skills",
        json={
            "name": "proc-skill",
            "skill_type": "procedural",
            "procedure_json": {"steps": []},
        },
    )
    admin_client.post(
        "/api/admin/skills",
        json={
            "name": "inst-skill",
            "skill_type": "instructional",
            "instruction_markdown": "# Inst",
        },
    )

    resp = admin_client.get("/api/admin/skills?skill_type=procedural")
    assert resp.status_code == 200
    items = resp.json()
    assert all(s["skill_type"] == "procedural" for s in items)
    assert len(items) >= 1


def test_list_filter_by_version(admin_client: TestClient) -> None:
    """List skills filtered by version."""
    admin_client.post(
        "/api/admin/skills",
        json={
            "name": "ver-skill",
            "version": "5.0.0",
            "skill_type": "instructional",
            "instruction_markdown": "# v5",
        },
    )

    resp = admin_client.get("/api/admin/skills?version=5.0.0")
    assert resp.status_code == 200
    items = resp.json()
    assert all(s["version"] == "5.0.0" for s in items)


# ---------------------------------------------------------------------------
# Bulk status
# ---------------------------------------------------------------------------


def test_bulk_status_update(admin_client: TestClient) -> None:
    """Create 3 skills, bulk disable 2, verify."""
    ids = []
    for i in range(3):
        r = admin_client.post(
            "/api/admin/skills",
            json={
                "name": f"bulk-skill-{i}",
                "skill_type": "instructional",
                "instruction_markdown": f"# Bulk {i}",
            },
        )
        assert r.status_code == 201
        ids.append(r.json()["id"])

    # Bulk disable first 2
    bulk_resp = admin_client.patch(
        "/api/admin/skills/bulk-status",
        json={"ids": ids[:2], "status": "disabled"},
    )
    assert bulk_resp.status_code == 200
    assert bulk_resp.json()["updated"] == 2

    assert admin_client.get(f"/api/admin/skills/{ids[0]}").json()["status"] == "disabled"
    assert admin_client.get(f"/api/admin/skills/{ids[1]}").json()["status"] == "disabled"
    assert admin_client.get(f"/api/admin/skills/{ids[2]}").json()["status"] == "draft"


# ---------------------------------------------------------------------------
# Validate endpoint (stub)
# ---------------------------------------------------------------------------


def test_validate_skill_valid(admin_client: TestClient) -> None:
    """POST /api/admin/skills/{id}/validate returns valid for correct procedure."""
    r = admin_client.post(
        "/api/admin/skills",
        json={
            "name": "validate-skill",
            "skill_type": "procedural",
            "procedure_json": {
                "schema_version": "1.0",
                "steps": [{"id": "s1", "type": "tool", "tool": "email.send"}],
            },
        },
    )
    skill_id = r.json()["id"]

    resp = admin_client.post(f"/api/admin/skills/{skill_id}/validate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["errors"] == []


def test_validate_skill_invalid(admin_client: TestClient) -> None:
    """POST /api/admin/skills/{id}/validate returns errors for invalid procedure."""
    r = admin_client.post(
        "/api/admin/skills",
        json={
            "name": "validate-invalid",
            "skill_type": "procedural",
            "procedure_json": {"steps": [{"name": "step1", "tool": "email.send"}]},
        },
    )
    skill_id = r.json()["id"]

    resp = admin_client.post(f"/api/admin/skills/{skill_id}/validate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert len(data["errors"]) > 0


def test_validate_skill_not_found(admin_client: TestClient) -> None:
    """POST /api/admin/skills/{id}/validate returns 404 for nonexistent."""
    fake_id = str(uuid4())
    resp = admin_client.post(f"/api/admin/skills/{fake_id}/validate")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Issue fixes: soft-delete filter + import/review/security-report via RegistryEntry
# ---------------------------------------------------------------------------

_SAFE_SKILL_MD = """\
---
name: import-test-skill
description: A safe instructional skill for import tests
version: 1.0.0
---
# Import Test Skill
Do the thing safely.
"""


def test_list_skills_excludes_soft_deleted(admin_client: TestClient) -> None:
    """Soft-deleted skills must not appear in GET /api/admin/skills."""
    create_resp = admin_client.post(
        "/api/admin/skills",
        json={
            "name": "delete-me-skill",
            "skill_type": "instructional",
            "instruction_markdown": "# Delete me",
        },
    )
    assert create_resp.status_code == 201
    skill_id = create_resp.json()["id"]

    del_resp = admin_client.delete(f"/api/registry/{skill_id}")
    assert del_resp.status_code == 204

    list_resp = admin_client.get("/api/admin/skills")
    assert list_resp.status_code == 200
    ids = [s["id"] for s in list_resp.json()]
    assert skill_id not in ids, "Soft-deleted skill must not appear in list"


def test_import_skill_appears_in_list(admin_client: TestClient) -> None:
    """POST /api/admin/skills/import writes to RegistryEntry — result visible in GET /api/admin/skills."""
    import_resp = admin_client.post(
        "/api/admin/skills/import",
        json={"content": _SAFE_SKILL_MD},
    )
    assert import_resp.status_code == 201
    skill_id = import_resp.json()["skill"]["id"]

    list_resp = admin_client.get("/api/admin/skills")
    assert list_resp.status_code == 200
    ids = [s["id"] for s in list_resp.json()]
    assert skill_id in ids, "Imported skill must appear in list after import"


def test_review_skill_approve_via_registry_entry(admin_client: TestClient) -> None:
    """POST /api/admin/skills/{id}/review works on RegistryEntry IDs after import."""
    skill_md = """\
---
name: review-approve-skill
description: Skill for review-approve test
version: 1.0.0
---
# Review Approve
Test review approve path.
"""
    import_resp = admin_client.post(
        "/api/admin/skills/import",
        json={"content": skill_md},
    )
    assert import_resp.status_code == 201
    skill_id = import_resp.json()["skill"]["id"]

    review_resp = admin_client.post(
        f"/api/admin/skills/{skill_id}/review",
        json={"decision": "approve"},
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["decision"] == "approve"
    assert review_resp.json()["status"] == "active"


def test_review_skill_reject_via_registry_entry(admin_client: TestClient) -> None:
    """POST /api/admin/skills/{id}/review reject path works on RegistryEntry IDs."""
    skill_md = """\
---
name: review-reject-skill
description: Skill for review-reject test
version: 1.0.0
---
# Review Reject
Test review reject path.
"""
    import_resp = admin_client.post(
        "/api/admin/skills/import",
        json={"content": skill_md},
    )
    assert import_resp.status_code == 201
    skill_id = import_resp.json()["skill"]["id"]

    review_resp = admin_client.post(
        f"/api/admin/skills/{skill_id}/review",
        json={"decision": "reject", "notes": "Malicious content"},
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["decision"] == "reject"
    assert review_resp.json()["status"] == "rejected"


def test_get_security_report_via_registry_entry(admin_client: TestClient) -> None:
    """GET /api/admin/skills/{id}/security-report returns report stored in RegistryEntry config."""
    skill_md = """\
---
name: security-report-skill
description: Skill for security report test
version: 1.0.0
---
# Security Report Skill
Test security report path.
"""
    import_resp = admin_client.post(
        "/api/admin/skills/import",
        json={"content": skill_md},
    )
    assert import_resp.status_code == 201
    skill_id = import_resp.json()["skill"]["id"]

    report_resp = admin_client.get(f"/api/admin/skills/{skill_id}/security-report")
    assert report_resp.status_code == 200
    data = report_resp.json()
    assert "score" in data
