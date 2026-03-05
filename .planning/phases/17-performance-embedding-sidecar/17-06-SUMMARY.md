---
phase: 17
plan: "06"
subsystem: backend/db
tags: [performance, db-sessions, contextvar, middleware, PERF-08]
dependency_graph:
  requires: [17-02]
  provides: [single-session-per-request, get_session helper]
  affects: [agents/master_agent.py, agents/delivery_router.py, agents/subagents/project_agent.py, agents/node_handlers.py, gateway/runtime.py, core/db.py, main.py]
tech_stack:
  added: [contextvars.ContextVar, contextlib.asynccontextmanager, starlette.middleware.base.BaseHTTPMiddleware]
  patterns: [single-session-per-request via contextvar, middleware session lifecycle]
key_files:
  created: [backend/core/db.py (_request_session_ctx, get_session, RequestSessionMiddleware), backend/tests/test_request_session.py]
  modified: [backend/main.py, backend/agents/master_agent.py, backend/agents/delivery_router.py, backend/agents/subagents/project_agent.py, backend/agents/node_handlers.py, backend/gateway/runtime.py, backend/tests/agents/test_master_agent_memory.py, backend/tests/agents/test_master_agent_routing.py, backend/tests/agents/test_node_handlers.py, backend/tests/agents/test_project_agent.py, backend/tests/agents/test_tool_node_handler.py, backend/tests/test_agent_registry.py, backend/tests/test_slash_dispatch.py]
decisions:
  - "[17-06]: get_session() is an asynccontextmanager yielding the contextvar session (no commit) when set, or opening a new async_session() otherwise — callers don't need to change commit patterns"
  - "[17-06]: RequestSessionMiddleware commits on success and rolls back on exception — route handlers and agent nodes no longer need to manage transaction lifecycle for the shared session"
  - "[17-06]: Celery tasks (scheduler/tasks/) explicitly excluded — they manage their own session lifecycle outside HTTP request context"
  - "[17-06]: Tests updated to patch get_session at import sites (agents.master_agent.get_session, agents.node_handlers.get_session, etc.) rather than the old async_session patches"
metrics:
  duration: "6 minutes"
  completed: "2026-03-05"
  tasks_completed: 5
  files_changed: 15
---

# Phase 17 Plan 06: DB Session Optimization — Single Session Per Request Summary

Single-session-per-request contextvar infrastructure replacing 6-9 separate `async with async_session()` opens per agent invocation with one shared session managed by `RequestSessionMiddleware`.

## What Was Built

### Core infrastructure (`backend/core/db.py`)
- `_request_session_ctx: ContextVar[AsyncSession | None]` — stores the request-scoped session
- `get_session()` — asynccontextmanager that returns the contextvar session when set, or falls through to `async with async_session()` for non-HTTP contexts (Celery, tests, startup)
- `RequestSessionMiddleware` — opens one `AsyncSession` per HTTP request, stores it in `_request_session_ctx`, commits on success, rolls back on exception, resets contextvar in `finally`

### Registration (`backend/main.py`)
- `RequestSessionMiddleware` registered after `CORSMiddleware` so the session is available when route handlers run (Starlette applies middleware in reverse registration order)

### Migration (`PERF-08`)
Files migrated from `async with async_session()` to `async with get_session()`:
- `backend/agents/master_agent.py` — 12 call sites (all nodes: load_memory, save_memory, master_node, skill_executor, capabilities, slash cache, agent enabled cache, etc.)
- `backend/agents/delivery_router.py` — `_resolve_channel_account`
- `backend/agents/subagents/project_agent.py` — `project_agent_node`
- `backend/agents/node_handlers.py` — `_handle_tool_node`, `_handle_channel_output_node`
- `backend/gateway/runtime.py` — `_check_gates`, agent/connect history load, agent/run artifact_builder permission check

Celery tasks under `backend/scheduler/tasks/` explicitly excluded — 13 call sites remain using `async_session()` for their own session lifecycle.

### Tests
- `backend/tests/test_request_session.py` — 2 unit tests: `test_get_session_returns_contextvar_session` and `test_get_session_opens_new_when_not_set`
- 7 existing test files updated to patch `get_session` at import sites instead of `async_session`

## Verification Results

All 4 must-haves verified:

1. Zero `async with async_session()` calls in routes/agents/memory/gateway paths
2. 13 Celery task calls remain unchanged in `scheduler/tasks/`
3. 2 `get_session()` unit tests pass
4. 742 tests pass (count unchanged from pre-plan baseline)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated 7 test files to patch `get_session` instead of `async_session`**
- **Found during:** Task 4 verification (20 test failures after migration)
- **Issue:** Test patches targeting `agents.master_agent.async_session`, `agents.node_handlers.async_session`, `agents.subagents.project_agent.async_session` broke because those modules now import `get_session` not `async_session`
- **Fix:** Updated all patch targets in test files to use the new import name at the definition site
- **Files modified:** `tests/agents/test_master_agent_memory.py`, `tests/agents/test_master_agent_routing.py`, `tests/agents/test_node_handlers.py`, `tests/agents/test_project_agent.py`, `tests/agents/test_tool_node_handler.py`, `tests/test_agent_registry.py`, `tests/test_slash_dispatch.py`
- **Commits:** included in Task 4 commit (0cf3db0)

## Commits

| Task | Hash | Message |
|------|------|---------|
| 1+2 (TDD: tests + implementation) | 6a91af4 | feat(17-06): add get_session() contextvar and RequestSessionMiddleware |
| 3 (middleware registration) | 8d3922b | feat(17-06): register RequestSessionMiddleware in FastAPI app |
| 4 (migrate callers + fix tests) | 0cf3db0 | feat(17-06): migrate async_session() callers in routes/agents/memory/gateway to get_session() (PERF-08) |

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `backend/core/db.py` exists with `_request_session_ctx`, `get_session`, `RequestSessionMiddleware` | FOUND |
| `backend/main.py` has `RequestSessionMiddleware` registered | FOUND |
| `backend/tests/test_request_session.py` exists | FOUND |
| Commit 6a91af4 exists | FOUND |
| Commit 8d3922b exists | FOUND |
| Commit 0cf3db0 exists | FOUND |
| Zero `async_session()` calls in routes/agents/memory/gateway | VERIFIED |
| 13 Celery task `async_session()` calls unchanged | VERIFIED |
| 742 tests pass | VERIFIED |
