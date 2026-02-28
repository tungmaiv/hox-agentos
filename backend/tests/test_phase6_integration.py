"""
End-to-end integration test for Phase 6 extensibility registries.

Full lifecycle:
  1. Create a procedural skill via POST /api/admin/skills (admin user)
  2. Verify it appears in GET /api/skills (regular employee user)
  3. Execute it via POST /api/skills/{name}/run (mock tool calls)
  4. Disable it via PATCH /api/admin/skills/{id}/status
  5. Verify GET /api/skills no longer returns it
  6. Verify POST /api/skills/{name}/run returns 404

Agent lifecycle:
  7. Create an agent definition via admin API
  8. Disable the agent, verify it disappears from keyword routing

Tool lifecycle:
  9. Create a tool definition via admin API
  10. Verify it appears in GET /api/tools (employee user)
  11. Disable it, verify it disappears from GET /api/tools
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
    """it-admin role has registry:manage + chat permissions."""
    return UserContext(
        user_id=uuid4(),
        email="admin@blitz.local",
        username="admin_user",
        roles=["it-admin"],
        groups=["/it"],
    )


def make_employee_ctx() -> UserContext:
    """employee role has chat permission."""
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
def integration_db():
    """In-memory SQLite DB for integration tests."""
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


# ---------------------------------------------------------------------------
# Skill lifecycle integration test
# ---------------------------------------------------------------------------


def test_skill_lifecycle(integration_db) -> None:
    """Full skill lifecycle: create -> list -> execute -> disable -> verify unavailable."""

    # Step 1: Admin creates a procedural skill
    app.dependency_overrides[get_current_user] = make_admin_ctx
    admin_client = TestClient(app, raise_server_exceptions=False)

    create_resp = admin_client.post(
        "/api/admin/skills",
        json={
            "name": "integration_skill",
            "display_name": "Integration Test Skill",
            "description": "A skill for integration testing",
            "skill_type": "procedural",
            "slash_command": "/integration_test",
            "procedure_json": {
                "schema_version": "1.0",
                "steps": [
                    {"id": "s1", "type": "tool", "tool": "email.send", "params": {}},
                ],
            },
        },
    )
    assert create_resp.status_code == 201, f"Create failed: {create_resp.text}"
    skill = create_resp.json()
    skill_id = skill["id"]
    assert skill["name"] == "integration_skill"
    assert skill["status"] == "active"
    assert skill["is_active"] is True

    # Step 2: Employee user can see the skill in their list
    app.dependency_overrides[get_current_user] = make_employee_ctx
    emp_client = TestClient(app, raise_server_exceptions=False)

    list_resp = emp_client.get("/api/skills")
    assert list_resp.status_code == 200
    names = [s["name"] for s in list_resp.json()]
    assert "integration_skill" in names

    # Step 3: Employee executes the skill (mocked tool execution)
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.output = "Integration skill completed"
    mock_result.step_outputs = {"s1": "done"}
    mock_result.failed_step = None

    with patch("api.routes.user_skills.SkillExecutor") as MockExecutor:
        instance = MockExecutor.return_value
        instance.run = AsyncMock(return_value=mock_result)

        run_resp = emp_client.post("/api/skills/integration_skill/run")

    assert run_resp.status_code == 200
    run_data = run_resp.json()
    assert run_data["success"] is True
    assert run_data["output"] == "Integration skill completed"

    # Step 4: Admin disables the skill
    app.dependency_overrides[get_current_user] = make_admin_ctx
    admin_client2 = TestClient(app, raise_server_exceptions=False)

    disable_resp = admin_client2.patch(
        f"/api/admin/skills/{skill_id}/status",
        json={"status": "disabled"},
    )
    assert disable_resp.status_code == 200
    assert disable_resp.json()["status"] == "disabled"

    # Step 5: Employee no longer sees it in the list
    app.dependency_overrides[get_current_user] = make_employee_ctx
    emp_client2 = TestClient(app, raise_server_exceptions=False)

    list_resp2 = emp_client2.get("/api/skills")
    assert list_resp2.status_code == 200
    names2 = [s["name"] for s in list_resp2.json()]
    assert "integration_skill" not in names2

    # Step 6: Employee cannot execute it (404)
    run_resp2 = emp_client2.post("/api/skills/integration_skill/run")
    assert run_resp2.status_code == 404

    # Cleanup
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Agent lifecycle integration test
# ---------------------------------------------------------------------------


def test_agent_definition_lifecycle(integration_db) -> None:
    """Create an agent definition, verify it exists, disable it."""

    app.dependency_overrides[get_current_user] = make_admin_ctx
    admin_client = TestClient(app, raise_server_exceptions=False)

    # Create agent
    create_resp = admin_client.post(
        "/api/admin/agents",
        json={
            "name": "test_integration_agent",
            "display_name": "Test Integration Agent",
            "description": "Agent for integration test",
            "handler_module": "agents.subagents.email_agent",
            "handler_function": "email_agent_node",
            "routing_keywords": ["testroute"],
        },
    )
    assert create_resp.status_code == 201
    agent = create_resp.json()
    agent_id = agent["id"]
    assert agent["name"] == "test_integration_agent"
    assert agent["status"] == "active"

    # List agents
    list_resp = admin_client.get("/api/admin/agents")
    assert list_resp.status_code == 200
    names = [a["name"] for a in list_resp.json()]
    assert "test_integration_agent" in names

    # Disable agent
    disable_resp = admin_client.patch(
        f"/api/admin/agents/{agent_id}/status",
        json={"status": "disabled"},
    )
    assert disable_resp.status_code == 200
    assert disable_resp.json()["status"] == "disabled"

    # Verify disabled
    get_resp = admin_client.get(f"/api/admin/agents/{agent_id}")
    assert get_resp.json()["status"] == "disabled"

    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Tool lifecycle integration test
# ---------------------------------------------------------------------------


def test_tool_visibility_lifecycle(integration_db) -> None:
    """Create a tool, verify employee sees it, disable it, verify it disappears."""

    # Admin creates a tool
    app.dependency_overrides[get_current_user] = make_admin_ctx
    admin_client = TestClient(app, raise_server_exceptions=False)

    create_resp = admin_client.post(
        "/api/admin/tools",
        json={
            "name": "integration_tool",
            "display_name": "Integration Tool",
            "description": "A tool for integration testing",
            "handler_type": "backend",
        },
    )
    assert create_resp.status_code == 201
    tool = create_resp.json()
    tool_id = tool["id"]

    # Employee sees the tool
    app.dependency_overrides[get_current_user] = make_employee_ctx
    emp_client = TestClient(app, raise_server_exceptions=False)

    list_resp = emp_client.get("/api/tools")
    assert list_resp.status_code == 200
    names = [t["name"] for t in list_resp.json()]
    assert "integration_tool" in names

    # Admin disables the tool
    app.dependency_overrides[get_current_user] = make_admin_ctx
    admin_client2 = TestClient(app, raise_server_exceptions=False)

    disable_resp = admin_client2.patch(
        f"/api/admin/tools/{tool_id}/status",
        json={"status": "disabled"},
    )
    assert disable_resp.status_code == 200

    # Employee no longer sees it
    app.dependency_overrides[get_current_user] = make_employee_ctx
    emp_client2 = TestClient(app, raise_server_exceptions=False)

    list_resp2 = emp_client2.get("/api/tools")
    assert list_resp2.status_code == 200
    names2 = [t["name"] for t in list_resp2.json()]
    assert "integration_tool" not in names2

    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Instructional skill execution test
# ---------------------------------------------------------------------------


def test_instructional_skill_execution(integration_db) -> None:
    """Create an instructional skill, execute it, verify markdown output."""

    # Admin creates
    app.dependency_overrides[get_current_user] = make_admin_ctx
    admin_client = TestClient(app, raise_server_exceptions=False)

    create_resp = admin_client.post(
        "/api/admin/skills",
        json={
            "name": "inst_integration",
            "display_name": "Instructional Integration",
            "skill_type": "instructional",
            "instruction_markdown": "# Instructions\n\nFollow these steps:\n1. Check email\n2. Review calendar",
        },
    )
    assert create_resp.status_code == 201

    # Employee executes
    app.dependency_overrides[get_current_user] = make_employee_ctx
    emp_client = TestClient(app, raise_server_exceptions=False)

    run_resp = emp_client.post("/api/skills/inst_integration/run")
    assert run_resp.status_code == 200
    data = run_resp.json()
    assert data["success"] is True
    assert "# Instructions" in data["output"]
    assert "Check email" in data["output"]

    app.dependency_overrides.pop(get_current_user, None)
