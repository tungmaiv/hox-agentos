# Phase 14-01: Capabilities Tool Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Register a `system.capabilities` agent tool that queries all four registries and returns a user-scoped structured response when users ask "what can you do?"

**Architecture:** New `backend/capabilities/` module with Pydantic schemas and an async tool function. The tool is seeded into `tool_definitions` at startup (not via migration — seeded like legacy tools). The master agent's keyword routing directs capability-related intents to this tool.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, structlog

---

### Task 1: Create capabilities schemas

**Files:**
- Create: `backend/capabilities/__init__.py`
- Create: `backend/capabilities/schemas.py`

**Step 1: Create the module init**

```python
# backend/capabilities/__init__.py
```

(Empty file — just makes it a package.)

**Step 2: Write the Pydantic schemas**

```python
# backend/capabilities/schemas.py
"""Pydantic schemas for the system.capabilities tool response."""
import uuid
from pydantic import BaseModel, ConfigDict


class AgentInfo(BaseModel):
    name: str
    display_name: str | None
    description: str | None
    status: str

    model_config = ConfigDict(from_attributes=True)


class ToolInfo(BaseModel):
    name: str
    display_name: str | None
    description: str | None
    handler_type: str

    model_config = ConfigDict(from_attributes=True)


class SkillInfo(BaseModel):
    name: str
    display_name: str | None
    description: str | None
    slash_command: str | None

    model_config = ConfigDict(from_attributes=True)


class McpServerInfo(BaseModel):
    name: str
    display_name: str | None
    tools_count: int

    model_config = ConfigDict(from_attributes=True)


class CapabilitiesResponse(BaseModel):
    agents: list[AgentInfo]
    tools: list[ToolInfo]
    skills: list[SkillInfo]
    mcp_servers: list[McpServerInfo]
    summary: str
```

**Step 3: Commit**

```bash
git add backend/capabilities/__init__.py backend/capabilities/schemas.py
git commit -m "feat(14-01): add capabilities module with Pydantic schemas"
```

---

### Task 2: Write the capabilities tool function

**Files:**
- Create: `backend/capabilities/tool.py`

**Step 1: Write the tool function**

This queries all four registry tables, filters by user artifact permissions, and returns a structured response.

```python
# backend/capabilities/tool.py
"""
system.capabilities agent tool — returns what the platform can do.

Queries all four registries (agents, tools, skills, MCP servers) and
filters results by the calling user's artifact permissions.
"""
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from capabilities.schemas import (
    AgentInfo,
    CapabilitiesResponse,
    McpServerInfo,
    SkillInfo,
    ToolInfo,
)
from core.models.agent_definition import AgentDefinition
from core.models.mcp_server import McpServer
from core.models.skill_definition import SkillDefinition
from core.models.tool_definition import ToolDefinition
from security.rbac import batch_check_artifact_permissions

logger = structlog.get_logger(__name__)


async def system_capabilities(
    user_id: UUID,
    roles: list[str],
    session: AsyncSession,
) -> CapabilitiesResponse:
    """Return all platform capabilities visible to the given user.

    Called as an agent tool by the master agent when user asks
    "what can you do?" or similar capability-inquiry intents.
    """
    user_ctx = {"user_id": user_id, "roles": roles}

    # ── Agents ──────────────────────────────────────────────────
    agent_rows = (
        await session.execute(
            select(AgentDefinition).where(
                AgentDefinition.status == "active",
                AgentDefinition.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()

    agent_ids = [a.id for a in agent_rows]
    allowed_agent_ids = await batch_check_artifact_permissions(
        user_ctx, "agent", agent_ids, session
    )
    agents = [
        AgentInfo.model_validate(a)
        for a in agent_rows
        if a.id in allowed_agent_ids
    ]

    # ── Tools ───────────────────────────────────────────────────
    tool_rows = (
        await session.execute(
            select(ToolDefinition).where(
                ToolDefinition.status == "active",
                ToolDefinition.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()

    tool_ids = [t.id for t in tool_rows]
    allowed_tool_ids = await batch_check_artifact_permissions(
        user_ctx, "tool", tool_ids, session
    )
    tools = [
        ToolInfo.model_validate(t)
        for t in tool_rows
        if t.id in allowed_tool_ids
    ]

    # ── Skills ──────────────────────────────────────────────────
    skill_rows = (
        await session.execute(
            select(SkillDefinition).where(
                SkillDefinition.status == "active",
                SkillDefinition.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()

    skill_ids = [s.id for s in skill_rows]
    allowed_skill_ids = await batch_check_artifact_permissions(
        user_ctx, "skill", skill_ids, session
    )
    skills = [
        SkillInfo.model_validate(s)
        for s in skill_rows
        if s.id in allowed_skill_ids
    ]

    # ── MCP Servers (no per-server ACL currently) ───────────────
    mcp_rows = (
        await session.execute(
            select(McpServer).where(
                McpServer.is_active == True,  # noqa: E712
                McpServer.status == "active",
            )
        )
    ).scalars().all()

    # Count tools per MCP server from cached tool list
    mcp_tool_counts: dict[str, int] = {}
    for t in tool_rows:
        if t.handler_type == "mcp" and "." in t.name:
            server_name = t.name.split(".")[0]
            mcp_tool_counts[server_name] = mcp_tool_counts.get(server_name, 0) + 1

    mcp_servers = [
        McpServerInfo(
            name=m.name,
            display_name=m.display_name,
            tools_count=mcp_tool_counts.get(m.name, 0),
        )
        for m in mcp_rows
    ]

    summary = (
        f"{len(agents)} agent{'s' if len(agents) != 1 else ''}, "
        f"{len(tools)} tool{'s' if len(tools) != 1 else ''}, "
        f"{len(skills)} skill{'s' if len(skills) != 1 else ''}, "
        f"{len(mcp_servers)} MCP server{'s' if len(mcp_servers) != 1 else ''} available"
    )

    logger.info(
        "capabilities_queried",
        user_id=str(user_id),
        agents=len(agents),
        tools=len(tools),
        skills=len(skills),
        mcp_servers=len(mcp_servers),
    )

    return CapabilitiesResponse(
        agents=agents,
        tools=tools,
        skills=skills,
        mcp_servers=mcp_servers,
        summary=summary,
    )
```

**Step 2: Commit**

```bash
git add backend/capabilities/tool.py
git commit -m "feat(14-01): add system_capabilities tool function"
```

---

### Task 3: Write tests for capabilities tool

**Files:**
- Create: `backend/tests/test_capabilities.py`

**Step 1: Write the test file**

```python
# backend/tests/test_capabilities.py
"""Tests for the system.capabilities tool."""
import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from core.db import Base

# Import all models so Base.metadata has all tables
from core.models.agent_definition import AgentDefinition  # noqa: F401
from core.models.artifact_permission import ArtifactPermission  # noqa: F401
from core.models.mcp_server import McpServer  # noqa: F401
from core.models.role_permission import RolePermission  # noqa: F401
from core.models.skill_definition import SkillDefinition  # noqa: F401
from core.models.tool_definition import ToolDefinition  # noqa: F401
from core.models.user_artifact_permission import UserArtifactPermission  # noqa: F401


@pytest.fixture
def db_session():
    """Create in-memory SQLite DB with all tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(_setup())
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return factory


@pytest.fixture
def user_id():
    return uuid4()


@pytest.mark.asyncio
async def test_capabilities_empty_registries(db_session, user_id):
    """Returns empty lists when no artifacts are registered."""
    from capabilities.tool import system_capabilities

    async with db_session() as session:
        result = await system_capabilities(user_id, ["employee"], session)

    assert result.agents == []
    assert result.tools == []
    assert result.skills == []
    assert result.mcp_servers == []
    assert "0 agents" in result.summary


@pytest.mark.asyncio
async def test_capabilities_returns_active_artifacts(db_session, user_id):
    """Returns only active artifacts, not disabled ones."""
    from capabilities.tool import system_capabilities

    async with db_session() as session:
        # Add active agent
        session.add(AgentDefinition(
            name="email_agent", display_name="Email", description="Handles email",
            status="active", is_active=True,
        ))
        # Add disabled agent (should not appear)
        session.add(AgentDefinition(
            name="disabled_agent", display_name="Disabled", description="Off",
            status="disabled", is_active=False,
        ))
        # Add active tool
        session.add(ToolDefinition(
            name="email.fetch", display_name="Fetch Email", description="Fetch emails",
            handler_type="backend", status="active", is_active=True,
        ))
        # Add active skill
        session.add(SkillDefinition(
            name="morning-digest", display_name="Morning Digest",
            description="Daily summary", skill_type="instructional",
            slash_command="/digest", instruction_markdown="# Digest",
            status="active", is_active=True,
        ))
        # Add active MCP server
        session.add(McpServer(
            name="crm", url="http://mcp-crm:8001", status="active", is_active=True,
        ))
        await session.commit()

        result = await system_capabilities(user_id, ["employee"], session)

    assert len(result.agents) == 1
    assert result.agents[0].name == "email_agent"
    assert len(result.tools) == 1
    assert result.tools[0].name == "email.fetch"
    assert len(result.skills) == 1
    assert result.skills[0].slash_command == "/digest"
    assert len(result.mcp_servers) == 1
    assert result.mcp_servers[0].name == "crm"
    assert "1 agent" in result.summary


@pytest.mark.asyncio
async def test_capabilities_counts_mcp_tools(db_session, user_id):
    """MCP server tools_count reflects tool_definitions with matching prefix."""
    from capabilities.tool import system_capabilities

    async with db_session() as session:
        session.add(McpServer(
            name="crm", url="http://mcp-crm:8001", status="active", is_active=True,
        ))
        session.add(ToolDefinition(
            name="crm.list_projects", handler_type="mcp",
            status="active", is_active=True,
        ))
        session.add(ToolDefinition(
            name="crm.get_status", handler_type="mcp",
            status="active", is_active=True,
        ))
        await session.commit()

        result = await system_capabilities(user_id, ["employee"], session)

    assert result.mcp_servers[0].tools_count == 2
```

**Step 2: Run tests to verify they pass**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_capabilities.py -v
```

Expected: 3 PASSED

**Step 3: Commit**

```bash
git add backend/tests/test_capabilities.py
git commit -m "test(14-01): add capabilities tool unit tests"
```

---

### Task 4: Seed system.capabilities in tool registry at startup

**Files:**
- Modify: `backend/gateway/tool_registry.py` (lines 227-255, the `_LEGACY_REGISTRY` list)

**Step 1: Add system.capabilities to the legacy registry seed list**

In `backend/gateway/tool_registry.py`, add to the `_LEGACY_REGISTRY` list (after line 254):

```python
    {
        "name": "system.capabilities",
        "description": "List all agents, tools, skills, and MCP servers available to the current user",
        "required_permissions": ["chat"],
        "sandbox_required": False,
        "handler_type": "backend",
        "handler_module": "capabilities.tool",
        "handler_function": "system_capabilities",
    },
```

**Step 2: Run existing tool registry tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_tool_registry_db.py -v
```

Expected: all existing tests pass

**Step 3: Commit**

```bash
git add backend/gateway/tool_registry.py
git commit -m "feat(14-01): seed system.capabilities tool in startup registry"
```

---

### Task 5: Add keyword routing for capabilities intent

**Files:**
- Modify: `backend/agents/master_agent.py` (the `_FALLBACK_KEYWORD_MAP` dict)

**Step 1: Find and update the fallback keyword map**

In `backend/agents/master_agent.py`, locate `_FALLBACK_KEYWORD_MAP` (around line 415-430). Add capability-related keywords that route to the master agent (which will then invoke the tool):

The capabilities tool is invoked BY the master agent, not as a separate sub-agent. So instead of adding to the keyword map (which routes to sub-agents), we need to ensure the master agent knows to invoke `system.capabilities` when it detects these intents.

The master agent's LLM already has access to all registered tools via `create_master_graph()`. Since `system.capabilities` is registered as a `backend` tool in `tool_definitions`, the LLM will see it in its tool list and can decide to call it.

**No code change needed here** — the tool registration in Task 4 is sufficient. The master agent's LLM will see `system.capabilities` in the tool list with its description and invoke it when appropriate.

**Step 2: Verify the full test suite still passes**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: all tests pass (258+ baseline)

**Step 3: Commit (skip if no code changed)**

No commit needed for this task — routing is automatic via tool registration.

---

### Task 6: Run full test suite and verify

**Step 1: Run backend tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: baseline + 3 new = 261+ tests pass

**Step 2: Run frontend build**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build
```

Expected: 0 errors (no frontend changes in this plan)
