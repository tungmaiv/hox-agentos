---
phase: 17-performance-embedding-sidecar
verified: 2026-03-05T00:00:00Z
status: passed
score: 13/13 must-haves verified
re_verification: false
---

# Phase 17: Performance & Embedding Sidecar Verification Report

**Phase Goal:** Add embedding sidecar service, instrumentation, caching, and performance optimizations to reduce agent response latency
**Verified:** 2026-03-05
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Embedding sidecar Docker Compose service exists with health check | VERIFIED | `docker-compose.yml` lines 59-75: `michaelf34/infinity:latest`, `EMBEDDING_MODEL` env var, `7997:7997`, healthcheck present |
| 2 | `SidecarEmbeddingProvider` calls HTTP sidecar with fallback to `BGE_M3Provider` | VERIFIED | `backend/memory/embeddings.py` lines 108-175: class defined, `POST /embeddings`, `ConnectError` fallback |
| 3 | Embedding model dimension validated at startup | VERIFIED | `backend/main.py` lines 104-116: `validate_dimension()` called in lifespan, non-fatal on failure |
| 4 | `BGE_M3Provider` removed from uvicorn/FastAPI path (no dual-load) | VERIFIED | Only lazy import inside `scheduler/tasks/embedding.py` (Celery task, inside function body) — not imported in `main.py`, `master_agent.py`, or any API route |
| 5 | Admin reindex endpoint exists with admin-role guard and confirm=true requirement | VERIFIED | `backend/api/routes/admin_memory.py`: `POST /api/admin/memory/reindex`, `has_permission(user, "tool:admin")`, `model_validator` enforces `confirm=True` |
| 6 | `duration_ms` logged via `timed()` on 7 critical paths | VERIFIED | 7 call sites confirmed: `master_agent.py` (memory_search, llm_call), `node_handlers.py` (tool_execution), `graphs.py` (canvas_compile), `mcp/client.py` (mcp_call), `channels/gateway.py` (channel_delivery), `scheduler/tasks/workflow_execution.py` (workflow_run) |
| 7 | Single DB session per HTTP request via contextvar (no 6-9 session opens) | VERIFIED | `core/db.py`: `_request_session_ctx`, `get_session()`, `RequestSessionMiddleware` all present. Zero `async with async_session()` calls remain in routes/agents/memory/gateway. Celery tasks still use `async_session()` (correct) |
| 8 | Tool ACL results cached with 60s TTL per user+tool | VERIFIED | `security/acl.py`: `_acl_cache = TTLCache(maxsize=500, ttl=60)`, `check_tool_acl_cached()`, `clear_acl_cache()` present |
| 9 | Episode threshold cached with 60s TTL | VERIFIED | `memory/medium_term.py`: `_threshold_cache = TTLCache(maxsize=200, ttl=60)`, `get_episode_threshold_cached()`, private `_get_episode_threshold()` removed from `master_agent.py` |
| 10 | User instructions cached per-user with 60s TTL | VERIFIED | `api/routes/user_instructions.py`: `_instructions_cache = TTLCache(maxsize=200, ttl=60)`, `get_user_instructions_cached()`, `clear_instructions_cache()`, cache invalidated on PUT |
| 11 | JWKS refresh uses `asyncio.Lock` to prevent thundering herd | VERIFIED | `security/jwt.py` line 46: `_jwks_refresh_lock: asyncio.Lock = asyncio.Lock()`, double-checked locking pattern in `_get_jwks()` |
| 12 | `useSkills()` hoisted above CopilotKit key boundary | VERIFIED | `chat-panel.tsx` line 522: `useSkills()` inside `ChatPanel` (starts at line 512), NOT inside `ChatPanelInner` (starts at line 343). `skills` passed as prop at line 546 |
| 13 | Admin UI Memory tab with confirmation dialog exists | VERIFIED | `admin/layout.tsx` line 18: `{ label: "Memory", href: "/admin/memory" }`. `admin/memory/page.tsx`: "Yes, Reindex", "confirming" state, "cannot be undone" text, `/api/admin/memory/reindex` proxy URL (not direct backend) |

**Score:** 13/13 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docker-compose.yml` | `embedding-sidecar` service block | VERIFIED | `michaelf34/infinity:latest`, `embedding_model_cache` volume, healthcheck, port 7997 |
| `backend/memory/embeddings.py` | `SidecarEmbeddingProvider` class | VERIFIED | 1024-dim, HTTP POST to `/embeddings`, `ConnectError` fallback, `validate_dimension()` |
| `backend/tests/memory/test_sidecar_embedding.py` | 4 tests | VERIFIED | 4 PASSED |
| `backend/core/logging.py` | `timed()` context manager | VERIFIED | `@contextmanager`, `finally` block guarantees logging even on exception |
| `backend/tests/test_timed_logging.py` | 3 tests | VERIFIED | 3 PASSED |
| `backend/core/config.py` | `embedding_sidecar_url` setting | VERIFIED | Line 75: `embedding_sidecar_url: str = "http://embedding-sidecar:7997"` |
| `backend/security/acl.py` | `check_tool_acl_cached()`, `_acl_cache`, `clear_acl_cache()` | VERIFIED | All present, TTL=60s, maxsize=500 |
| `backend/memory/medium_term.py` | `get_episode_threshold_cached()`, `_threshold_cache`, `clear_threshold_cache()` | VERIFIED | All present, TTL=60s, maxsize=200 |
| `backend/agents/master_agent.py` | Uses `SidecarEmbeddingProvider` and `get_episode_threshold_cached()` | VERIFIED | Import confirmed at lines 48 and 50; old `_get_episode_threshold()` removed |
| `backend/api/routes/user_instructions.py` | `get_user_instructions_cached()`, `_instructions_cache`, `clear_instructions_cache()` | VERIFIED | All present; cache invalidated on PUT at line 130 |
| `backend/tests/test_acl_cache.py` | 3 tests | VERIFIED | 3 PASSED |
| `backend/tests/test_memory_caches.py` | 2 tests | VERIFIED | 2 PASSED |
| `frontend/src/app/(authenticated)/admin/memory/page.tsx` | Admin memory reindex page with confirmation dialog | VERIFIED | "Yes, Reindex", "confirming" state, "cannot be undone", proxy URL correct |
| `frontend/src/app/api/admin/memory/reindex/route.ts` | Next.js JWT-forwarding proxy | VERIFIED | Uses `auth()` session, injects `Authorization: Bearer` header |
| `frontend/src/app/(authenticated)/admin/layout.tsx` | Memory tab in ADMIN_TABS | VERIFIED | Line 18: `{ label: "Memory", href: "/admin/memory" }` |
| `backend/agents/master_agent.py` | `timed()` on memory_search and llm_call | VERIFIED | Lines 133 and 298 |
| `backend/api/routes/admin_memory.py` | `POST /api/admin/memory/reindex` route | VERIFIED | 403 for non-admin, 422 for `confirm=false`, 202 + job_id for admin |
| `backend/scheduler/tasks/embedding.py` | `reindex_memory_task` Celery task | VERIFIED | `@celery_app.task(name="blitz.reindex_memory")`, re-embeds facts and episodes in batches of 32 |
| `backend/tests/api/test_memory_reindex.py` | 3 tests | VERIFIED | 3 PASSED |
| `backend/main.py` | `SidecarEmbeddingProvider` startup validation + `RequestSessionMiddleware` registered | VERIFIED | Lines 104-116 (startup), line 145 (middleware) |
| `backend/core/db.py` | `_request_session_ctx`, `get_session()`, `RequestSessionMiddleware` | VERIFIED | All present; contextvar fallback to new session when not set |
| `backend/tests/test_request_session.py` | 2 tests | VERIFIED | 2 PASSED |
| `backend/security/jwt.py` | `_jwks_refresh_lock` with double-checked locking | VERIFIED | Line 46: lock declaration, lines 89-115: double-check pattern |
| `backend/tests/security/test_jwks_lock.py` | 1 test | VERIFIED | 1 PASSED — concurrent refresh fires only 1 HTTP call |
| `frontend/src/components/chat/chat-panel.tsx` | `useSkills()` in `ChatPanel`, not `ChatPanelInner` | VERIFIED | Line 522 (ChatPanel starts at 512); `skills` prop passed at line 546 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `master_agent.py` | `memory/embeddings.py` | `SidecarEmbeddingProvider` import | WIRED | Import confirmed line 48; usage at line 129 |
| `master_agent.py` | `memory/medium_term.py` | `get_episode_threshold_cached` import | WIRED | Import confirmed line 50; usage at line 404 |
| `agents/node_handlers.py` | `core/logging.py` | `timed()` | WIRED | `timed(logger, "tool_execution", ...)` at line 196 |
| `security/acl.py` | `gateway/runtime.py` | `check_tool_acl_cached` | WIRED | `check_tool_acl_cached` called in gate 3 flow |
| `core/db.py` | `main.py` | `RequestSessionMiddleware` registration | WIRED | Import at line 42, `app.add_middleware()` at line 145 |
| `api/routes/admin_memory.py` | `scheduler/tasks/embedding.py` | `reindex_memory_task.delay()` | WIRED | Import confirmed; `.delay()` called in route handler |
| `api/routes/admin_memory.py` | `main.py` | `include_router()` | WIRED | Line 35 import, line 207 registration |
| `admin/memory/page.tsx` | `app/api/admin/memory/reindex/route.ts` | `fetch("/api/admin/memory/reindex")` | WIRED | Line 37: relative proxy URL, not backend URL |
| `chat-panel.tsx` `ChatPanel` | `ChatPanelInner` | `skills={skills}` prop | WIRED | Line 546; `ChatPanelInnerProps` updated to accept `skills: SkillItem[]` |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PERF-01 | 17-01, 17-05 | `SidecarEmbeddingProvider` in `master_agent.py` | SATISFIED | `master_agent.py` imports and uses `SidecarEmbeddingProvider`; `BGE_M3Provider` removed from uvicorn path |
| PERF-02 | 17-01 | `EMBEDDING_MODEL` env var configurable; health endpoint reports model/dim | SATISFIED | `docker-compose.yml` uses `${EMBEDDING_MODEL:-BAAI/bge-m3}`; `validate_dimension()` calls `/health` |
| PERF-03 | 17-01 | HTTP sidecar first, fallback to Celery path on `ConnectError` | SATISFIED | `SidecarEmbeddingProvider.embed()` catches `httpx.ConnectError`, falls back to `BGE_M3Provider()` |
| PERF-04 | 17-01, 17-05 | `BGE_M3Provider` not dual-loaded in uvicorn | SATISFIED | Only lazy import inside Celery task function body in `scheduler/tasks/embedding.py`; no module-level import in FastAPI code |
| PERF-05 | 17-04, 17-05 | Admin reindex via UI + `POST /api/admin/memory/reindex` | SATISFIED | Backend route (admin_memory.py, 202+job_id) + frontend page (admin/memory/page.tsx, confirmation dialog) + proxy route |
| PERF-06 | 17-05 | Startup dimension validation | SATISFIED | `main.py` lifespan calls `validate_dimension()`, logs `embedding_sidecar_validated` or `embedding_sidecar_startup_check_failed` |
| PERF-07 | 17-02 | `duration_ms` logged on 7 critical paths | SATISFIED | 7 `timed(logger, ...)` call sites confirmed across 6 files |
| PERF-08 | 17-06 | Single DB session per request via contextvar | SATISFIED | 0 residual `async with async_session()` in routes/agents/memory/gateway; `RequestSessionMiddleware` registered |
| PERF-09 | 17-03 | Tool ACL TTL cache 60s per user | SATISFIED | `_acl_cache = TTLCache(maxsize=500, ttl=60)` in `security/acl.py` |
| PERF-10 | 17-03 | Episode threshold TTL cache 60s | SATISFIED | `_threshold_cache = TTLCache(maxsize=200, ttl=60)` in `memory/medium_term.py`; `master_agent.py` uses `get_episode_threshold_cached` |
| PERF-11 | 17-03 | User instructions TTL cache 60s per user | SATISFIED | `_instructions_cache = TTLCache(maxsize=200, ttl=60)` in `api/routes/user_instructions.py`; invalidated on PUT |
| PERF-12 | 17-07 | JWKS `asyncio.Lock` prevents thundering herd | SATISFIED | `_jwks_refresh_lock: asyncio.Lock = asyncio.Lock()` at line 46 with double-checked locking |
| PERF-13 | 17-07 | `useSkills()` hoisted above CopilotKit key boundary | SATISFIED | `useSkills()` at line 522 inside `ChatPanel` (line 512); `ChatPanelInner` (line 343) receives `skills` as prop |

All 13 PERF requirements SATISFIED. No orphaned requirements.

---

### Anti-Patterns Found

No blockers or warnings. All new code follows project patterns:
- `BGE_M3Provider` import in `scheduler/tasks/embedding.py` is a lazy import inside the Celery task function body — this is the documented correct pattern per CLAUDE.md (Celery tasks use `asyncio.run()` and lazy imports).
- `main.py` comment "fallback to BGE_M3Provider" at line 106 is a comment, not an import — no issue.
- `timed()` uses `finally` block ensuring duration is always logged even on exceptions — correct.
- `RequestSessionMiddleware` is registered after CORSMiddleware in `main.py` — correct order per plan.

---

### Human Verification Required

The following items cannot be verified programmatically:

#### 1. Embedding Sidecar Warm-Up Time

**Test:** Run `just up embedding-sidecar` and monitor `docker compose logs -f embedding-sidecar` for `bge-m3` model download and load completion message.
**Expected:** Service becomes healthy within 120s (start_period in healthcheck). Backend logs `"embedding_sidecar_validated"` once healthy.
**Why human:** Requires Docker infrastructure running and network access to download `BAAI/bge-m3` model (~1.1GB).

#### 2. Admin Memory UI End-to-End Flow

**Test:** Navigate to `http://localhost:3000/admin/memory` as an `it-admin` user. Click "Reindex Memory", verify confirmation dialog appears, click "Yes, Reindex".
**Expected:** Transitions to "Reindex in progress" state with a job_id displayed. Backend logs `"memory_reindex_enqueued"`.
**Why human:** Requires running frontend, backend, and valid admin JWT session.

#### 3. `useSkills()` Remount Behavior

**Test:** Open the chat panel, switch between conversations. Open browser DevTools Network tab and filter for `/api/skills` requests.
**Expected:** `GET /api/skills` is called once on page load, NOT on every conversation switch.
**Why human:** Requires a running browser with conversation switching capability.

#### 4. `duration_ms` Log Output Validation

**Test:** Trigger an agent conversation. Check `logs/blitz/` for structured JSON log entries with `duration_ms` field.
**Expected:** Log entries present for `memory_search`, `llm_call`, `tool_execution`, `canvas_compile`, `mcp_call`, `channel_delivery`, `workflow_run` events with non-zero `duration_ms` values.
**Why human:** Requires live agent execution to generate log entries.

---

## Test Suite Results

- **Total backend tests:** 743 (719 baseline + 24 new Phase 17 tests), 1 skipped, 0 failures
- **Phase 17 new tests:** 18 PASSED (4 sidecar embedding, 3 timed logging, 3 ACL cache, 2 memory caches, 3 reindex endpoint, 2 request session, 1 JWKS lock)
- **Frontend TypeScript:** `pnpm exec tsc --noEmit` exits 0 with no errors
- **Git commits:** 20 atomic commits with correct `feat(17-0X):` prefix format

---

## Gaps Summary

No gaps. All 13 PERF requirements are satisfied with working, wired, and substantive implementations. The phase goal is achieved:

- **Embedding sidecar** (`michaelf34/infinity:latest`) is defined as a Docker Compose service with model caching, health check, and configurable `EMBEDDING_MODEL`
- **SidecarEmbeddingProvider** replaces `BGE_M3Provider` in the FastAPI request path with automatic fallback; no dual-load in uvicorn
- **7 critical paths** instrumented with `timed()` duration logging
- **Single DB session** per HTTP request eliminates 6-9 redundant session opens
- **3 TTL caches** eliminate repeated DB queries for ACL, episode threshold, and user instructions
- **JWKS lock** prevents thundering herd on concurrent token validation
- **useSkills() hoisted** prevents re-fetch on every conversation switch
- **Admin reindex** available via UI with confirmation dialog and backend Celery task

---

_Verified: 2026-03-05_
_Verifier: Claude (gsd-verifier)_
