---
phase: 03-sub-agents-memory-and-integrations
plan: "01"
subsystem: database, infra, memory
tags: [celery, redis, pgvector, bge-m3, FlagEmbedding, sqlalchemy, alembic, embeddings, long-term-memory]

# Dependency graph
requires:
  - phase: 03-sub-agents-memory-and-integrations
    provides: "03-00: system_config + mcp_servers tables, migration 007, Settings infrastructure"
  - phase: 02
    provides: "async_session(), get_llm(), load_recent_turns(), ConversationTurn ORM, Redis URL in Settings"
provides:
  - "Migration 008: memory_episodes + memory_facts tables with HNSW vector indexes and user_id isolation indexes"
  - "MemoryEpisode + MemoryFact ORM models with vector(1024) columns (pgvector.sqlalchemy.Vector)"
  - "EmbeddingProvider Protocol + BGE_M3Provider (1024-dim, lazy-load, fp16, run_in_executor)"
  - "Celery app (blitz, Redis broker, embedding + default queues)"
  - "embed_and_store task: embeds via bge-m3, inserts MemoryFact or MemoryEpisode"
  - "summarize_episode task: reads 50 turns, calls blitz/summarizer, dispatches embed_and_store"
  - "Docker Compose: celery-worker (embedding queue, concurrency=2) + celery-worker-default (default queue, concurrency=4)"
affects: [03-02-medium-term-memory, 03-03-long-term-memory, 03-04-oauth, 03-05-subagents]

# Tech tracking
tech-stack:
  added:
    - "pgvector>=0.4.2 (Python client for pgvector SQLAlchemy integration)"
    - "flagembedding>=1.3.5 (BAAI/bge-m3 model wrapper)"
    - "transformers<5.0 (pinned for FlagEmbedding 1.3.x compatibility)"
  patterns:
    - "Celery task async body pattern: asyncio.run(_run()) wraps async code inside sync Celery task"
    - "Lazy model loading at class level: BGE_M3Provider._model = None, loaded on first call"
    - "run_in_executor for CPU-bound embedding: never blocks the event loop"
    - "Soft-delete for facts: superseded_at = now() when new fact conflicts, old row preserved"

key-files:
  created:
    - "backend/alembic/versions/008_phase3_memory_tables.py"
    - "backend/core/models/memory_long_term.py"
    - "backend/memory/embeddings.py"
    - "backend/scheduler/__init__.py"
    - "backend/scheduler/celery_app.py"
    - "backend/scheduler/tasks/__init__.py"
    - "backend/scheduler/tasks/embedding.py"
    - "backend/tests/memory/test_embeddings.py"
    - "backend/tests/scheduler/__init__.py"
    - "backend/tests/scheduler/test_embedding_task.py"
  modified:
    - "backend/core/models/__init__.py (added MemoryEpisode, MemoryFact imports)"
    - "backend/core/config.py (added embedding_model_path field)"
    - "backend/pyproject.toml (added pgvector, flagembedding, pinned transformers<5.0)"
    - "docker-compose.yml (split celery-worker into queue-specific embedding + default workers)"

key-decisions:
  - "asyncio.run() pattern in Celery tasks: Celery workers are synchronous; async DB/LLM calls are wrapped in asyncio.run(_run()) — one event loop per task invocation"
  - "No FK from memory tables to users table: Keycloak manages user identity; no PostgreSQL users table exists; user_id validated at Gate 1 (JWT) not DB constraint"
  - "Pin transformers<5.0 (4.57.6): FlagEmbedding 1.3.x uses is_torch_fx_available removed in transformers 5.0; pinning resolves import error without downgrading FlagEmbedding"
  - "Split Celery workers by queue: embedding queue (concurrency=2) is CPU/memory-intensive (bge-m3); default queue (concurrency=4) is I/O-bound (LLM calls); separate processes prevent OOM"
  - "HNSW indexes partial (WHERE embedding IS NOT NULL): rows without embeddings not indexed, keeping index small during backfill"

patterns-established:
  - "Celery async pattern: all Celery tasks use asyncio.run(_run()) for async code, never asyncio.get_event_loop().run_until_complete()"
  - "EmbeddingProvider Protocol: runtime_checkable Protocol + concrete BGE_M3Provider — future providers (e.g. OpenAI embeddings) can swap in without changing callers"
  - "Class-level model cache: BGE_M3Provider._model is None → loaded once per worker process, not per task"

requirements-completed: [MEMO-02, MEMO-03, MEMO-04]

# Metrics
duration: 27min
completed: 2026-02-26
---

# Phase 3 Plan 01: Celery Embedding Pipeline + Long-Term Memory Tables Summary

**Async embedding pipeline with BAAI/bge-m3 via Celery workers: migration 008 adds memory_episodes + memory_facts tables with HNSW vector indexes, BGE_M3Provider wraps bge-m3 with lazy loading, embed_and_store and summarize_episode tasks persist 1024-dim vectors to pgvector**

## Performance

- **Duration:** 27 min
- **Started:** 2026-02-26T11:13:55Z
- **Completed:** 2026-02-26T11:41:00Z
- **Tasks:** 3
- **Files modified:** 13

## Accomplishments
- Migration 008 applied cleanly: memory_episodes + memory_facts tables with vector(1024) columns, HNSW cosine indexes (partial), user_id isolation indexes, updated_at trigger
- BGE_M3Provider satisfies EmbeddingProvider Protocol, returns 1024-dim vectors, lazy-loads 570MB model once per worker process
- Celery pipeline: embed_and_store (embedding queue) + summarize_episode (default queue) tasks with retry support and structured logging
- Docker Compose updated with two queue-specific workers (embedding=2, default=4 concurrency)
- 15 tests pass: 6 embedding tests + 9 Celery task tests (all mocked, no real model/DB required)

## Task Commits

Each task was committed atomically:

1. **Task 1: DB migration 008 + ORM models** - `0ead075` (feat)
2. **Task 2: BGE_M3Provider + Celery app + tasks** - `d08e554` (feat)
3. **Task 3: TDD tests for embeddings + Celery tasks** - `3c579e6` (test)

**Plan metadata:** _(docs commit — pending)_

## Files Created/Modified
- `backend/alembic/versions/008_phase3_memory_tables.py` - Migration 008: memory_episodes + memory_facts tables, HNSW indexes, updated_at trigger
- `backend/core/models/memory_long_term.py` - MemoryEpisode + MemoryFact ORM models with Vector(1024) columns
- `backend/core/models/__init__.py` - Added MemoryEpisode, MemoryFact imports for Alembic detection
- `backend/memory/embeddings.py` - EmbeddingProvider Protocol + BGE_M3Provider (1024-dim, lazy-load, fp16)
- `backend/scheduler/__init__.py` - Scheduler package init
- `backend/scheduler/celery_app.py` - Celery app: Redis broker, embedding + default queues, task routing
- `backend/scheduler/tasks/__init__.py` - Tasks subpackage init
- `backend/scheduler/tasks/embedding.py` - embed_and_store + summarize_episode Celery tasks
- `backend/core/config.py` - Added embedding_model_path field to Settings
- `backend/pyproject.toml` - Added pgvector, flagembedding; pinned transformers<5.0
- `docker-compose.yml` - Split celery-worker into celery-worker (embedding) + celery-worker-default (default) services
- `backend/tests/memory/test_embeddings.py` - 6 tests for BGE_M3Provider with mocked FlagModel
- `backend/tests/scheduler/test_embedding_task.py` - 9 tests for embed_and_store + summarize_episode tasks

## Decisions Made

1. **asyncio.run() in Celery tasks**: Celery workers run synchronous Python; the async DB/LLM calls are wrapped in `asyncio.run(_run())` inside each task. One event loop per task invocation. This is the standard pattern for bridging Celery + asyncio.

2. **No FK to users table**: The plan spec included `sa.ForeignKeyConstraint(["user_id"], ["users.id"])` but no `users` table exists in PostgreSQL — Keycloak manages user identity. All other Phase 1-2 tables (tool_acl, memory_conversations, etc.) follow the same pattern. Removed FK constraints from migration.

3. **Pin transformers<5.0**: FlagEmbedding 1.3.5 imports `is_torch_fx_available` from `transformers.utils.import_utils` which was removed in transformers 5.0. Pinned `transformers<5.0` (resolved to 4.57.6). This is a correct fix — FlagEmbedding's dependency constraints should specify this but don't.

4. **Split Celery worker services**: The plan had one generic `celery-worker` service; replaced with two queue-specific services so the CPU/memory-intensive bge-m3 embedding queue doesn't share resources with the I/O-bound LLM summarization queue.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed non-existent FK constraint from migration**
- **Found during:** Task 1 (migration 008 execution)
- **Issue:** Plan spec included `sa.ForeignKeyConstraint(["user_id"], ["users.id"])` but no `users` table exists in PostgreSQL — Keycloak manages user identity externally
- **Fix:** Removed FK constraint; added comment explaining Keycloak manages user identity, JWT validates user_id at Gate 1
- **Files modified:** `backend/alembic/versions/008_phase3_memory_tables.py`
- **Verification:** Migration applied cleanly; `alembic current` shows 008 (head)
- **Committed in:** `0ead075` (Task 1 commit)

**2. [Rule 3 - Blocking] Pin transformers<5.0 for FlagEmbedding compatibility**
- **Found during:** Task 2 (FlagEmbedding installation + verification)
- **Issue:** FlagEmbedding 1.3.5 raised `ImportError: cannot import name 'is_torch_fx_available' from transformers.utils.import_utils` because transformers 5.x removed this function
- **Fix:** `uv add "transformers<5.0"` — resolved to transformers==4.57.6; FlagModel import verified working
- **Files modified:** `backend/pyproject.toml`
- **Verification:** `from FlagEmbedding import FlagModel; print('OK')` succeeds
- **Committed in:** `d08e554` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
- FlagEmbedding 1.3.5 + transformers 5.2.0 incompatibility (pinned transformers<5.0 as fix)
- migration 008 FK reference to non-existent `users` table (removed FK, consistent with existing tables)

## User Setup Required
None - no external service configuration required for this plan.

## Next Phase Readiness
- 03-02 (medium-term memory) can proceed: `async_session()`, `MemoryFact`, `embed_and_store.delay()` are all available
- 03-03 (long-term memory search) can proceed: HNSW indexes on memory_facts + memory_episodes are ready
- Celery workers need `just up` with updated docker-compose.yml to activate in development
- bge-m3 model (570MB) will be downloaded from HuggingFace on first Celery worker startup — plan for this in staging

## Self-Check: PASSED

All created files verified present. All task commits verified in git log.

---
*Phase: 03-sub-agents-memory-and-integrations*
*Completed: 2026-02-26*
