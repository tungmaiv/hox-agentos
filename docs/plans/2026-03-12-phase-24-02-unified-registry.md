# Phase 24-02: Unified Registry Foundation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace fragmented agents/skills/tools/mcp_servers tables with a single `registry_entries` table; merge instructional/procedural skill types; expose unified `/api/registry/*` CRUD routes; keep old domain routes as thin shims.

**Architecture:** New `registry_entries` table with a JSONB `config` blob per entity type. Strategy handlers (`AgentHandler`, `SkillHandler`, `ToolHandler`, `McpHandler`) implement type-specific logic. Data migrated from existing tables in migration 029. Old domain routes (`/api/skills/*`, `/api/agents/*`, `/api/tools/*`) become one-line proxy shims.

**Tech Stack:** SQLAlchemy 2.0 async, Alembic, FastAPI, pydantic v2. Migration next number: **028**.

---

## Task 1: Create `RegistryEntry` ORM Model

**Files:**
- Create: `backend/core/models/registry_entry.py`
- Modify: `backend/core/models/__init__.py`

**Step 1: Write the model**

```python
# backend/core/models/registry_entry.py
"""
RegistryEntry ORM model — unified registry for all entity types.

Replaces separate agents, skill_definitions, tool_definitions, and mcp_servers
tables. Each row stores a type discriminator and a type-specific config JSONB blob.

Types:
- agent: config = {system_prompt, model_alias, tools[]}
- skill: config = {instruction_markdown, procedure (optional), allowed_tools[], ...}
- tool: config = {handler_type, handler_code (optional), mcp_server, mcp_tool, ...}
- mcp_server: config = {url, server_type, transport, pool_size, ...}
- policy: config = {rules[], applies_to[]}

status values: "active" | "inactive" | "pending_review"
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON

from core.db import Base

_JSONB = JSON().with_variant(JSONB(), "postgresql")


class RegistryEntry(Base):
    """Unified registry entry for all manageable entity types."""

    __tablename__ = "registry_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    type: Mapped[str] = mapped_column(
        String(20), nullable=False  # agent | skill | tool | mcp_server | policy
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="'active'"
    )
    config: Mapped[dict[str, Any]] = mapped_column(
        _JSONB, nullable=False, server_default="'{}'"
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", _JSONB, nullable=False, server_default="'{}'"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

**Step 2: Register in `__init__.py`**

Open `backend/core/models/__init__.py`. Add the import:

```python
from core.models.registry_entry import RegistryEntry  # noqa: F401
```

**Step 3: Write a test to verify model imports cleanly**

```python
# backend/tests/test_registry_entry_model.py
def test_registry_entry_model_importable():
    from core.models.registry_entry import RegistryEntry
    assert RegistryEntry.__tablename__ == "registry_entries"

def test_registry_entry_has_required_columns():
    from core.models.registry_entry import RegistryEntry
    cols = {c.name for c in RegistryEntry.__table__.columns}
    assert {"id", "type", "name", "status", "config", "metadata"}.issubset(cols)
```

**Step 4: Run test**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_registry_entry_model.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/core/models/registry_entry.py backend/core/models/__init__.py \
        backend/tests/test_registry_entry_model.py
git commit -m "feat(24-02): add RegistryEntry ORM model"
```

---

## Task 2: Alembic Migration 028 — Create `registry_entries` Table

**Files:**
- Create: `backend/alembic/versions/028_registry_entries.py`

**Step 1: Generate the migration**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
.venv/bin/alembic revision --autogenerate -m "028_registry_entries"
```

This creates a file in `backend/alembic/versions/`. Rename it to `028_registry_entries.py` if needed.

**Step 2: Review the generated migration**

Open the generated file. Ensure `upgrade()` creates the `registry_entries` table. It should contain:

```python
def upgrade() -> None:
    op.create_table(
        "registry_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False,
                  server_default="'active'"),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default="'{}'"),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default="'{}'"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_registry_entries_type", "registry_entries", ["type"])
    op.create_index("ix_registry_entries_status", "registry_entries", ["status"])


def downgrade() -> None:
    op.drop_index("ix_registry_entries_status")
    op.drop_index("ix_registry_entries_type")
    op.drop_table("registry_entries")
```

Edit the generated file to match if autogenerate added extras you don't want.

**Step 3: Apply the migration**

```bash
# Cannot run alembic from host — must run via docker exec
docker compose exec backend sh -c "cd /app && alembic upgrade head"
```

If docker isn't running, apply manually:
```bash
docker compose up -d postgres
docker compose exec backend sh -c "cd /app && alembic upgrade head"
```

**Step 4: Verify table exists**

```bash
docker compose exec postgres psql -U blitz blitz -c "\d registry_entries"
```

Expected: table columns displayed.

**Step 5: Commit**

```bash
git add backend/alembic/versions/028_registry_entries.py
git commit -m "feat(24-02): migration 028 — create registry_entries table"
```

---

## Task 3: Strategy Handlers

**Files:**
- Create: `backend/registry/__init__.py`
- Create: `backend/registry/base.py`
- Create: `backend/registry/handlers.py`

**Step 1: Write the base handler interface**

```python
# backend/registry/base.py
"""Base interface for registry entry strategy handlers."""
from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class RegistryHandler(ABC):
    """Strategy interface for type-specific registry operations."""

    @abstractmethod
    async def validate(self, config: dict[str, Any]) -> None:
        """Validate config for this entry type. Raises ValueError on invalid."""
        ...

    @abstractmethod
    async def activate(self, entry_id: UUID, session: AsyncSession) -> None:
        """Perform activation side-effects (e.g., register tool in cache)."""
        ...

    @abstractmethod
    async def deactivate(self, entry_id: UUID, session: AsyncSession) -> None:
        """Perform deactivation side-effects."""
        ...

    async def test(self, config: dict[str, Any]) -> dict[str, Any]:
        """Run a connectivity/validation test. Returns {ok: bool, message: str}."""
        return {"ok": True, "message": "No test defined for this type"}
```

**Step 2: Write the four concrete handlers**

```python
# backend/registry/handlers.py
"""Strategy handlers for each registry entry type."""
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from registry.base import RegistryHandler

logger = structlog.get_logger(__name__)


class AgentHandler(RegistryHandler):
    async def validate(self, config: dict[str, Any]) -> None:
        if not config.get("system_prompt"):
            raise ValueError("agent config requires system_prompt")

    async def activate(self, entry_id: UUID, session: AsyncSession) -> None:
        logger.info("agent_activated", entry_id=str(entry_id))

    async def deactivate(self, entry_id: UUID, session: AsyncSession) -> None:
        logger.info("agent_deactivated", entry_id=str(entry_id))


class SkillHandler(RegistryHandler):
    async def validate(self, config: dict[str, Any]) -> None:
        if not config.get("instruction_markdown") and not config.get("procedure"):
            raise ValueError(
                "skill config requires either instruction_markdown or procedure"
            )

    async def activate(self, entry_id: UUID, session: AsyncSession) -> None:
        logger.info("skill_activated", entry_id=str(entry_id))

    async def deactivate(self, entry_id: UUID, session: AsyncSession) -> None:
        logger.info("skill_deactivated", entry_id=str(entry_id))


class ToolHandler(RegistryHandler):
    async def validate(self, config: dict[str, Any]) -> None:
        if not config.get("handler_type"):
            raise ValueError("tool config requires handler_type")

    async def activate(self, entry_id: UUID, session: AsyncSession) -> None:
        # Refresh the tool cache so this tool becomes available immediately
        from gateway.tool_registry import _refresh_tool_cache
        await _refresh_tool_cache(session)
        logger.info("tool_activated", entry_id=str(entry_id))

    async def deactivate(self, entry_id: UUID, session: AsyncSession) -> None:
        from gateway.tool_registry import _refresh_tool_cache
        await _refresh_tool_cache(session)
        logger.info("tool_deactivated", entry_id=str(entry_id))


class McpServerHandler(RegistryHandler):
    async def validate(self, config: dict[str, Any]) -> None:
        if not config.get("url") and config.get("server_type") != "stdio":
            raise ValueError("mcp_server config requires url for non-stdio servers")

    async def activate(self, entry_id: UUID, session: AsyncSession) -> None:
        logger.info("mcp_server_activated", entry_id=str(entry_id))

    async def deactivate(self, entry_id: UUID, session: AsyncSession) -> None:
        logger.info("mcp_server_deactivated", entry_id=str(entry_id))


class PolicyHandler(RegistryHandler):
    async def validate(self, config: dict[str, Any]) -> None:
        if not config.get("rules"):
            raise ValueError("policy config requires non-empty rules list")

    async def activate(self, entry_id: UUID, session: AsyncSession) -> None:
        logger.info("policy_activated", entry_id=str(entry_id))

    async def deactivate(self, entry_id: UUID, session: AsyncSession) -> None:
        logger.info("policy_deactivated", entry_id=str(entry_id))


_HANDLERS: dict[str, RegistryHandler] = {
    "agent": AgentHandler(),
    "skill": SkillHandler(),
    "tool": ToolHandler(),
    "mcp_server": McpServerHandler(),
    "policy": PolicyHandler(),
}


def get_handler(entry_type: str) -> RegistryHandler:
    """Return the strategy handler for the given entry type."""
    handler = _HANDLERS.get(entry_type)
    if handler is None:
        raise ValueError(f"Unknown registry entry type: {entry_type!r}")
    return handler
```

**Step 3: Write tests**

```python
# backend/tests/test_registry_handlers.py
import pytest


def test_get_handler_returns_correct_type():
    from registry.handlers import get_handler, SkillHandler
    assert isinstance(get_handler("skill"), SkillHandler)


def test_get_handler_unknown_raises():
    from registry.handlers import get_handler
    with pytest.raises(ValueError, match="Unknown registry entry type"):
        get_handler("unknown_type")


@pytest.mark.asyncio
async def test_skill_handler_validates_empty_config():
    from registry.handlers import SkillHandler
    handler = SkillHandler()
    with pytest.raises(ValueError, match="instruction_markdown or procedure"):
        await handler.validate({})


@pytest.mark.asyncio
async def test_skill_handler_validates_instruction_only():
    from registry.handlers import SkillHandler
    handler = SkillHandler()
    # Should not raise
    await handler.validate({"instruction_markdown": "Do the thing"})
```

**Step 4: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_registry_handlers.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/registry/
git commit -m "feat(24-02): add registry strategy handlers"
```

---

## Task 4: `/api/registry/*` Routes

**Files:**
- Create: `backend/api/routes/registry.py`
- Modify: `backend/main.py`
- Create: `backend/tests/api/test_registry_routes.py`

**Step 1: Write failing tests first**

```python
# backend/tests/api/test_registry_routes.py
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_registry_entries_requires_auth(async_client: AsyncClient):
    resp = await async_client.get("/api/registry")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_registry_entries_returns_list(
    async_client: AsyncClient, admin_token: str
):
    resp = await async_client.get(
        "/api/registry", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_create_registry_entry(
    async_client: AsyncClient, admin_token: str
):
    payload = {
        "type": "skill",
        "name": "test-registry-skill",
        "description": "Test skill",
        "config": {"instruction_markdown": "Do the thing"},
    }
    resp = await async_client.post(
        "/api/registry",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-registry-skill"
    assert data["type"] == "skill"


@pytest.mark.asyncio
async def test_get_registry_entry_by_id(
    async_client: AsyncClient, admin_token: str
):
    # Create first
    payload = {
        "type": "skill",
        "name": "test-get-skill",
        "config": {"instruction_markdown": "Get me"},
    }
    create_resp = await async_client.post(
        "/api/registry",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    entry_id = create_resp.json()["id"]

    # Then get
    resp = await async_client.get(
        f"/api/registry/{entry_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == entry_id


@pytest.mark.asyncio
async def test_delete_registry_entry(
    async_client: AsyncClient, admin_token: str
):
    payload = {
        "type": "skill",
        "name": "test-delete-skill",
        "config": {"instruction_markdown": "Delete me"},
    }
    create_resp = await async_client.post(
        "/api/registry",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    entry_id = create_resp.json()["id"]

    del_resp = await async_client.delete(
        f"/api/registry/{entry_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert del_resp.status_code == 204
```

**Step 2: Run tests to confirm they fail**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/api/test_registry_routes.py -v 2>&1 | tail -20
```

Expected: FAIL (route not found).

**Step 3: Implement the routes**

```python
# backend/api/routes/registry.py
"""
Unified Registry CRUD routes.

All entity types (agent, skill, tool, mcp_server, policy) are managed here.
Old domain routes (/api/skills/*, /api/agents/*) are thin shims that proxy here.

Required permission: registry:read (list/get), registry:manage (create/update/delete)
"""
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_session
from core.models.registry_entry import RegistryEntry
from registry.handlers import get_handler
from security.deps import get_current_user, require_permission

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/registry", tags=["registry"])


class RegistryEntryCreate(BaseModel):
    type: str
    name: str
    display_name: str | None = None
    description: str | None = None
    config: dict[str, Any] = {}
    metadata: dict[str, Any] = {}


class RegistryEntryUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    status: str | None = None
    config: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class RegistryEntryOut(BaseModel):
    id: uuid.UUID
    type: str
    name: str
    display_name: str | None
    description: str | None
    status: str
    config: dict[str, Any]
    metadata: dict[str, Any]

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj: RegistryEntry) -> "RegistryEntryOut":
        return cls(
            id=obj.id,
            type=obj.type,
            name=obj.name,
            display_name=obj.display_name,
            description=obj.description,
            status=obj.status,
            config=obj.config,
            metadata=obj.metadata_,
        )


@router.get("")
async def list_entries(
    type: str | None = Query(None),
    status: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_permission("registry:read")),
) -> dict:
    stmt = select(RegistryEntry)
    if type:
        stmt = stmt.where(RegistryEntry.type == type)
    if status:
        stmt = stmt.where(RegistryEntry.status == status)
    stmt = stmt.order_by(RegistryEntry.created_at.desc())
    result = await session.execute(stmt)
    entries = result.scalars().all()
    return {"items": [RegistryEntryOut.from_orm(e) for e in entries]}


@router.post("", status_code=201)
async def create_entry(
    body: RegistryEntryCreate,
    session: AsyncSession = Depends(get_session),
    user=Depends(require_permission("registry:manage")),
) -> RegistryEntryOut:
    handler = get_handler(body.type)
    await handler.validate(body.config)

    entry = RegistryEntry(
        type=body.type,
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        config=body.config,
        metadata_=body.metadata,
        created_by=user.id if hasattr(user, "id") else None,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    logger.info("registry_entry_created", id=str(entry.id), type=entry.type, name=entry.name)
    return RegistryEntryOut.from_orm(entry)


@router.get("/{entry_id}")
async def get_entry(
    entry_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_permission("registry:read")),
) -> RegistryEntryOut:
    entry = await session.get(RegistryEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Registry entry not found")
    return RegistryEntryOut.from_orm(entry)


@router.put("/{entry_id}")
async def update_entry(
    entry_id: uuid.UUID,
    body: RegistryEntryUpdate,
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_permission("registry:manage")),
) -> RegistryEntryOut:
    entry = await session.get(RegistryEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Registry entry not found")
    if body.display_name is not None:
        entry.display_name = body.display_name
    if body.description is not None:
        entry.description = body.description
    if body.status is not None:
        entry.status = body.status
    if body.config is not None:
        handler = get_handler(entry.type)
        await handler.validate(body.config)
        entry.config = body.config
    if body.metadata is not None:
        entry.metadata_ = body.metadata
    await session.commit()
    await session.refresh(entry)
    return RegistryEntryOut.from_orm(entry)


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_permission("registry:manage")),
) -> None:
    entry = await session.get(RegistryEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Registry entry not found")
    await session.delete(entry)
    await session.commit()
    logger.info("registry_entry_deleted", id=str(entry_id))


@router.post("/{entry_id}/clone", status_code=201)
async def clone_entry(
    entry_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user=Depends(require_permission("registry:manage")),
) -> RegistryEntryOut:
    original = await session.get(RegistryEntry, entry_id)
    if not original:
        raise HTTPException(status_code=404, detail="Registry entry not found")
    clone = RegistryEntry(
        type=original.type,
        name=f"{original.name}-copy",
        display_name=f"{original.display_name or original.name} (copy)",
        description=original.description,
        status="inactive",  # clones start inactive
        config=dict(original.config),
        metadata_=dict(original.metadata_),
        created_by=user.id if hasattr(user, "id") else None,
    )
    session.add(clone)
    await session.commit()
    await session.refresh(clone)
    return RegistryEntryOut.from_orm(clone)
```

**Step 4: Register router in `main.py`**

Open `backend/main.py`. Add import and `app.include_router()` call:

```python
# Add to imports section:
from api.routes.registry import router as registry_router

# Add to router registration section (after existing routers):
app.include_router(registry_router)
```

Also add `registry:read` and `registry:manage` permissions to `backend/security/rbac.py`:
```python
# In DEFAULT_ROLE_PERMISSIONS, add to admin/developer roles:
"registry:read",
"registry:manage",
```

**Step 5: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/api/test_registry_routes.py -v
```

Expected: all PASS.

**Step 6: Commit**

```bash
git add backend/api/routes/registry.py backend/main.py backend/security/rbac.py \
        backend/tests/api/test_registry_routes.py
git commit -m "feat(24-02): add unified registry CRUD routes"
```

---

## Task 5: Data Migration 029 — Migrate Existing Entities

**Files:**
- Create: `backend/alembic/versions/029_migrate_to_registry.py`

**Step 1: Create migration manually** (autogenerate won't capture data migrations)

```bash
cd /home/tungmv/Projects/hox-agentos/backend
.venv/bin/alembic revision -m "029_migrate_existing_entities_to_registry"
```

**Step 2: Write the data migration**

Open the generated file. Replace `upgrade()` with:

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


def upgrade() -> None:
    conn = op.get_bind()

    # --- Migrate skill_definitions → registry_entries (type=skill) ---
    skills = conn.execute(sa.text("""
        SELECT id, name, display_name, description,
               status, instruction_markdown, procedure_json,
               allowed_tools, tags, category, source_url,
               created_by, created_at, updated_at
        FROM skill_definitions
    """)).fetchall()

    for s in skills:
        config = {
            "instruction_markdown": s.instruction_markdown,
            "allowed_tools": s.allowed_tools or [],
        }
        if s.procedure_json:
            config["procedure"] = s.procedure_json

        metadata = {
            "tags": s.tags or [],
            "category": s.category,
            "source_url": s.source_url,
        }
        conn.execute(sa.text("""
            INSERT INTO registry_entries
                (id, type, name, display_name, description, status, config, metadata,
                 created_by, created_at, updated_at)
            VALUES
                (:id, 'skill', :name, :display_name, :description, :status,
                 :config::jsonb, :metadata::jsonb, :created_by, :created_at, :updated_at)
            ON CONFLICT (name) DO NOTHING
        """), {
            "id": str(s.id),
            "name": s.name,
            "display_name": s.display_name,
            "description": s.description,
            "status": s.status or "active",
            "config": __import__("json").dumps(config),
            "metadata": __import__("json").dumps(metadata),
            "created_by": str(s.created_by) if s.created_by else None,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
        })

    # --- Migrate mcp_servers → registry_entries (type=mcp_server) ---
    mcp_servers = conn.execute(sa.text("""
        SELECT id, name, display_name, url, status, created_at
        FROM mcp_servers
        WHERE is_active = true
    """)).fetchall()

    for m in mcp_servers:
        config = {"url": m.url, "server_type": "builtin", "transport": "http"}
        conn.execute(sa.text("""
            INSERT INTO registry_entries
                (id, type, name, display_name, status, config, metadata, created_at, updated_at)
            VALUES
                (:id, 'mcp_server', :name, :display_name, :status,
                 :config::jsonb, '{}'::jsonb, :created_at, now())
            ON CONFLICT (name) DO NOTHING
        """), {
            "id": str(m.id),
            "name": m.name,
            "display_name": m.display_name or m.name,
            "status": m.status or "active",
            "config": __import__("json").dumps(config),
            "created_at": m.created_at,
        })

    # --- Migrate tool_definitions → registry_entries (type=tool) ---
    tools = conn.execute(sa.text("""
        SELECT id, name, display_name, description,
               handler_type, handler_code, mcp_server, mcp_tool,
               required_permissions, created_at
        FROM tool_definitions
        WHERE is_active = true
    """)).fetchall()

    for t in tools:
        config = {
            "handler_type": t.handler_type,
            "required_permissions": t.required_permissions or [],
        }
        if t.handler_code:
            config["handler_code"] = t.handler_code
        if t.mcp_server:
            config["mcp_server"] = t.mcp_server
            config["mcp_tool"] = t.mcp_tool

        conn.execute(sa.text("""
            INSERT INTO registry_entries
                (id, type, name, display_name, description, status, config, metadata,
                 created_at, updated_at)
            VALUES
                (:id, 'tool', :name, :display_name, :description, 'active',
                 :config::jsonb, '{}'::jsonb, :created_at, now())
            ON CONFLICT (name) DO NOTHING
        """), {
            "id": str(t.id),
            "name": t.name,
            "display_name": t.display_name or t.name,
            "description": t.description,
            "config": __import__("json").dumps(config),
            "created_at": t.created_at,
        })

    # --- Migrate agent_definitions → registry_entries (type=agent) ---
    agents = conn.execute(sa.text("""
        SELECT id, name, display_name, description,
               system_prompt, model_alias, tools,
               created_by, created_at
        FROM agent_definitions
        WHERE is_active = true
    """)).fetchall()

    for a in agents:
        config = {
            "system_prompt": a.system_prompt or "",
            "model_alias": a.model_alias or "blitz/master",
            "tools": a.tools or [],
        }
        conn.execute(sa.text("""
            INSERT INTO registry_entries
                (id, type, name, display_name, description, status, config, metadata,
                 created_by, created_at, updated_at)
            VALUES
                (:id, 'agent', :name, :display_name, :description, 'active',
                 :config::jsonb, '{}'::jsonb, :created_by, :created_at, now())
            ON CONFLICT (name) DO NOTHING
        """), {
            "id": str(a.id),
            "name": a.name,
            "display_name": a.display_name or a.name,
            "description": a.description,
            "config": __import__("json").dumps(config),
            "created_by": str(a.created_by) if a.created_by else None,
            "created_at": a.created_at,
        })


def downgrade() -> None:
    op.execute("DELETE FROM registry_entries")
```

**Step 3: Apply migration**

```bash
docker compose exec backend sh -c "cd /app && alembic upgrade head"
```

**Step 4: Verify data migrated**

```bash
docker compose exec postgres psql -U blitz blitz \
  -c "SELECT type, count(*) FROM registry_entries GROUP BY type;"
```

Expected: rows for skill, tool, mcp_server, agent with counts > 0.

**Step 5: Commit**

```bash
git add backend/alembic/versions/029_migrate_existing_entities_to_registry.py
git commit -m "feat(24-02): migration 029 — migrate existing entities to registry_entries"
```

---

## Task 6: Old Domain Routes Become Shims

**Files:**
- Modify: `backend/api/routes/admin_skills.py`
- Modify: `backend/api/routes/admin_agents.py`
- Modify: `backend/api/routes/admin_tools.py`
- Modify: `backend/api/routes/mcp_servers.py`

For each route file, the list/get/create/delete handlers should be replaced with calls to the registry service layer. Since this is a big refactor, do it incrementally per route file.

**Step 1: Add a `RegistryService` helper**

```python
# backend/registry/service.py
"""Thin service layer wrapping common registry queries."""
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.registry_entry import RegistryEntry


async def get_entries_by_type(
    session: AsyncSession, entry_type: str, status: str | None = None
) -> list[RegistryEntry]:
    stmt = select(RegistryEntry).where(RegistryEntry.type == entry_type)
    if status:
        stmt = stmt.where(RegistryEntry.status == status)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_entry(session: AsyncSession, entry_id: UUID) -> RegistryEntry | None:
    return await session.get(RegistryEntry, entry_id)
```

**Step 2: Update `admin_skills.py` list endpoint to read from registry**

Find the handler that does `SELECT * FROM skill_definitions`. Replace the DB query with:

```python
from registry.service import get_entries_by_type

entries = await get_entries_by_type(session, "skill", status="active")
# Map RegistryEntry → existing SkillDefinitionOut schema
```

Repeat for admin_agents.py, admin_tools.py, mcp_servers.py.

**Step 3: Run full test suite to confirm no regressions**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: same pass count as before (currently 719+).

**Step 4: Commit**

```bash
git commit -m "feat(24-02): domain routes now read from registry_entries (shim layer)"
```

---

## Completion Check

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q

cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
```

Both exit 0.
