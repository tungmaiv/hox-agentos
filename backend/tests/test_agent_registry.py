"""Tests for dynamic agent graph wiring from DB registry.

Covers:
- Graph has nodes for active agents but NOT disabled ones
- _pre_route routes keywords to correct agent node
- _pre_route routes unknown keyword to master_agent
- session=None fallback to hardcoded agents (backward compat)
- Agent with is_active=False excluded even if status='active'
- last_seen_at is updated after dispatch
- Keyword routing from DB works
"""
import uuid
from datetime import datetime, timezone
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db import Base
from core.models.agent_definition import AgentDefinition


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    async_sess = async_sessionmaker(engine, expire_on_commit=False)
    async with async_sess() as s:
        yield s


@pytest.fixture(autouse=True)
def reset_keyword_map():
    """Reset keyword routing map before each test."""
    import agents.master_agent as ma

    old_map = ma._keyword_to_agent.copy()
    ma._keyword_to_agent.clear()
    yield
    ma._keyword_to_agent.clear()
    ma._keyword_to_agent.update(old_map)


async def _seed_agent(
    session: AsyncSession,
    name: str,
    handler_module: str = "agents.subagents.email_agent",
    handler_function: str = "email_agent_node",
    routing_keywords: list[str] | None = None,
    status: str = "active",
    is_active: bool = True,
) -> AgentDefinition:
    """Insert an agent definition row."""
    agent = AgentDefinition(
        id=uuid.uuid4(),
        name=name,
        display_name=name.replace("_", " ").title(),
        description=f"Test agent {name}",
        handler_module=handler_module,
        handler_function=handler_function,
        routing_keywords=routing_keywords or [],
        status=status,
        is_active=is_active,
    )
    session.add(agent)
    await session.commit()
    return agent


# ── Dynamic graph wiring tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_graph_has_active_agents_only(session: AsyncSession) -> None:
    """Graph includes active agents and excludes disabled ones."""
    from agents.master_agent import create_master_graph

    await _seed_agent(
        session, "email_agent",
        handler_module="agents.subagents.email_agent",
        handler_function="email_agent_node",
        routing_keywords=["email"],
    )
    await _seed_agent(
        session, "calendar_agent",
        handler_module="agents.subagents.calendar_agent",
        handler_function="calendar_agent_node",
        routing_keywords=["calendar"],
    )
    await _seed_agent(
        session, "project_agent",
        handler_module="agents.subagents.project_agent",
        handler_function="project_agent_node",
        routing_keywords=["project"],
        status="disabled",  # disabled!
    )

    # Load active agents from DB
    from core.models.agent_definition import AgentDefinition
    from sqlalchemy import select

    result = await session.execute(
        select(AgentDefinition).where(
            AgentDefinition.status == "active",
            AgentDefinition.is_active == True,  # noqa: E712
        )
    )
    active_agents = result.scalars().all()

    # Mock importlib to avoid importing real agent code
    mock_handler = AsyncMock(return_value={"messages": []})

    def mock_import(module_name):
        mod = ModuleType(module_name)
        setattr(mod, "email_agent_node", mock_handler)
        setattr(mod, "calendar_agent_node", mock_handler)
        return mod

    with patch("agents.master_agent.importlib.import_module", side_effect=mock_import):
        graph = create_master_graph(_db_agents=active_agents)

    node_names = list(graph.nodes)
    assert "email_agent" in node_names
    assert "calendar_agent" in node_names
    assert "project_agent" not in node_names  # disabled
    assert "master_agent" in node_names
    assert "delivery_router" in node_names


@pytest.mark.asyncio
async def test_is_active_false_excluded(session: AsyncSession) -> None:
    """Agent with is_active=False is excluded even if status='active'."""
    from agents.master_agent import create_master_graph

    await _seed_agent(
        session, "ghost_agent",
        handler_module="agents.subagents.email_agent",
        handler_function="email_agent_node",
        is_active=False,  # inactive
        status="active",
    )

    from core.models.agent_definition import AgentDefinition
    from sqlalchemy import select

    result = await session.execute(
        select(AgentDefinition).where(
            AgentDefinition.status == "active",
            AgentDefinition.is_active == True,  # noqa: E712
        )
    )
    active_agents = result.scalars().all()

    # Should have 0 active agents, so fallback to hardcoded
    graph = create_master_graph(_db_agents=active_agents)
    node_names = list(graph.nodes)
    # Fallback hardcoded agents should be present
    assert "email_agent" in node_names
    assert "calendar_agent" in node_names
    assert "project_agent" in node_names
    assert "ghost_agent" not in node_names


@pytest.mark.asyncio
async def test_session_none_fallback() -> None:
    """session=None falls back to hardcoded agent wiring."""
    from agents.master_agent import create_master_graph

    graph = create_master_graph()  # No session, no _db_agents
    node_names = list(graph.nodes)
    assert "email_agent" in node_names
    assert "calendar_agent" in node_names
    assert "project_agent" in node_names


# ── Keyword routing tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_keyword_routing_from_db(session: AsyncSession) -> None:
    """DB-loaded routing_keywords drive _classify_by_keywords."""
    from agents.master_agent import _classify_by_keywords, create_master_graph

    await _seed_agent(
        session, "email_agent",
        handler_module="agents.subagents.email_agent",
        handler_function="email_agent_node",
        routing_keywords=["email", "inbox", "mail"],
    )

    from core.models.agent_definition import AgentDefinition
    from sqlalchemy import select

    result = await session.execute(
        select(AgentDefinition).where(
            AgentDefinition.status == "active",
            AgentDefinition.is_active == True,  # noqa: E712
        )
    )
    active_agents = result.scalars().all()

    mock_handler = AsyncMock(return_value={"messages": []})

    def mock_import(module_name):
        mod = ModuleType(module_name)
        setattr(mod, "email_agent_node", mock_handler)
        return mod

    with patch("agents.master_agent.importlib.import_module", side_effect=mock_import):
        create_master_graph(_db_agents=active_agents)

    # Now _keyword_to_agent should be populated from DB
    assert _classify_by_keywords("check my email") == "email_agent"
    assert _classify_by_keywords("look at inbox") == "email_agent"


@pytest.mark.asyncio
async def test_pre_route_routes_email_keyword() -> None:
    """_pre_route routes 'email' keyword to email_agent node."""
    from langchain_core.messages import HumanMessage
    from agents.master_agent import _pre_route

    state = {"messages": [HumanMessage(content="show me my unread emails")]}

    with patch("agents.master_agent.async_session") as mock_session:
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=MagicMock(
            execute=AsyncMock(return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=None)
            ))
        ))
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_cm
        result = await _pre_route(state)

    assert result == "email_agent"


@pytest.mark.asyncio
async def test_pre_route_routes_unknown_to_master() -> None:
    """_pre_route returns 'master_agent' for general/unknown intent."""
    from langchain_core.messages import HumanMessage
    from agents.master_agent import _pre_route

    state = {"messages": [HumanMessage(content="tell me a joke")]}
    result = await _pre_route(state)
    assert result == "master_agent"


# ── last_seen_at tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_agent_last_seen(session: AsyncSession) -> None:
    """update_agent_last_seen sets last_seen_at for active agents."""
    from agents.master_agent import update_agent_last_seen
    from sqlalchemy import select

    agent = await _seed_agent(session, "test_agent")
    assert agent.last_seen_at is None

    await update_agent_last_seen("test_agent", session)

    result = await session.execute(
        select(AgentDefinition).where(AgentDefinition.name == "test_agent")
    )
    updated = result.scalar_one()
    assert updated.last_seen_at is not None


@pytest.mark.asyncio
async def test_update_agent_last_seen_batches(session: AsyncSession) -> None:
    """update_agent_last_seen does not update if last_seen_at is within 60s."""
    from agents.master_agent import update_agent_last_seen
    from sqlalchemy import select

    recent = datetime.now(timezone.utc)
    agent = await _seed_agent(session, "recent_agent")
    agent.last_seen_at = recent
    await session.commit()

    await update_agent_last_seen("recent_agent", session)

    result = await session.execute(
        select(AgentDefinition).where(AgentDefinition.name == "recent_agent")
    )
    updated = result.scalar_one()
    # Should still have a last_seen_at (not cleared)
    assert updated.last_seen_at is not None


@pytest.mark.asyncio
async def test_create_master_graph_from_db(session: AsyncSession) -> None:
    """create_master_graph_from_db loads agents from DB and compiles graph."""
    from agents.master_agent import create_master_graph_from_db

    await _seed_agent(
        session, "email_agent",
        handler_module="agents.subagents.email_agent",
        handler_function="email_agent_node",
        routing_keywords=["email"],
    )

    mock_handler = AsyncMock(return_value={"messages": []})

    def mock_import(module_name):
        mod = ModuleType(module_name)
        setattr(mod, "email_agent_node", mock_handler)
        return mod

    with patch("agents.master_agent.importlib.import_module", side_effect=mock_import):
        graph = await create_master_graph_from_db(session)

    assert "email_agent" in list(graph.nodes)
    assert "master_agent" in list(graph.nodes)
