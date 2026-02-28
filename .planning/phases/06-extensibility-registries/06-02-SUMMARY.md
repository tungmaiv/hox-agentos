---
phase: 06-extensibility-registries
plan: 02
subsystem: security
tags: [rbac, permissions, async, sqlalchemy, caching, artifact-permissions]

# Dependency graph
requires:
  - phase: 06-extensibility-registries
    plan: 01
    provides: "RolePermission, ArtifactPermission, UserArtifactPermission ORM models"
provides:
  - "Async DB-backed has_permission() with 60s TTL cache and session=None fallback"
  - "check_artifact_permission() with default-allow, staged status, per-user overrides"
  - "invalidate_permission_cache() for immediate cache reset on admin writes"
  - "All callers updated to async+session pattern"
affects: [06-03-PLAN, 06-04-PLAN, 06-05-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Async has_permission with session=None fallback for backward compat"
    - "In-process TTL cache for role_permissions DB queries (60s, immediate invalidation)"
    - "Artifact permission check: user override > role-level > default-allow"
    - "Staged permission model: only status='active' rows are evaluated"

key-files:
  created:
    - backend/tests/test_rbac_db.py
  modified:
    - backend/security/rbac.py
    - backend/tests/test_rbac.py
    - backend/api/routes/mcp_servers.py
    - backend/api/routes/system_config.py
    - backend/api/routes/agents.py
    - backend/gateway/runtime.py
    - backend/mcp/registry.py
    - backend/tests/mcp/test_mcp_registry.py

key-decisions:
  - "has_permission session=None fallback preserves all existing sync test behavior without DB"
  - "runtime.py _check_gates uses shared session for Gate 2 (RBAC) + Gate 3 (ACL) -- avoids opening two sessions"
  - "_require_admin dependency in mcp_servers.py and system_config.py takes session via Depends(get_db) for DB-backed RBAC"
  - "MCP registry test mocks updated to AsyncMock for has_permission (async function)"

patterns-established:
  - "async has_permission(user, perm, session=None) -- all callers use await"
  - "check_artifact_permission user override > role-level > default-allow precedence"

requirements-completed: [EXTD-04]

# Metrics
duration: 4min
completed: 2026-02-28
---

# Phase 6 Plan 02: DB-Backed RBAC Migration Summary

**Async DB-backed has_permission() with 60s cache TTL, check_artifact_permission() with staged model and per-user overrides, all 7 callers migrated to async+session pattern**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-28T11:32:28Z
- **Completed:** 2026-02-28T11:37:08Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Converted has_permission() from sync to async with DB-backed permission queries and 60s in-process cache
- Added check_artifact_permission() implementing Gate 2.5 with user override precedence, staged status filtering, and default-allow semantics
- Updated all 7 production callers (agents.py, mcp_servers.py, system_config.py, runtime.py, registry.py) to async+session pattern
- Updated 3 test files (test_rbac.py, test_mcp_registry.py, test_rbac_db.py) -- 348 total tests, all green

## Task Commits

Each task was committed atomically:

1. **Task 1: DB-Backed RBAC with Cache and Artifact Permission Check** - `82d935a` (feat)
2. **Task 2: Update All has_permission Callers** - `f05b0ea` (feat)

## Files Created/Modified
- `backend/security/rbac.py` - Async has_permission with DB cache, check_artifact_permission, invalidate_permission_cache
- `backend/tests/test_rbac_db.py` - 11 new tests: DB-backed RBAC, artifact perms, staged model, user overrides, cache
- `backend/tests/test_rbac.py` - 20 sync tests converted to async+await (session=None fallback path)
- `backend/api/routes/mcp_servers.py` - _require_admin passes session to has_permission
- `backend/api/routes/system_config.py` - _require_admin passes session to has_permission
- `backend/api/routes/agents.py` - Inline chat gate passes session to has_permission
- `backend/gateway/runtime.py` - _check_gates uses shared session for Gate 2 + Gate 3
- `backend/mcp/registry.py` - call_mcp_tool passes db_session to has_permission
- `backend/tests/mcp/test_mcp_registry.py` - has_permission mocks use AsyncMock

## Decisions Made
- has_permission session=None fallback preserves all existing sync test behavior without DB -- zero breaking changes for tests that don't provide a session
- runtime.py _check_gates uses shared session for Gate 2 (RBAC) + Gate 3 (ACL) -- avoids opening two separate sessions per request
- _require_admin dependency in mcp_servers.py and system_config.py takes session via Depends(get_db) for DB-backed RBAC
- MCP registry test mocks updated to AsyncMock for has_permission since it is now an async function

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. The role_permissions table was already seeded by migration 014 (Plan 01).

## Next Phase Readiness
- DB-backed has_permission() ready for admin CRUD API in Plan 06-03
- check_artifact_permission() ready for Gate 2.5 integration in agent/tool/skill routes
- invalidate_permission_cache() available for admin write endpoints to trigger immediate refresh
- Full test suite green (348 tests) -- safe foundation for subsequent plans

## Self-Check: PASSED

- All 9 files verified present on disk
- Both task commits (82d935a, f05b0ea) verified in git log
- 348 tests passing, 0 failures

---
*Phase: 06-extensibility-registries*
*Completed: 2026-02-28*
