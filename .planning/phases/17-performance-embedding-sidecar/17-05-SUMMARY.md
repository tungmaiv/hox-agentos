---
phase: 17-performance-embedding-sidecar
plan: "05"
subsystem: memory
tags: [embedding, sidecar, celery, fastapi, admin-api, memory-reindex]

# Dependency graph
requires:
  - phase: 17-01
    provides: SidecarEmbeddingProvider in memory/embeddings.py with validate_dimension()

provides:
  - master_agent.py uses SidecarEmbeddingProvider (non-blocking HTTP path for FastAPI)
  - Backend startup validates embedding sidecar dimension (non-fatal, logs warning on failure)
  - POST /api/admin/memory/reindex endpoint (202 Accepted, tool:admin required, confirm=true required)
  - reindex_memory_task Celery task (re-embeds all MemoryFact and MemoryEpisode rows in batches of 32)

affects:
  - 17-performance-embedding-sidecar
  - any phase touching master_agent.py or memory embedding paths

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Admin endpoint pattern: _require_admin dependency with has_permission(user, 'tool:admin', session)"
    - "Celery task with asyncio.run(_run()) wrapping for async DB operations"
    - "Non-fatal startup validation: try/except around sidecar check in lifespan()"

key-files:
  created:
    - backend/api/routes/admin_memory.py
    - backend/tests/api/test_memory_reindex.py
  modified:
    - backend/agents/master_agent.py
    - backend/main.py
    - backend/scheduler/tasks/embedding.py
    - backend/tests/agents/test_master_agent_memory.py

key-decisions:
  - "Admin memory reindex uses tool:admin permission (not registry:manage) — matches system_config.py pattern for system-wide admin ops"
  - "reindex_memory_task uses session-per-batch pattern (separate async_session() for read vs write) — avoids holding long-running transactions"
  - "Startup sidecar check is non-fatal — backend starts even when sidecar not yet warm (fallback to BGE_M3Provider)"
  - "Test patches updated from BGE_M3Provider to SidecarEmbeddingProvider at import site (agents.master_agent.SidecarEmbeddingProvider)"

requirements-completed: [PERF-01, PERF-05, PERF-06]

# Metrics
duration: 5min
completed: 2026-03-05
---

# Phase 17 Plan 05: Embedding Sidecar Migration, Startup Validation, Admin Endpoint Summary

**SidecarEmbeddingProvider replaces BGE_M3Provider in master_agent.py, startup validates sidecar dimension non-fatally, and POST /api/admin/memory/reindex triggers full re-embedding via Celery**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-05T12:41:05Z
- **Completed:** 2026-03-05T12:46:11Z
- **Tasks:** 5 (Tasks 3+4 combined as TDD RED+GREEN)
- **Files modified:** 6

## Accomplishments
- `agents/master_agent.py` now calls `SidecarEmbeddingProvider` (non-blocking HTTP) instead of `BGE_M3Provider` (CPU-bound, for Celery only)
- `main.py` lifespan hook calls `validate_dimension()` at startup — logs `embedding_sidecar_validated` on success, `embedding_sidecar_startup_check_failed` on failure (non-fatal)
- `POST /api/admin/memory/reindex` endpoint: 403 for non-admin, 422 if `confirm=false`, 202+job_id when enqueued
- `reindex_memory_task` Celery task re-embeds all `MemoryFact` and `MemoryEpisode` rows using `SidecarEmbeddingProvider`, batch size 32
- 3 new tests; total test count 740 (was 737 before this plan)

## Task Commits

1. **Task 1: Replace BGE_M3Provider with SidecarEmbeddingProvider in master_agent** - `c94b6cc` (feat)
2. **Task 2: Validate embedding sidecar dimension on backend startup** - `56436df` (feat)
3. **Tasks 3+4: Add POST /api/admin/memory/reindex endpoint and Celery task** - `988486b` (feat)

**Plan metadata:** (see docs commit below)

## Files Created/Modified
- `backend/agents/master_agent.py` - Replaced BGE_M3Provider import/usage with SidecarEmbeddingProvider
- `backend/main.py` - Added non-fatal sidecar validate_dimension() call in lifespan startup + admin_memory_router registration
- `backend/api/routes/admin_memory.py` - New: ReindexRequest (confirm validator), ReindexResponse, _require_admin Gate 2 dep, POST /reindex route
- `backend/scheduler/tasks/embedding.py` - Added reindex_memory_task Celery task (re-embeds facts+episodes in batches of 32)
- `backend/tests/api/test_memory_reindex.py` - New: 3 tests (403 non-admin, 422 no-confirm, 202+job_id success)
- `backend/tests/agents/test_master_agent_memory.py` - Updated 5 test patches from BGE_M3Provider to SidecarEmbeddingProvider

## Decisions Made
- Admin memory reindex uses `tool:admin` permission (not `registry:manage`) — consistent with `system_config.py` pattern for system-wide admin operations
- `reindex_memory_task` uses separate `async_session()` for read and each write batch — avoids holding transactions open during slow embedding calls
- Startup check is non-fatal — backend starts and serves requests even when sidecar not yet warm (BGE_M3Provider fallback active)
- Test fixtures follow existing `TestClient` pattern with `app.dependency_overrides` (not `AsyncClient` with `admin_headers` as in plan — `AsyncClient` not used elsewhere in this codebase)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test patches from BGE_M3Provider to SidecarEmbeddingProvider**
- **Found during:** Task 1 (after running full test suite post-migration)
- **Issue:** 5 tests in `test_master_agent_memory.py` patched `agents.master_agent.BGE_M3Provider` which no longer exists at that import site — all 5 tests failed with AttributeError
- **Fix:** Updated all 5 `patch()` calls to patch `agents.master_agent.SidecarEmbeddingProvider`; updated test docstring
- **Files modified:** `backend/tests/agents/test_master_agent_memory.py`
- **Verification:** All 5 tests pass; 737 total pass after fix
- **Committed in:** `c94b6cc` (Task 1 commit)

**2. [Rule 1 - Bug] Used TestClient pattern instead of AsyncClient with fixtures**
- **Found during:** Task 3 (writing tests)
- **Issue:** Plan specified `AsyncClient` with `user_headers`/`admin_headers` dict fixtures — neither pattern exists in this codebase; all API tests use `TestClient` + `app.dependency_overrides`
- **Fix:** Wrote tests using established `TestClient` pattern with `make_admin_ctx()`/`make_employee_ctx()` dependency overrides and `sqlite_db` fixture
- **Files modified:** `backend/tests/api/test_memory_reindex.py`
- **Verification:** All 3 tests pass
- **Committed in:** `988486b` (Tasks 3+4 commit)

**3. [Rule 1 - Bug] Used `has_permission(user, "tool:admin", session)` instead of non-existent `require_roles(user, ["admin"])`**
- **Found during:** Task 4 (implementing admin_memory.py)
- **Issue:** Plan used `require_roles(user, ["admin"])` — this function does not exist in the codebase; all admin routes use `has_permission()` with a specific permission string
- **Fix:** Implemented `_require_admin` dependency using `has_permission(user, "tool:admin", session)` following `system_config.py` pattern
- **Files modified:** `backend/api/routes/admin_memory.py`
- **Verification:** 403 test passes with employee role (lacks tool:admin), 202 test passes with it-admin role
- **Committed in:** `988486b` (Tasks 3+4 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 - bugs / incompatibilities)
**Impact on plan:** All fixes necessary for correctness and consistency with codebase conventions. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations documented above.

## User Setup Required
None - no external service configuration required. The embedding sidecar itself was set up in 17-01.

## Next Phase Readiness
- PERF-01 (master_agent migration), PERF-05 (admin endpoint), PERF-06 (startup validation) all satisfied
- Plans 17-06 and 17-07 can proceed independently
- `BGE_M3Provider` remains only in `scheduler/tasks/embedding.py` (Celery worker path) as intended — confirmed by grep

---
*Phase: 17-performance-embedding-sidecar*
*Completed: 2026-03-05*
