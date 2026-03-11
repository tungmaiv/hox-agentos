# Memory Management — Implementation Reference

> **Audience:** Backend engineers implementing, debugging, or extending the memory subsystem.
> **Covers:** ORM models, query patterns, agent graph integration, Celery tasks, embedding providers, and security invariants.
> **Design context:** `docs/design/memory-sub-system.md`

---

## 1. Overview

The memory subsystem is a three-tier architecture that gives agents persistent, user-scoped context across conversations and sessions.

| Tier | Storage | Purpose | Latency |
|------|---------|---------|---------|
| Short-term | `memory_conversations` | Verbatim turn history for the current conversation | Synchronous — loaded before LLM call |
| Medium-term | `memory_episodes` | LLM-generated summaries of past conversations | Synchronous — loaded before LLM call |
| Long-term | `memory_facts` | Durable semantic facts with pgvector retrieval | Synchronous load; async write via Celery |

### Data Flow

```
Agent request (AG-UI)
    │
    ▼
_load_memory_node
    ├─ load_recent_turns()         → last 20 turns from memory_conversations
    ├─ SidecarEmbeddingProvider    → embed last user message (HTTP, non-blocking)
    ├─ search_facts()              → top-5 semantic matches from memory_facts
    └─ load_recent_episodes()      → last 3 summaries from memory_episodes
    │   (all injected as SystemMessage prefixes before messages list)
    ▼
LLM call (blitz/master)
    │
    ▼
_save_memory_node
    ├─ COUNT existing turns in DB  → deduplication guard
    ├─ save_turn() for each new message (synchronous)
    ├─ embed_and_store.delay()     → fire-and-forget per AIMessage
    └─ summarize_episode.delay()   → triggered when total_turns % threshold == 0
    │
    ▼
Celery worker (embedding queue)
    └─ BGE_M3Provider.embed()     → bge-m3 in-process (CPU-bound, FP16)
       └─ UPDATE memory_facts.embedding / INSERT memory_episodes
```

### Technology Decisions

| Decision | Technology | Rationale |
|----------|-----------|----------|
| Vector search | pgvector (HNSW) in PostgreSQL | No separate vector DB; 100-user scale fits PostgreSQL |
| Embedding model | `BAAI/bge-m3` (1024-dim, FP16) | Multilingual (Vietnamese + English), self-hosted |
| Embedding path (requests) | `SidecarEmbeddingProvider` → infinity-emb HTTP | Non-blocking; CPU-bound embedding stays out of FastAPI event loop |
| Embedding path (Celery) | `BGE_M3Provider` (in-process) | Workers are long-running processes; model cached at class level |
| Async writes | Celery (`embedding` queue) | Avoids blocking agent response on CPU-bound bge-m3 inference |

---

## 2. Database Schema

### 2.1 `memory_conversations` (short-term)

**ORM:** `core/models/memory.py` → `ConversationTurn`

```sql
CREATE TABLE memory_conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL,
    user_id         UUID NOT NULL,
    role            TEXT NOT NULL,        -- 'user' | 'assistant' | 'tool'
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Isolation indexes
CREATE INDEX ON memory_conversations (user_id);
CREATE INDEX ON memory_conversations (conversation_id);
```

No FK to a `users` table — user identity is managed by Keycloak and validated via JWT (Gate 1). The composite `(user_id, conversation_id)` query pattern is the primary access path.

### 2.2 `memory_episodes` (medium-term)

**ORM:** `core/models/memory_long_term.py` → `MemoryEpisode`

```sql
CREATE TABLE memory_episodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    conversation_id UUID NOT NULL,
    summary         TEXT NOT NULL,
    embedding       vector(1024),         -- null until Celery fills it
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Isolation indexes
CREATE INDEX ix_memory_episodes_user_id ON memory_episodes (user_id);
CREATE INDEX ix_memory_episodes_user_conversation ON memory_episodes (user_id, conversation_id);

-- HNSW partial index — only on rows with embeddings (avoids indexing nulls)
CREATE INDEX ix_memory_episodes_embedding_hnsw
    ON memory_episodes USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;
```

### 2.3 `memory_facts` (long-term)

**ORM:** `core/models/memory_long_term.py` → `MemoryFact`

```sql
CREATE TABLE memory_facts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL,
    content       TEXT NOT NULL,
    source        TEXT,                  -- e.g. 'conversation'
    embedding     vector(1024),          -- null until Celery fills it
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    superseded_at TIMESTAMPTZ           -- null = active; set = soft-deleted
);

-- Isolation index
CREATE INDEX ix_memory_facts_user_id ON memory_facts (user_id);

-- HNSW partial index — only on active, embedded rows
CREATE INDEX ix_memory_facts_embedding_hnsw
    ON memory_facts USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;

-- Auto-update trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ language 'plpgsql';

CREATE TRIGGER memory_facts_updated_at
    BEFORE UPDATE ON memory_facts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

**Migration:** `alembic/versions/008_phase3_memory_tables.py`

---

## 3. Memory Tier Details

### 3.1 Short-Term: Conversation Turns

**File:** `backend/memory/short_term.py`

**Purpose:** Verbatim turn-by-turn history for the current conversation window. Gives the LLM exact phrasing of what was said.

#### `load_recent_turns()`

```python
async def load_recent_turns(
    session: AsyncSession,
    *,
    user_id: UUID,
    conversation_id: UUID,
    n: int = 20,
) -> list[ConversationTurn]:
```

Query pattern:
```sql
SELECT * FROM memory_conversations
WHERE user_id = $1 AND conversation_id = $2
ORDER BY created_at DESC
LIMIT 20;
```

Results are reversed before return — DESC retrieves newest-first, but LangGraph expects oldest-first for correct message ordering.

#### `save_turn()`

```python
async def save_turn(
    session: AsyncSession,
    *,
    user_id: UUID,
    conversation_id: UUID,
    role: str,       -- 'user' | 'assistant' | 'tool'
    content: str,
) -> ConversationTurn:
```

**No `session.commit()` inside `save_turn`.** The caller owns the transaction. `_save_memory_node` calls `save_turn` in a loop and the transaction is committed by `get_session()` context manager on exit.

### 3.2 Medium-Term: Episode Summaries

**File:** `backend/memory/medium_term.py`

**Purpose:** Cross-session context. When a conversation ends (at threshold), it's summarized into a 2–3 sentence episode. Episodes provide historical context that outlasts the short-term window.

#### `save_episode()`

Inserts a row with `embedding=NULL`. Celery fills the embedding asynchronously via `embed_and_store.delay()`.

#### `load_recent_episodes()`

```sql
SELECT * FROM memory_episodes
WHERE user_id = $1
ORDER BY created_at DESC
LIMIT 5;
```

Default `n=5`; `_load_memory_node` calls with `n=3`.

#### `get_episode_threshold_cached()`

Episode summarization is triggered when `total_turns % threshold == 0`. The threshold is configurable per user via the `system_config` table (key: `memory.episode_turn_threshold`). If not set, falls back to `settings.episode_turn_threshold` (default: 10).

The value is cached for 60 seconds (TTL cache, max 200 entries) to avoid a DB query on every `save_memory` call:

```python
_threshold_cache: TTLCache = TTLCache(maxsize=200, ttl=60)
```

Call chain: `_save_memory_node` → `get_episode_threshold_cached()` → (cache miss) → `get_episode_threshold_db()` → `system_config` table or `settings` fallback.

### 3.3 Long-Term: Semantic Facts

**File:** `backend/memory/long_term.py`

**Purpose:** Durable facts about the user extracted from conversation context (preferences, stated facts, decisions). Retrieved semantically — the most contextually relevant facts for the current message are injected into the LLM context.

#### `save_fact()`

Inserts with `embedding=NULL`. Celery fills it. The `source` field defaults to `"conversation"`.

#### `search_facts()`

```sql
SELECT * FROM memory_facts
WHERE user_id = $1
  AND embedding IS NOT NULL
  AND superseded_at IS NULL
ORDER BY embedding <=> $2   -- cosine distance (pgvector)
LIMIT 5;
```

Only queries active rows (`superseded_at IS NULL`) with populated embeddings. The HNSW partial index (`WHERE embedding IS NOT NULL`) accelerates this query.

#### `mark_fact_superseded()`

Sets `superseded_at = now()`. Facts are **never hard-deleted** — the old row is preserved for audit and rollback. This is a soft-delete pattern: conflicting facts (e.g., user changes their preference) mark the old fact superseded rather than overwriting it.

---

## 4. Agent Graph Integration

**File:** `backend/agents/master_agent.py`

### Graph Topology

```
START → load_memory → [_pre_route]
                          ├── master_agent    ─┐
                          ├── skill_executor  ─┤
                          ├── capabilities_node─┤→ delivery_router → save_memory → END
                          ├── email_agent     ─┤
                          ├── calendar_agent  ─┤
                          └── project_agent   ─┘
```

Memory nodes are the outermost wrapper — every request path starts at `load_memory` and ends at `save_memory`.

### `_load_memory_node` (lines ~57–192)

1. **Resolve identity:** Read `user_id` and `conversation_id` from `BlitzState`. If absent (normal when invoked via `LangGraphAGUIAgent`), fall back to `current_user_ctx` and `current_conversation_id_ctx` contextvars set by `gateway/runtime.py`.

2. **Short-term check:** If `state["messages"]` is already populated (CopilotKit provides full history on every call), skip DB load but continue to long-term injection. If empty, load last 20 turns from DB and convert to LangChain messages.

3. **Long-term — semantic search:**
   - Extract last `HumanMessage` from state
   - `SidecarEmbeddingProvider.embed([last_user_message])` → 1024-dim vector (HTTP, non-blocking)
   - `search_facts(session, user_id=user_id, query_embedding=..., k=5)` → top-5 cosine matches
   - Prepend as `SystemMessage("[Long-term memory — relevant facts about this user:]\n...")`

4. **Medium-term — episode summaries:**
   - `load_recent_episodes(session, user_id=user_id, n=3)` → last 3 summaries
   - Prepend as `SystemMessage("[Medium-term memory — summaries of past conversations:]\n...")`

5. Both long-term and medium-term loading are wrapped in `try/except` — failures log a warning but do not block the agent response (graceful degradation).

### `_save_memory_node` (lines ~304–410)

1. **Resolve identity:** Same contextvar fallback as `_load_memory_node`.

2. **Deduplication guard (critical):** CopilotKit sends the full message history on every `agent/run` request. Without a guard, every call would re-save all historical turns.

   Solution: count existing turns for this `(user_id, conversation_id)` in the DB, then slice:
   ```python
   existing_count = <COUNT from DB>
   new_messages = messages[existing_count:]
   ```

3. **Save new turns:** `save_turn()` for each `HumanMessage` and `AIMessage` in `new_messages`. Transaction committed by `get_session()` on context exit.

4. **Fire-and-forget embedding:** For each `AIMessage` in `new_messages`:
   ```python
   embed_and_store.delay(str(msg.content), str(user_id), "fact")
   ```
   Only AI turns are embedded as facts — user messages are ephemeral context.

5. **Episode threshold check:**
   ```python
   total_after = existing_count + len(new_messages)
   threshold = await get_episode_threshold_cached(user_id, session)
   if total_after > 0 and total_after % threshold == 0:
       summarize_episode.delay(str(conversation_id), str(user_id))
   ```

---

## 5. Embedding Infrastructure

**File:** `backend/memory/embeddings.py`

### `EmbeddingProvider` Protocol

All providers satisfy:
```python
@runtime_checkable
class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimension(self) -> int: ...
```

### `SidecarEmbeddingProvider` (primary path — FastAPI requests)

Used in `_load_memory_node` and `reindex_memory_task`. Calls an infinity-emb HTTP sidecar:

```
POST {embedding_sidecar_url}/embeddings
Body: {"input": ["text..."], "model": "BAAI/bge-m3"}
Response: {"data": [{"embedding": [...1024 floats...], "index": 0}]}
```

- Non-blocking HTTP call — safe for FastAPI event loop
- `timeout=30.0` seconds
- Falls back to `BGE_M3Provider` on `httpx.ConnectError` (sidecar down)
- Validates dimension via `GET {sidecar_url}/health` at backend startup
- Config: `settings.embedding_sidecar_url` (default: `"http://embedding-sidecar:7997"`)

### `BGE_M3Provider` (Celery workers + fallback)

Used directly in `embed_and_store` Celery task, and as fallback when sidecar unreachable.

```python
class BGE_M3Provider:
    _model = None           # class-level cache — one instance per worker process
    _lock = threading.Lock()  # guards lazy initialization
    dimension: int = 1024

    def _get_model(self):
        # Double-checked locking: avoids lock on every post-init call
        if self.__class__._model is None:
            with self.__class__._lock:
                if self.__class__._model is None:
                    from FlagEmbedding import FlagModel
                    self.__class__._model = FlagModel(
                        "BAAI/bge-m3",
                        use_fp16=True,   # halves memory; negligible accuracy loss
                        query_instruction_for_retrieval="",
                    )
        return self.__class__._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        loop = asyncio.get_running_loop()
        model = self._get_model()
        result = await loop.run_in_executor(
            None, lambda: model.encode(texts).tolist()
        )
        return result
```

Key properties:
- Model loaded lazily on first call — ~2–5s startup penalty per worker, then instant
- `use_fp16=True` — halves GPU/CPU memory with negligible accuracy loss on bge-m3
- `run_in_executor()` — runs CPU-bound `model.encode()` in thread pool, non-blocking async
- Dimension: **1024 — LOCKED**. Changing requires full DB reindex (see §9 Runbook)

---

## 6. Celery Task System

**File:** `backend/scheduler/tasks/embedding.py`

All tasks use the `asyncio.run(_async_body())` pattern — Celery task functions are synchronous; async logic is wrapped in an inner `async def _run()` function.

### `embed_and_store`

```python
@celery_app.task(
    queue="embedding",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="scheduler.tasks.embedding.embed_and_store",
)
def embed_and_store(self, text: str, user_id_str: str, entry_type: str,
                    conversation_id_str: str | None = None) -> None:
```

| Attribute | Value |
|-----------|-------|
| Queue | `embedding` |
| Retries | 3 with 30s delay |
| `entry_type="fact"` | INSERT into `memory_facts` with embedding |
| `entry_type="episode"` | INSERT into `memory_episodes` with embedding (requires `conversation_id_str`) |

Uses `BGE_M3Provider` (in-process bge-m3). On retry, re-embeds and re-inserts.

### `summarize_episode`

```python
@celery_app.task(
    queue="default",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name="scheduler.tasks.embedding.summarize_episode",
)
def summarize_episode(self, conversation_id_str: str, user_id_str: str) -> None:
```

| Attribute | Value |
|-----------|-------|
| Queue | `default` (LLM-backed, I/O-bound) |
| Retries | 2 with 60s delay |

Steps:
1. `load_recent_turns(session, user_id=..., conversation_id=..., n=50)` — reads last 50 turns
2. Format as `User: ..\nAssistant: ..` transcript
3. `get_llm("blitz/summarizer").ainvoke([HumanMessage(content=prompt)])` → 2–3 sentence summary
4. `embed_and_store.delay(summary, user_id_str, "episode", conversation_id_str=...)` — dispatches embedding on the `embedding` queue

### `reindex_memory_task`

```python
@celery_app.task(name="blitz.reindex_memory")
def reindex_memory_task() -> None:
```

| Attribute | Value |
|-----------|-------|
| Queue | `default` |
| Trigger | `POST /api/admin/memory/reindex` with `confirm=true` |
| Batch size | 32 rows per embedding call |

Re-embeds all `memory_facts` rows, then all `memory_episodes` rows using `SidecarEmbeddingProvider`. Overwrites existing vectors. This is a destructive operation — run only during maintenance windows.

---

## 7. Security Isolation

**Invariant:** `user_id` flows from JWT → contextvar → all memory functions. It is never accepted from request body, agent state input, or Celery task arguments supplied by external callers.

### How it works

```
HTTP request (CopilotKit AG-UI)
    │
    ▼
gateway/runtime.py
    ├── JWT validation (Gate 1: security/jwt.py)
    ├── RBAC check (Gate 2: security/rbac.py)
    └── current_user_ctx.set(validated_user)        ← contextvar set HERE
        current_conversation_id_ctx.set(thread_uuid) ← threadId from request body
    │
    ▼
graph.ainvoke(state)
    │
    ├── _load_memory_node: user_id = current_user_ctx.get()["user_id"]
    └── _save_memory_node: user_id = current_user_ctx.get()["user_id"]
        │
        └── embed_and_store.delay(text, str(user_id), ...)
            ← user_id serialized from JWT-derived contextvar, not user input
```

### SQL-level enforcement

Every query in `memory/*.py` includes `WHERE user_id = $1`:

```python
# short_term.py
.where(
    ConversationTurn.user_id == user_id,
    ConversationTurn.conversation_id == conversation_id,
)

# long_term.py — search
.where(
    MemoryFact.user_id == user_id,
    MemoryFact.embedding.is_not(None),
    MemoryFact.superseded_at.is_(None),
)

# medium_term.py
.where(MemoryEpisode.user_id == user_id)
```

Cross-user reads are **physically impossible at the SQL level** — even if `user_id` were somehow wrong, the indexed column filter prevents touching another user's rows.

### Indexes supporting isolation

```sql
CREATE INDEX ix_memory_conversations_user_id ON memory_conversations (user_id);
CREATE INDEX ix_memory_conversations_conversation_id ON memory_conversations (conversation_id);
CREATE INDEX ix_memory_episodes_user_id ON memory_episodes (user_id);
CREATE INDEX ix_memory_facts_user_id ON memory_facts (user_id);
```

No FK constraint to a `users` table — Keycloak manages user identity. The `user_id` UUID is validated at the application layer (Gate 1 JWT check) before any DB access.

---

## 8. Configuration Reference

All settings read from `backend/core/config.py` via `settings.*`.

| Setting | Default | Notes |
|---------|---------|-------|
| `embedding_model_path` | `"BAAI/bge-m3"` | LOCKED — changing requires full reindex; DB column is `vector(1024)` |
| `embedding_sidecar_url` | `"http://embedding-sidecar:7997"` | infinity-emb HTTP sidecar URL |
| `episode_turn_threshold` | `10` | Fallback when `system_config` key not set |
| `memory_facts_search_k` | `5` | Top-k facts for semantic search (passed to `search_facts()`) |

The `episode_turn_threshold` can be overridden per-deployment via the `system_config` table:
```sql
INSERT INTO system_config (key, value) VALUES ('memory.episode_turn_threshold', '15');
```
Change takes effect within 60 seconds (TTL cache expiry).

---

## 9. Operational Runbook

### Reindex after embedding model upgrade

**Warning:** Overwrites all existing embedding vectors. Semantic search returns no results until reindex completes. Run during off-hours.

```bash
# Trigger via admin API (requires admin JWT)
curl -X POST http://localhost:8000/api/admin/memory/reindex \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"confirm": true}'

# Monitor Celery worker
celery -A scheduler.celery_app inspect active -Q default
```

### Check embedding queue health

```bash
# See active embedding tasks
celery -A scheduler.celery_app inspect active -Q embedding

# Check for stuck episodes (summarized but not yet embedded)
docker exec blitz-postgres psql -U blitz blitz \
  -c "SELECT COUNT(*) FROM memory_episodes WHERE embedding IS NULL;"

# Check for stuck facts
docker exec blitz-postgres psql -U blitz blitz \
  -c "SELECT COUNT(*) FROM memory_facts WHERE embedding IS NULL;"
```

Rows stuck with `embedding IS NULL` after >5 minutes indicate the embedding Celery worker is down. Restart it:
```bash
just dev-local-restart-workers
```

### Verify memory isolation

```bash
# Get two test users' turn counts — should never overlap
docker exec blitz-postgres psql -U blitz blitz \
  -c "SELECT user_id, COUNT(*) FROM memory_conversations GROUP BY user_id;"

# Confirm no cross-user facts
docker exec blitz-postgres psql -U blitz blitz \
  -c "SELECT user_id, COUNT(*) FROM memory_facts GROUP BY user_id;"
```

### Check episode threshold

```bash
# View current system config threshold
docker exec blitz-postgres psql -U blitz blitz \
  -c "SELECT key, value FROM system_config WHERE key = 'memory.episode_turn_threshold';"
```

---

## 10. Critical Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| `save_memory` missing contextvar fallback | `BlitzState.user_id` is always `None` when graph runs via `LangGraphAGUIAgent` (doesn't inject custom state fields) | Both `_load_memory_node` and `_save_memory_node` must use `current_user_ctx.get()` as fallback |
| Historical turns re-saved on every request | CopilotKit sends full message history on each `agent/run` call; naive save would duplicate all history | Count existing DB turns first; only save `messages[existing_count:]` |
| Embedding never fires for episodes | `summarize_episode` must explicitly call `embed_and_store.delay()` after inserting the episode row | See `summarize_episode` task — it dispatches embedding at the end of `_run()` |
| `FlagEmbedding` import fails with `is_torch_fx_available` error | `transformers>=5.0` removed `is_torch_fx_available`; `FlagEmbedding 1.3.x` depends on it | Pin `transformers<5.0` in `backend/pyproject.toml` — do NOT upgrade |
| Long-term facts never loaded | `search_facts()` only returns rows with `embedding IS NOT NULL` — if Celery embedding worker is down, facts are invisible | Monitor embedding queue; rows inserted with null embedding are invisible to search until Celery processes them |
| Medium-term load blocks on failed episode query | Episode load in `_load_memory_node` is not guarded | Wrapped in `try/except` — any failure logs a warning and allows the agent to proceed |
| `save_turn()` leaves transaction open | Caller is expected to commit; forgetting to commit loses the turn | `get_session()` context manager auto-commits on normal exit in `_save_memory_node` |
| Threshold cache stale after config change | 60s TTL; new DB value not visible immediately | Use `clear_threshold_cache()` in tests; production waits up to 60s naturally |

---

## 11. File Reference Quick Index

| File | Role |
|------|------|
| `backend/core/models/memory.py` | `ConversationTurn` ORM model → `memory_conversations` table |
| `backend/core/models/memory_long_term.py` | `MemoryFact`, `MemoryEpisode` ORM models → `memory_facts`, `memory_episodes` tables |
| `backend/memory/short_term.py` | `load_recent_turns()`, `save_turn()` |
| `backend/memory/long_term.py` | `save_fact()`, `search_facts()`, `mark_fact_superseded()` |
| `backend/memory/medium_term.py` | `save_episode()`, `load_recent_episodes()`, `get_episode_threshold_cached()`, threshold TTL cache |
| `backend/memory/embeddings.py` | `EmbeddingProvider` protocol, `BGE_M3Provider`, `SidecarEmbeddingProvider` |
| `backend/agents/master_agent.py` | `_load_memory_node()`, `_save_memory_node()`, `create_master_graph()` |
| `backend/core/context.py` | `current_user_ctx`, `current_conversation_id_ctx` — request-scoped contextvars |
| `backend/scheduler/tasks/embedding.py` | `embed_and_store`, `summarize_episode`, `reindex_memory_task` Celery tasks |
| `backend/alembic/versions/008_phase3_memory_tables.py` | DB migration: `memory_episodes` + `memory_facts` tables, HNSW indexes, `updated_at` trigger |
