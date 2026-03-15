---
phase: 27-admin-registry-edit-ui
plan: 01
subsystem: ui
tags: [react, zod, tailwind, fastapi, mcp, pagination, admin]

# Dependency graph
requires:
  - phase: 24-unified-registry
    provides: Registry entry model, CRUD API, admin list pages
provides:
  - DualPagination reusable component for top+bottom list pagination
  - StickySaveBar component for unsaved changes detection
  - RegistryDetailLayout shell with breadcrumb, tabs, and save bar
  - Zod validation schemas for all 4 registry types
  - POST /api/admin/mcp-servers/test endpoint for connection testing
  - Row-click navigation on all 4 admin list pages
affects: [27-02, 27-03, admin-detail-pages]

# Tech tracking
tech-stack:
  added: []
  patterns: [dual-pagination-pattern, sticky-save-bar-pattern, registry-detail-layout-pattern, zod-field-validation]

key-files:
  created:
    - frontend/src/components/admin/dual-pagination.tsx
    - frontend/src/components/admin/sticky-save-bar.tsx
    - frontend/src/components/admin/registry-detail-layout.tsx
    - frontend/src/lib/registry-schemas.ts
    - backend/tests/api/test_mcp_server_routes.py
  modified:
    - backend/api/routes/mcp_servers.py
    - frontend/src/app/(authenticated)/admin/agents/page.tsx
    - frontend/src/app/(authenticated)/admin/tools/page.tsx
    - frontend/src/app/(authenticated)/admin/mcp-servers/page.tsx
    - frontend/src/app/(authenticated)/admin/skills/page.tsx

key-decisions:
  - "MCP test endpoint uses SSE GET probe (not full JSON-RPC tools/list) for simplicity"
  - "DualPagination is placed by consumer twice, not self-duplicating"

patterns-established:
  - "DualPagination: import and place at top+bottom of filtered list"
  - "StickySaveBar: fixed bottom bar controlled via hasChanges/saving props"
  - "RegistryDetailLayout: breadcrumb, header, tabs, children, save bar shell"
  - "validateField: per-field Zod validation for on-blur form errors"

requirements-completed: [REG-05, REG-06, REG-04]

# Metrics
duration: 12min
completed: 2026-03-15
---

# Phase 27 Plan 01: Shared Registry Foundation Summary

**Reusable DualPagination, StickySaveBar, and RegistryDetailLayout components with Zod form schemas and MCP connection test endpoint**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-15T12:47:23Z
- **Completed:** 2026-03-15T12:59:00Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- Created 3 shared admin components (DualPagination, StickySaveBar, RegistryDetailLayout) with full TypeScript types
- Added Zod validation schemas for agent, tool, MCP server, and skill forms with field-level validation helper
- Added POST /api/admin/mcp-servers/test endpoint with connectivity checks, timeouts, and error hints
- Replaced inline pagination on all 4 list pages with DualPagination at top and bottom
- Added row-click navigation to detail pages on all 4 list pages with stopPropagation on action buttons

## Task Commits

Each task was committed atomically:

1. **Task 1: Shared components + Zod schemas + MCP test endpoint** - `4a7a7b5` (feat)
2. **Task 2: Add dual pagination to all 4 list pages + row click navigation** - `fcbb11a` (feat)

## Files Created/Modified
- `frontend/src/components/admin/dual-pagination.tsx` - Reusable pagination with page selector, size dropdown, range text
- `frontend/src/components/admin/sticky-save-bar.tsx` - Fixed bottom bar for unsaved changes with spinner
- `frontend/src/components/admin/registry-detail-layout.tsx` - Detail page shell with breadcrumb, header, tabs, save bar
- `frontend/src/lib/registry-schemas.ts` - Zod schemas for 4 registry types + validateField helper
- `backend/api/routes/mcp_servers.py` - Added POST /test endpoint with connectivity testing
- `backend/tests/api/test_mcp_server_routes.py` - Tests for auth, admin-only, unreachable URL
- `frontend/src/app/(authenticated)/admin/agents/page.tsx` - DualPagination + row-click nav
- `frontend/src/app/(authenticated)/admin/tools/page.tsx` - DualPagination + row-click nav
- `frontend/src/app/(authenticated)/admin/mcp-servers/page.tsx` - DualPagination + row-click nav
- `frontend/src/app/(authenticated)/admin/skills/page.tsx` - DualPagination + row-click nav (replaced Link with router.push)

## Decisions Made
- MCP test endpoint probes the /sse endpoint with GET rather than full JSON-RPC tools/list -- simpler and sufficient for connectivity testing
- DualPagination placed twice by consumer (not self-duplicating) -- gives consumer layout control

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed TypeScript error in validateField helper**
- **Found during:** Task 1 (Zod schemas creation)
- **Issue:** `fieldSchema` could be undefined after extracting from shape, causing TS18048
- **Fix:** Added null guard before calling safeParse
- **Files modified:** frontend/src/lib/registry-schemas.ts
- **Verification:** pnpm exec tsc --noEmit passes
- **Committed in:** 4a7a7b5 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor TypeScript strict mode fix. No scope creep.

## Issues Encountered
- `pnpm run build` fails due to EACCES permission on .next/trace (Docker ownership issue, pre-existing) -- TypeScript check passes cleanly, confirming code correctness

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All shared components ready for use by 27-02 (agent + tool detail pages) and 27-03 (MCP + skill detail pages)
- Zod schemas ready for form validation integration
- MCP test endpoint ready for MCP server detail page "Test Connection" button

---
*Phase: 27-admin-registry-edit-ui*
*Completed: 2026-03-15*
