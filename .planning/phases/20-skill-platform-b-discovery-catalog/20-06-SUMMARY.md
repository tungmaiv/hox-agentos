---
phase: 20-skill-platform-b-discovery-catalog
plan: "06"
subsystem: ui
tags: [react, typescript, admin, skills, sort, artifact-table]

requires:
  - phase: 20-skill-platform-b-discovery-catalog
    provides: admin /skills page with filter bars and ArtifactTable (plan 03)

provides:
  - disableInternalSort prop on ArtifactTable — parent-managed order preserved in table view
  - usageCount: number field on SkillDefinition TypeScript type
  - Most Used sort comparator in admin/skills page correctly sorts by usageCount DESC

affects:
  - admin/skills page users who use the sort dropdown
  - any future page that uses ArtifactTable with parent-managed sort order

tech-stack:
  added: []
  patterns:
    - "disableInternalSort prop pattern: parent passes sorted items + disableInternalSort=true to ArtifactTable to bypass internal sort state"

key-files:
  created: []
  modified:
    - frontend/src/components/admin/artifact-table.tsx
    - frontend/src/lib/admin-types.ts
    - frontend/src/app/(authenticated)/admin/skills/page.tsx

key-decisions:
  - "disableInternalSort prop bypasses internal sort entirely — column-header sort buttons still work if user clicks them (overrides parent order, acceptable UX)"
  - "usageCount: number (not optional) — backend always returns this field; nullish coalescing handles skills predating the column"

patterns-established:
  - "Parent-managed sort + disableInternalSort: when parent provides pre-sorted displayItems, pass disableInternalSort={true} so ArtifactTable skips its internal alphabetical sort"

requirements-completed:
  - SKCAT-01

duration: 2min
completed: 2026-03-08
---

# Phase 20 Plan 06: Admin Skills Sort Fix Summary

**ArtifactTable disableInternalSort prop + SkillDefinition.usageCount field fixes the Newest/Oldest/Most Used sort dropdown so it actually reorders admin /skills table rows**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-08T04:21:53Z
- **Completed:** 2026-03-08T04:23:13Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `disableInternalSort?: boolean` prop to `ArtifactTable` — when true, renders filtered items in parent-provided order instead of always sorting alphabetically by name
- Added `usageCount: number` to `SkillDefinition` TypeScript interface — maps from backend `usage_count` via existing `mapSnakeToCamel` in admin-types.ts
- Fixed `most_used` sort branch in admin/skills/page.tsx from no-op `return 0` to `(b.usageCount ?? 0) - (a.usageCount ?? 0)` (descending by usage)
- Passed `disableInternalSort={true}` to `ArtifactTable` on admin/skills page so the parent `displayItems` sort order is preserved in table view

## Task Commits

1. **Task 1: Add disableInternalSort prop to ArtifactTable + usageCount to SkillDefinition** - `a63d645` (feat)
2. **Task 2: Wire disableInternalSort and fix most_used sort in admin/skills page** - `09b000b` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `frontend/src/components/admin/artifact-table.tsx` - Added `disableInternalSort` prop to interface + function signature; renamed `sorted` → `displayItems` with conditional sort logic
- `frontend/src/lib/admin-types.ts` - Added `usageCount: number` to `SkillDefinition` interface between `reviewedAt` and `createdBy`
- `frontend/src/app/(authenticated)/admin/skills/page.tsx` - Fixed `most_used` comparator; added `disableInternalSort={true}` to `<ArtifactTable>`

## Decisions Made

- `disableInternalSort` bypasses the internal sort entirely but column-header sort buttons remain clickable — if user clicks a column header, it overrides parent order (acceptable UX, secondary sort)
- `usageCount: number` (required, not optional) since backend always returns this field; `?? 0` in the sort comparator handles any legacy rows

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Admin /skills sort dropdown now fully functional (Newest, Oldest, Most Used all reorder table rows)
- `disableInternalSort` pattern available for other admin pages that use ArtifactTable with parent-controlled sort
- SKCAT-01 requirement satisfied

---
*Phase: 20-skill-platform-b-discovery-catalog*
*Completed: 2026-03-08*

## Self-Check: PASSED

- FOUND: frontend/src/components/admin/artifact-table.tsx
- FOUND: frontend/src/lib/admin-types.ts
- FOUND: frontend/src/app/(authenticated)/admin/skills/page.tsx
- FOUND: .planning/phases/20-skill-platform-b-discovery-catalog/20-06-SUMMARY.md
- FOUND commit: a63d645 (Task 1)
- FOUND commit: 09b000b (Task 2)
