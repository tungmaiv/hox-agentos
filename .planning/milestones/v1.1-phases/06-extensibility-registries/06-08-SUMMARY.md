---
phase: 06-extensibility-registries
plan: 08
subsystem: database, ui
tags: [alembic, migration, skills, slash-commands, typescript, admin-dashboard]

requires:
  - phase: 06-extensibility-registries
    provides: skill_definitions table (migration 014), skills admin page (plan 06-07)

provides:
  - Alembic migration 015 seeding 3 built-in skills (/summarize, /debug, /export) with status='active' and security_score=90
  - Corrected Pending Review filter predicate in skills admin page (status === 'pending_review')
  - ArtifactStatus type extended with 'pending_review' value and orange badge styling

affects:
  - Phase 7 (any admin UI work referencing ArtifactStatus type)
  - Chat slash command menu (reads skill_definitions via GET /api/skills)

tech-stack:
  added: []
  patterns:
    - "Alembic seed migrations with ON CONFLICT (name, version) DO NOTHING for idempotency"
    - "ArtifactStatus as exhaustive union type — all status values must appear in StatusBadge color maps"

key-files:
  created:
    - backend/alembic/versions/015_seed_builtin_skills.py
  modified:
    - frontend/src/app/admin/skills/page.tsx
    - frontend/src/lib/admin-types.ts
    - frontend/src/components/admin/artifact-card-grid.tsx
    - frontend/src/components/admin/artifact-table.tsx

key-decisions:
  - "06-08: ArtifactStatus union extended with 'pending_review' — backend status column is VARCHAR(20) with no DB enum; frontend type must mirror all real values"
  - "06-08: StatusBadge color for pending_review is orange (bg-orange-100 text-orange-800) — visually distinct from yellow (deprecated) and gray (disabled)"

requirements-completed:
  - EXTD-03
  - EXTD-05

duration: 8min
completed: 2026-03-01
---

# Phase 06 Plan 08: Skill Seeds and Pending Review Filter Summary

**Alembic migration 015 seeding /summarize, /debug, /export built-in skills plus corrected Pending Review filter using `status === 'pending_review'` predicate**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-01T17:00:00Z
- **Completed:** 2026-03-01T17:07:24Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created migration 015 inserting summarize, debug, export skills into skill_definitions with slash_command, source_type='builtin', status='active', security_score=90
- Applied migration via docker exec psql (backend container not running; postgres container healthy)
- Fixed skills admin Pending Review filter from `status === 'active' && securityScore < 70` to `status === 'pending_review'`
- Extended ArtifactStatus type with 'pending_review' and updated StatusBadge color maps in both table and card components

## Task Commits

Each task was committed atomically:

1. **Task 1: Seed 3 built-in skills via Alembic migration 015** - `ac42261` (feat)
2. **Task 2: Fix Pending Review filter predicate in skills admin page** - `cb353b9` (fix)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `backend/alembic/versions/015_seed_builtin_skills.py` - Migration seeding /summarize, /debug, /export skills with ON CONFLICT DO NOTHING
- `frontend/src/app/admin/skills/page.tsx` - Filter now uses `s.status === "pending_review"`
- `frontend/src/lib/admin-types.ts` - ArtifactStatus extended with `"pending_review"` union member
- `frontend/src/components/admin/artifact-card-grid.tsx` - StatusBadge color map includes pending_review (orange)
- `frontend/src/components/admin/artifact-table.tsx` - StatusBadge color map includes pending_review (orange)

## Decisions Made
- ArtifactStatus union extended with 'pending_review' — backend status column is VARCHAR(20) with no DB enum; frontend type must mirror all real status values to pass TypeScript strict mode
- StatusBadge color for pending_review is orange (bg-orange-100 text-orange-800) — visually distinct from yellow (deprecated) and gray (disabled)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ArtifactStatus type missing 'pending_review' value**
- **Found during:** Task 2 (Fix Pending Review filter predicate)
- **Issue:** `ArtifactStatus = "active" | "disabled" | "deprecated"` caused TS2367 error when comparing `s.status === "pending_review"` — no overlap between type and literal
- **Fix:** Added `"pending_review"` to ArtifactStatus union in admin-types.ts; added `pending_review` entry to StatusBadge color maps in artifact-card-grid.tsx and artifact-table.tsx
- **Files modified:** frontend/src/lib/admin-types.ts, frontend/src/components/admin/artifact-card-grid.tsx, frontend/src/components/admin/artifact-table.tsx
- **Verification:** TypeScript tsc --noEmit passes with 0 errors; 536 backend tests pass
- **Committed in:** cb353b9 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - type bug)
**Impact on plan:** Necessary cascade fix — adding 'pending_review' to the type required updating two StatusBadge components that use `Record<ArtifactStatus, string>`. No scope creep.

## Issues Encountered
- backend container not running — migration applied via docker exec psql directly on postgres container and alembic_version updated manually. Migration file is the canonical source of truth.

## Next Phase Readiness
- skill_definitions table now has 3 active skills with slash commands; GET /api/skills returns all 3
- Chat slash command menu will show /summarize, /debug, /export when backend restarts
- Skills admin Pending Review filter correctly shows only pending_review status skills
- Ready for Phase 7 (Hardening and Sandboxing)

---
*Phase: 06-extensibility-registries*
*Completed: 2026-03-01*
