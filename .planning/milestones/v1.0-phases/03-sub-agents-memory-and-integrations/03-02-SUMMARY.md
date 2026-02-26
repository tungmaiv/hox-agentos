---
phase: "03"
plan: "02"
subsystem: memory
tags: [memory, long-term, pgvector, celery, master-agent, blitz-state]
dependency_graph:
  requires: [03-01]
  provides: [medium-term-memory, long-term-memory, agent-memory-integration]
  affects: [master-agent, blitz-state, settings]
tech_stack:
  added: []
  patterns:
    - pgvector cosine_distance() on MemoryFact.embedding for semantic search
    - Graceful degradation on embedding failure (try/except in _load_memory_node)
    - Mock session pattern for pgvector tests (SQLite incompatible with Vector DDL)
    - _get_episode_threshold() DB-first with settings fallback
key_files:
  created:
    - backend/memory/medium_term.py
    - backend/memory/long_term.py
    - backend/tests/memory/test_medium_term.py
    - backend/tests/memory/test_long_term.py
    - backend/tests/agents/test_master_agent_memory.py
  modified:
    - backend/agents/master_agent.py
    - backend/agents/state/types.py
    - backend/core/config.py
decisions:
  - "Mock session approach for pgvector tests: SQLite+aiosqlite cannot create VECTOR(1024) DDL columns; all long_term and medium_term tests use AsyncMock sessions and verify SQL WHERE clause content via stmt.compile()"
  - "Graceful degradation in _load_memory_node: embedding failure (GPU OOM, model unavailable) must not block the agent; wrapped in try/except with warning log"
  - "_get_episode_threshold() defined as top-level async function (not nested): enables patching in tests via patch('agents.master_agent._get_episode_threshold')"
  - "BlitzState.delivery_targets pre-registered (list[str], default WEB_CHAT) as placeholder for DeliveryRouterNode in 03-04"
  - "Skip short-term DB load when CopilotKit provides history in state, but STILL inject long-term facts — the two are independent operations"
metrics:
  duration: "17 min"
  completed: "2026-02-26"
  tasks_completed: 3
  files_created: 5
  files_modified: 3
---

# Phase 3 Plan 02: Medium-Term + Long-Term Memory Layer Summary

Implemented medium-term (episode summaries) and long-term (semantic fact search) memory layers, then wired both into the master agent's load and save nodes. After this plan, the agent can recall facts from previous sessions via pgvector semantic search.

## What Was Built

### New Files

**`backend/memory/medium_term.py`**
- `save_episode(session, *, user_id, conversation_id, summary) -> MemoryEpisode`
  - Inserts episode row with `embedding=None` (Celery fills it later)
  - Security: `user_id` from JWT context, never from request body
- `load_recent_episodes(session, *, user_id, n=5) -> list[MemoryEpisode]`
  - Returns n most recent episodes descending by `created_at`
  - Security: `WHERE user_id = $1` parameterized

**`backend/memory/long_term.py`**
- `save_fact(session, *, user_id, content, source="conversation") -> MemoryFact`
  - Inserts fact row with `embedding=None` (Celery fills it later)
- `mark_fact_superseded(session, *, fact_id) -> None`
  - Soft-delete: sets `superseded_at = datetime.now(utc)`, no hard delete
  - If fact_id not found, silently no-ops (not an error)
- `search_facts(session, *, user_id, query_embedding, k=5) -> list[MemoryFact]`
  - Cosine distance search via pgvector `<=>` operator
  - Filters: `embedding IS NOT NULL` + `superseded_at IS NULL` + `user_id = $1`
  - Returns top k facts by ascending cosine distance (most similar first)

### Modified Files

**`backend/agents/state/types.py`**
- Added `loaded_facts: list[str]` — fact content strings injected by `_load_memory_node` (audit trail)
- Added `delivery_targets: list[str]` — placeholder for DeliveryRouterNode in 03-04 (default `["WEB_CHAT"]`)

**`backend/core/config.py`**
- Added `episode_turn_threshold: int = 10` to `Settings` class
- Fallback value when `system_config` DB key `memory.episode_turn_threshold` is not set

**`backend/agents/master_agent.py`** — major additions:
- Imports: `BGE_M3Provider`, `search_facts`, `embed_and_store`, `summarize_episode`, `settings`
- `_load_memory_node`: Added long-term memory injection after short-term turn loading
  - Embeds last user message via `BGE_M3Provider().embed()` (uses `run_in_executor`, non-blocking)
  - Calls `search_facts()` for top-5 cosine-similar facts for this user
  - Injects facts as `SystemMessage("[Long-term memory — relevant facts about this user:]...")` as first message
  - Returns `{"loaded_facts": [...]}` for audit
  - Graceful degradation: embedding failure logs a warning but never blocks the agent
- `_save_memory_node`: Added Celery dispatch after turn persistence
  - Calls `embed_and_store.delay(content, user_id, "fact")` for each new AI turn (fire-and-forget)
  - Reads `threshold = await _get_episode_threshold()` (DB-first, settings fallback)
  - Calls `summarize_episode.delay(conv_id, user_id)` when `total_turns % threshold == 0`
- `_get_episode_threshold()`: New top-level async function
  - Reads `system_config.value WHERE key = 'memory.episode_turn_threshold'`
  - Falls back to `settings.episode_turn_threshold` (=10) on absence or DB error

### Test Files

**`backend/tests/memory/test_medium_term.py`** — 5 tests
- `test_save_episode_inserts_row_with_correct_fields`: user_id, conv_id, summary, embedding=None
- `test_save_episode_embedding_is_none_on_insert`: explicit null check
- `test_load_recent_episodes_queries_by_user_id`: WHERE clause contains user_id
- `test_load_recent_episodes_returns_user_episodes_only`: user isolation
- `test_load_recent_episodes_respects_limit`: LIMIT in compiled SQL

**`backend/tests/memory/test_long_term.py`** — 8 tests
- `test_save_fact_inserts_row`: fields, embedding=None, superseded_at=None
- `test_save_fact_uses_provided_source`: custom source value
- `test_mark_fact_superseded_sets_timestamp_not_deletes`: soft delete, no session.delete()
- `test_mark_fact_superseded_noop_for_missing_id`: graceful no-op
- `test_search_facts_includes_user_id_filter`: WHERE user_id isolation
- `test_search_facts_filters_null_embeddings`: WHERE embedding IS NOT NULL
- `test_search_facts_filters_superseded_facts`: WHERE superseded_at IS NULL
- `test_search_facts_returns_list_of_facts`: result list structure

**`backend/tests/agents/test_master_agent_memory.py`** — 8 tests
- `test_load_memory_node_injects_facts_as_system_message`: fact in loaded_facts
- `test_load_memory_node_no_facts_no_system_message`: empty result = no injection
- `test_load_memory_node_gracefully_handles_embedding_failure`: no exception on GPU OOM
- `test_save_memory_node_dispatches_embed_task_for_ai_turns`: embed_and_store.delay called
- `test_save_memory_node_triggers_summarize_at_threshold`: threshold reached = dispatch
- `test_save_memory_node_no_summarize_below_threshold`: below threshold = no dispatch
- `test_get_episode_threshold_returns_db_value`: DB value preferred (=20)
- `test_get_episode_threshold_falls_back_to_settings`: absent key = settings (=10)

## Test Fixture Approach

**Why mock sessions instead of aiosqlite:** Both `MemoryEpisode` and `MemoryFact` ORM models declare `embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)`. SQLite+aiosqlite cannot execute `CREATE TABLE memory_facts (... embedding VECTOR(1024) ...)` DDL because SQLite doesn't recognize the `VECTOR` type. Attempting `Base.metadata.create_all` with these models registered causes a timeout.

**Solution:** Use `AsyncMock` for sessions throughout `test_long_term.py` and `test_medium_term.py`. For WHERE clause correctness tests, call `stmt.compile()` on the SQLAlchemy statement passed to `mock_session.execute()` and assert `"user_id"` / `"embedding"` / `"superseded_at"` appear in the SQL string. This verifies the security-critical filters are present without needing a live DB.

**For master agent tests:** Patch all external dependencies (`search_facts`, `BGE_M3Provider`, `embed_and_store`, `summarize_episode`, `_get_episode_threshold`, `async_session`). This isolates the test from DB and Celery while verifying the orchestration logic.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test state had wrong message count for threshold test**
- **Found during:** Task 3 — `test_save_memory_node_triggers_summarize_at_threshold`
- **Issue:** Test state had only 1 message but `existing_count=9`. `_save_memory_node` slices `messages[9:]` = `[]` (empty), so no new messages → early return, summarize never triggered.
- **Fix:** Updated test to include 10 messages total (9 existing + 1 new) to correctly simulate CopilotKit's full-history-in-state pattern.
- **Files modified:** `tests/agents/test_master_agent_memory.py`

**2. [Rule 2 - Missing Feature] Graceful degradation in _load_memory_node**
- **Found during:** Task 2 — plan noted "NOTE: BGE_M3Provider.embed() call runs on FastAPI request handler thread"
- **Issue:** If embedding fails (model OOM, disk full, FlagEmbedding crash), the unhandled exception would propagate up and break the entire agent response.
- **Fix:** Wrapped long-term memory search in `try/except Exception` with `logger.warning("long_term_memory_load_failed")`. Agent continues without long-term context rather than returning a 500.
- **Files modified:** `backend/agents/master_agent.py`

**3. [Rule 2 - Missing Feature] _get_episode_threshold() as top-level function**
- **Found during:** Task 2 — plan showed it as a nested function inside `_save_memory_node`
- **Issue:** Nested functions cannot be patched with `patch("agents.master_agent._get_episode_threshold")` — only module-level names are patchable.
- **Fix:** Moved to top-level async function in the module, enabling clean test isolation.
- **Files modified:** `backend/agents/master_agent.py`

## Exit Criterion

**All tests pass (32/32):**
- `tests/memory/test_embeddings.py` — 6 tests (no change, still passing)
- `tests/memory/test_short_term.py` — 5 tests (no change, still passing)
- `tests/memory/test_medium_term.py` — 5 new tests, all passing
- `tests/memory/test_long_term.py` — 8 new tests, all passing
- `tests/agents/test_master_agent_memory.py` — 8 new tests, all passing
- `tests/agents/test_master_agent.py` — 5 existing tests, all still passing

**Cross-session memory recall scenario:** The architecture is wired. Real end-to-end verification requires:
1. Start Celery embedding worker: `docker compose up -d queue_embedding`
2. Session 1: POST with "My name is Tung and I prefer dark mode" → saves turns → embed_and_store.delay fires → MemoryFact row created with 1024-dim embedding in PostgreSQL
3. Session 2: POST with "What do you know about me?" → `_load_memory_node` embeds query → cosine search → finds fact → injects as SystemMessage → LLM references "Tung" and "dark mode"

This requires the full Docker stack (PostgreSQL + pgvector + Redis + Celery) and is verified during integration testing of the phase.

## Self-Check: PASSED

Files created:
- `/home/tungmv/Projects/hox-agentos/backend/memory/medium_term.py` — EXISTS
- `/home/tungmv/Projects/hox-agentos/backend/memory/long_term.py` — EXISTS
- `/home/tungmv/Projects/hox-agentos/backend/tests/memory/test_medium_term.py` — EXISTS
- `/home/tungmv/Projects/hox-agentos/backend/tests/memory/test_long_term.py` — EXISTS
- `/home/tungmv/Projects/hox-agentos/backend/tests/agents/test_master_agent_memory.py` — EXISTS

Commits:
- `013d777` — feat(03-02): add medium_term.py + long_term.py memory layer functions
- `4f3df65` — feat(03-02): wire long-term memory into master_agent + update BlitzState + config
- `12c4c42` — test(03-02): TDD tests for medium_term, long_term, master agent memory integration
