---
phase: 25-skill-builder-tool-resolver
plan: "04"
subsystem: api
tags: [registry, skills, builder, security-scanner, fastapi]

requires:
  - phase: 24-unified-registry-mcp-platform-enhancement-skill-import-adapters
    provides: UnifiedRegistryService.create_entry/update_entry, SkillHandler.on_create with scan
  - phase: 25-skill-builder-tool-resolver
    provides: SkillHandler draft enforcement for tool_gaps (25-02), bell icon and pending_activation (25-03)

provides:
  - builder_save endpoint writes RegistryEntry rows via UnifiedRegistryService.create_entry()
  - Re-scan path uses get_entry() + update_entry() + manual scan_skill_with_fallback call
  - SkillHandler.on_create() owns security scan and draft enforcement for tool_gaps
  - test_security_gate.py updated to test new RegistryEntry-based contract

affects: [skill-builder-frontend, admin-skills-ui, uat-gap-tests]

tech-stack:
  added: []
  patterns:
    - builder_save delegates scan to SkillHandler via UnifiedRegistryService.create_entry
    - security_report stored in entry.config JSONB, returned in BuilderSaveResponse
    - patch target for scan tests is security.scan_client.scan_skill_with_fallback (lazy import in handler)

key-files:
  created: []
  modified:
    - backend/api/routes/admin_skills.py
    - backend/tests/skills/test_security_gate.py

key-decisions:
  - "builder_save now writes RegistryEntry (type=skill) not SkillDefinition — fixes 500 error from dropped skill_definitions table"
  - "SkillHandler.on_create() owns security scan — removed duplicate SecurityScanner block from builder_save"
  - "status starts as draft — SkillHandler.on_create() only forces draft for tool_gaps, no auto-promotion to active"
  - "test_security_gate.py patching updated from api.routes.admin_skills.SecurityScanner to security.scan_client.scan_skill_with_fallback (lazy import site)"
  - "Re-scan path (skill_id provided) calls scan_skill_with_fallback manually since update_entry does not invoke on_create"

requirements-completed: [TRES-07]

duration: 4min
completed: 2026-03-13
---

# Phase 25 Plan 04: Migrate builder_save to UnifiedRegistryService Summary

**builder_save endpoint migrated from dropped skill_definitions table to registry_entries via UnifiedRegistryService, fixing the 500 UAT blocker (test 7)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-13T03:49:58Z
- **Completed:** 2026-03-13T03:54:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Fixed 500 error on POST /api/admin/skills/builder-save — endpoint now writes to registry_entries via UnifiedRegistryService.create_entry()
- Removed duplicate SecurityScanner block from builder_save — SkillHandler.on_create() owns scan + draft enforcement
- Updated test_security_gate.py: 3 tests replaced with 6 tests testing new RegistryEntry contract
- Full backend suite: 929 passed, 7 skipped — no regressions

## Task Commits

1. **Task 1: Migrate builder_save to UnifiedRegistryService** - `4d9a12f` (feat)
2. **Task 2: Full backend test suite verification** - no new commit (verification only, no file changes)

**Plan metadata:** pending (created below)

## Files Created/Modified

- `backend/api/routes/admin_skills.py` — builder_save replaced with UnifiedRegistryService-based implementation; removed SecurityScanner block; added _registry_service singleton; added RegistryEntryCreate/Update imports
- `backend/tests/skills/test_security_gate.py` — replaced 3 old SecurityScanner-patching tests with 6 tests matching new RegistryEntry contract

## Decisions Made

- builder_save now writes RegistryEntry (type=skill) not SkillDefinition — fixes 500 error from dropped skill_definitions table (Phase 24 dropped skill_definitions but didn't update builder_save)
- SkillHandler.on_create() owns the security scan — removing the SecurityScanner block from builder_save prevents double scanning and uses the unified registry pattern
- status starts as "draft" for all builder-saved skills — SkillHandler.on_create() only forces draft when tool_gaps are present, does NOT auto-promote to active
- Re-scan path (skill_id provided) must call scan_skill_with_fallback manually since update_entry() does not invoke on_create
- test_security_gate.py patch target changed to security.scan_client.scan_skill_with_fallback — skill_handler uses a lazy import inside on_create, so patching at the definition site (security.scan_client) is the correct approach

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_security_gate.py to match new contract**
- **Found during:** Task 1 (after implementing migration)
- **Issue:** test_security_gate.py had 3 tests patching `api.routes.admin_skills.SecurityScanner` and asserting `status == "active"` / `status == "pending_review"` — both the patch target and the status expectations were invalidated by the migration
- **Fix:** Replaced 3 failing tests with 6 tests that: (1) patch `security.scan_client.scan_skill_with_fallback`, (2) assert `status == "draft"`, (3) test tool_gaps enforcement, re-scan path, invalid UUID, and unknown UUID error cases
- **Files modified:** backend/tests/skills/test_security_gate.py
- **Verification:** All 6 new tests pass; full suite 929 passed
- **Committed in:** 4d9a12f (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug: test expectations invalidated by contract change)
**Impact on plan:** Auto-fix necessary for test suite correctness. Tests now accurately describe the new RegistryEntry-based behavior. No scope creep.

## Issues Encountered

None — migration was straightforward. The SkillHandler.on_create() already existed and was correctly implemented for this purpose.

## Next Phase Readiness

- POST /api/admin/skills/builder-save now correctly writes to registry_entries (type=skill)
- UAT test 7 (builder-save 500 error) is unblocked
- 4 follow-up UAT tests that depended on test 7 can now be re-evaluated
- Full backend test suite clean at 929 passed

---
*Phase: 25-skill-builder-tool-resolver*
*Completed: 2026-03-13*
