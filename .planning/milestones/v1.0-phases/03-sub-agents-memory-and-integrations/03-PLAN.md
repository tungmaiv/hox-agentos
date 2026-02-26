# Phase 3 Implementation Plan: Sub-Agents, Memory, and Integrations

**Phase:** 03 — Sub-Agents, Memory, and Integrations
**Design doc:** `docs/plans/2026-02-26-phase3-design.md`
**Date:** 2026-02-26
**Status:** Ready to execute

---

## Overview

Phase 3 makes the agent genuinely useful for daily work. It delivers in three waves:

- **Pre-wave (03-00):** Settings infrastructure — shared scaffolding used by all waves
- **Wave 1 (03-01, 03-02):** Memory infrastructure — Celery + bge-m3 + pgvector + medium/long-term memory
- **Wave 2 (03-03):** MCP framework — HTTP+SSE client, CRM mock server, security gates
- **Wave 3 (03-04, 03-05):** Sub-agents + A2UI — email/calendar/project agents, rich UI output

**Dependency order (strict — each sub-phase must pass its exit criterion before the next starts):**

```
03-00  (no dependencies — start immediately)
03-01  (no dependencies — can start in parallel with 03-00)
03-02  → depends on 03-01
03-03  → depends on 03-00
03-04  → depends on 03-02 + 03-03
03-05  → depends on 03-04
```

---

## Sub-Phase 03-00: Settings Infrastructure

### Goal

Create the `system_config` and `mcp_servers` DB tables, the Settings page navigation shell with Agents and Integrations submenus (as stubs), so the admin can toggle agents on/off and the settings page renders without errors.

### Files to Create

| File | Description |
|------|-------------|
| `backend/core/models/system_config.py` | SQLAlchemy ORM model for `system_config` table (key/JSONB value store) |
| `backend/core/models/mcp_server.py` | SQLAlchemy ORM model for `mcp_servers` table (name, url, encrypted auth_token, is_active) |
| `backend/api/routes/system_config.py` | FastAPI router: `GET /api/admin/config`, `PUT /api/admin/config/{key}` — admin-only (RBAC gate: "admin") |
| `backend/alembic/versions/007_phase3_settings.py` | Alembic migration: create `system_config`, `mcp_servers` tables with HNSW indexes |
| `frontend/src/app/settings/agents/page.tsx` | Settings → Agents page: reads `GET /api/admin/config`, renders toggle per sub-agent (email, calendar, project). Client Component (`"use client"`). |
| `frontend/src/app/settings/integrations/page.tsx` | Settings → Integrations page: MCP server list stub (static placeholder for 03-03) |
| `frontend/src/app/api/admin/config/route.ts` | Next.js proxy: `GET /api/admin/config` → backend |
| `frontend/src/app/api/admin/config/[key]/route.ts` | Next.js proxy: `PUT /api/admin/config/{key}` → backend |

### Files to Modify

| File | Changes |
|------|---------|
| `backend/core/models/__init__.py` | Import `SystemConfig`, `McpServer` so Alembic autogenerate detects them |
| `backend/main.py` | `app.include_router(system_config.router)` |
| `frontend/src/app/settings/page.tsx` | Add nav links to "Agents" and "Integrations" sub-sections (keep existing Custom Instructions section) |

### DB Migration Needed

**File:** `backend/alembic/versions/007_phase3_settings.py`

```python
# Revision ID: 007
# Revises: 006
# Creates: system_config, mcp_servers

def upgrade() -> None:
    # system_config: admin key/value store
    op.create_table(
        "system_config",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    # mcp_servers: MCP server registry
    op.create_table(
        "mcp_servers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("auth_token", sa.LargeBinary(), nullable=True),  # AES-256 encrypted
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    # Seed default agent flags
    op.execute("""
        INSERT INTO system_config (key, value) VALUES
            ('agent.email.enabled',    'true'::jsonb),
            ('agent.calendar.enabled', 'true'::jsonb),
            ('agent.project.enabled',  'true'::jsonb),
            ('embedding_model',        '"bge-m3"'::jsonb)
    """)
```

### ORM Models

**`backend/core/models/system_config.py`:**

```python
class SystemConfig(Base):
    __tablename__ = "system_config"
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

**`backend/core/models/mcp_server.py`:**

```python
class McpServer(Base):
    __tablename__ = "mcp_servers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    auth_token: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)  # AES-256
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### API Route Pattern

**`backend/api/routes/system_config.py`:**

```python
# GET /api/admin/config → returns dict[str, Any]
# PUT /api/admin/config/{key} body: {"value": <any JSON>}
# Both gates: Gate 2 RBAC requires "admin" permission; Gate 3 ACL tool "admin.config"
```

### Frontend Agent Toggle

`frontend/src/app/settings/agents/page.tsx` fetches `GET /api/admin/config`, extracts keys matching `agent.*.enabled`, renders one `<Switch>` per agent. Toggle calls `PUT /api/admin/config/{key}` with `{"value": true|false}`. Use Zod to validate the API response shape.

Schema:
```typescript
const AgentConfigSchema = z.object({
    "agent.email.enabled": z.boolean().optional(),
    "agent.calendar.enabled": z.boolean().optional(),
    "agent.project.enabled": z.boolean().optional(),
})
```

### Tests to Write

**`backend/tests/test_system_config.py`:**
- `test_get_config_requires_admin_role` — 403 for non-admin user
- `test_get_config_returns_seeded_values` — after migration, seeded keys present
- `test_put_config_updates_value` — PUT updates the value; GET returns new value
- `test_put_config_returns_422_for_missing_value` — missing body field → 422

**`frontend/src/app/settings/agents/page.test.tsx`** (if Jest/Vitest is set up):
- Renders agent toggles from mocked API response
- Toggle fires PUT with correct key and value

### Exit Criterion

Admin (user with "admin" role) can navigate to `/settings/agents`, see three toggles (Email, Calendar, Project), toggle each on/off, and observe the setting persists across page reload. `/settings/integrations` renders without errors (stub content). Migration 007 applies cleanly via `just migrate`.

### Dependencies

None — start immediately in parallel with 03-01.

---

## Sub-Phase 03-01: Celery + Embedding Pipeline

### Goal

Stand up the Celery worker with Redis broker, implement the bge-m3 embedding provider, and create two Celery tasks (`embed_and_store`, `summarize_episode`) — the async infrastructure that all memory operations in 03-02 depend on.

### Files to Create

| File | Description |
|------|-------------|
| `backend/scheduler/__init__.py` | Empty init |
| `backend/scheduler/celery_app.py` | Celery app configured with Redis broker (`settings.redis_url`), `backend_db` as Redis result backend. Defines two queues: `embedding` (concurrency=2) and `default` (concurrency=4). |
| `backend/scheduler/tasks/__init__.py` | Empty init |
| `backend/scheduler/tasks/embedding.py` | `embed_and_store(text, user_id_str, entry_type)` Celery task and `summarize_episode(conversation_id_str, user_id_str)` Celery task |
| `backend/memory/embeddings.py` | `EmbeddingProvider` Protocol + `BGE_M3Provider` concrete class. Loads `BAAI/bge-m3` via `FlagEmbedding.FlagModel`. Exposes `async def embed(texts: list[str]) -> list[list[float]]` and `dimension: int = 1024`. |
| `backend/alembic/versions/008_phase3_memory_tables.py` | Alembic migration: create `memory_episodes` and `memory_facts` tables with `vector(1024)` columns and HNSW indexes |
| `backend/core/models/memory_long_term.py` | SQLAlchemy ORM models: `MemoryEpisode` and `MemoryFact` |
| `backend/tests/memory/test_embeddings.py` | TDD tests for BGE_M3Provider |
| `backend/tests/scheduler/test_embedding_task.py` | TDD tests for `embed_and_store` task |

### Files to Modify

| File | Changes |
|------|---------|
| `backend/pyproject.toml` | `uv add celery[redis] FlagEmbedding pgvector` |
| `backend/core/models/__init__.py` | Import `MemoryEpisode`, `MemoryFact` |
| `backend/core/config.py` | No URL changes needed — `redis_url` already exists. Add `embedding_model_path: str = "BAAI/bge-m3"` field to Settings. |
| `backend/docker-compose.yml` (infra) | Verify `celery-worker` service exists or add it; command: `celery -A scheduler.celery_app worker -Q embedding --concurrency=2` |

### DB Migration Needed

**File:** `backend/alembic/versions/008_phase3_memory_tables.py`

```python
# Revision ID: 008
# Revises: 007

def upgrade() -> None:
    # Ensure pgvector extension is active
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "memory_episodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),  # nullable until Celery runs
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_table(
        "memory_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),  # "conversation" | "user_stated" | "inferred"
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    # User isolation indexes
    op.create_index("ix_memory_episodes_user_id", "memory_episodes", ["user_id"])
    op.create_index("ix_memory_episodes_user_conversation", "memory_episodes", ["user_id", "conversation_id"])
    op.create_index("ix_memory_facts_user_id", "memory_facts", ["user_id"])
    # HNSW indexes for semantic search (only on non-null embeddings)
    op.execute("""
        CREATE INDEX ix_memory_facts_embedding_hnsw
        ON memory_facts USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX ix_memory_episodes_embedding_hnsw
        ON memory_episodes USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL
    """)
    # onupdate trigger for memory_facts.updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN NEW.updated_at = now(); RETURN NEW; END;
        $$ language 'plpgsql'
    """)
    op.execute("""
        CREATE TRIGGER memory_facts_updated_at
        BEFORE UPDATE ON memory_facts
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
    """)
```

### ORM Models

**`backend/core/models/memory_long_term.py`:**

```python
from pgvector.sqlalchemy import Vector

class MemoryEpisode(Base):
    __tablename__ = "memory_episodes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class MemoryFact(Base):
    __tablename__ = "memory_facts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### Embedding Provider

**`backend/memory/embeddings.py`:**

```python
from typing import Protocol, runtime_checkable
import structlog

logger = structlog.get_logger(__name__)

@runtime_checkable
class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimension(self) -> int: ...

class BGE_M3Provider:
    """
    bge-m3 embedding provider via FlagEmbedding.
    Dimension: 1024. Multilingual (Vietnamese + English).
    CPU-bound: always called from Celery workers, never from FastAPI request handlers.
    Model loaded lazily on first call and cached on the instance.
    """
    _model = None  # class-level cache (one per worker process)
    dimension: int = 1024

    def _get_model(self):
        if self._model is None:
            from FlagEmbedding import FlagModel
            self.__class__._model = FlagModel(
                "BAAI/bge-m3",
                use_fp16=True,      # halves memory; negligible accuracy loss
                query_instruction_for_retrieval="",
            )
            logger.info("bge_m3_model_loaded")
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import asyncio
        loop = asyncio.get_event_loop()
        # Run CPU-bound encoding in executor so event loop is not blocked
        model = self._get_model()
        result = await loop.run_in_executor(None, lambda: model.encode(texts).tolist())
        logger.debug("embeddings_generated", count=len(texts))
        return result
```

### Celery Tasks

**`backend/scheduler/tasks/embedding.py`:**

```python
# embed_and_store(text: str, user_id_str: str, entry_type: str) -> None
#   entry_type: "fact" → INSERT into memory_facts
#   entry_type: "episode" → INSERT into memory_episodes (requires conversation_id_str kwarg)
#
# summarize_episode(conversation_id_str: str, user_id_str: str) -> None
#   1. Load all turns from memory_conversations for this conversation
#   2. Call get_llm("blitz/summarizer") to produce a 2-3 sentence summary
#   3. dispatch embed_and_store(summary, user_id_str, entry_type="episode", conversation_id_str=...)

# Celery app wiring:
from scheduler.celery_app import celery_app

@celery_app.task(queue="embedding", bind=True, max_retries=3, default_retry_delay=30)
def embed_and_store(self, text: str, user_id_str: str, entry_type: str, conversation_id_str: str | None = None) -> None:
    ...

@celery_app.task(queue="default", bind=True, max_retries=2, default_retry_delay=60)
def summarize_episode(self, conversation_id_str: str, user_id_str: str) -> None:
    ...
```

**`backend/scheduler/celery_app.py`:**

```python
from celery import Celery
from core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "blitz",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["scheduler.tasks.embedding"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "scheduler.tasks.embedding.embed_and_store": {"queue": "embedding"},
        "scheduler.tasks.embedding.summarize_episode": {"queue": "default"},
    },
)
```

### Tests to Write

**`backend/tests/memory/test_embeddings.py`:**
```python
# test_bge_m3_provider_dimension — dimension property returns 1024
# test_bge_m3_provider_embed_returns_correct_shape — embed(["hello"]) returns list of len 1, inner list len 1024
# test_embedding_provider_protocol — BGE_M3Provider satisfies EmbeddingProvider protocol
# (Mock FlagEmbedding.FlagModel to avoid loading 570MB model in CI)
```

**`backend/tests/scheduler/test_embedding_task.py`:**
```python
# test_embed_and_store_fact_inserts_row — calls embed_and_store.delay(..., entry_type="fact"); row appears in memory_facts
# test_embed_and_store_episode_inserts_row — entry_type="episode" inserts into memory_episodes
# test_embed_and_store_sets_embedding_vector — row.embedding is not None after task runs
# test_summarize_episode_calls_summarizer_llm — verifies get_llm("blitz/summarizer") is called
# (Use Celery CELERY_ALWAYS_EAGER=True or task.apply() for synchronous test execution)
```

### Exit Criterion

`cd backend && .venv/bin/python -c "from memory.embeddings import BGE_M3Provider; import asyncio; p = BGE_M3Provider(); v = asyncio.run(p.embed(['test string'])); assert len(v[0]) == 1024; print('OK')"` passes. Celery task `embed_and_store.apply(args=["test string", str(any_uuid), "fact"])` inserts a row into `memory_facts` with a non-null 1024-dimensional embedding vector. `SELECT 1 FROM memory_facts ORDER BY embedding <=> '[0,0,...0]'::vector(1024) LIMIT 1` returns a row (pgvector cosine search functional).

### Dependencies

None — start immediately in parallel with 03-00.

---

## Sub-Phase 03-02: Medium + Long-term Memory

### Goal

Implement episode summarization (medium-term) and semantic fact search (long-term), then wire both into `master_agent.py` — so after 2+ sessions, the agent correctly recalls facts stated in previous conversations.

### Files to Create

| File | Description |
|------|-------------|
| `backend/memory/medium_term.py` | `save_episode(session, user_id, conversation_id, summary)` and `load_recent_episodes(session, user_id, n)` — manages `memory_episodes` table |
| `backend/memory/long_term.py` | `save_fact(session, user_id, content, source)` and `search_facts(session, user_id, query_embedding, k=5)` — manages `memory_facts` table with pgvector cosine search |
| `backend/tests/memory/test_medium_term.py` | TDD tests for medium-term memory CRUD |
| `backend/tests/memory/test_long_term.py` | TDD tests for long-term semantic search with user isolation |

### Files to Modify

| File | Changes |
|------|---------|
| `backend/agents/master_agent.py` | (1) `_load_memory_node`: after loading short-term turns, call `search_facts` with query embedding of the last user message; inject top-5 facts as a `SystemMessage` prefix. (2) `_save_memory_node`: after saving turns, dispatch `embed_and_store.delay(turn_content, user_id_str, "fact")` for assistant turns; check turn count — if multiple of `EPISODE_TURN_THRESHOLD` (default 10), dispatch `summarize_episode.delay(conversation_id_str, user_id_str)`. |
| `backend/agents/state/types.py` | Add `loaded_facts: list[str]` field (list of fact content strings injected by `_load_memory_node` for debugging/audit). |
| `backend/core/config.py` | Add `episode_turn_threshold: int = 10` to Settings (controls how often episodes are summarized). |

### Memory Load Pattern

Updated `_load_memory_node` in `backend/agents/master_agent.py`:

```python
async def _load_memory_node(state: BlitzState) -> dict:
    # ... existing short-term turn loading (unchanged) ...

    # NEW: semantic search for relevant long-term facts
    last_user_message = next(
        (m.content for m in reversed(state.get("messages", [])) if isinstance(m, HumanMessage)),
        None
    )
    loaded_facts: list[str] = []
    if last_user_message and user_id:
        provider = BGE_M3Provider()
        query_embedding = (await provider.embed([last_user_message]))[0]
        async with async_session() as session:
            facts = await search_facts(session, user_id=user_id, query_embedding=query_embedding, k=5)
        loaded_facts = [f.content for f in facts]
        if loaded_facts:
            facts_context = "\n".join(f"- {f}" for f in loaded_facts)
            history.insert(0, SystemMessage(content=f"[Long-term memory — relevant facts about this user:]\n{facts_context}"))
            logger.debug("long_term_memory_loaded", fact_count=len(loaded_facts))

    return {"messages": history, "loaded_facts": loaded_facts}
```

Memory save dispatches (appended to `_save_memory_node`):

```python
    # Dispatch async embedding for new assistant turns (fire-and-forget)
    for msg in new_messages:
        if isinstance(msg, AIMessage) and user_id:
            embed_and_store.delay(str(msg.content), str(user_id), "fact")

    # Trigger episode summarization every EPISODE_TURN_THRESHOLD turns
    total_after = existing_count + len(new_messages)
    threshold = settings.episode_turn_threshold
    if user_id and conversation_id and total_after > 0 and total_after % threshold == 0:
        summarize_episode.delay(str(conversation_id), str(user_id))
        logger.info("episode_summarization_triggered", turn_count=total_after)
```

### Long-term Search Function

**`backend/memory/long_term.py`:**

```python
from pgvector.sqlalchemy import Vector
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from core.models.memory_long_term import MemoryFact
import structlog

logger = structlog.get_logger(__name__)

async def save_fact(
    session: AsyncSession,
    *,
    user_id: UUID,
    content: str,
    source: str = "conversation",
) -> MemoryFact:
    """Insert one fact row. embedding is null — Celery will fill it."""
    fact = MemoryFact(user_id=user_id, content=content, source=source)
    session.add(fact)
    logger.debug("fact_saved", user_id=str(user_id), source=source)
    return fact

async def search_facts(
    session: AsyncSession,
    *,
    user_id: UUID,
    query_embedding: list[float],
    k: int = 5,
) -> list[MemoryFact]:
    """
    Semantic search over memory_facts for a user.
    SECURITY: WHERE user_id = $1 from JWT — never from request body.
    Uses pgvector cosine distance operator (<=>).
    Only searches rows where embedding IS NOT NULL (Celery has processed them).
    """
    result = await session.execute(
        select(MemoryFact)
        .where(
            MemoryFact.user_id == user_id,
            MemoryFact.embedding.is_not(None),
        )
        .order_by(MemoryFact.embedding.cosine_distance(query_embedding))
        .limit(k)
    )
    return list(result.scalars().all())
```

### Tests to Write

**`backend/tests/memory/test_long_term.py`:**
```python
# test_save_fact_inserts_row — row appears in memory_facts; embedding is None (not yet processed)
# test_search_facts_returns_closest_match — insert 3 facts with known embeddings; search returns nearest
# test_search_facts_isolation — user A's facts never returned when user_id = user B's UUID
# test_search_facts_skips_null_embeddings — facts with embedding=None not returned in search
```

**`backend/tests/memory/test_medium_term.py`:**
```python
# test_save_episode_inserts_row — episode row with summary text stored correctly
# test_load_recent_episodes_returns_user_episodes_only — user B's episodes never returned for user A
# test_load_recent_episodes_ordered_descending — most recent episode first
```

**`backend/tests/agents/test_master_agent_memory.py`:**
```python
# test_load_memory_node_injects_facts_as_system_message — mocked search_facts returns facts; SystemMessage appears in returned messages
# test_save_memory_node_dispatches_embed_task — after save, embed_and_store.delay was called for AI turns
# test_save_memory_node_triggers_summarization_at_threshold — mock turn count at threshold; summarize_episode.delay called
```

### Exit Criterion

Scenario test (can be automated or manual): Start session 1, tell the agent "My name is Tung and I work on backend infrastructure." End session. Wait for Celery worker to process the embed task. Start session 2 with a new `conversation_id`. Ask "What do you know about me?" The agent responds with something referencing "Tung" and "backend infrastructure" — retrieved from `memory_facts` via pgvector search. Automated: `test_load_memory_node_injects_facts_as_system_message` passes with mocked search.

### Dependencies

03-01 must be complete (needs `memory_facts`/`memory_episodes` tables, `BGE_M3Provider`, Celery tasks).

---

## Sub-Phase 03-03: MCP Framework + CRM Mock

### Goal

Implement the HTTP+SSE MCP client, wire MCP tools through all 3 security gates into `gateway/tool_registry.py`, build the CRM mock server, and make the Settings → Integrations CRUD live (backed by `mcp_servers` table).

### Files to Create

| File | Description |
|------|-------------|
| `backend/mcp/__init__.py` | Empty init |
| `backend/mcp/client.py` | `MCPClient` class: connects to a server's `/sse` endpoint, sends `tools/call` JSON-RPC, returns structured result. Uses `httpx.AsyncClient` with SSE streaming. |
| `backend/mcp/registry.py` | `MCPToolRegistry`: loads active `mcp_servers` rows from DB, calls `tools/list` on each server, registers discovered tools in `gateway/tool_registry.py`. Called at startup from `main.py`. Also provides `async def call_mcp_tool(tool_name, arguments, user: UserContext, session) -> dict` — the gated entry point for agent tool calls. |
| `backend/api/routes/mcp_servers.py` | CRUD router: `GET /api/admin/mcp-servers`, `POST /api/admin/mcp-servers`, `DELETE /api/admin/mcp-servers/{id}`. Admin-only (Gate 2: "admin" permission). Encrypts auth_token with same AES-256-GCM pattern as `UserCredential`. |
| `infra/mcp-crm/main.py` | Mock CRM MCP server (FastAPI). Exposes `/sse` SSE endpoint implementing MCP spec. Two tools: `crm.get_project_status(project_name: str)` and `crm.list_projects()`. Returns deterministic mock JSON. |
| `infra/mcp-crm/Dockerfile` | Dockerfile for mock CRM server — `FROM python:3.12-slim`, installs `fastapi uvicorn`. |
| `infra/mcp-crm/pyproject.toml` | Minimal dependencies: `fastapi`, `uvicorn`, `sse-starlette`. |
| `backend/tests/mcp/test_mcp_client.py` | TDD tests for MCPClient |
| `backend/tests/mcp/test_mcp_registry.py` | TDD tests for tool registration and gated tool call |
| `frontend/src/app/settings/integrations/page.tsx` | Replace 03-00 stub: live CRUD — list servers (name, URL, status), add form, delete button. Zod for API response validation. |
| `frontend/src/app/api/admin/mcp-servers/route.ts` | Next.js proxy: `GET /api/admin/mcp-servers` and `POST /api/admin/mcp-servers` |
| `frontend/src/app/api/admin/mcp-servers/[id]/route.ts` | Next.js proxy: `DELETE /api/admin/mcp-servers/{id}` |

### Files to Modify

| File | Changes |
|------|---------|
| `backend/main.py` | (1) `app.include_router(mcp_servers.router)`. (2) Add startup event: `await MCPToolRegistry.refresh()` — discovers tools from all active MCP servers on boot. |
| `backend/gateway/tool_registry.py` | Add `required_permissions: list[str]`, `mcp_server: str | None`, `mcp_tool: str | None` fields to the tool definition dict schema. Add `get_tool_definition(name) -> ToolDefinition` typed return. |
| `docker-compose.yml` | Add `mcp-crm` service: `build: ./infra/mcp-crm`, `ports: ["8001:8001"]`, depends on nothing. |

### MCP Client Design

**`backend/mcp/client.py`:**

```python
import httpx
import structlog
from typing import Any

logger = structlog.get_logger(__name__)

class MCPClient:
    """
    HTTP+SSE MCP client. One instance per server URL.
    Implements tools/list (discovery) and tools/call (invocation).
    """
    def __init__(self, server_url: str, auth_token: str | None = None) -> None:
        self._base_url = server_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}

    async def list_tools(self) -> list[dict[str, Any]]:
        """Call tools/list JSON-RPC. Returns list of tool definitions."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._base_url}/sse",
                json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json().get("result", {}).get("tools", [])

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call tools/call JSON-RPC. Returns structured result."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base_url}/sse",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                    "id": 2,
                },
                headers=self._headers,
            )
            response.raise_for_status()
            result = response.json()
            if "error" in result:
                logger.warning("mcp_tool_error", tool=tool_name, error=result["error"])
                return {"error": result["error"]["message"], "success": False}
            return {"result": result.get("result"), "success": True}
```

### Gated MCP Tool Call Pattern

**`backend/mcp/registry.py`** — `call_mcp_tool` enforces all 3 gates before calling the MCP server:

```python
async def call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
    user: UserContext,
    db_session: AsyncSession,
) -> dict[str, Any]:
    """
    Execute an MCP tool call through all 3 security gates.
    Gate 1 (JWT): user already validated by caller's Depends(get_current_user)
    Gate 2 (RBAC): check required_permissions from tool definition
    Gate 3 (ACL): check tool_acl table for (user_id, tool_name)
    """
    start_ms = int(time.monotonic() * 1000)
    tool_def = get_tool(tool_name)
    if tool_def is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not registered")

    # Gate 2: RBAC
    for permission in tool_def.get("required_permissions", []):
        if not has_permission(user, permission):
            elapsed = int(time.monotonic() * 1000) - start_ms
            await log_tool_call(user["user_id"], tool_name, False, elapsed)
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")

    # Gate 3: ACL
    allowed = await check_tool_acl(user["user_id"], tool_name, db_session)
    elapsed = int(time.monotonic() * 1000) - start_ms
    await log_tool_call(user["user_id"], tool_name, allowed, elapsed)
    if not allowed:
        raise HTTPException(status_code=403, detail="Tool call denied by ACL")

    # All gates passed — call the MCP server
    server_name = tool_def["mcp_server"]
    mcp_tool_name = tool_def["mcp_tool"]
    client = _get_client(server_name)  # returns cached MCPClient for this server
    return await client.call_tool(mcp_tool_name, arguments)
```

### CRM Mock Server Design

**`infra/mcp-crm/main.py`:**

The mock CRM implements the MCP JSON-RPC protocol over HTTP (not requiring SSE streaming for the mock — POST returns JSON immediately). Two tools:

```python
# Tool: crm.get_project_status
# Input: {"project_name": str}
# Output: {"project_name": str, "status": "active"|"on-hold"|"completed", "owner": str, "progress_pct": int, "last_update": str}

# Tool: crm.list_projects
# Input: {} (no args)
# Output: {"projects": [{"name": str, "status": str, "owner": str}]}

MOCK_PROJECTS = {
    "Project Alpha": {"status": "active", "owner": "tung@blitz.local", "progress_pct": 65, "last_update": "2026-02-25"},
    "Project Beta": {"status": "on-hold", "owner": "admin@blitz.local", "progress_pct": 30, "last_update": "2026-02-10"},
    "Project Gamma": {"status": "completed", "owner": "tung@blitz.local", "progress_pct": 100, "last_update": "2026-01-15"},
}
```

### Tests to Write

**`backend/tests/mcp/test_mcp_client.py`:**
```python
# test_list_tools_returns_tool_definitions — httpx mock returns valid tools/list response; client returns list
# test_call_tool_returns_success_result — mock tools/call response; client returns {"result": ..., "success": True}
# test_call_tool_returns_error_on_mcp_error — MCP error response; client returns {"error": ..., "success": False}
# test_call_tool_raises_on_http_error — server returns 500; HTTPStatusError propagates
```

**`backend/tests/mcp/test_mcp_registry.py`:**
```python
# test_call_mcp_tool_denied_without_permission — user lacks required permission → 403
# test_call_mcp_tool_denied_by_acl — ACL row denies user → 403; audit log entry created
# test_call_mcp_tool_succeeds_with_all_gates — user has permission + ACL allows → MCPClient.call_tool called
# test_call_mcp_tool_logs_every_attempt — even on success, audit log has entry with tool name + user_id
```

**Integration (optional, against running mcp-crm container):**
```python
# test_crm_get_project_status_returns_mock_data — end-to-end call to mcp-crm returns expected JSON
```

### Exit Criterion

`POST /api/admin/mcp-servers` with `{"name": "crm", "url": "http://localhost:8001", "auth_token": null}` registers the CRM server. `GET /api/admin/mcp-servers` returns it with `status: "connected"` (health check passes). Agent call to `crm.get_project_status` with `project_name="Project Alpha"` returns `{"status": "active", "progress_pct": 65}` (verified in test). The call passes all 3 security gates: a user without "crm:read" permission receives 403. Settings → Integrations page shows the registered server.

### Dependencies

03-00 must be complete (`mcp_servers` table and settings page navigation structure must exist).

---

## Sub-Phase 03-04: Sub-Agents

### Goal

Implement email, calendar, and project sub-agents as LangGraph nodes; extend `_route_after_master` in `master_agent.py` to delegate to sub-agents based on intent classification; have the project agent call CRM via MCP tools.

### Files to Create

| File | Description |
|------|-------------|
| `backend/agents/subagents/__init__.py` | Empty init |
| `backend/agents/subagents/email_agent.py` | Email sub-agent node: `async def email_agent_node(state: BlitzState) -> dict`. Classifies email query, generates a mock structured response (list of `EmailSummaryItem`). Phase 3 uses mock data — OAuth wiring is Phase 4. Returns AG-UI structured output. |
| `backend/agents/subagents/calendar_agent.py` | Calendar sub-agent node: `async def calendar_agent_node(state: BlitzState) -> dict`. Returns list of `CalendarEvent` for today (mock data). Includes conflict detection (overlapping time ranges in mock data). |
| `backend/agents/subagents/project_agent.py` | Project sub-agent node: `async def project_agent_node(state: BlitzState) -> dict`. Calls `call_mcp_tool("crm.get_project_status", ...)` via `mcp/registry.py`. Returns `ProjectStatusResult`. |
| `backend/agents/subagents/router.py` | `classify_intent(message: str) -> str` — calls `get_llm("blitz/fast")` with a classification prompt. Returns one of: `"email"`, `"calendar"`, `"project"`, `"general"`. |
| `backend/core/schemas/agent_outputs.py` | Pydantic v2 models for structured sub-agent outputs: `EmailSummaryItem`, `EmailSummaryOutput`, `CalendarEvent`, `CalendarOutput`, `ProjectStatusResult`. |
| `backend/tests/agents/test_email_agent.py` | TDD tests for email_agent_node |
| `backend/tests/agents/test_calendar_agent.py` | TDD tests for calendar_agent_node |
| `backend/tests/agents/test_project_agent.py` | TDD tests for project_agent_node |
| `backend/tests/agents/test_router.py` | TDD tests for intent classification |

### Files to Modify

| File | Changes |
|------|---------|
| `backend/agents/master_agent.py` | (1) Update `_route_after_master` to call `classify_intent` and return `"email_agent"`, `"calendar_agent"`, `"project_agent"`, or `"save_memory"`. (2) Register sub-agent nodes in `create_master_graph()`. (3) Check `system_config` feature flags before routing to a sub-agent (if flag is False, route to `"save_memory"` instead). (4) Update `_DEFAULT_SYSTEM_PROMPT` to advertise the new capabilities. |
| `backend/agents/state/types.py` | Add `route_to: str | None`, `sub_agent_output: dict | None` fields. |
| `backend/gateway/tool_registry.py` | Register `crm.get_project_status` and `crm.list_projects` with `required_permissions: ["crm:read"]`, `mcp_server: "crm"`, `mcp_tool: "crm.get_project_status"`. |

### Graph Topology After 03-04

```
START → load_memory → master_agent → [_route_after_master]
                                          ├── "email_agent"    → email_agent_node    → save_memory → END
                                          ├── "calendar_agent" → calendar_agent_node → save_memory → END
                                          ├── "project_agent"  → project_agent_node  → save_memory → END
                                          └── "save_memory"    → save_memory → END
```

### Intent Classification Prompt

**`backend/agents/subagents/router.py`:**

```python
_CLASSIFICATION_PROMPT = """You are an intent classifier. Given a user message, output EXACTLY one of these labels — nothing else:
- email     (user asks about emails, inbox, messages, read/send/reply)
- calendar  (user asks about schedule, meetings, appointments, events, today/tomorrow/week)
- project   (user asks about project status, CRM, tasks, Jira, sprint, milestones)
- general   (everything else)

User message: {message}
Label:"""

async def classify_intent(message: str) -> str:
    llm = get_llm("blitz/fast")
    response = await llm.ainvoke([HumanMessage(content=_CLASSIFICATION_PROMPT.format(message=message))])
    label = str(response.content).strip().lower()
    valid = {"email", "calendar", "project", "general"}
    if label not in valid:
        logger.warning("intent_classification_invalid_label", label=label, message=message[:50])
        return "general"
    return label
```

### Sub-Agent Output Schema

**`backend/core/schemas/agent_outputs.py`:**

```python
from pydantic import BaseModel
from datetime import datetime

class EmailSummaryItem(BaseModel):
    from_: str
    subject: str
    received_at: str
    snippet: str
    is_unread: bool

class EmailSummaryOutput(BaseModel):
    agent: str = "email"
    unread_count: int
    items: list[EmailSummaryItem]

class CalendarEvent(BaseModel):
    title: str
    start_time: str
    end_time: str
    location: str | None = None
    has_conflict: bool = False

class CalendarOutput(BaseModel):
    agent: str = "calendar"
    date: str
    events: list[CalendarEvent]

class ProjectStatusResult(BaseModel):
    agent: str = "project"
    project_name: str
    status: str
    owner: str
    progress_pct: int
    last_update: str
```

### Mock Data Pattern (Phase 3)

Each sub-agent returns deterministic mock data in Phase 3. The schema design (Pydantic models) is identical to what real data will use in Phase 4 (when OAuth flows are implemented). This ensures the A2UI components built in 03-05 require zero changes when real data arrives.

**`backend/agents/subagents/email_agent.py` mock:**

```python
_MOCK_EMAILS = [
    EmailSummaryItem(from_="ceo@blitz.local", subject="Q1 OKRs Review", received_at="2026-02-26T09:00:00Z", snippet="Please review the Q1 objectives attached...", is_unread=True),
    EmailSummaryItem(from_="devops@blitz.local", subject="Deployment successful", received_at="2026-02-26T08:30:00Z", snippet="The production deployment completed at 08:28 UTC...", is_unread=True),
    EmailSummaryItem(from_="hr@blitz.local", subject="Team lunch tomorrow", received_at="2026-02-25T16:00:00Z", snippet="We're doing team lunch at noon tomorrow...", is_unread=False),
]
```

### Feature Flag Check in Router

```python
async def _get_agent_enabled(key: str) -> bool:
    """Check system_config for agent feature flag. Default True if not set."""
    async with async_session() as session:
        result = await session.execute(select(SystemConfig).where(SystemConfig.key == key))
        row = result.scalar_one_or_none()
        if row is None:
            return True  # default enabled
        return bool(row.value)
```

Updated `_route_after_master`:

```python
async def _route_after_master(state: BlitzState) -> str:
    last_user_msg = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), ""
    )
    intent = await classify_intent(str(last_user_msg))
    if intent == "email" and await _get_agent_enabled("agent.email.enabled"):
        return "email_agent"
    if intent == "calendar" and await _get_agent_enabled("agent.calendar.enabled"):
        return "calendar_agent"
    if intent == "project" and await _get_agent_enabled("agent.project.enabled"):
        return "project_agent"
    return "save_memory"
```

### Tests to Write

**`backend/tests/agents/test_router.py`:**
```python
# test_classify_intent_email — "check my unread emails" → "email"
# test_classify_intent_calendar — "what meetings do I have today?" → "calendar"
# test_classify_intent_project — "what's the status of Project Alpha?" → "project"
# test_classify_intent_general — "write me a haiku" → "general"
# test_classify_intent_invalid_label_returns_general — LLM returns garbage → "general" (no exception)
# (Mock get_llm("blitz/fast") in all tests)
```

**`backend/tests/agents/test_email_agent.py`:**
```python
# test_email_agent_node_returns_email_output — node returns dict with EmailSummaryOutput-compatible data
# test_email_agent_output_has_unread_count — unread_count >= 0
```

**`backend/tests/agents/test_project_agent.py`:**
```python
# test_project_agent_calls_mcp_tool — verifies call_mcp_tool is called with "crm.get_project_status"
# test_project_agent_returns_structured_output — result is ProjectStatusResult-compatible dict
# test_project_agent_403_without_crm_permission — user lacks "crm:read" → 403 propagated
```

**`backend/tests/agents/test_master_agent_routing.py`:**
```python
# test_route_to_email_agent_on_email_intent — classify_intent returns "email"; route = "email_agent"
# test_route_to_general_on_disabled_agent — email agent disabled in system_config; route = "save_memory"
# test_graph_topology_has_sub_agent_nodes — compiled graph has nodes: email_agent, calendar_agent, project_agent
```

### Exit Criterion

Two functional verifications:
1. `POST /api/copilotkit` with message "what's on my calendar today?" triggers `calendar_agent_node`, which returns an `AIMessage` whose content includes structured event data (verifiable in test by mocking `classify_intent` to return "calendar").
2. `POST /api/copilotkit` with message "what's the status of Project Alpha?" triggers `project_agent_node`, which calls `call_mcp_tool("crm.get_project_status", {"project_name": "Project Alpha"})` and returns `{"status": "active", "progress_pct": 65}` (with mcp-crm running, end-to-end verified).

### Dependencies

03-02 must be complete (memory nodes updated, graph structure extended). 03-03 must be complete (`call_mcp_tool` function and CRM mock server available).

---

## Sub-Phase 03-05: A2UI Components

### Goal

Build `CalendarCard`, `EmailSummaryCard`, and `ProjectStatusWidget` frontend components; wire them into `A2UIMessageRenderer` so rich cards render automatically in the chat panel when the corresponding sub-agent responds.

### Files to Create

| File | Description |
|------|-------------|
| `frontend/src/components/a2ui/CalendarCard.tsx` | Server Component (no interactivity needed). Props: `CalendarOutput`. Renders a date header, list of events with time/title/location, conflict warning badge. Tailwind only — no external UI library. |
| `frontend/src/components/a2ui/EmailSummaryCard.tsx` | Server Component. Props: `EmailSummaryOutput`. Renders unread count badge, list of email summaries with sender/subject/snippet. Truncates snippet at 120 chars. |
| `frontend/src/components/a2ui/ProjectStatusWidget.tsx` | Server Component. Props: `ProjectStatusResult`. Renders project name, status badge (color-coded: active=green, on-hold=yellow, completed=gray), progress bar, owner, last update date. |
| `frontend/src/components/a2ui/A2UIMessageRenderer.tsx` | Client Component (`"use client"`). Receives `content: string` prop. Attempts `JSON.parse(content)`; if it has `agent: "calendar"` → renders `<CalendarCard>`, `agent: "email"` → `<EmailSummaryCard>`, `agent: "project"` → `<ProjectStatusWidget>`. Falls back to `<ReactMarkdown>` for plain text. |
| `frontend/src/lib/a2ui-types.ts` | TypeScript interfaces mirroring Pydantic schemas: `CalendarOutput`, `EmailSummaryOutput`, `ProjectStatusResult`, `CalendarEvent`, `EmailSummaryItem`. Zod schemas for runtime validation. |
| `frontend/src/components/a2ui/index.ts` | Re-export all A2UI components |

### Files to Modify

| File | Changes |
|------|---------|
| `frontend/src/components/chat/chat-panel.tsx` | Replace plain `<div>{message.content}</div>` rendering with `<A2UIMessageRenderer content={message.content} />` for assistant messages. |
| `backend/agents/subagents/email_agent.py` | Ensure the AIMessage content returned is valid JSON string of `EmailSummaryOutput.model_dump_json()`. |
| `backend/agents/subagents/calendar_agent.py` | Return AIMessage with `CalendarOutput.model_dump_json()`. |
| `backend/agents/subagents/project_agent.py` | Return AIMessage with `ProjectStatusResult.model_dump_json()`. |

### Zod Validation Schemas

**`frontend/src/lib/a2ui-types.ts`:**

```typescript
import { z } from "zod"

export const CalendarEventSchema = z.object({
    title: z.string(),
    start_time: z.string(),
    end_time: z.string(),
    location: z.string().nullable().optional(),
    has_conflict: z.boolean().default(false),
})

export const CalendarOutputSchema = z.object({
    agent: z.literal("calendar"),
    date: z.string(),
    events: z.array(CalendarEventSchema),
})

export const EmailSummaryItemSchema = z.object({
    from_: z.string(),
    subject: z.string(),
    received_at: z.string(),
    snippet: z.string(),
    is_unread: z.boolean(),
})

export const EmailSummaryOutputSchema = z.object({
    agent: z.literal("email"),
    unread_count: z.number(),
    items: z.array(EmailSummaryItemSchema),
})

export const ProjectStatusResultSchema = z.object({
    agent: z.literal("project"),
    project_name: z.string(),
    status: z.enum(["active", "on-hold", "completed"]),
    owner: z.string(),
    progress_pct: z.number().min(0).max(100),
    last_update: z.string(),
})

export type CalendarOutput = z.infer<typeof CalendarOutputSchema>
export type EmailSummaryOutput = z.infer<typeof EmailSummaryOutputSchema>
export type ProjectStatusResult = z.infer<typeof ProjectStatusResultSchema>
```

### A2UI Renderer Pattern

**`frontend/src/components/a2ui/A2UIMessageRenderer.tsx`:**

```typescript
"use client"

import { CalendarOutputSchema, EmailSummaryOutputSchema, ProjectStatusResultSchema } from "@/lib/a2ui-types"
import { CalendarCard } from "./CalendarCard"
import { EmailSummaryCard } from "./EmailSummaryCard"
import { ProjectStatusWidget } from "./ProjectStatusWidget"
import ReactMarkdown from "react-markdown"

interface Props {
    content: string
    role: "user" | "assistant"
}

export function A2UIMessageRenderer({ content, role }: Props) {
    if (role !== "assistant") {
        return <div className="whitespace-pre-wrap">{content}</div>
    }

    // Attempt to parse as A2UI structured output
    try {
        const parsed = JSON.parse(content)
        const agentType = parsed?.agent

        if (agentType === "calendar") {
            const result = CalendarOutputSchema.safeParse(parsed)
            if (result.success) return <CalendarCard data={result.data} />
        }
        if (agentType === "email") {
            const result = EmailSummaryOutputSchema.safeParse(parsed)
            if (result.success) return <EmailSummaryCard data={result.data} />
        }
        if (agentType === "project") {
            const result = ProjectStatusResultSchema.safeParse(parsed)
            if (result.success) return <ProjectStatusWidget data={result.data} />
        }
    } catch {
        // Not JSON — fall through to markdown rendering
    }

    return <ReactMarkdown className="prose prose-sm max-w-none">{content}</ReactMarkdown>
}
```

### Component Design

**`CalendarCard.tsx`:**

```typescript
// Props: { data: CalendarOutput }
// Renders:
//   - Date header (e.g., "Today — February 26, 2026")
//   - For each event:
//       - Time range (start_time → end_time, formatted)
//       - Event title (bold)
//       - Location (if set, muted text)
//       - Conflict badge (red "Conflict" badge if has_conflict=true)
//   - "No events today" if events array is empty
// Tailwind classes only — no Radix/shadcn
// Example conflict detection display:
//   <span className="ml-2 px-1.5 py-0.5 bg-red-100 text-red-700 text-xs rounded">
//     Conflict
//   </span>
```

**`EmailSummaryCard.tsx`:**

```typescript
// Props: { data: EmailSummaryOutput }
// Renders:
//   - Header: "Inbox — {unread_count} unread" (bold count, blue)
//   - List of email rows:
//       - Sender (from_) — truncated at 30 chars
//       - Subject (bold if is_unread)
//       - Snippet — truncated at 120 chars, muted
//       - Time (relative: "2h ago", "Yesterday")
//   - Unread rows: slightly highlighted bg-blue-50
```

**`ProjectStatusWidget.tsx`:**

```typescript
// Props: { data: ProjectStatusResult }
// Renders:
//   - Project name (h3)
//   - Status badge: active=green/100, on-hold=yellow/100, completed=gray/100
//   - Progress bar: w-full bg-gray-200 rounded; inner div width={progress_pct%} bg-blue-500
//   - "Progress: {progress_pct}%" text
//   - Owner: "Owner: {owner}"
//   - Last update: "Updated: {last_update}"
```

### Frontend Dependencies

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm add react-markdown zod
# zod already installed from Phase 2; verify; react-markdown may already be present
```

### Tests to Write

**Frontend (if Vitest/Jest configured — check `frontend/package.json`):**

```typescript
// frontend/src/components/a2ui/A2UIMessageRenderer.test.tsx
// test_renders_calendar_card_for_calendar_agent_json — parses CalendarOutput JSON, renders CalendarCard
// test_renders_email_card_for_email_agent_json — parses EmailSummaryOutput JSON, renders EmailSummaryCard
// test_renders_project_widget_for_project_agent_json — parses ProjectStatusResult JSON, renders widget
// test_falls_back_to_markdown_for_plain_text — plain string renders <ReactMarkdown>
// test_falls_back_to_markdown_for_invalid_json — malformed JSON renders as text (no throw)
// test_conflict_badge_shown_when_has_conflict_true — CalendarCard shows conflict badge
// test_unread_count_shown_in_email_card — "3 unread" appears in rendered output
```

**Backend (smoke tests for structured output format):**

```python
# backend/tests/agents/test_agent_outputs.py
# test_email_agent_output_is_valid_json — email_agent_node returns AIMessage; JSON.parse succeeds; validates against EmailSummaryOutput schema
# test_calendar_agent_output_has_correct_agent_field — CalendarOutput.agent == "calendar"
# test_project_agent_output_validates_against_schema — ProjectStatusResult.model_validate(json.loads(content)) succeeds
```

### Exit Criterion

Manual end-to-end: With the backend, frontend, and mcp-crm container all running:
1. Send "summarize my unread emails" → chat panel renders `EmailSummaryCard` with unread count badge and email rows (not raw JSON text).
2. Send "what's on my calendar today?" → chat panel renders `CalendarCard` with date header and event list.
3. Send "what's the status of Project Alpha?" → chat panel renders `ProjectStatusWidget` with green "active" badge and 65% progress bar.
4. Send "write me a haiku about databases" → general intent, chat panel renders standard markdown (no card).
5. A2UI components pass Zod validation on every render (no `safeParse` failures in browser console).

### Dependencies

03-04 must be complete (sub-agents producing structured JSON output). Frontend `react-markdown` and `zod` must be installed.

---

## Phase-Level Exit Criterion (All 5 Phase 3 Success Criteria)

All the following must be simultaneously true before Phase 3 is marked complete in `ROADMAP.md`:

1. **Email agent:** User sends "summarize my unread emails" → `EmailSummaryCard` renders in chat with correct unread count and at least 3 email rows.
2. **Calendar agent:** User sends "what's on my calendar today?" → `CalendarCard` renders with date header, events list, conflict badge on any event with `has_conflict=true`.
3. **Project agent via MCP:** User sends "what's the status of Project Alpha?" → `ProjectStatusWidget` renders with "active" status badge, 65% progress bar — data sourced from live mcp-crm container via MCP HTTP+SSE protocol through all 3 security gates.
4. **Long-term memory:** Start session 1, state a fact ("My name is Tung"). End session. Wait for Celery embedding task. Start session 2. Ask "What do you know about me?" → agent recalls "Tung" (retrieved via pgvector semantic search on `memory_facts`). An episode summary exists in `memory_episodes` after 10 turns.
5. **A2UI rich responses:** All 3 card types render without raw JSON leaking to UI. Plain text queries render markdown. All Zod `safeParse` calls succeed (no silent parse failures in browser console).

---

## Cross-Cutting Constraints (Apply to All Sub-Phases)

These invariants from `CLAUDE.md` must be enforced in every file created or modified in Phase 3:

| Invariant | Enforcement |
|-----------|-------------|
| All memory queries: `WHERE user_id = $1` from JWT | `search_facts`, `save_fact`, `save_episode`, `load_recent_episodes` all take `user_id: UUID` from JWT — never from request body |
| All LLM calls via `get_llm()` | `email_agent_node`, `calendar_agent_node`, `project_agent_node`, `classify_intent`, `summarize_episode` — all call `get_llm("blitz/...")` only |
| All MCP tool calls through 3 gates | `call_mcp_tool` in `mcp/registry.py` enforces Gate 2 + Gate 3; Gate 1 (JWT) enforced by endpoint's `Depends(get_current_user)` |
| Credentials never logged | `auth_token` in `mcp_servers` is AES-256 encrypted; never logged; `log_tool_call` logs only `user_id`, `tool_name`, `allowed`, `duration_ms` |
| Celery tasks run as job owner | `embed_and_store` and `summarize_episode` receive `user_id_str` from the request context and use it for all DB writes — no service account shortcuts |
| No direct SDK imports | No `import anthropic`, `import openai` in any backend file |
| Full type annotations | Every function in every new backend file has full type annotations; no bare `dict`, `list`, `Any` |
| `structlog` exclusively | No `print()`, no `logging.info()` |
| Pydantic v2 `BaseModel` | All tool I/O in `core/schemas/agent_outputs.py` uses `BaseModel` |
| TypeScript `strict: true` | All frontend files — no `any`, no `// @ts-ignore` |
| Zod for API validation | `a2ui-types.ts` Zod schemas used in `A2UIMessageRenderer` before rendering |

---

## Docker Compose Services Added in Phase 3

| Service | Image / Build | Port | Notes |
|---------|--------------|------|-------|
| `celery-worker` | Same image as backend | — | Command: `celery -A scheduler.celery_app worker -Q embedding --concurrency=2 -l info` |
| `celery-worker-default` | Same image as backend | — | Command: `celery -A scheduler.celery_app worker -Q default --concurrency=4 -l info` |
| `mcp-crm` | `./infra/mcp-crm` | 8001 | Mock CRM MCP server |

The `celery-worker` service uses `extra_hosts: ["host.docker.internal:host-gateway"]` if Ollama access is needed for the `blitz/summarizer` model (summarize_episode task calls LiteLLM which routes to Ollama on host).

---

## Alembic Migration Run Order

```
007_phase3_settings      (03-00) → system_config, mcp_servers
008_phase3_memory_tables (03-01) → memory_episodes, memory_facts
```

Both must be applied before any Phase 3 code runs:

```bash
just migrate
# or:
cd backend && .venv/bin/alembic upgrade head
```

---

## Key File Paths Quick Reference

```
backend/
├── scheduler/
│   ├── celery_app.py                          (03-01)
│   └── tasks/embedding.py                     (03-01)
├── memory/
│   ├── short_term.py                          (existing — modified in 03-02)
│   ├── embeddings.py                          (03-01)
│   ├── medium_term.py                         (03-02)
│   └── long_term.py                           (03-02)
├── mcp/
│   ├── client.py                              (03-03)
│   └── registry.py                            (03-03)
├── agents/
│   ├── master_agent.py                        (modified in 03-02, 03-04)
│   ├── state/types.py                         (modified in 03-02, 03-04)
│   └── subagents/
│       ├── router.py                          (03-04)
│       ├── email_agent.py                     (03-04)
│       ├── calendar_agent.py                  (03-04)
│       └── project_agent.py                   (03-04)
├── api/routes/
│   ├── system_config.py                       (03-00)
│   └── mcp_servers.py                         (03-03)
├── core/
│   ├── models/
│   │   ├── system_config.py                   (03-00)
│   │   ├── mcp_server.py                      (03-00)
│   │   └── memory_long_term.py                (03-01)
│   └── schemas/
│       └── agent_outputs.py                   (03-04)
└── alembic/versions/
    ├── 007_phase3_settings.py                 (03-00)
    └── 008_phase3_memory_tables.py            (03-01)

infra/
└── mcp-crm/
    ├── main.py                                (03-03)
    ├── Dockerfile                             (03-03)
    └── pyproject.toml                         (03-03)

frontend/src/
├── app/settings/
│   ├── agents/page.tsx                        (03-00)
│   └── integrations/page.tsx                 (03-00 stub → 03-03 live)
├── app/api/admin/
│   ├── config/route.ts                        (03-00)
│   ├── config/[key]/route.ts                  (03-00)
│   ├── mcp-servers/route.ts                   (03-03)
│   └── mcp-servers/[id]/route.ts             (03-03)
├── components/a2ui/
│   ├── A2UIMessageRenderer.tsx               (03-05)
│   ├── CalendarCard.tsx                       (03-05)
│   ├── EmailSummaryCard.tsx                   (03-05)
│   ├── ProjectStatusWidget.tsx                (03-05)
│   └── index.ts                               (03-05)
└── lib/
    └── a2ui-types.ts                          (03-05)
```
