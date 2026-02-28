# Phase 6: Extensibility Registries — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build database-backed registries for agents, tools, skills, and MCP servers with admin CRUD APIs, per-artifact permissions, a skill execution runtime with `/command` support, and a skill import pipeline with security scanning.

**Architecture:** Per-type registry tables (agent_definitions, tool_definitions, skill_definitions + evolved mcp_servers). Shared artifact_permissions and role_permissions tables. RBAC migrated from hardcoded dict to DB with in-process cache. SkillExecutor runs procedural skill pipelines. Import pipeline parses AgentSkills SKILL.md format with security scoring.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Pydantic v2, aiosqlite (tests), structlog, httpx (import fetching)

**Design doc:** `docs/plans/2026-02-28-phase-6-extensibility-registries-design.md`

**Test command:** `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q`

**Migration note:** Next migration number is `014` (current head is `013`).

---

## Task 1: ORM Models + Alembic Migration

**Files:**
- Create: `backend/core/models/agent_definition.py`
- Create: `backend/core/models/tool_definition.py`
- Create: `backend/core/models/skill_definition.py`
- Create: `backend/core/models/artifact_permission.py`
- Create: `backend/core/models/role_permission.py`
- Modify: `backend/core/models/__init__.py` (add imports)
- Modify: `backend/core/models/mcp_server.py` (add version, display_name, status)
- Create: `backend/alembic/versions/014_extensibility_registries.py`
- Create: `backend/tests/test_registry_models.py`

### Step 1: Write tests for new ORM models

Create `backend/tests/test_registry_models.py`:

```python
"""Tests for Phase 6 extensibility registry ORM models."""
import asyncio
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db import Base
from core.models.agent_definition import AgentDefinition
from core.models.tool_definition import ToolDefinition
from core.models.skill_definition import SkillDefinition
from core.models.artifact_permission import ArtifactPermission
from core.models.role_permission import RolePermission


@pytest.fixture
def db_session():
    """Create in-memory SQLite DB with all tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    loop = asyncio.new_event_loop()

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop.run_until_complete(_setup())
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _get():
        async with factory() as s:
            yield s

    yield factory, loop
    loop.run_until_complete(engine.dispose())
    loop.close()


def test_agent_definition_create(db_session):
    factory, loop = db_session

    async def _run():
        async with factory() as session:
            agent = AgentDefinition(
                name="email_agent",
                display_name="Email Agent",
                description="Handles email tasks",
                version="1.0.0",
                status="active",
                handler_module="agents.subagents.email_agent",
                handler_function="email_agent_node",
                routing_keywords=["email", "inbox", "mail"],
                config_json={},
            )
            session.add(agent)
            await session.commit()

            result = await session.execute(
                select(AgentDefinition).where(AgentDefinition.name == "email_agent")
            )
            row = result.scalar_one()
            assert row.display_name == "Email Agent"
            assert row.status == "active"
            assert row.routing_keywords == ["email", "inbox", "mail"]

    loop.run_until_complete(_run())


def test_tool_definition_create(db_session):
    factory, loop = db_session

    async def _run():
        async with factory() as session:
            tool = ToolDefinition(
                name="email.fetch_inbox",
                display_name="Fetch Inbox",
                description="Fetch emails from inbox",
                version="1.0.0",
                status="active",
                handler_type="backend",
                handler_module="tools.email_tools",
                handler_function="fetch_inbox",
            )
            session.add(tool)
            await session.commit()

            result = await session.execute(
                select(ToolDefinition).where(ToolDefinition.name == "email.fetch_inbox")
            )
            row = result.scalar_one()
            assert row.handler_type == "backend"
            assert row.sandbox_required is False

    loop.run_until_complete(_run())


def test_skill_definition_create(db_session):
    factory, loop = db_session

    async def _run():
        async with factory() as session:
            skill = SkillDefinition(
                name="morning_digest",
                display_name="Morning Digest",
                description="Use when user wants a summary of morning emails",
                version="1.0.0",
                status="active",
                skill_type="procedural",
                slash_command="/morning_digest",
                procedure_json={
                    "schema_version": "1.0",
                    "steps": [
                        {"id": "fetch", "type": "tool", "tool": "email.fetch_inbox",
                         "params": {"max_results": 10}},
                    ],
                    "output": "{{fetch.output}}",
                },
                source_type="builtin",
            )
            session.add(skill)
            await session.commit()

            result = await session.execute(
                select(SkillDefinition).where(SkillDefinition.name == "morning_digest")
            )
            row = result.scalar_one()
            assert row.skill_type == "procedural"
            assert row.slash_command == "/morning_digest"
            assert row.procedure_json["schema_version"] == "1.0"

    loop.run_until_complete(_run())


def test_skill_definition_instructional(db_session):
    factory, loop = db_session

    async def _run():
        async with factory() as session:
            skill = SkillDefinition(
                name="email_etiquette",
                display_name="Email Etiquette",
                description="Use when drafting professional emails",
                version="1.0.0",
                status="active",
                skill_type="instructional",
                slash_command="/email_etiquette",
                instruction_markdown="# Email Etiquette\n\nAlways be polite...",
                source_type="admin_created",
            )
            session.add(skill)
            await session.commit()

            result = await session.execute(
                select(SkillDefinition).where(SkillDefinition.name == "email_etiquette")
            )
            row = result.scalar_one()
            assert row.skill_type == "instructional"
            assert row.instruction_markdown.startswith("# Email Etiquette")

    loop.run_until_complete(_run())


def test_artifact_permission_create(db_session):
    factory, loop = db_session

    async def _run():
        async with factory() as session:
            artifact_id = uuid.uuid4()
            perm = ArtifactPermission(
                artifact_type="skill",
                artifact_id=artifact_id,
                role="employee",
                allowed=True,
            )
            session.add(perm)
            await session.commit()

            result = await session.execute(
                select(ArtifactPermission).where(
                    ArtifactPermission.artifact_id == artifact_id
                )
            )
            row = result.scalar_one()
            assert row.artifact_type == "skill"
            assert row.role == "employee"
            assert row.allowed is True

    loop.run_until_complete(_run())


def test_role_permission_create(db_session):
    factory, loop = db_session

    async def _run():
        async with factory() as session:
            rp = RolePermission(role="employee", permission="chat")
            session.add(rp)
            await session.commit()

            result = await session.execute(
                select(RolePermission).where(RolePermission.role == "employee")
            )
            row = result.scalar_one()
            assert row.permission == "chat"

    loop.run_until_complete(_run())


def test_name_uniqueness_enforced(db_session):
    """Unique constraint on name prevents duplicate registrations."""
    factory, loop = db_session

    async def _run():
        async with factory() as session:
            session.add(AgentDefinition(
                name="dup_agent", display_name="A", description="A",
                version="1.0", status="active",
                handler_module="m", handler_function="f",
            ))
            await session.commit()

        async with factory() as session:
            session.add(AgentDefinition(
                name="dup_agent", display_name="B", description="B",
                version="1.0", status="active",
                handler_module="m", handler_function="f",
            ))
            with pytest.raises(Exception):  # IntegrityError
                await session.commit()

    loop.run_until_complete(_run())
```

### Step 2: Run tests to verify they fail

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_registry_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'core.models.agent_definition'`

### Step 3: Create ORM model files

Create `backend/core/models/agent_definition.py`:

```python
"""Agent definition registry model."""
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class AgentDefinition(Base):
    __tablename__ = "agent_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    version: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, server_default="active"
    )
    handler_module: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    handler_function: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    routing_keywords: Mapped[dict | None] = mapped_column(
        sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
    )
    config_json: Mapped[dict | None] = mapped_column(
        sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )
```

Create `backend/core/models/tool_definition.py`:

```python
"""Tool definition registry model."""
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class ToolDefinition(Base):
    __tablename__ = "tool_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    version: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, server_default="active"
    )
    handler_type: Mapped[str] = mapped_column(
        sa.String(20), nullable=False
    )  # backend, mcp, sandbox
    handler_module: Mapped[str | None] = mapped_column(sa.String(256), nullable=True)
    handler_function: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    mcp_server_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, nullable=True)
    mcp_tool_name: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    sandbox_required: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("false")
    )
    input_schema: Mapped[dict | None] = mapped_column(
        sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
    )
    output_schema: Mapped[dict | None] = mapped_column(
        sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )
```

Create `backend/core/models/skill_definition.py`:

```python
"""Skill definition registry model."""
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class SkillDefinition(Base):
    __tablename__ = "skill_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    version: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, server_default="active"
    )
    skill_type: Mapped[str] = mapped_column(
        sa.String(20), nullable=False
    )  # instructional, procedural
    slash_command: Mapped[str | None] = mapped_column(
        sa.String(64), nullable=True, unique=True
    )
    instruction_markdown: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    procedure_json: Mapped[dict | None] = mapped_column(
        sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
    )
    input_schema: Mapped[dict | None] = mapped_column(
        sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
    )
    output_schema: Mapped[dict | None] = mapped_column(
        sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
    )
    source_type: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, server_default="admin_created"
    )
    source_url: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    security_score: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    security_report: Mapped[dict | None] = mapped_column(
        sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )
```

Create `backend/core/models/artifact_permission.py`:

```python
"""Artifact permission model — per-artifact per-role access control."""
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class ArtifactPermission(Base):
    __tablename__ = "artifact_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, default=uuid.uuid4
    )
    artifact_type: Mapped[str] = mapped_column(
        sa.String(20), nullable=False
    )  # agent, tool, skill, mcp_server
    artifact_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False)
    role: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    allowed: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("artifact_type", "artifact_id", "role"),
        sa.Index("ix_artifact_permissions_lookup", "artifact_type", "artifact_id"),
    )
```

Create `backend/core/models/role_permission.py`:

```python
"""Role permission model — replaces hardcoded ROLE_PERMISSIONS dict."""
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, primary_key=True, default=uuid.uuid4
    )
    role: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    permission: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("role", "permission"),
        sa.Index("ix_role_permissions_role", "role"),
    )
```

### Step 4: Add model imports to `__init__.py`

Add to `backend/core/models/__init__.py`:

```python
from core.models.agent_definition import AgentDefinition       # noqa: F401
from core.models.artifact_permission import ArtifactPermission # noqa: F401
from core.models.role_permission import RolePermission         # noqa: F401
from core.models.skill_definition import SkillDefinition       # noqa: F401
from core.models.tool_definition import ToolDefinition         # noqa: F401
```

### Step 5: Evolve `mcp_server.py` — add version, display_name, status columns

Add to `backend/core/models/mcp_server.py` (after existing `is_active` column):

```python
    version: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'active'")
    )
```

### Step 6: Create Alembic migration 014

Create `backend/alembic/versions/014_extensibility_registries.py`. The migration must:
1. Create all 5 new tables
2. Add 3 new columns to `mcp_servers`
3. Seed `role_permissions` with current ROLE_PERMISSIONS values
4. Seed `agent_definitions` with 4 agent rows
5. Seed `tool_definitions` with 3 CRM tool rows

The migration uses `op.bulk_insert()` for seed data. Use `ON CONFLICT DO NOTHING` pattern for idempotency.

### Step 7: Run model tests to verify they pass

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_registry_models.py -v
```

Expected: all 7 tests PASS

### Step 8: Run full test suite to check for regressions

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: all existing tests still pass (new models don't affect existing code)

### Step 9: Commit

```bash
git add backend/core/models/agent_definition.py backend/core/models/tool_definition.py \
  backend/core/models/skill_definition.py backend/core/models/artifact_permission.py \
  backend/core/models/role_permission.py backend/core/models/__init__.py \
  backend/core/models/mcp_server.py backend/alembic/versions/014_extensibility_registries.py \
  backend/tests/test_registry_models.py
git commit -m "feat(06-01): add extensibility registry ORM models and migration 014"
```

---

## Task 2: RBAC Migration — DB-Backed Permissions

**Files:**
- Modify: `backend/security/rbac.py`
- Create: `backend/tests/test_rbac_db.py`

### Step 1: Write tests for DB-backed has_permission

Create `backend/tests/test_rbac_db.py`:

```python
"""Tests for DB-backed RBAC permission checks (Phase 6 migration)."""
import asyncio
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.db import Base
from core.models.role_permission import RolePermission
from core.models.artifact_permission import ArtifactPermission
from security.rbac import (
    has_permission,
    check_artifact_permission,
    invalidate_permission_cache,
)


@pytest.fixture
def db_with_perms():
    """SQLite DB seeded with role_permissions matching current hardcoded dict."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    loop = asyncio.new_event_loop()

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            # Seed employee permissions
            for perm in ["chat", "tool:email", "tool:calendar", "tool:project", "crm:read"]:
                session.add(RolePermission(role="employee", permission=perm))
            # Seed it-admin permissions
            for perm in ["chat", "tool:email", "tool:calendar", "tool:project",
                         "crm:read", "crm:write", "tool:reports", "workflow:create",
                         "workflow:approve", "tool:admin", "sandbox:execute",
                         "registry:manage"]:
                session.add(RolePermission(role="it-admin", permission=perm))
            await session.commit()

    loop.run_until_complete(_setup())
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory, loop
    loop.run_until_complete(engine.dispose())
    loop.close()


def test_employee_has_chat_permission(db_with_perms):
    factory, loop = db_with_perms
    user = {"user_id": uuid.uuid4(), "roles": ["employee"], "email": "e@b.l", "username": "e", "groups": []}
    invalidate_permission_cache()

    async def _run():
        async with factory() as session:
            result = await has_permission(user, "chat", session)
            assert result is True

    loop.run_until_complete(_run())


def test_employee_denied_registry_manage(db_with_perms):
    factory, loop = db_with_perms
    user = {"user_id": uuid.uuid4(), "roles": ["employee"], "email": "e@b.l", "username": "e", "groups": []}
    invalidate_permission_cache()

    async def _run():
        async with factory() as session:
            result = await has_permission(user, "registry:manage", session)
            assert result is False

    loop.run_until_complete(_run())


def test_admin_has_registry_manage(db_with_perms):
    factory, loop = db_with_perms
    user = {"user_id": uuid.uuid4(), "roles": ["it-admin"], "email": "a@b.l", "username": "a", "groups": []}
    invalidate_permission_cache()

    async def _run():
        async with factory() as session:
            result = await has_permission(user, "registry:manage", session)
            assert result is True

    loop.run_until_complete(_run())


def test_unknown_role_denied(db_with_perms):
    factory, loop = db_with_perms
    user = {"user_id": uuid.uuid4(), "roles": ["unknown_role"], "email": "u@b.l", "username": "u", "groups": []}
    invalidate_permission_cache()

    async def _run():
        async with factory() as session:
            result = await has_permission(user, "chat", session)
            assert result is False

    loop.run_until_complete(_run())


def test_artifact_permission_default_allow(db_with_perms):
    """No artifact_permissions row = default allow."""
    factory, loop = db_with_perms
    user = {"user_id": uuid.uuid4(), "roles": ["employee"], "email": "e@b.l", "username": "e", "groups": []}

    async def _run():
        async with factory() as session:
            result = await check_artifact_permission(
                user, "skill", uuid.uuid4(), session
            )
            assert result is True

    loop.run_until_complete(_run())


def test_artifact_permission_explicit_deny(db_with_perms):
    """Explicit allowed=False denies access for that role."""
    factory, loop = db_with_perms
    artifact_id = uuid.uuid4()

    async def _seed_deny():
        async with factory() as session:
            session.add(ArtifactPermission(
                artifact_type="skill", artifact_id=artifact_id,
                role="employee", allowed=False,
            ))
            await session.commit()

    loop = db_with_perms[1]
    loop.run_until_complete(_seed_deny())

    user = {"user_id": uuid.uuid4(), "roles": ["employee"], "email": "e@b.l", "username": "e", "groups": []}

    async def _run():
        async with factory() as session:
            result = await check_artifact_permission(
                user, "skill", artifact_id, session
            )
            assert result is False

    loop.run_until_complete(_run())
```

### Step 2: Run tests to verify they fail

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_rbac_db.py -v
```

Expected: FAIL — `has_permission` signature mismatch (currently sync, no session param)

### Step 3: Update `security/rbac.py`

Modify `backend/security/rbac.py`:

1. Keep `ROLE_PERMISSIONS` dict as **fallback** during migration (used when DB is empty)
2. Add `has_permission()` as async with session parameter and in-process cache
3. Add `check_artifact_permission()` for Gate 2.5
4. Add `invalidate_permission_cache()` for admin write endpoints
5. Keep sync `get_permissions()` for backward compatibility (existing callers)

Key changes:
- `has_permission(user, permission)` becomes `has_permission(user, permission, session)` — async, queries `role_permissions` table
- Cache: module-level `_permission_cache: dict[str, set[str]]` with `_cache_timestamp: float` and 60s TTL
- Fallback: if no rows in DB, fall back to `ROLE_PERMISSIONS` dict (backward compat during migration rollout)

### Step 4: Update all callers of has_permission to pass session

Search for all callers:
- `security/acl.py` — already has session
- `mcp/registry.py:call_mcp_tool` — already has session
- `api/routes/mcp_servers.py:_require_admin` — needs session added via Depends
- `agents/master_agent.py:_pre_route` — uses its own session

Each caller that uses `has_permission` as a sync function call needs to be updated to `await has_permission(user, perm, session)`.

**Important:** This is a breaking change for existing test mocks. Update test patches accordingly.

### Step 5: Run tests

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_rbac_db.py tests/ -q
```

Expected: all tests pass (new + existing)

### Step 6: Commit

```bash
git add backend/security/rbac.py backend/tests/test_rbac_db.py
# Also add any files with updated has_permission callers
git commit -m "feat(06-02): migrate RBAC to DB-backed role_permissions with cache"
```

---

## Task 3: Pydantic Schemas for Registry APIs

**Files:**
- Create: `backend/core/schemas/registry.py`

### Step 1: Create Pydantic request/response schemas

Create `backend/core/schemas/registry.py` with:

- `AgentDefinitionCreate` / `AgentDefinitionUpdate` / `AgentDefinitionResponse`
- `ToolDefinitionCreate` / `ToolDefinitionUpdate` / `ToolDefinitionResponse`
- `SkillDefinitionCreate` / `SkillDefinitionUpdate` / `SkillDefinitionResponse`
- `ArtifactPermissionSet` / `ArtifactPermissionResponse`
- `RolePermissionSet` / `RolePermissionResponse`
- `StatusUpdate` (shared for PATCH status endpoints)
- `SkillImportRequest` / `SkillReviewRequest` / `SecurityReportResponse`

All schemas use Pydantic v2 `BaseModel` with strict validation. `SkillDefinitionCreate` validates that either `instruction_markdown` or `procedure_json` is provided (not both or neither) based on `skill_type`.

### Step 2: Commit

```bash
git add backend/core/schemas/registry.py
git commit -m "feat(06-03): add Pydantic schemas for registry CRUD APIs"
```

---

## Task 4: Admin CRUD APIs — Agents, Tools, Skills

**Files:**
- Create: `backend/api/routes/admin_agents.py`
- Create: `backend/api/routes/admin_tools.py`
- Create: `backend/api/routes/admin_skills.py`
- Create: `backend/api/routes/admin_permissions.py`
- Modify: `backend/main.py` (include new routers)
- Create: `backend/tests/api/test_admin_agents.py`
- Create: `backend/tests/api/test_admin_tools.py`
- Create: `backend/tests/api/test_admin_skills.py`
- Create: `backend/tests/api/test_admin_permissions.py`

### Step 1: Write tests for admin agent CRUD

Follow the pattern from `tests/test_system_config.py`:
- SQLite in-memory DB fixture with seed data
- `_require_registry_manager` dependency override
- Test cases: 401 without auth, 403 with employee, 200 with it-admin
- CRUD: list, create, get by id, update, patch status

### Step 2: Implement admin agent routes

`backend/api/routes/admin_agents.py`:
- Router prefix: `/api/admin/agents`
- Dependency: `_require_registry_manager` checks `registry:manage`
- Endpoints: GET list, POST create, GET by id, PUT update, PATCH status
- Uses `get_db` dependency for async session
- Logging: structlog audit events for create/update/disable

### Step 3: Write tests + implement admin tool routes

Same pattern as agents. `backend/api/routes/admin_tools.py` with prefix `/api/admin/tools`.

### Step 4: Write tests + implement admin skill routes

`backend/api/routes/admin_skills.py` with prefix `/api/admin/skills`.

Additional endpoints beyond basic CRUD:
- `POST /validate` — dry-run procedure_json validation
- `GET /pending` — list skills with `status='pending_review'`
- Import and review endpoints added in Task 7

### Step 5: Write tests + implement admin permission routes

`backend/api/routes/admin_permissions.py` with prefix `/api/admin/permissions`.

Endpoints:
- `GET /roles` — list all role-permission mappings
- `PUT /roles/{role}` — set permissions for a role (invalidates cache)
- `GET /artifacts/{type}/{id}` — get artifact permission overrides
- `PUT /artifacts/{type}/{id}` — set per-role permissions for artifact

### Step 6: Register routers in main.py

Add to `backend/main.py` imports and include:

```python
from api.routes import admin_agents, admin_tools, admin_skills, admin_permissions

app.include_router(admin_agents.router)
app.include_router(admin_tools.router)
app.include_router(admin_skills.router)
app.include_router(admin_permissions.router)
```

### Step 7: Run tests

```bash
PYTHONPATH=. .venv/bin/pytest tests/api/test_admin_agents.py tests/api/test_admin_tools.py \
  tests/api/test_admin_skills.py tests/api/test_admin_permissions.py -v
```

### Step 8: Run full suite

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

### Step 9: Commit

```bash
git add backend/api/routes/admin_agents.py backend/api/routes/admin_tools.py \
  backend/api/routes/admin_skills.py backend/api/routes/admin_permissions.py \
  backend/main.py backend/tests/api/test_admin_*.py
git commit -m "feat(06-04): add admin CRUD APIs for agents, tools, skills, and permissions"
```

---

## Task 5: Tool Registry DB Integration

**Files:**
- Modify: `backend/gateway/tool_registry.py`
- Modify: `backend/mcp/registry.py`
- Create: `backend/tests/test_tool_registry_db.py`

### Step 1: Write tests for DB-backed tool registry

Test that:
- `get_tool()` returns tools from DB where `status='active'`
- `get_tool()` returns `None` for `status='disabled'`
- `register_tool()` upserts into `tool_definitions` table
- `list_tools()` only returns active tools
- Cache works (second call doesn't hit DB if within TTL)
- `invalidate_tool_cache()` forces refresh

### Step 2: Migrate `tool_registry.py`

Replace the in-process `_registry` dict with DB queries:

```python
# Keep _cache as in-process dict for performance
_cache: dict[str, dict] = {}
_cache_timestamp: float = 0.0
_CACHE_TTL = 60.0  # seconds

async def _refresh_cache(session: AsyncSession) -> None:
    """Reload active tools from DB into in-process cache."""
    global _cache, _cache_timestamp
    result = await session.execute(
        select(ToolDefinition).where(ToolDefinition.status == "active")
    )
    tools = result.scalars().all()
    _cache = {t.name: _tool_to_dict(t) for t in tools}
    _cache_timestamp = time.time()

async def get_tool(name: str, session: AsyncSession) -> dict | None:
    """Get tool by name from cache (refreshed from DB on TTL expiry)."""
    if time.time() - _cache_timestamp > _CACHE_TTL:
        await _refresh_cache(session)
    return _cache.get(name)
```

### Step 3: Update `MCPToolRegistry.refresh()`

Modify `mcp/registry.py` to upsert discovered MCP tools into `tool_definitions` table instead of calling `register_tool()` with the old dict-based API.

### Step 4: Update all callers of `get_tool()` to pass session

### Step 5: Run tests

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_tool_registry_db.py tests/ -q
```

### Step 6: Commit

```bash
git add backend/gateway/tool_registry.py backend/mcp/registry.py \
  backend/tests/test_tool_registry_db.py
git commit -m "feat(06-05): migrate tool registry from in-process dict to DB-backed"
```

---

## Task 6: Agent Registry — Dynamic Graph Wiring

**Files:**
- Modify: `backend/agents/master_agent.py`
- Create: `backend/tests/test_agent_registry.py`

### Step 1: Write tests for dynamic agent graph

Test that:
- `create_master_graph()` loads agents from `agent_definitions` where `status='active'`
- Disabled agents are not wired into the graph
- `_pre_route()` uses `routing_keywords` from DB instead of hardcoded keywords
- Unknown routes fall through to `master_agent` node

### Step 2: Update `create_master_graph()`

```python
async def create_master_graph(session: AsyncSession | None = None) -> CompiledStateGraph:
    """Build graph with dynamically loaded agents from DB."""
    # Load active agents from DB
    if session:
        result = await session.execute(
            select(AgentDefinition).where(AgentDefinition.status == "active")
        )
        agents = result.scalars().all()
    else:
        agents = []  # fallback: master-only graph

    graph = StateGraph(BlitzState)
    graph.add_node("load_memory", _load_memory_node)
    graph.add_node("master_agent", _master_node)
    graph.add_node("delivery_router", _delivery_router_node)
    graph.add_node("save_memory", _save_memory_node)

    # Dynamically add agent nodes
    for agent_def in agents:
        if agent_def.name == "master_agent":
            continue  # master is always added above
        module = importlib.import_module(agent_def.handler_module)
        handler = getattr(module, agent_def.handler_function)
        graph.add_node(agent_def.name, handler)
        graph.add_edge(agent_def.name, "delivery_router")

    # Build routing map from DB keywords
    # ... (see _pre_route update below)
```

### Step 3: Update `_pre_route()` to use DB keywords

Load `routing_keywords` from `agent_definitions` and build keyword map dynamically instead of hardcoded keyword sets.

### Step 4: Run tests

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_agent_registry.py tests/ -q
```

### Step 5: Commit

```bash
git add backend/agents/master_agent.py backend/tests/test_agent_registry.py
git commit -m "feat(06-06): dynamic agent graph wiring from DB registry"
```

---

## Task 7: Skill Runtime — SkillExecutor

**Files:**
- Create: `backend/skills/__init__.py`
- Create: `backend/skills/executor.py`
- Create: `backend/skills/validator.py`
- Create: `backend/tests/test_skill_executor.py`
- Create: `backend/tests/test_skill_validator.py`

### Step 1: Write tests for skill validator

Test:
- Valid procedural skill procedure_json passes validation
- Missing required fields fail
- Unknown step types fail
- Variable references to non-existent steps fail
- Step count > 20 fails
- Valid instructional skill passes

### Step 2: Implement skill validator

`backend/skills/validator.py`:

```python
class SkillValidator:
    """Validates skill definitions before save or execution."""

    def validate_procedure(self, procedure_json: dict) -> list[str]:
        """Returns list of error messages. Empty = valid."""
        errors = []
        if "schema_version" not in procedure_json:
            errors.append("Missing schema_version")
        steps = procedure_json.get("steps", [])
        if len(steps) > 20:
            errors.append(f"Too many steps: {len(steps)} (max 20)")
        # ... validate step types, variable refs, etc.
        return errors
```

### Step 3: Write tests for SkillExecutor

Test:
- Procedural skill with one tool step executes successfully (mock tool call)
- Procedural skill with LLM step calls `get_llm()` with correct alias
- Variable interpolation `{{step_id.output}}` works between steps
- Failed tool step stops execution and returns partial result
- Security: tool step checks 3-gate security (mock `check_tool_acl`)
- Audit log emitted for each step

### Step 4: Implement SkillExecutor

`backend/skills/executor.py`:

```python
class SkillExecutor:
    """Runs procedural skill pipelines step-by-step."""

    async def run(
        self,
        skill: SkillDefinition,
        user_context: UserContext,
        session: AsyncSession,
        user_input: dict | None = None,
    ) -> SkillResult:
        context = StepContext(user_input=user_input, outputs={})

        for step in skill.procedure_json["steps"]:
            step_type = step.get("type", "tool")
            try:
                match step_type:
                    case "tool":
                        result = await self._run_tool_step(step, context, user_context, session)
                    case "llm":
                        result = await self._run_llm_step(step, context)
                    case "condition":
                        result = await self._run_condition_step(step, context)
                    case _:
                        raise SkillStepError(f"Unknown step type: {step_type}")
            except Exception as exc:
                return SkillResult(
                    success=False,
                    output=str(exc),
                    step_outputs=context.outputs,
                    failed_step=step["id"],
                )
            context.outputs[step["id"]] = result

        return SkillResult(
            success=True,
            output=self._resolve_template(skill.procedure_json["output"], context),
            step_outputs=context.outputs,
        )

    async def _run_tool_step(self, step, context, user_context, session):
        """Execute a tool step through 3-gate security."""
        tool_name = step["tool"]
        # Gate 2: RBAC
        tool_def = await get_tool(tool_name, session)
        if not tool_def:
            raise SkillStepError(f"Tool not found: {tool_name}")
        # Gate 3: ACL
        allowed = await check_tool_acl(user_context["user_id"], tool_name, session)
        if not allowed:
            raise SkillStepError(f"Access denied to tool: {tool_name}")
        # Execute
        params = self._resolve_params(step.get("params", {}), context)
        # ... call tool handler
```

### Step 5: Run tests

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_skill_executor.py tests/test_skill_validator.py -v
```

### Step 6: Commit

```bash
git add backend/skills/ backend/tests/test_skill_executor.py backend/tests/test_skill_validator.py
git commit -m "feat(06-07): implement SkillExecutor runtime and validator"
```

---

## Task 8: Skill Import Pipeline + Security Scanner

**Files:**
- Create: `backend/skills/importer.py`
- Create: `backend/skills/security_scanner.py`
- Create: `backend/tests/test_skill_importer.py`
- Create: `backend/tests/test_security_scanner.py`

### Step 1: Write tests for security scanner

Test:
- Clean text gets score 100 for prompt_safety
- Known injection pattern "ignore all previous instructions" gets score 0
- Source reputation: agentskills.io = 95, unknown URL = 20
- Tool scope: read-only tools = 100, admin tools = 0
- Overall score computed correctly with weights
- Score below threshold (60) flags as rejected

### Step 2: Implement security scanner

`backend/skills/security_scanner.py`:

```python
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"forget\s+(everything|all|your)",
    r"you\s+are\s+now\s+a",
    r"system\s*:\s*",
    r"<\|im_start\|>",
    r"Human:\s*|Assistant:\s*",
    r"(curl|wget|fetch)\s+http",
    r"base64\.(encode|decode)",
    r"eval\(|exec\(|__import__",
]

class SecurityScanner:
    def scan(self, skill_data: dict, source_url: str | None) -> SecurityReport:
        """Compute security score and generate report."""
        # ...
```

### Step 3: Write tests for SKILL.md importer

Test:
- Parse valid AgentSkills SKILL.md with YAML frontmatter → correct name, description, instruction_markdown
- Parse SKILL.md with procedure metadata → correct procedure_json
- Invalid YAML frontmatter → error
- Missing required fields → error

### Step 4: Implement SKILL.md importer

`backend/skills/importer.py`:

```python
import re
import yaml

class SkillImporter:
    def parse_skill_md(self, content: str) -> dict:
        """Parse AgentSkills SKILL.md format into internal representation."""
        # Extract YAML frontmatter between --- delimiters
        match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
        if not match:
            raise ImportError("No YAML frontmatter found")
        frontmatter = yaml.safe_load(match.group(1))
        body = match.group(2).strip()
        return {
            "name": frontmatter["name"],
            "description": frontmatter.get("description", ""),
            "instruction_markdown": body,
            "skill_type": "instructional",
            # ... extract version, metadata
        }

    async def import_from_url(self, url: str) -> dict:
        """Fetch SKILL.md from URL and parse it."""
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30)
            response.raise_for_status()
        return self.parse_skill_md(response.text)
```

### Step 5: Add import + review endpoints to admin skills router

Add to `backend/api/routes/admin_skills.py`:

- `POST /import` — accepts `{source_url: str}` or `{content: str}`, runs importer + scanner, creates skill with `status='pending_review'`
- `POST /{id}/review` — accepts `{decision: "approve" | "reject", notes: str}`, updates status
- `GET /{id}/security-report` — returns stored security report

### Step 6: Run tests

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_skill_importer.py tests/test_security_scanner.py -v
```

### Step 7: Commit

```bash
git add backend/skills/importer.py backend/skills/security_scanner.py \
  backend/tests/test_skill_importer.py backend/tests/test_security_scanner.py \
  backend/api/routes/admin_skills.py
git commit -m "feat(06-08): implement skill import pipeline with security scanning"
```

---

## Task 9: User-Facing Skill APIs + Slash Command Dispatch

**Files:**
- Create: `backend/api/routes/user_skills.py`
- Modify: `backend/agents/master_agent.py` (add `/command` detection)
- Modify: `backend/main.py` (include user_skills router)
- Create: `backend/tests/api/test_user_skills.py`
- Create: `backend/tests/test_slash_dispatch.py`

### Step 1: Write tests for user skill listing

Test:
- `GET /api/skills` returns only active skills visible to user's role
- Skills with `artifact_permissions` deny for user's role are excluded
- Response includes name, display_name, description, slash_command

### Step 2: Write tests for skill execution

Test:
- `POST /api/skills/morning_digest/run` executes the skill (mock tools)
- Skill not found → 404
- Skill disabled → 404
- User's role denied artifact permission → 403
- Procedural skill returns structured result
- Instructional skill returns instruction text (for agent context injection)

### Step 3: Implement user_skills router

`backend/api/routes/user_skills.py`:

```python
router = APIRouter(prefix="/api/skills", tags=["skills"])

@router.get("")
async def list_available_skills(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SkillListItem]:
    """List skills available to the current user."""
    # Query active skills, filter by artifact_permissions for user's roles
    ...

@router.post("/{skill_name}/run")
async def run_skill(
    skill_name: str,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SkillRunResponse:
    """Execute a skill by name."""
    # Lookup skill, check permissions, dispatch to SkillExecutor
    ...
```

### Step 4: Add `/command` detection to master_agent

Modify `_pre_route()` in `backend/agents/master_agent.py`:

```python
async def _pre_route(state: BlitzState) -> str:
    last_msg = state["messages"][-1].content if state["messages"] else ""

    # Detect slash command
    if isinstance(last_msg, str) and last_msg.strip().startswith("/"):
        command = last_msg.strip().split()[0]  # e.g., "/morning_digest"
        async with async_session() as session:
            result = await session.execute(
                select(SkillDefinition).where(
                    SkillDefinition.slash_command == command,
                    SkillDefinition.status == "active",
                )
            )
            skill = result.scalar_one_or_none()
            if skill:
                return "skill_executor"  # route to skill node

    # ... existing keyword routing logic
```

Add `skill_executor` node to the graph that invokes `SkillExecutor.run()`.

### Step 5: Run tests

```bash
PYTHONPATH=. .venv/bin/pytest tests/api/test_user_skills.py tests/test_slash_dispatch.py -v
```

### Step 6: Run full suite

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

### Step 7: Commit

```bash
git add backend/api/routes/user_skills.py backend/agents/master_agent.py \
  backend/main.py backend/tests/api/test_user_skills.py backend/tests/test_slash_dispatch.py
git commit -m "feat(06-09): user-facing skill APIs and slash command dispatch in chat"
```

---

## Task 10: MCP Server Evolution

**Files:**
- Modify: `backend/api/routes/mcp_servers.py` (add health-check + status patch)
- Modify: `backend/mcp/registry.py` (respect status, fix cache eviction)
- Create: `backend/tests/test_mcp_evolution.py`

### Step 1: Write tests for new MCP endpoints

Test:
- `GET /api/admin/mcp-servers/{id}/health` returns reachability status
- `PATCH /api/admin/mcp-servers/{id}/status` updates status field
- `MCPToolRegistry.refresh()` skips servers with `status != 'active'`
- Disabling a server evicts its client from `_clients` cache

### Step 2: Add health-check endpoint

```python
@router.get("/{server_id}/health")
async def check_health(
    server_id: UUID,
    user: UserContext = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Check if an MCP server is reachable."""
    # ... lookup server, try httpx.get(server.url + "/health"), return status
```

### Step 3: Add status patch endpoint

```python
@router.patch("/{server_id}/status")
async def update_status(
    server_id: UUID,
    body: StatusUpdate,
    user: UserContext = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Enable or disable an MCP server."""
    # ... update status column, invalidate tool cache, evict client if disabled
```

### Step 4: Update `MCPToolRegistry.refresh()` to use status field

Change filter from `is_active == True` to `status == 'active'`.

### Step 5: Run tests + commit

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_mcp_evolution.py tests/ -q
git add backend/api/routes/mcp_servers.py backend/mcp/registry.py \
  backend/tests/test_mcp_evolution.py
git commit -m "feat(06-10): evolve MCP server registry with health-check and status management"
```

---

## Task 11: Frontend Skill Menu

**Files:**
- Modify: `frontend/src/components/chat/chat-panel.tsx`
- Create: `frontend/src/hooks/use-skills.ts`
- Create: `frontend/src/app/api/skills/route.ts` (Next.js proxy)

### Step 1: Create skills API hook

`frontend/src/hooks/use-skills.ts`:

```typescript
"use client";

import { useState, useEffect } from "react";

interface SkillItem {
  name: string;
  displayName: string;
  description: string;
  slashCommand: string | null;
}

export function useSkills() {
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/skills")
      .then((res) => res.json())
      .then((data) => setSkills(data))
      .catch(() => setSkills([]))
      .finally(() => setLoading(false));
  }, []);

  return { skills, loading };
}
```

### Step 2: Create Next.js proxy route

`frontend/src/app/api/skills/route.ts` — proxy to backend `GET /api/skills` with JWT injection (same pattern as other proxy routes).

### Step 3: Add skill menu to chat sidebar

Modify `frontend/src/components/chat/chat-panel.tsx`:

Add a skill command dropdown/menu near the `SlashCommandInput` component. When user types `/`, show available skills as autocomplete suggestions. Clicking a skill fills the input with the slash command.

Update `handleSlashCommand()` to forward unknown `/commands` to the agent (instead of only handling `/new` and `/clear`):

```typescript
const handleSlashCommand = (value: string): boolean => {
    const trimmed = value.trim();
    if (trimmed === "/new") { onNewConversation(); return true; }
    if (trimmed === "/clear") { onClearMessages(); return true; }
    // Skill slash commands are sent to the agent as regular messages
    // The agent's _pre_route() detects and dispatches them
    return false;  // let it go through to the agent
};
```

### Step 4: Build and type-check

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build
```

### Step 5: Commit

```bash
git add frontend/src/hooks/use-skills.ts frontend/src/app/api/skills/route.ts \
  frontend/src/components/chat/chat-panel.tsx
git commit -m "feat(06-11): add skill /command menu to chat sidebar"
```

---

## Task 12: Integration Wiring + Final Verification

**Files:**
- Modify: `backend/main.py` (lifespan startup hooks)
- Modify: `docs/dev-context.md` (add new endpoints)
- Create: `backend/tests/test_phase6_integration.py`

### Step 1: Add registry refresh to lifespan

Add to `backend/main.py` lifespan function:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from mcp.registry import MCPToolRegistry
        await MCPToolRegistry.refresh()
    except Exception as exc:
        logger.warning("mcp_refresh_failed", error=str(exc))

    # Phase 6: refresh tool registry cache from DB
    try:
        from gateway.tool_registry import refresh_tool_cache
        async with async_session() as session:
            await refresh_tool_cache(session)
    except Exception as exc:
        logger.warning("tool_cache_refresh_failed", error=str(exc))

    yield
```

### Step 2: Write integration tests

`backend/tests/test_phase6_integration.py`:

Test the full flow:
1. Create a skill via admin API
2. Verify it appears in user skill listing
3. Execute the skill via `/api/skills/{name}/run`
4. Disable the skill via admin API
5. Verify it no longer appears in user listing
6. Verify execution returns 404

### Step 3: Update docs/dev-context.md

Add all new Phase 6 endpoints to the API reference section.

### Step 4: Run full test suite

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: all tests pass, no regressions

### Step 5: Frontend build check

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build
```

### Step 6: Commit

```bash
git add backend/main.py backend/tests/test_phase6_integration.py docs/dev-context.md
git commit -m "feat(06-12): Phase 6 integration wiring, startup hooks, and docs"
```

---

## Summary

| Task | Description | Key Deliverables |
|------|-------------|------------------|
| 1 | ORM Models + Migration | 5 model files, migration 014, seed data |
| 2 | RBAC Migration | DB-backed has_permission, check_artifact_permission |
| 3 | Pydantic Schemas | Request/response schemas for all CRUD APIs |
| 4 | Admin CRUD APIs | 4 route files, CRUD for agents/tools/skills/permissions |
| 5 | Tool Registry DB | Migrate from dict to DB-backed with cache |
| 6 | Agent Registry | Dynamic graph wiring from DB |
| 7 | Skill Runtime | SkillExecutor + validator |
| 8 | Skill Import Pipeline | Importer + security scanner |
| 9 | User Skill APIs | List/run endpoints + slash command dispatch |
| 10 | MCP Server Evolution | Health-check + status management |
| 11 | Frontend Skill Menu | Chat sidebar /command autocomplete |
| 12 | Integration Wiring | Lifespan hooks, integration tests, docs |
