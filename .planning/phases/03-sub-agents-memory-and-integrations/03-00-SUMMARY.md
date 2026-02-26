---
phase: 03-sub-agents-memory-and-integrations
plan: "00"
subsystem: settings, database, admin-api, ui
tags: [alembic, sqlalchemy, postgresql, jsonb, fastapi, nextjs, react, zod, rbac]

# Dependency graph
requires:
  - phase: 02-agents-tools-and-memory
    provides: "async_session/get_db, get_current_user, has_permission, RBAC role-permission map"
  - phase: 02.1-tech-debt-cleanup
    provides: "migration 006 head, NEXT_PUBLIC_API_URL standardization"

provides:
  - "system_config table: admin key/JSONB value store, seeded with 5 default rows"
  - "mcp_servers table: MCP server registry with AES-256 encrypted auth_token column"
  - "GET /api/admin/config and PUT /api/admin/config/{key} — admin-only FastAPI routes"
  - "Settings → Agents page with Email/Calendar/Project toggle switches"
  - "Settings → Integrations stub page (live CRUD wired in 03-03)"
  - "Next.js proxy routes for admin config API with server-side Bearer injection"

affects:
  - "03-01: agent routing reads agent.*.enabled from system_config"
  - "03-02: memory.episode_turn_threshold seeded in system_config"
  - "03-03: mcp_servers table used for CRUD admin UI"
  - "03-04: agent feature flags gated on system_config values"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SystemConfig.value uses JSON().with_variant(JSONB(), 'postgresql') for cross-dialect SQLite test compatibility"
    - "Admin Gate 2 via _require_admin() dependency: has_permission(user, 'tool:admin')"
    - "Admin proxy routes use auth() from @/auth with (session as unknown as Record) cast for accessToken"

key-files:
  created:
    - backend/alembic/versions/007_phase3_settings.py
    - backend/core/models/system_config.py
    - backend/core/models/mcp_server.py
    - backend/api/routes/system_config.py
    - backend/tests/test_system_config.py
    - frontend/src/app/settings/agents/page.tsx
    - frontend/src/app/settings/integrations/page.tsx
    - frontend/src/app/api/admin/config/route.ts
    - frontend/src/app/api/admin/config/[key]/route.ts
  modified:
    - backend/core/models/__init__.py
    - backend/main.py
    - frontend/src/app/settings/page.tsx

key-decisions:
  - "SystemConfig.value uses JSON().with_variant(JSONB(), 'postgresql') — not bare JSONB — so SQLite test fixtures work without mocking"
  - "Admin permission check uses has_permission(user, 'tool:admin') not 'admin' — plan used incorrect string, fixed to match RBAC table (it-admin role grants tool:admin)"
  - "system_config routes use get_db (not get_async_session from plan) — codebase only exports get_db"
  - "5 tests written (plan specified 4): added JWT missing test for completeness"

patterns-established:
  - "Pattern: Admin routes protected by _require_admin() dependency calling has_permission(user, 'tool:admin')"
  - "Pattern: Next.js admin proxy routes use auth() + (session as unknown as Record<string, unknown>).accessToken cast"
  - "Pattern: SQLite-compatible ORM models use JSON().with_variant(JSONB(), 'postgresql') for JSONB columns"

requirements-completed:
  - INTG-01
  - INTG-02

# Metrics
duration: 9min
completed: 2026-02-26
---

# Phase 3 Plan 00: Settings Infrastructure Summary

**Admin config API (GET/PUT /api/admin/config) + system_config/mcp_servers tables + Settings Agents toggle UI with Zod-validated toggle state persistence**

## Performance

- **Duration:** 9 min 25s
- **Started:** 2026-02-26T11:00:41Z
- **Completed:** 2026-02-26T11:10:06Z
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- Migration 007 creates system_config and mcp_servers tables; seeds 5 default rows including agent flags and memory.episode_turn_threshold
- Admin-only GET/PUT /api/admin/config FastAPI routes with Gate 2 RBAC (tool:admin permission), 5 passing tests
- /settings/agents Client Component with Email/Calendar/Project toggle switches; Zod-validated API responses; state persists across reload via PUT calls
- /settings/integrations stub Server Component ready for 03-03 live CRUD
- Next.js proxy routes with server-side Bearer token injection; pnpm build zero TypeScript errors

## Task Commits

Each task was committed atomically:

1. **Task 1: DB migration 007 + ORM models** - `26670dd` (feat)
2. **Task 2: Backend admin config API routes + tests** - `3ec451d` (feat)
3. **Task 3: Frontend Settings pages** - `9bd4f18` (feat)

## Files Created/Modified

- `backend/alembic/versions/007_phase3_settings.py` - Migration 007: system_config + mcp_servers tables + 5 seed rows
- `backend/core/models/system_config.py` - SystemConfig ORM model with JSON/JSONB cross-dialect value column
- `backend/core/models/mcp_server.py` - McpServer ORM model with AES-256 encrypted auth_token
- `backend/core/models/__init__.py` - Added SystemConfig + McpServer imports for Alembic autogenerate
- `backend/api/routes/system_config.py` - GET/PUT /api/admin/config with _require_admin Gate 2 dependency
- `backend/main.py` - Registered system_config.router
- `backend/tests/test_system_config.py` - 5 tests covering JWT, 403, seeded values, PUT, 422
- `frontend/src/app/settings/page.tsx` - Added Admin nav section with Agents + Integrations links
- `frontend/src/app/settings/agents/page.tsx` - Client Component with 3 agent toggle switches + Zod validation
- `frontend/src/app/settings/integrations/page.tsx` - Server Component stub for 03-03
- `frontend/src/app/api/admin/config/route.ts` - GET proxy with server-side Bearer token
- `frontend/src/app/api/admin/config/[key]/route.ts` - PUT proxy with server-side Bearer token

## Decisions Made

- **SystemConfig.value type:** Used `JSON().with_variant(JSONB(), "postgresql")` instead of bare `JSONB` from plan — JSONB breaks SQLite test fixtures; this preserves PostgreSQL JSONB for production while allowing aiosqlite in tests
- **Admin permission string:** Used `"tool:admin"` not `"admin"` — plan used incorrect string; the RBAC table grants `"tool:admin"` to `"it-admin"` role only
- **DB dependency:** Used `get_db` (not `get_async_session` from plan) — codebase does not export `get_async_session`; `get_db` is the established pattern in all other routes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed incorrect admin permission string**
- **Found during:** Task 2 (admin config API routes)
- **Issue:** Plan used `has_permission(user, "admin")` but RBAC table grants `"tool:admin"` to `"it-admin"` role — using `"admin"` would always return False (no role grants it)
- **Fix:** Used `has_permission(user, "tool:admin")` to match actual RBAC permission map in `security/rbac.py`
- **Files modified:** `backend/api/routes/system_config.py`
- **Verification:** test_get_config_requires_admin_role passes with employee getting 403; admin gets 200
- **Committed in:** `3ec451d` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed JSONB incompatibility with SQLite test engine**
- **Found during:** Task 2 (test execution)
- **Issue:** `postgresql.JSONB` type not supported by SQLite's DDL compiler — `Base.metadata.create_all` raised `CompileError: can't render element of type JSONB`
- **Fix:** Changed `SystemConfig.value` to `JSON().with_variant(JSONB(), "postgresql")` — uses JSONB in PostgreSQL (production), falls back to JSON in SQLite (tests)
- **Files modified:** `backend/core/models/system_config.py`
- **Verification:** All 5 tests pass; migration 007 still creates JSONB column in PostgreSQL
- **Committed in:** `3ec451d` (Task 2 commit)

**3. [Rule 3 - Blocking] Used existing `get_db` instead of non-existent `get_async_session`**
- **Found during:** Task 2 (reviewing existing route patterns)
- **Issue:** Plan referenced `from core.db import get_async_session` but `core/db.py` only exports `get_db`; import would fail at startup
- **Fix:** Used `Depends(get_db)` matching all other routes (credentials, user_instructions, conversations)
- **Files modified:** `backend/api/routes/system_config.py`
- **Verification:** Routes load; tests pass; backend starts without ImportError
- **Committed in:** `3ec451d` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (2 Rule 1 bugs, 1 Rule 3 blocking)
**Impact on plan:** All auto-fixes were necessary for correctness and test execution. No scope creep.

## Issues Encountered

None — all deviations were caught and fixed inline during task execution.

## User Setup Required

None — migration 007 applies via `just migrate`. All seed data is inserted automatically by the migration.

## Next Phase Readiness

- system_config and mcp_servers tables ready for 03-01 through 03-04 to use
- agent.*.enabled flags seeded — 03-04 can read them immediately for routing decisions
- memory.episode_turn_threshold seeded — 03-02 can read it for episode summarization trigger
- mcp_servers table ready — 03-03 can build CRUD admin UI on top
- /settings/integrations stub in place — navigation structure established

---
*Phase: 03-sub-agents-memory-and-integrations*
*Completed: 2026-02-26*
