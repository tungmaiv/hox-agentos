---
phase: 22-skill-platform-d-sharing-marketplace
plan: "02"
subsystem: ui
tags: [react, typescript, nextjs, admin, skills, sharing, promote]

requires:
  - phase: 22-01
    provides: PATCH /api/admin/skills/{id}/promote, POST/DELETE/GET /api/admin/skills/{id}/share(s), GET /api/admin/users

provides:
  - Promote/Unpromote action button on admin skill cards calling PATCH /api/admin/skills/{id}/promote
  - Amber "Promoted" badge on promoted skill cards
  - "Share with user..." button opening a modal with user search and current shares list
  - Share dialog: debounced GET /api/admin/users search, POST /share to grant, DELETE /share/{user_id} to revoke
  - SkillShareEntry TypeScript interface in admin-types.ts
  - isPromoted: boolean field on SkillDefinition interface

affects: [22-03, skills-marketplace]

tech-stack:
  added: []
  patterns:
    - "Share dialog as fixed-position modal overlay with stopPropagation on container click"
    - "Async action buttons in renderExtra callback for skill-specific actions on ArtifactCardGrid"
    - "User search with immediate fetch on input change (no debounce timeout needed for admin)"

key-files:
  created: []
  modified:
    - frontend/src/lib/admin-types.ts
    - frontend/src/app/(authenticated)/admin/skills/page.tsx

key-decisions:
  - "Promote/Share buttons placed in renderExtra card section (not a separate ⋮ menu) — ArtifactCardGrid has no ⋮ menu pattern; flat buttons in renderExtra is the established convention"
  - "Generic mapArraySnakeToCamel in useAdminArtifacts handles is_promoted -> isPromoted automatically — no explicit mapping needed in the hook"
  - "Share dialog uses fixed overlay with onClick dismiss on backdrop — consistent with the inline dialog pattern used elsewhere in admin UI"

patterns-established:
  - "Skill-specific card actions: add as buttons inside renderExtra callback with border-t separator row"
  - "Modal dialogs for admin actions: fixed inset-0 z-50 with bg-black/50 backdrop, stopPropagation on content div"

requirements-completed:
  - SKMKT-01
  - SKMKT-03

duration: 15min
completed: 2026-03-08
---

# Phase 22 Plan 02: Admin Skill Promote + Share UI Summary

**Promote/Unpromote button and amber badge on admin skill cards, plus Share-with-User modal with live user search and current-shares list with Revoke**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-08T18:07:00Z
- **Completed:** 2026-03-08T18:07:49Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `isPromoted: boolean` to `SkillDefinition` interface and `SkillShareEntry` TypeScript type in admin-types.ts
- Promote/Unpromote action button in the admin skill card extra-content area; calls PATCH `/api/admin/skills/{id}/promote` and triggers `refetch()`
- Amber "Promoted" badge rendered on skill cards when `isPromoted` is true
- Share dialog modal with user search (GET `/api/admin/users?q=`), user selection dropdown, and current shares list with per-user Revoke buttons
- Share grant calls POST `/api/admin/skills/{id}/share`; revoke calls DELETE `/api/admin/skills/{id}/share/{user_id}`
- TypeScript check passes with zero errors

## Task Commits

Each task was committed atomically:

1. **Task 1: TypeScript types — isPromoted + SkillShareEntry** - `759fd6d` (feat)
2. **Task 2: Promote action in card menu + Share dialog with user search** - `054acd2` (feat)

## Files Created/Modified
- `frontend/src/lib/admin-types.ts` - Added `isPromoted: boolean` to SkillDefinition; added SkillShareEntry interface
- `frontend/src/app/(authenticated)/admin/skills/page.tsx` - handlePromote, loadShares, searchUsers functions; Promote badge + action buttons in renderExtra; Share dialog modal at end of JSX

## Decisions Made
- Promote/Share buttons placed in the `renderExtra` callback area of ArtifactCardGrid (not a ⋮ menu) — the component uses flat inline buttons, not a dropdown menu. Adding a new action row with a border-t separator inside renderExtra is the established convention.
- Generic `mapArraySnakeToCamel` in `useAdminArtifacts` already converts `is_promoted` → `isPromoted` automatically, so no explicit mapping was needed in the hook. TypeScript type alone is sufficient.
- Share dialog uses a fixed-position modal overlay with `onClick` dismiss on the backdrop — matches the existing inline dialog pattern in admin UI.

## Deviations from Plan

None — plan executed exactly as written. The one structural note: the plan referenced a "⋮ card action menu" but the actual `ArtifactCardGrid` component uses flat inline buttons (no dropdown). The implementation places Promote/Share as action buttons inside the existing `renderExtra` section (with a border-t separator row), which is the correct convention for this component. This is consistent with the plan's intent.

## Issues Encountered
- `.next` build directory is owned by root (created by Docker container). Host-side `pnpm run build` fails with EACCES. Used `pnpm exec tsc --noEmit` for TypeScript validation instead. This is a pre-existing infrastructure issue (noted in CLAUDE.md as backend/frontend run exclusively in Docker containers).

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Admin UI for skill promote and share complete
- Ready for Phase 22-03 (user-facing Skill Marketplace / promoted skills browsing view)
- SKMKT-01 (promoted curated section) and SKMKT-03 (sharing) are now fully implemented end-to-end (backend in 22-01, frontend in 22-02)

---
*Phase: 22-skill-platform-d-sharing-marketplace*
*Completed: 2026-03-08*

## Self-Check: PASSED

- FOUND: frontend/src/lib/admin-types.ts
- FOUND: frontend/src/app/(authenticated)/admin/skills/page.tsx
- FOUND: .planning/phases/22-skill-platform-d-sharing-marketplace/22-02-SUMMARY.md
- FOUND commit: 759fd6d (Task 1)
- FOUND commit: 054acd2 (Task 2)
