"""
Tests for slash command dispatch in master agent _pre_route.

Covers:
  - _pre_route detects "/test_skill" and returns "skill_executor"
  - _pre_route passes through non-slash messages to normal routing
  - _pre_route handles unknown /commands (not in DB) by passing through to master_agent
  - skill_executor node in graph topology is wired correctly
"""
import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.db import Base
from core.models.agent_definition import AgentDefinition  # noqa: F401
from core.models.artifact_permission import ArtifactPermission  # noqa: F401
from core.models.role_permission import RolePermission  # noqa: F401
from core.models.skill_definition import SkillDefinition
from core.models.tool_definition import ToolDefinition  # noqa: F401
from core.models.user_artifact_permission import UserArtifactPermission  # noqa: F401


# ---------------------------------------------------------------------------
# SQLite in-memory DB for skill lookup tests
# ---------------------------------------------------------------------------


@pytest.fixture
def skill_db():
    """In-memory SQLite session factory with seeded skill."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            skill = SkillDefinition(
                name="test_skill",
                display_name="Test Skill",
                description="A test skill",
                skill_type="procedural",
                slash_command="/test_skill",
                status="active",
                is_active=True,
                procedure_json={"schema_version": "1.0", "steps": []},
            )
            session.add(skill)
            await session.commit()

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_setup())

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    yield session_factory, engine

    loop.run_until_complete(engine.dispose())
    loop.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pre_route_detects_slash_command(skill_db) -> None:
    """_pre_route detects '/test_skill' and returns 'skill_executor'."""
    session_factory, _ = skill_db

    # Mock async_session to use our SQLite session
    async def mock_async_session():
        return session_factory()

    # Create a context manager mock that returns our session
    class MockContextManager:
        def __init__(self):
            self.session = None

        async def __aenter__(self):
            self.session = session_factory()
            return await self.session.__aenter__()

        async def __aexit__(self, *args):
            if self.session:
                await self.session.__aexit__(*args)

    from agents.master_agent import _pre_route

    state = {
        "messages": [HumanMessage(content="/test_skill some args")],
        "user_id": None,
        "conversation_id": None,
        "loaded_facts": [],
        "initial_message_count": 0,
        "delivery_targets": [],
    }

    with patch("agents.master_agent.async_session", MockContextManager):
        result = await _pre_route(state)

    assert result == "skill_executor"


@pytest.mark.asyncio
async def test_pre_route_passes_non_slash_messages(skill_db) -> None:
    """_pre_route passes through non-slash messages to normal routing."""
    session_factory, _ = skill_db

    from agents.master_agent import _pre_route

    state = {
        "messages": [HumanMessage(content="Hello, how are you?")],
        "user_id": None,
        "conversation_id": None,
        "loaded_facts": [],
        "initial_message_count": 0,
        "delivery_targets": [],
    }

    # No DB lookup needed for non-slash messages
    result = await _pre_route(state)
    assert result == "master_agent"


@pytest.mark.asyncio
async def test_pre_route_unknown_slash_command(skill_db) -> None:
    """_pre_route handles unknown /commands by falling through to master_agent."""
    session_factory, _ = skill_db

    class MockContextManager:
        def __init__(self):
            self.session = None

        async def __aenter__(self):
            self.session = session_factory()
            return await self.session.__aenter__()

        async def __aexit__(self, *args):
            if self.session:
                await self.session.__aexit__(*args)

    from agents.master_agent import _pre_route

    state = {
        "messages": [HumanMessage(content="/unknown_command")],
        "user_id": None,
        "conversation_id": None,
        "loaded_facts": [],
        "initial_message_count": 0,
        "delivery_targets": [],
    }

    with patch("agents.master_agent.async_session", MockContextManager):
        result = await _pre_route(state)

    # Unknown command falls through to master_agent (no keyword match)
    assert result == "master_agent"


@pytest.mark.asyncio
async def test_pre_route_keyword_routing_not_affected() -> None:
    """_pre_route still routes email-related messages to email_agent."""
    from agents.master_agent import _pre_route

    state = {
        "messages": [HumanMessage(content="check my email inbox")],
        "user_id": None,
        "conversation_id": None,
        "loaded_facts": [],
        "initial_message_count": 0,
        "delivery_targets": [],
    }

    result = await _pre_route(state)
    assert result == "email_agent"


def test_skill_executor_node_in_graph() -> None:
    """skill_executor node exists in compiled master graph."""
    from agents.master_agent import create_master_graph

    with patch("agents.master_agent.MemorySaver"):
        graph = create_master_graph()

    # Check that skill_executor is in the graph nodes
    node_names = list(graph.get_graph().nodes.keys())
    assert "skill_executor" in node_names


def test_skill_executor_edge_to_delivery_router() -> None:
    """skill_executor has an edge to delivery_router in the graph."""
    from agents.master_agent import create_master_graph

    with patch("agents.master_agent.MemorySaver"):
        graph = create_master_graph()

    # Check edges — skill_executor should connect to delivery_router
    edges = graph.get_graph().edges
    skill_edges = [e for e in edges if e.source == "skill_executor"]
    assert any(e.target == "delivery_router" for e in skill_edges)
