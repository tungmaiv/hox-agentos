---
phase: 25-skill-builder-tool-resolver
plan: 06
subsystem: api
tags: [skills, admin, registry, status, draft]

# Dependency graph
requires:
  - phase: 25-skill-builder-tool-resolver
    provides: activation gate + tool_gaps enforcement pipeline
provides:
  - create_skill endpoint always starts skills as draft (not active)
  - test_create_skill_defaults_to_draft asserting POST /api/admin/skills returns status=draft
affects: [skill-promotion-pipeline, uat-tests, admin-skills]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Skill lifecycle always starts as draft — admin must explicitly activate via /activate"

key-files:
  created: []
  modified:
    - backend/api/routes/admin_skills.py
    - backend/tests/api/test_admin_skills.py
    - backend/tests/test_phase6_integration.py

key-decisions:
  - "create_skill sets status=draft — activation is always an explicit admin action via /activate endpoint"
  - "Integration tests updated to activate skills before employee list/run operations"

patterns-established:
  - "Skill creation pattern: POST /api/admin/skills → draft; PATCH /activate → active"

requirements-completed:
  - "uat-gap: create_skill_default_status"

# Metrics
duration: 8min
completed: 2026-03-13
---

# Phase 25 Plan 06: Create Skill Default Status Fix Summary

**`create_skill` endpoint now always starts new skills as `draft`, closing the UAT gap that bypassed the entire draft→pending_activation→active promotion pipeline.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-13T18:28:00Z
- **Completed:** 2026-03-13T18:36:23Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments
- Changed `status="active"` to `status="draft"` in `create_skill()` route
- Added `test_create_skill_defaults_to_draft` test asserting POST returns `status=draft` and `is_active=False`
- Fixed `test_crud_flow`: `is_active` assertion corrected from `True` to `False` after create
- Fixed `test_bulk_status_update`: untouched skill now asserts `status=draft` instead of `status=active`
- Fixed `test_activate_skill`: removed intermediate disable step — draft→active now goes directly via /activate
- Fixed 3 integration tests in `test_phase6_integration.py` to add explicit activate step before employee operations

## Task Commits

1. **Task 1: Fix create_skill default status + repair impacted tests** - `59c2b83` (fix)

**Plan metadata:** (to be added in docs commit)

## Files Created/Modified
- `backend/api/routes/admin_skills.py` - Changed status="active" to status="draft" in RegistryEntryCreate call
- `backend/tests/api/test_admin_skills.py` - Added test_create_skill_defaults_to_draft; fixed test_crud_flow, test_bulk_status_update, test_activate_skill
- `backend/tests/test_phase6_integration.py` - Fixed test_skill_lifecycle, test_instructional_skill_execution, test_uat_12_admin_create_skill

## Decisions Made
- `create_skill` default is `draft` — activation is always an explicit admin step via PATCH /activate
- Integration tests now follow the correct lifecycle: create (draft) → activate → employee access

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed phase6 integration tests asserting status=active on freshly created skills**
- **Found during:** Task 1 (running full test suite after the fix)
- **Issue:** `test_skill_lifecycle`, `test_instructional_skill_execution`, `test_uat_12_admin_create_skill` in `test_phase6_integration.py` all asserted `status == 'active'` immediately after POST, or tried to let employees list/run the skill without activating it first
- **Fix:** Updated all three tests — corrected create-response assertions to expect `draft`, added explicit `/activate` call before employee-facing operations
- **Files modified:** `backend/tests/test_phase6_integration.py`
- **Verification:** Full suite 934 passed, 7 skipped, 0 failed
- **Committed in:** `59c2b83` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** The integration test fixes were directly caused by the backend change. No scope creep — all changes are within the skill create/activate lifecycle.

## Issues Encountered
None beyond the expected integration test cascade from the backend change.

## Next Phase Readiness
- UAT gap `create_skill_default_status` is closed
- Skill promotion pipeline (draft → pending_activation → active) is now fully intact end-to-end
- Full test suite green (934 passed)

---
*Phase: 25-skill-builder-tool-resolver*
*Completed: 2026-03-13*
