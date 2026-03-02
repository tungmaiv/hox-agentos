---
phase: 06-extensibility-registries
plan: 07
subsystem: ui
tags: [nextjs, react, admin, dashboard, permissions, mcp, typescript, tailwind]

# Dependency graph
requires:
  - phase: 06-extensibility-registries/03
    provides: "Admin CRUD APIs for agents, tools, skills, permissions"
  - phase: 06-extensibility-registries/06
    provides: "User skill/tool APIs, slash command dispatch, frontend skill menu"
provides:
  - "Admin dashboard at /admin with role-based access (it-admin, developer only)"
  - "Tabbed navigation for Agents, Tools, Skills, MCP Servers, Permissions"
  - "Reusable ArtifactTable and ArtifactCardGrid components with view toggle"
  - "PermissionMatrix with role x artifact checkboxes and staged apply"
  - "Per-user permission override management UI"
  - "McpStatusDot component with green/yellow/red connectivity indicators"
  - "Next.js proxy route for /api/admin/* with JWT injection"
  - "TypeScript types and hooks for admin CRUD and permission management"
affects: [07-01-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Admin layout with server-side role check: layout.tsx reads session roles, renders 403 for non-admins"
    - "Generic artifact hooks: useAdminArtifacts<T>(type) for CRUD on any registry artifact"
    - "View toggle with localStorage persistence: table vs card grid switchable per user"
    - "Catch-all proxy route: /api/admin/[...path]/route.ts forwards all methods with JWT"
    - "MCP connectivity dot: color derived from last_seen_at timestamp thresholds (5min/30min)"

key-files:
  created:
    - frontend/src/app/admin/layout.tsx
    - frontend/src/app/admin/page.tsx
    - frontend/src/app/admin/agents/page.tsx
    - frontend/src/app/admin/tools/page.tsx
    - frontend/src/app/admin/skills/page.tsx
    - frontend/src/app/admin/mcp-servers/page.tsx
    - frontend/src/app/admin/permissions/page.tsx
    - frontend/src/app/api/admin/[...path]/route.ts
    - frontend/src/lib/admin-types.ts
    - frontend/src/hooks/use-admin-artifacts.ts
    - frontend/src/hooks/use-admin-permissions.ts
    - frontend/src/components/admin/artifact-table.tsx
    - frontend/src/components/admin/artifact-card-grid.tsx
    - frontend/src/components/admin/permission-matrix.tsx
    - frontend/src/components/admin/mcp-status-dot.tsx
    - frontend/src/components/admin/view-toggle.tsx
  modified: []

key-decisions:
  - "KNOWN_ROLES and KNOWN_PERMISSIONS in permission-matrix.tsx must match backend seed data exactly -- mismatches cause empty matrix columns"
  - "Admin layout renders 403 inline (not redirect) for non-admin users -- simpler than redirect, no flash"
  - "Generic useAdminArtifacts<T> hook parameterized by ArtifactType -- single hook handles all 4 artifact types"
  - "View mode stored in localStorage (admin-view-mode) -- persists across sessions without backend state"
  - "Catch-all proxy at /api/admin/[...path] forwards GET/POST/PUT/PATCH/DELETE with JWT from session"

patterns-established:
  - "Admin page pattern: Client Component with useAdminArtifacts + ViewToggle + ArtifactTable/ArtifactCardGrid conditional render"
  - "Permission matrix pattern: rows=artifacts, columns=roles, cells=checkboxes, pending changes with yellow highlight and Apply button"
  - "MCP status dot pattern: green (<5min), yellow (<30min), red (>30min or never) based on last_seen_at"

requirements-completed: [EXTD-02, EXTD-04]

# Metrics
duration: 15min
completed: 2026-02-28
---

# Phase 6 Plan 07: Admin Dashboard UI Summary

**Tabbed admin dashboard at /admin with table/card views for all registry artifacts, role x artifact permission matrix with staged apply, per-user overrides, and MCP connectivity dots**

## Performance

- **Duration:** ~15 min (across checkpoint verification)
- **Started:** 2026-02-28T15:30:00Z
- **Completed:** 2026-02-28T15:55:17Z
- **Tasks:** 3 (2 auto + 1 human-verify checkpoint)
- **Files modified:** 16

## Accomplishments
- Full admin dashboard at /admin with role-based access control (it-admin and developer roles only, 403 for others)
- Five tabbed pages: Agents, Tools, Skills, MCP Servers, Permissions -- each with artifact CRUD
- Reusable ArtifactTable and ArtifactCardGrid components with localStorage-persisted view toggle
- PermissionMatrix with role x artifact checkbox grid, pending change highlighting, and Apply Pending button
- Per-user permission override management with add/remove from Permissions tab
- McpStatusDot with green/yellow/red coloring based on last_seen_at thresholds
- Next.js catch-all proxy route at /api/admin/[...path] forwarding all HTTP methods with JWT injection
- Comprehensive TypeScript types (admin-types.ts) and generic hooks (useAdminArtifacts, useAdminPermissions)
- Skills tab includes pending review filter shortcut and approve/reject actions
- Frontend builds clean with strict TypeScript (0 errors)

## Task Commits

Each task was committed atomically:

1. **Task 1: Admin Dashboard Layout, Proxy Route, Types, and Hooks** - `5e43b37` (feat)
2. **Task 2: Artifact Views (Table + Cards), Permission Matrix, MCP Dots, Tab Pages** - `317bdc6` (feat)
3. **Task 3: Verify Admin Dashboard** - `0b06cc6` (fix -- KNOWN_ROLES mismatch bug found and fixed during verification)

## Files Created/Modified
- `frontend/src/app/admin/layout.tsx` - Admin layout with role-based access check and tab navigation
- `frontend/src/app/admin/page.tsx` - Root redirect to /admin/agents
- `frontend/src/app/admin/agents/page.tsx` - Agents tab with table/card views and create dialog
- `frontend/src/app/admin/tools/page.tsx` - Tools tab with handler_type and sandbox_required columns
- `frontend/src/app/admin/skills/page.tsx` - Skills tab with pending review filter, approve/reject actions
- `frontend/src/app/admin/mcp-servers/page.tsx` - MCP Servers tab with connectivity dots
- `frontend/src/app/admin/permissions/page.tsx` - Permissions tab with global matrix and per-user overrides
- `frontend/src/app/api/admin/[...path]/route.ts` - Catch-all proxy for admin API with JWT injection
- `frontend/src/lib/admin-types.ts` - TypeScript interfaces for all admin API response types
- `frontend/src/hooks/use-admin-artifacts.ts` - Generic CRUD hook for any artifact type
- `frontend/src/hooks/use-admin-permissions.ts` - Permission management hook with staged apply
- `frontend/src/components/admin/artifact-table.tsx` - Sortable table with status badges and row actions
- `frontend/src/components/admin/artifact-card-grid.tsx` - Responsive card grid with status badges
- `frontend/src/components/admin/permission-matrix.tsx` - Role x artifact permission matrix with pending state
- `frontend/src/components/admin/mcp-status-dot.tsx` - Green/yellow/red connectivity indicator
- `frontend/src/components/admin/view-toggle.tsx` - Table/card toggle with localStorage persistence

## Decisions Made
- KNOWN_ROLES and KNOWN_PERMISSIONS arrays in permission-matrix.tsx must be kept in sync with backend seed data (role_permissions table) -- mismatch caused empty columns during verification, fixed in commit 0b06cc6
- Admin layout renders 403 message inline rather than redirecting -- simpler implementation, no layout flash
- Generic useAdminArtifacts<T> hook handles all four artifact types (agents, tools, skills, mcp-servers) through a single parameterized interface
- View mode preference stored in localStorage under "admin-view-mode" key -- persists per-browser without backend roundtrip
- Catch-all proxy pattern (/api/admin/[...path]) exports GET, POST, PUT, PATCH, DELETE handlers that all inject JWT from server session

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] KNOWN_ROLES and KNOWN_PERMISSIONS mismatch with backend seed data**
- **Found during:** Task 3 (human verification checkpoint)
- **Issue:** Permission matrix rendered with incorrect/empty columns because KNOWN_ROLES and KNOWN_PERMISSIONS arrays in permission-matrix.tsx did not match the roles and permissions seeded in the backend role_permissions table
- **Fix:** Aligned KNOWN_ROLES and KNOWN_PERMISSIONS constants with actual backend seed data
- **Files modified:** frontend/src/components/admin/permission-matrix.tsx
- **Verification:** Permission matrix renders correctly with all expected role columns populated
- **Committed in:** 0b06cc6

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Bug fix necessary for correct permission matrix rendering. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviation above.

## User Setup Required
None - admin dashboard uses existing JWT auth and backend admin APIs. No new environment variables or services required.

## Next Phase Readiness
- Phase 6 (Extensibility Registries) is now COMPLETE -- all 7 plans executed
- All registry artifacts (agents, tools, skills, MCP servers) manageable via API and admin UI
- Permission model (role-based + per-user overrides + staged apply) fully operational
- Skill runtime with /command support and import pipeline functional
- Admin dashboard provides visual management for all registry operations
- Ready for Phase 7 (Hardening and Sandboxing) -- Docker sandbox execution, security audit, RLS policies

## Self-Check: PASSED

- All 16 files verified present on disk
- All 3 task commits (5e43b37, 317bdc6, 0b06cc6) verified in git log

---
*Phase: 06-extensibility-registries*
*Completed: 2026-02-28*
