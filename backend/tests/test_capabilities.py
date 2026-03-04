"""
capabilities tool test suite.

Tests the system_capabilities() function with an in-memory SQLite database
to verify it returns the correct CapabilitiesResponse structure, applies
permission filtering, handles empty registries, and the master agent's
_classify_by_keywords detects capabilities-intent phrases.
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db import Base
from core.models.agent_definition import AgentDefinition
from core.models.mcp_server import McpServer
from core.models.skill_definition import SkillDefinition
from core.models.tool_definition import ToolDefinition


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session() -> AsyncSession:
    """
    In-memory SQLite async session with all tables created.

    Uses aiosqlite driver. SQLite is sufficient for capabilities unit tests
    since the queries are simple selects — no PostgreSQL-specific features.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _seed_agent(session: AsyncSession, name: str = "email_agent") -> uuid.UUID:
    """Seed a single active agent definition."""
    agent_id = uuid.uuid4()
    await session.execute(
        insert(AgentDefinition).values(
            id=agent_id,
            name=name,
            display_name=name.replace("_", " ").title(),
            description=f"Test {name}",
            status="active",
            is_active=True,
        )
    )
    await session.commit()
    return agent_id


async def _seed_tool(
    session: AsyncSession, name: str = "email.fetch", handler_type: str = "backend"
) -> uuid.UUID:
    """Seed a single active tool definition."""
    tool_id = uuid.uuid4()
    await session.execute(
        insert(ToolDefinition).values(
            id=tool_id,
            name=name,
            display_name=name,
            description=f"Test {name}",
            status="active",
            is_active=True,
            handler_type=handler_type,
            sandbox_required=False,
        )
    )
    await session.commit()
    return tool_id


async def _seed_skill(
    session: AsyncSession, name: str = "morning_digest", slash_command: str | None = "/morning"
) -> uuid.UUID:
    """Seed a single active skill definition."""
    skill_id = uuid.uuid4()
    await session.execute(
        insert(SkillDefinition).values(
            id=skill_id,
            name=name,
            display_name=name.replace("_", " ").title(),
            description=f"Test {name}",
            status="active",
            is_active=True,
            skill_type="instructional",
            slash_command=slash_command,
            source_type="builtin",
        )
    )
    await session.commit()
    return skill_id


async def _seed_mcp_server(session: AsyncSession, name: str = "crm") -> uuid.UUID:
    """Seed a single active MCP server."""
    server_id = uuid.uuid4()
    await session.execute(
        insert(McpServer).values(
            id=server_id,
            name=name,
            url=f"http://mcp-{name}:8001",
            status="active",
            is_active=True,
        )
    )
    await session.commit()
    return server_id


# ---------------------------------------------------------------------------
# system_capabilities() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_capabilities_returns_all_artifact_types(db_session: AsyncSession) -> None:
    """system_capabilities() returns a CapabilitiesResponse with all four lists."""
    from capabilities.tool import system_capabilities

    agent_id = await _seed_agent(db_session, "email_agent")
    tool_id = await _seed_tool(db_session, "email.fetch")
    skill_id = await _seed_skill(db_session, "morning_digest")
    server_id = await _seed_mcp_server(db_session, "crm")

    user_id = uuid.uuid4()

    # Patch batch_check_artifact_permissions to allow everything
    with patch(
        "capabilities.tool.batch_check_artifact_permissions",
        new_callable=AsyncMock,
    ) as mock_check:
        # Return the artifact IDs as allowed
        mock_check.side_effect = lambda user, artifact_type, artifact_ids, session: (
            set(artifact_ids)
        )

        result = await system_capabilities(user_id=user_id, session=db_session)

    assert len(result.agents) == 1
    assert result.agents[0].name == "email_agent"
    assert len(result.tools) == 1
    assert result.tools[0].name == "email.fetch"
    assert len(result.skills) == 1
    assert result.skills[0].name == "morning_digest"
    assert len(result.mcp_servers) == 1
    assert result.mcp_servers[0].name == "crm"


@pytest.mark.asyncio
async def test_capabilities_summary_counts_match(db_session: AsyncSession) -> None:
    """summary field shows correct counts."""
    from capabilities.tool import system_capabilities

    await _seed_agent(db_session, "email_agent")
    await _seed_agent(db_session, "calendar_agent")
    await _seed_tool(db_session, "email.fetch")
    await _seed_skill(db_session, "morning_digest")
    await _seed_mcp_server(db_session, "crm")

    user_id = uuid.uuid4()

    with patch(
        "capabilities.tool.batch_check_artifact_permissions",
        new_callable=AsyncMock,
    ) as mock_check:
        mock_check.side_effect = lambda user, artifact_type, artifact_ids, session: (
            set(artifact_ids)
        )
        result = await system_capabilities(user_id=user_id, session=db_session)

    assert "2 agents" in result.summary
    assert "1 tool" in result.summary
    assert "1 skill" in result.summary
    assert "1 MCP server" in result.summary


@pytest.mark.asyncio
async def test_capabilities_permission_filtering(db_session: AsyncSession) -> None:
    """Results filtered by batch_check_artifact_permissions — denied artifacts excluded."""
    from capabilities.tool import system_capabilities

    # Seed two tools
    tool_id_allowed = await _seed_tool(db_session, "email.fetch")
    tool_id_denied = await _seed_tool(db_session, "admin.tool")

    user_id = uuid.uuid4()

    with patch(
        "capabilities.tool.batch_check_artifact_permissions",
        new_callable=AsyncMock,
    ) as mock_check:
        # Only allow email.fetch — deny admin.tool
        async def selective_check(user, artifact_type, artifact_ids, session):
            if artifact_type == "tool":
                return {aid for aid in artifact_ids if aid == tool_id_allowed}
            return set(artifact_ids)

        mock_check.side_effect = selective_check

        result = await system_capabilities(user_id=user_id, session=db_session)

    assert len(result.tools) == 1
    assert result.tools[0].name == "email.fetch"
    # admin.tool should be excluded
    assert not any(t.name == "admin.tool" for t in result.tools)


@pytest.mark.asyncio
async def test_capabilities_empty_registries(db_session: AsyncSession) -> None:
    """Empty registries return empty lists with correct summary."""
    from capabilities.tool import system_capabilities

    user_id = uuid.uuid4()

    with patch(
        "capabilities.tool.batch_check_artifact_permissions",
        new_callable=AsyncMock,
    ) as mock_check:
        mock_check.return_value = set()

        result = await system_capabilities(user_id=user_id, session=db_session)

    assert result.agents == []
    assert result.tools == []
    assert result.skills == []
    assert result.mcp_servers == []
    assert "0 agents" in result.summary
    assert "0 tools" in result.summary
    assert "0 skills" in result.summary
    assert "0 MCP servers" in result.summary


@pytest.mark.asyncio
async def test_capabilities_inactive_artifacts_excluded(db_session: AsyncSession) -> None:
    """Inactive artifacts (is_active=False or status='disabled') are excluded."""
    from capabilities.tool import system_capabilities

    # Seed one active and one inactive agent
    active_id = await _seed_agent(db_session, "email_agent")

    # Seed an inactive agent directly
    inactive_id = uuid.uuid4()
    await db_session.execute(
        insert(AgentDefinition).values(
            id=inactive_id,
            name="disabled_agent",
            status="disabled",
            is_active=False,
        )
    )
    await db_session.commit()

    user_id = uuid.uuid4()

    with patch(
        "capabilities.tool.batch_check_artifact_permissions",
        new_callable=AsyncMock,
    ) as mock_check:
        mock_check.side_effect = lambda user, artifact_type, artifact_ids, session: (
            set(artifact_ids)
        )
        result = await system_capabilities(user_id=user_id, session=db_session)

    agent_names = [a.name for a in result.agents]
    assert "email_agent" in agent_names
    assert "disabled_agent" not in agent_names


# ---------------------------------------------------------------------------
# _classify_by_keywords capabilities intent tests
# ---------------------------------------------------------------------------


def test_classify_what_can_you_do() -> None:
    """'what can you do' phrase returns 'capabilities' intent."""
    from agents.master_agent import _classify_by_keywords

    assert _classify_by_keywords("what can you do") == "capabilities"


def test_classify_what_are_your_capabilities() -> None:
    """'what are your capabilities' phrase returns 'capabilities' intent."""
    from agents.master_agent import _classify_by_keywords

    assert _classify_by_keywords("what are your capabilities") == "capabilities"


def test_classify_show_me_your_capabilities() -> None:
    """'show me your capabilities' phrase returns 'capabilities' intent."""
    from agents.master_agent import _classify_by_keywords

    assert _classify_by_keywords("show me your capabilities") == "capabilities"


def test_classify_list_capabilities() -> None:
    """'list capabilities' phrase returns 'capabilities' intent."""
    from agents.master_agent import _classify_by_keywords

    assert _classify_by_keywords("list capabilities") == "capabilities"


def test_classify_available_tools() -> None:
    """'available tools' phrase returns 'capabilities' intent."""
    from agents.master_agent import _classify_by_keywords

    assert _classify_by_keywords("available tools") == "capabilities"


def test_classify_available_skills() -> None:
    """'available skills' phrase returns 'capabilities' intent."""
    from agents.master_agent import _classify_by_keywords

    assert _classify_by_keywords("available skills") == "capabilities"


def test_classify_capabilities_case_insensitive() -> None:
    """Capabilities detection is case-insensitive."""
    from agents.master_agent import _classify_by_keywords

    assert _classify_by_keywords("What Can You Do?") == "capabilities"
    assert _classify_by_keywords("SHOW CAPABILITIES") == "capabilities"


def test_classify_non_capabilities_returns_general() -> None:
    """Non-capabilities messages return general or agent name (not capabilities)."""
    from agents.master_agent import _classify_by_keywords

    # General message
    assert _classify_by_keywords("hello how are you") == "general"
    # Email message — should route to email agent (hardcoded fallback)
    assert _classify_by_keywords("check my email") != "capabilities"


# ---------------------------------------------------------------------------
# CapabilitiesResponse schema tests
# ---------------------------------------------------------------------------


def test_capabilities_response_schema() -> None:
    """CapabilitiesResponse can be instantiated with all required fields."""
    from capabilities.schemas import (
        AgentInfo,
        CapabilitiesResponse,
        McpServerInfo,
        SkillInfo,
        ToolInfo,
    )

    response = CapabilitiesResponse(
        agents=[AgentInfo(name="email_agent", display_name="Email Agent", description="Manages email", status="active")],
        tools=[ToolInfo(name="email.fetch", display_name="Email Fetch", description="Fetch emails", handler_type="mcp")],
        skills=[SkillInfo(name="morning_digest", display_name="Morning Digest", description="Daily briefing", slash_command="/morning")],
        mcp_servers=[McpServerInfo(name="crm", display_name="CRM", tools_count=3)],
        summary="1 agent, 1 tool, 1 skill, 1 MCP server",
    )

    assert response.agents[0].name == "email_agent"
    assert response.tools[0].handler_type == "mcp"
    assert response.skills[0].slash_command == "/morning"
    assert response.mcp_servers[0].tools_count == 3
    assert "1 agent" in response.summary
