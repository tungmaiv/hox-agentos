---
phase: 01-identity-and-infrastructure-skeleton
plan: "04"
subsystem: api
tags: [fastapi, routes, security, jwt, rbac, acl, next-auth, sonner, typescript, pytest, sqlite, alembic]

# Dependency graph
requires:
  - phase: 01-02
    provides: UserContext TypedDict, get_current_user() FastAPI dependency, JWT Gate 1
  - phase: 01-03
    provides: has_permission() RBAC Gate 2, check_tool_acl() ACL Gate 3, log_tool_call() audit
  - phase: 01-01
    provides: core/config.py Settings, core/db.py get_db(), core/logging.py configure_logging()
provides:
  - GET /health → 200 HealthResponse (no authentication required)
  - POST /api/agents/chat with full 3-gate security chain (Gate 1+2+3) — Phase 1 stub returning 501
  - FastAPI app factory with routes registered via app.include_router()
  - 58-test backend test suite (all passing, no ordering failures)
  - frontend/src/lib/api-client.ts serverFetch<T>() with server-side Bearer injection
  - AuthHeader Server Component showing user email + SignOutButton Client Component
  - AuthErrorToasts (Sonner Toaster) for 401/403 error notifications
  - Alembic migration 001 run: tool_acl table + pgvector + uuid-ossp in PostgreSQL
affects:
  - 02+ (Agent routes — Phase 2 will implement actual chat logic in the 501 stub endpoint)
  - All future FastAPI routes — must follow Depends(get_current_user) + has_permission() pattern
  - Frontend Phase 2 — serverFetch() available for all server-side API calls

# Tech tracking
tech-stack:
  added:
    - sonner (toast notifications for 401/403 auth errors — frontend)
  patterns:
    - FastAPI router pattern: health.router (no prefix) + agents.router (prefix=/api)
    - 3-gate security chain in route handlers: Depends(get_current_user) → has_permission() → check_tool_acl() → log_tool_call()
    - SQLite dependency override pattern for integration tests that reach Gate 3 (check_tool_acl needs DB)
    - serverFetch<T>() server-side fetch wrapper: access token from server session, never exposed to browser
    - AuthHeader as Server Component: auth() read server-side, no useSession() Client Component needed for displaying user email

key-files:
  created:
    - backend/api/__init__.py
    - backend/api/routes/__init__.py
    - backend/api/routes/health.py
    - backend/api/routes/agents.py
    - backend/tests/test_health.py
    - backend/tests/test_agents_auth.py
    - frontend/src/lib/api-client.ts
    - frontend/src/components/auth-header.tsx
    - frontend/src/components/sign-out-button.tsx
    - frontend/src/components/auth-error-toasts.tsx
  modified:
    - backend/main.py (added app.include_router() calls)
    - backend/tests/conftest.py (added configure_logging() at session start)
    - backend/tests/test_acl.py (fixed audit log capture: caplog+capsys for stdlib.LoggerFactory)
    - backend/tests/test_config.py (removed reload() causing cross-test settings contamination)
    - frontend/src/app/chat/page.tsx (use AuthHeader component)
    - frontend/src/app/layout.tsx (add AuthErrorToasts)
    - frontend/src/auth.ts (include accessToken in server session for serverFetch())
    - frontend/package.json (added sonner)

key-decisions:
  - "GET /health has no /api prefix so Docker/load balancer health checks can reach it without credentials"
  - "test_agents_auth.py overrides get_db with in-memory SQLite so tests reaching Gate 3 don't need a live PostgreSQL"
  - "conftest.py calls configure_logging() at session start to prevent structlog config state from causing test ordering failures"
  - "test_config.py removed reload() inside patch.dict context — reload() persisted module state after patch exit, causing JWT test contamination"
  - "test_acl.py audit log test uses both caplog+capsys to capture structlog output regardless of LoggerFactory config state"
  - "auth.ts uses (session as unknown as Record<string, unknown>).accessToken to avoid TS2352 strict-mode cast error"
  - "AuthHeader is a Server Component (reads auth() directly) — no useSession() Client Component needed for displaying user email"

patterns-established:
  - "3-gate route pattern: Depends(get_current_user) in function signature → has_permission() → check_tool_acl() → log_tool_call() → business logic"
  - "Integration test DB pattern: pytest fixture creates SQLite engine, runs create_all(), overrides get_db dependency"
  - "serverFetch<T>(path, options): only for Server Components/Actions; access token injected automatically"
  - "403 response format: {detail, permission_required, user_roles, hint} — enforced in all denied routes"

requirements-completed:
  - AUTH-01
  - AUTH-04
  - AUTH-05

# Metrics
duration: 20min
completed: "2026-02-24"
---

# Phase 1 Plan 04: FastAPI Routes + Frontend API Client Summary

**FastAPI /health + /api/agents/chat with 3-gate security (JWT->RBAC->ACL->audit), 58 backend tests all passing, frontend serverFetch() Bearer injection, AuthHeader Server Component — Phase 1 complete with browser SSO verified**

## Performance

- **Duration:** ~20 min (Tasks 1+2+3 complete, checkpoint approved)
- **Started:** 2026-02-24T14:19:39Z
- **Completed:** 2026-02-24T14:39:25Z
- **Tasks:** 3/3 complete
- **Files modified:** 18

## Accomplishments

- `api/routes/health.py` GET /health -> 200 HealthResponse (no auth, no /api prefix)
- `api/routes/agents.py` POST /api/agents/chat enforcing full 3-gate chain: JWT (Gate 1 via Depends) -> RBAC "chat" permission (Gate 2) -> Tool ACL (Gate 3) -> audit log -> 501 stub
- `main.py` updated: `app.include_router(health.router)` + `app.include_router(agents.router, prefix="/api")`
- 6 health tests + 6 agents auth tests — 58 total backend tests, all passing (verified final run: 58 passed, 7 warnings, 1.20s)
- Alembic migration 001 ran against real PostgreSQL: tool_acl, alembic_version tables confirmed
- `frontend/src/lib/api-client.ts`: serverFetch<T>() with server-side Bearer token injection
- AuthHeader, SignOutButton, AuthErrorToasts frontend components
- TypeScript strict: true compiles cleanly
- Browser SSO flow verified: / -> Keycloak login -> /chat with user email in header -> sign out working

## Task Commits

Each task was committed atomically:

1. **Task 1: FastAPI routes and complete security integration** - `583c843` (feat)
2. **Task 2: Frontend API client with Authorization header injection** - `03c34b9` (feat)
3. **Task 3: Verify Phase 1 SSO and security chain end-to-end** - (see plan metadata commit)

**Plan metadata:** (see final docs commit)

## Files Created/Modified

**Backend:**
- `backend/api/__init__.py` - api package init
- `backend/api/routes/__init__.py` - routes package init
- `backend/api/routes/health.py` - GET /health (no auth, HealthResponse)
- `backend/api/routes/agents.py` - POST /api/agents/chat (3-gate security chain)
- `backend/main.py` - include_router() for health + agents
- `backend/tests/test_health.py` - 3 health endpoint tests
- `backend/tests/test_agents_auth.py` - 6 integration tests (401/403/501 + audit)
- `backend/tests/conftest.py` - configure_logging() for consistent structlog in tests
- `backend/tests/test_acl.py` - audit log test uses caplog+capsys (both capture paths)
- `backend/tests/test_config.py` - removed reload() that caused cross-test contamination

**Frontend:**
- `frontend/src/lib/api-client.ts` - serverFetch<T>() with Bearer injection
- `frontend/src/components/auth-header.tsx` - AuthHeader Server Component (user email + sign out)
- `frontend/src/components/sign-out-button.tsx` - SignOutButton Client Component
- `frontend/src/components/auth-error-toasts.tsx` - AuthErrorToasts (Sonner Toaster)
- `frontend/src/app/chat/page.tsx` - use AuthHeader
- `frontend/src/app/layout.tsx` - add AuthErrorToasts at root
- `frontend/src/auth.ts` - include accessToken in server-side session
- `frontend/package.json` - added sonner

## Decisions Made

- **GET /health outside /api prefix:** Load balancers and Docker health checks need the endpoint without requiring credentials or knowing the /api path prefix.
- **SQLite dependency override in tests:** Tests that pass Gates 1 and 2 (employee/executive) reach Gate 3 (check_tool_acl) which requires a DB session. Override get_db with in-memory SQLite so tests run without PostgreSQL.
- **configure_logging() in conftest.py:** structlog's `cache_logger_on_first_use=True` causes test ordering failures if logging is configured mid-session. Calling it once at collection time ensures all 58 tests see the same structlog config.
- **Removed reload() in test_config.py:** `reload(config_module)` inside a `patch.dict` context left the module reloaded with `KEYCLOAK_REALM=blitz` after the patch exited, causing JWT tests to fail with issuer mismatch.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Tests reaching Gate 3 need DB session override**

- **Found during:** Task 1 (running test_agents_auth.py tests for employee/executive -> 501)
- **Issue:** Employee and executive users pass RBAC Gate 2 and reach Gate 3 (check_tool_acl), which calls `session.execute()`. The TestClient raises `ConnectionRefusedError` because no PostgreSQL is running in CI/test environment.
- **Fix:** Added `sqlite_session_override` pytest fixture in `test_agents_auth.py` that creates an in-memory SQLite engine, runs `Base.metadata.create_all`, and overrides `get_db` dependency for tests that need it.
- **Files modified:** `backend/tests/test_agents_auth.py`
- **Verification:** All 6 test_agents_auth tests pass
- **Committed in:** `583c843` (Task 1)

**2. [Rule 1 - Bug] conftest.py configure_logging() call prevents test-order structlog failures**

- **Found during:** Task 1 (running full test suite — test_acl.py::test_audit_log_contains_required_fields failed when test_health.py ran first)
- **Issue:** `test_health.py` imports `main.py` -> triggers `create_app()` -> `configure_logging()`, switching structlog to `stdlib.LoggerFactory()`. The module-level `audit_logger` in `acl.py` was initialized before this config change. After `configure_logging()`, output goes through Python logging, but `capsys` in the ACL test only captures direct stdout.
- **Fix:** Added `from core.logging import configure_logging; configure_logging(...)` to `conftest.py` so structlog config is established consistently before all tests, regardless of import order.
- **Files modified:** `backend/tests/conftest.py`
- **Verification:** 58/58 tests pass in all orderings
- **Committed in:** `583c843` (Task 1)

**3. [Rule 1 - Bug] test_acl.py audit log test needed both caplog AND capsys**

- **Found during:** Task 1 (after configuring structlog in conftest.py, capsys returned empty in test_audit_log_contains_required_fields)
- **Issue:** After `configure_logging()` sets `stdlib.LoggerFactory()`, structlog routes through Python's `logging` module, captured by `caplog.text` not `capsys.readouterr()`. The test was using only `capsys`.
- **Fix:** Updated test to use `with caplog.at_level(logging.INFO)` and check `captured.out + captured.err + caplog.text` so both stdout (default structlog) and Python logging paths are covered.
- **Files modified:** `backend/tests/test_acl.py`
- **Verification:** Test passes in all orderings
- **Committed in:** `583c843` (Task 1)

**4. [Rule 1 - Bug] test_config.py reload() caused cross-test JWT issuer contamination**

- **Found during:** Task 1 (running full suite — test_jwt.py::test_valid_token_returns_user_context and test_jwks_cache_hit failed after test_config.py ran)
- **Issue:** `test_settings_loads_required_fields` called `reload(config_module)` inside `patch.dict("os.environ", env, clear=True)`. After the `with` exited, `os.environ` was restored, but the reloaded module's `settings` retained `KEYCLOAK_REALM=blitz` (from the reload context). JWT tests then generated tokens with `issuer="http://keycloak:8080/realms/blitz"` but validated against settings showing `issuer="https://keycloak.blitz.local/realms/blitz-internal"`.
- **Fix:** Removed `reload(config_module)` and `get_settings.cache_clear()` from the test — just create a `Settings()` instance directly with the patched env vars.
- **Files modified:** `backend/tests/test_config.py`
- **Verification:** All 58 tests pass in all orderings, including after test_config.py runs
- **Committed in:** `583c843` (Task 1)

**5. [Rule 1 - Bug] auth.ts TypeScript TS2352 strict-mode cast error**

- **Found during:** Task 2 (running `pnpm tsc --noEmit`)
- **Issue:** `(session as Record<string, unknown>).accessToken` raises TS2352: neither Session type nor Record<string, unknown> overlap sufficiently for a direct cast.
- **Fix:** Changed to `(session as unknown as Record<string, unknown>).accessToken` (double cast through `unknown`) which TypeScript strict mode accepts.
- **Files modified:** `frontend/src/auth.ts`
- **Verification:** `pnpm tsc --noEmit` exits with code 0, no errors
- **Committed in:** `03c34b9` (Task 2)

---

**Total deviations:** 5 auto-fixed (3 test bugs, 1 blocking test infra, 1 TypeScript type error)
**Impact on plan:** All fixes necessary for correct test isolation and type safety. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviations above.

## Phase 1 Success Criteria — All Met

1. User can log in via Keycloak SSO and receive a valid session in the browser — verified (human approval)
2. Backend rejects requests with missing, expired, or invalid JWT tokens with 401 — verified (test_agents_auth.py: test_chat_no_jwt_returns_401)
3. User with "employee" role can access agent endpoints; unknown role cannot invoke tools (RBAC enforced) — verified (test_rbac.py + test_agents_auth.py)
4. Every tool call attempt is logged with user_id, tool name, allowed/denied, and duration — no credentials in logs — verified (test_acl.py)
5. All Docker Compose services start and pass health checks — verified (human approval during checkpoint)

## Next Phase Readiness

- Phase 1 is complete — all 5 success criteria met, all 58 backend tests passing
- Phase 2 can implement actual agent logic in the `/api/agents/chat` stub (replace 501 with real LangGraph invocation)
- `serverFetch()` in frontend is ready for Phase 2 chat UI components
- All 58 backend tests provide regression coverage for Phase 2 development
- `get_llm("blitz/master")` pattern ready to use; LiteLLM proxy service in docker-compose

---
*Phase: 01-identity-and-infrastructure-skeleton*
*Completed: 2026-02-24*
