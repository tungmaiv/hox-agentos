"""Tests for extensibility registry ORM models and Pydantic schemas.

Covers CRUD operations, unique constraint enforcement, default values,
is_active flag, last_seen_at, and user_artifact_permission for all 6 new
tables. Also validates Pydantic schema cross-field validation.
"""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db import Base
from core.models.agent_definition import AgentDefinition
from core.models.artifact_permission import ArtifactPermission
from core.models.role_permission import RolePermission
from core.models.skill_definition import SkillDefinition
from core.models.tool_definition import ToolDefinition
from core.models.user_artifact_permission import UserArtifactPermission
from core.schemas.registry import (
    AgentDefinitionCreate,
    AgentDefinitionResponse,
    ArtifactPermissionSet,
    SkillDefinitionCreate,
    SkillImportRequest,
    ToolDefinitionCreate,
    ToolDefinitionResponse,
)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_sess = async_sessionmaker(engine, expire_on_commit=False)
    async with async_sess() as s:
        yield s
    await engine.dispose()


# ─── AgentDefinition ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_agent_definition(session: AsyncSession):
    agent = AgentDefinition(
        id=uuid.uuid4(),
        name="email_agent",
        display_name="Email Agent",
        description="Handles email tasks",
        handler_module="agents.subagents.email_agent",
        handler_function="_email_agent_node",
        routing_keywords=["email", "mail"],
    )
    session.add(agent)
    await session.commit()

    result = await session.execute(
        select(AgentDefinition).where(AgentDefinition.name == "email_agent")
    )
    row = result.scalar_one()
    assert row.display_name == "Email Agent"
    assert row.version == "1.0.0"
    assert row.is_active is True
    assert row.status == "active"
    assert row.last_seen_at is None
    assert row.routing_keywords == ["email", "mail"]


@pytest.mark.asyncio
async def test_agent_unique_constraint_name_version(session: AsyncSession):
    """Same (name, version) cannot be inserted twice."""
    kwargs = dict(name="master_agent", version="1.0.0")
    session.add(AgentDefinition(id=uuid.uuid4(), **kwargs))
    await session.commit()

    session.add(AgentDefinition(id=uuid.uuid4(), **kwargs))
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_agent_different_versions_allowed(session: AsyncSession):
    """Same name with different versions is allowed."""
    session.add(AgentDefinition(id=uuid.uuid4(), name="email_agent", version="1.0.0"))
    session.add(AgentDefinition(id=uuid.uuid4(), name="email_agent", version="2.0.0"))
    await session.commit()

    result = await session.execute(
        select(AgentDefinition).where(AgentDefinition.name == "email_agent")
    )
    rows = result.scalars().all()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_agent_is_active_flag(session: AsyncSession):
    """is_active can be toggled."""
    agent_id = uuid.uuid4()
    session.add(AgentDefinition(id=agent_id, name="test_agent", is_active=False))
    await session.commit()

    result = await session.execute(
        select(AgentDefinition).where(AgentDefinition.id == agent_id)
    )
    row = result.scalar_one()
    assert row.is_active is False


# ─── ToolDefinition ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_tool_definition(session: AsyncSession):
    tool = ToolDefinition(
        id=uuid.uuid4(),
        name="email.fetch",
        display_name="Fetch Email",
        description="Fetches emails from mailbox",
        handler_type="backend",
        handler_module="tools.email_tools",
        handler_function="fetch_email",
        sandbox_required=False,
    )
    session.add(tool)
    await session.commit()

    result = await session.execute(
        select(ToolDefinition).where(ToolDefinition.name == "email.fetch")
    )
    row = result.scalar_one()
    assert row.handler_type == "backend"
    assert row.sandbox_required is False
    assert row.mcp_server_id is None
    assert row.version == "1.0.0"


@pytest.mark.asyncio
async def test_tool_unique_constraint_name_version(session: AsyncSession):
    """Same (name, version) cannot be inserted twice for tools."""
    kwargs = dict(name="email.send", version="1.0.0", handler_type="backend")
    session.add(ToolDefinition(id=uuid.uuid4(), **kwargs))
    await session.commit()

    session.add(ToolDefinition(id=uuid.uuid4(), **kwargs))
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_tool_mcp_type(session: AsyncSession):
    """MCP tools store server_id and tool_name."""
    server_id = uuid.uuid4()
    tool = ToolDefinition(
        id=uuid.uuid4(),
        name="crm.search",
        handler_type="mcp",
        mcp_server_id=server_id,
        mcp_tool_name="search_contacts",
    )
    session.add(tool)
    await session.commit()

    result = await session.execute(
        select(ToolDefinition).where(ToolDefinition.name == "crm.search")
    )
    row = result.scalar_one()
    assert row.handler_type == "mcp"
    assert row.mcp_server_id == server_id
    assert row.mcp_tool_name == "search_contacts"


# ─── SkillDefinition ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_instructional_skill(session: AsyncSession):
    skill = SkillDefinition(
        id=uuid.uuid4(),
        name="brainstorming",
        display_name="Brainstorming",
        description="Structured brainstorming skill",
        skill_type="instructional",
        slash_command="/brainstorm",
        instruction_markdown="# Brainstorming\n\nFollow these steps...",
    )
    session.add(skill)
    await session.commit()

    result = await session.execute(
        select(SkillDefinition).where(SkillDefinition.name == "brainstorming")
    )
    row = result.scalar_one()
    assert row.skill_type == "instructional"
    assert row.slash_command == "/brainstorm"
    assert row.instruction_markdown.startswith("# Brainstorming")


@pytest.mark.asyncio
async def test_create_procedural_skill(session: AsyncSession):
    skill = SkillDefinition(
        id=uuid.uuid4(),
        name="deploy_workflow",
        skill_type="procedural",
        procedure_json={"steps": [{"action": "build"}, {"action": "deploy"}]},
        input_schema={"type": "object", "properties": {"env": {"type": "string"}}},
    )
    session.add(skill)
    await session.commit()

    result = await session.execute(
        select(SkillDefinition).where(SkillDefinition.name == "deploy_workflow")
    )
    row = result.scalar_one()
    assert row.skill_type == "procedural"
    assert row.procedure_json["steps"][0]["action"] == "build"


@pytest.mark.asyncio
async def test_skill_unique_constraint_name_version(session: AsyncSession):
    kwargs = dict(name="test_skill", version="1.0.0", skill_type="instructional",
                  instruction_markdown="test")
    session.add(SkillDefinition(id=uuid.uuid4(), **kwargs))
    await session.commit()

    session.add(SkillDefinition(id=uuid.uuid4(), **kwargs))
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_skill_slash_command_unique(session: AsyncSession):
    """slash_command must be unique across all skills."""
    session.add(SkillDefinition(
        id=uuid.uuid4(), name="skill_a", skill_type="instructional",
        slash_command="/test", instruction_markdown="A",
    ))
    await session.commit()

    session.add(SkillDefinition(
        id=uuid.uuid4(), name="skill_b", skill_type="instructional",
        slash_command="/test", instruction_markdown="B",
    ))
    with pytest.raises(IntegrityError):
        await session.commit()


# ─── ArtifactPermission ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_artifact_permission(session: AsyncSession):
    perm = ArtifactPermission(
        id=uuid.uuid4(),
        artifact_type="tool",
        artifact_id=uuid.uuid4(),
        role="employee",
        allowed=True,
        status="active",
    )
    session.add(perm)
    await session.commit()

    result = await session.execute(
        select(ArtifactPermission).where(ArtifactPermission.role == "employee")
    )
    row = result.scalar_one()
    assert row.allowed is True
    assert row.status == "active"


@pytest.mark.asyncio
async def test_artifact_permission_staged_status(session: AsyncSession):
    """Permissions can be created with pending status."""
    perm = ArtifactPermission(
        id=uuid.uuid4(),
        artifact_type="agent",
        artifact_id=uuid.uuid4(),
        role="manager",
        allowed=True,
        status="pending",
    )
    session.add(perm)
    await session.commit()

    result = await session.execute(
        select(ArtifactPermission).where(ArtifactPermission.status == "pending")
    )
    row = result.scalar_one()
    assert row.status == "pending"


@pytest.mark.asyncio
async def test_artifact_permission_unique_constraint(session: AsyncSession):
    """Same (artifact_type, artifact_id, role) cannot be inserted twice."""
    artifact_id = uuid.uuid4()
    kwargs = dict(artifact_type="tool", artifact_id=artifact_id, role="employee")
    session.add(ArtifactPermission(id=uuid.uuid4(), **kwargs))
    await session.commit()

    session.add(ArtifactPermission(id=uuid.uuid4(), **kwargs))
    with pytest.raises(IntegrityError):
        await session.commit()


# ─── UserArtifactPermission ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_user_artifact_permission(session: AsyncSession):
    perm = UserArtifactPermission(
        id=uuid.uuid4(),
        artifact_type="tool",
        artifact_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        allowed=False,
        status="active",
    )
    session.add(perm)
    await session.commit()

    result = await session.execute(
        select(UserArtifactPermission).where(UserArtifactPermission.allowed == False)  # noqa: E712
    )
    row = result.scalar_one()
    assert row.artifact_type == "tool"
    assert row.allowed is False


@pytest.mark.asyncio
async def test_user_artifact_permission_unique_constraint(session: AsyncSession):
    """Same (artifact_type, artifact_id, user_id) cannot be inserted twice."""
    artifact_id = uuid.uuid4()
    user_id = uuid.uuid4()
    kwargs = dict(artifact_type="skill", artifact_id=artifact_id, user_id=user_id)
    session.add(UserArtifactPermission(id=uuid.uuid4(), **kwargs))
    await session.commit()

    session.add(UserArtifactPermission(id=uuid.uuid4(), **kwargs))
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_user_artifact_permission_pending_status(session: AsyncSession):
    """User permissions support staged (pending) status."""
    perm = UserArtifactPermission(
        id=uuid.uuid4(),
        artifact_type="agent",
        artifact_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        allowed=True,
        status="pending",
    )
    session.add(perm)
    await session.commit()

    result = await session.execute(
        select(UserArtifactPermission).where(UserArtifactPermission.status == "pending")
    )
    row = result.scalar_one()
    assert row.status == "pending"


# ─── RolePermission ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_role_permission(session: AsyncSession):
    perm = RolePermission(
        id=uuid.uuid4(),
        role="employee",
        permission="tool:email",
    )
    session.add(perm)
    await session.commit()

    result = await session.execute(
        select(RolePermission).where(RolePermission.role == "employee")
    )
    row = result.scalar_one()
    assert row.permission == "tool:email"


@pytest.mark.asyncio
async def test_role_permission_unique_constraint(session: AsyncSession):
    """Same (role, permission) cannot be inserted twice."""
    kwargs = dict(role="manager", permission="crm:write")
    session.add(RolePermission(id=uuid.uuid4(), **kwargs))
    await session.commit()

    session.add(RolePermission(id=uuid.uuid4(), **kwargs))
    with pytest.raises(IntegrityError):
        await session.commit()


# ─── Pydantic Schema Validation ──────────────────────────────────────────


def test_skill_create_instructional_requires_markdown():
    """Instructional skill without instruction_markdown should fail."""
    with pytest.raises(ValidationError, match="instruction_markdown"):
        SkillDefinitionCreate(
            name="test",
            skill_type="instructional",
            # Missing instruction_markdown
        )


def test_skill_create_procedural_requires_json():
    """Procedural skill without procedure_json should fail."""
    with pytest.raises(ValidationError, match="procedure_json"):
        SkillDefinitionCreate(
            name="test",
            skill_type="procedural",
            # Missing procedure_json
        )


def test_skill_create_valid_instructional():
    """Valid instructional skill passes validation."""
    skill = SkillDefinitionCreate(
        name="test_skill",
        skill_type="instructional",
        instruction_markdown="# Instructions\nDo this.",
    )
    assert skill.skill_type == "instructional"
    assert skill.version == "1.0.0"


def test_skill_create_valid_procedural():
    """Valid procedural skill passes validation."""
    skill = SkillDefinitionCreate(
        name="test_skill",
        skill_type="procedural",
        procedure_json={"steps": [{"action": "run"}]},
    )
    assert skill.procedure_json is not None


def test_skill_import_requires_at_least_one():
    """SkillImportRequest requires source_url or content."""
    with pytest.raises(ValidationError, match="At least one"):
        SkillImportRequest()


def test_skill_import_with_url():
    req = SkillImportRequest(source_url="https://example.com/skill.md")
    assert req.source_url is not None


def test_agent_create_defaults():
    """AgentDefinitionCreate has sensible defaults."""
    agent = AgentDefinitionCreate(name="test_agent")
    assert agent.version == "1.0.0"
    assert agent.routing_keywords is None
    assert agent.config_json is None


def test_tool_create_handler_type():
    """ToolDefinitionCreate validates handler_type literal."""
    tool = ToolDefinitionCreate(name="test_tool", handler_type="mcp")
    assert tool.handler_type == "mcp"

    with pytest.raises(ValidationError):
        ToolDefinitionCreate(name="test_tool", handler_type="invalid")


def test_schema_from_attributes():
    """Response schemas support from_attributes for ORM conversion."""
    assert AgentDefinitionResponse.model_config.get("from_attributes") is True
    assert ToolDefinitionResponse.model_config.get("from_attributes") is True
