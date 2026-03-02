---
phase: 06-extensibility-registries
plan: 03
subsystem: api
tags: [fastapi, crud, permissions, rbac, admin, multi-version, staged-permissions]

# Dependency graph
requires:
  - phase: 06-extensibility-registries
    plan: 01
    provides: "AgentDefinition, ToolDefinition, SkillDefinition ORM models + Pydantic schemas"
  - phase: 06-extensibility-registries
    plan: 02
    provides: "Async DB-backed has_permission, invalidate_permission_cache, check_artifact_permission"
provides:
  - "Admin CRUD API for agents at /api/admin/agents with multi-version + bulk status"
  - "Admin CRUD API for tools at /api/admin/tools with multi-version + bulk status"
  - "Admin CRUD API for skills at /api/admin/skills with validate, pending filter, multi-version"
  - "Admin permission management API at /api/admin/permissions with staged model, per-user overrides"
  - "42 new tests covering all admin APIs"
affects: [06-04-PLAN, 06-05-PLAN, 06-06-PLAN, 06-07-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_require_registry_manager dependency pattern for registry:manage permission check"
    - "Staged permission writes (status='pending') with explicit POST /apply activation"
    - "Graceful removal: status patch returns active_workflow_runs count"
    - "Multi-version activation: PATCH /{id}/activate deactivates all other versions of same name"
    - "Bulk status: PATCH /bulk-status updates multiple artifacts at once"

key-files:
  created:
    - backend/api/routes/admin_agents.py
    - backend/api/routes/admin_tools.py
    - backend/api/routes/admin_skills.py
    - backend/api/routes/admin_permissions.py
    - backend/tests/api/test_admin_agents.py
    - backend/tests/api/test_admin_tools.py
    - backend/tests/api/test_admin_skills.py
    - backend/tests/api/test_admin_permissions.py
  modified:
    - backend/main.py

key-decisions:
  - "Test fixture for permissions must seed role_permissions with it-admin's registry:manage -- cache invalidation queries DB, empty DB denies access"
  - "RBAC cache reset in test teardown prevents cross-test contamination from invalidate_permission_cache calls"
  - "Skill validate endpoint is a stub returning empty errors -- full SkillValidator deferred to Plan 06-05"
  - "Skill /pending endpoint declared BEFORE /{skill_id} to avoid FastAPI UUID matching collision"

patterns-established:
  - "Admin CRUD route pattern: _require_registry_manager + list/create/get/update/status/activate/bulk-status"
  - "Staged permission write pattern: PUT creates pending, POST /apply activates, cache invalidated only on apply"
  - "Per-user override pattern: same PUT/apply flow as role-level artifact permissions"

requirements-completed: [EXTD-02, EXTD-04, EXTD-05]

# Metrics
duration: 7min
completed: 2026-02-28
---

# Phase 6 Plan 03: Admin CRUD APIs Summary

**4 admin CRUD APIs (agents, tools, skills, permissions) with registry:manage gate, multi-version activation, bulk status, staged permission model (pending->apply->active), per-user overrides, and graceful removal with active workflow count**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-28T11:40:25Z
- **Completed:** 2026-02-28T11:47:38Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- 4 admin route files with full CRUD endpoints, multi-version activation, bulk status update, and graceful removal count
- Staged permission model: artifact and user permissions written as pending, activated via POST /apply with cache invalidation
- Role permission management with replace semantics and immediate cache invalidation
- 42 new tests covering auth (401/403), CRUD flows, multi-version, bulk status, staged model, per-user overrides, and cache timing
- Full test suite: 390 passed, no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Admin CRUD APIs for Agents and Tools** - `d13a053` (feat)
2. **Task 2: Admin CRUD APIs for Skills and Permissions** - `9c167b3` (feat)

## Files Created/Modified
- `backend/api/routes/admin_agents.py` - Agent CRUD with multi-version activation, bulk status, graceful removal
- `backend/api/routes/admin_tools.py` - Tool CRUD with same pattern as agents
- `backend/api/routes/admin_skills.py` - Skill CRUD with pending filter, validate stub, multi-version
- `backend/api/routes/admin_permissions.py` - Role permissions, artifact permissions (staged), per-user overrides, apply endpoint
- `backend/main.py` - Registered all 4 admin routers
- `backend/tests/api/test_admin_agents.py` - 9 tests: auth, CRUD, multi-version, bulk, graceful removal
- `backend/tests/api/test_admin_tools.py` - 9 tests: auth, CRUD, multi-version, bulk, graceful removal
- `backend/tests/api/test_admin_skills.py` - 11 tests: auth, CRUD, pending, multi-version, validate, bulk
- `backend/tests/api/test_admin_permissions.py` - 13 tests: auth, role CRUD, artifact staged model, per-user overrides, cache timing

## Decisions Made
- Test fixture for permissions must seed role_permissions table with it-admin's registry:manage permission -- after cache invalidation, DB-backed RBAC queries the role_permissions table, and an empty table causes 403 for all subsequent requests in the same test
- RBAC cache must be reset in test teardown to prevent cross-test contamination from invalidate_permission_cache() calls
- Skill validate endpoint is a stub returning empty errors list -- full SkillValidator with tool ref checking deferred to Plan 06-05
- Skill /pending and /bulk-status endpoints declared BEFORE /{skill_id} to avoid FastAPI matching string paths as UUID params

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Permission test fixture needs role_permissions seed data**
- **Found during:** Task 2 (Permission API tests)
- **Issue:** After PUT /roles sets permissions and invalidates cache, subsequent requests get 403 because DB has no it-admin entries and cache refresh from DB returns only the test-role entries
- **Fix:** Seeded SQLite fixture with it-admin role permissions (tool:admin, registry:manage, chat, sandbox:execute) and added cache reset in teardown
- **Files modified:** backend/tests/api/test_admin_permissions.py
- **Verification:** All 13 permission tests pass, including tests that trigger cache invalidation mid-flow
- **Committed in:** 9c167b3 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential fix for test correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed test fixture issue.

## User Setup Required
None - no external service configuration required. All admin APIs use existing JWT auth and DB.

## Next Phase Readiness
- All 4 admin CRUD APIs registered and functional -- ready for frontend admin UI in Plan 06-06
- Permission management API ready -- staged model tested end-to-end (pending -> apply -> active -> cache invalidated)
- Skill validate stub in place -- ready for SkillValidator integration in Plan 06-05
- Full test suite green (390 tests) -- safe foundation for subsequent plans

## Self-Check: PASSED

- All 9 files verified present on disk
- Both task commits (d13a053, 9c167b3) verified in git log
- 390 tests passing, 0 failures

---
*Phase: 06-extensibility-registries*
*Completed: 2026-02-28*
