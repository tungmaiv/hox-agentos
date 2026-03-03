---
phase: 12-unified-admin-desk
plan: "01"
subsystem: ui
tags: [admin, settings, credentials, oauth, nextjs, fastapi, rbac]

# Dependency graph
requires:
  - phase: 11-infra-and-debt
    provides: stable backend infrastructure and working Docker dev environment
  - phase: 09-admin-registry
    provides: /admin dashboard layout, admin_agents, admin_tools, admin_skills routes
provides:
  - /admin/config page with agent enable/disable toggles
  - /admin/credentials page with all-users OAuth connection view and admin force-revoke
  - GET/DELETE /api/admin/credentials backend endpoints with registry:manage RBAC gate
  - HTTP redirects from /settings/agents → /admin/config and /settings/integrations → /admin/mcp-servers
  - /settings page without Admin section (personal-only)
affects:
  - 12-02 (unified-admin-desk further consolidation if any)
  - 13-skill-tools-platform
  - 14-artifact-repository

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Admin credentials API: AdminCredentialView returns metadata only (user_id, provider, connected_at) — token values never returned
    - Next.js proxy pattern: getAccessToken() → NEXT_PUBLIC_API_URL → forward with Authorization header (matches existing admin proxy files)
    - Optimistic revoke: remove row immediately, restore on error with 5s timeout for error message
    - Server Component redirect: redirect() from next/navigation in a Server Component (no "use client")

key-files:
  created:
    - frontend/src/app/admin/config/page.tsx
    - frontend/src/app/admin/credentials/page.tsx
    - frontend/src/app/api/admin/credentials/route.ts
    - frontend/src/app/api/admin/credentials/[userId]/[provider]/route.ts
    - backend/api/routes/admin_credentials.py
  modified:
    - frontend/src/app/admin/layout.tsx
    - frontend/src/app/settings/page.tsx
    - frontend/src/app/settings/agents/page.tsx
    - frontend/src/app/settings/integrations/page.tsx
    - backend/main.py

key-decisions:
  - "Admin credential API returns only metadata (user_id, provider, connected_at) — token ciphertext never in response body"
  - "Next.js proxy uses NEXT_PUBLIC_API_URL (not BACKEND_INTERNAL_URL) — matches existing admin proxy pattern in config/route.ts"
  - "/settings/agents and /settings/integrations kept as files (not deleted) — Server Component redirect() returns HTTP redirect not 404"
  - "admin_credentials router uses async with session.begin() for read queries — prevents InFailedSQLTransactionError on pool reuse (discovered in Phase 11-live)"

patterns-established:
  - "Admin credentials view: AdminCredentialView Pydantic model with metadata-only fields + registry:manage RBAC gate"
  - "Optimistic revoke pattern: setCredentials(prev.filter(...)) before fetch, restore on catch with setTimeout 5000 for UX"

requirements-completed: [ADMIN-01]

# Metrics
duration: 3min
completed: 2026-03-03
---

# Phase 12 Plan 01: Unified Admin Desk (Consolidation) Summary

**Consolidated /admin to 8 tabs (Config + Credentials added), stripped Admin section from /settings, added redirects for old routes, and built backend GET/DELETE /api/admin/credentials with registry:manage RBAC gate**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-03T08:45:34Z
- **Completed:** 2026-03-03T08:48:35Z
- **Tasks:** 2 of 3 automated (Task 3 is human-verify checkpoint)
- **Files modified:** 10

## Accomplishments
- /admin nav now has 8 tabs — Config and Credentials tabs inserted before AI Builder
- /admin/config reuses agent toggle logic from /settings/agents (Zod schema, PUT /api/admin/config/{key})
- /admin/credentials shows all-users OAuth table with optimistic force-revoke
- Backend GET/DELETE /api/admin/credentials with registry:manage RBAC, metadata-only responses
- /settings page stripped of Admin grid section — personal-only now
- /settings/agents and /settings/integrations redirect (not 404) to their admin homes
- 609 backend tests pass; TypeScript strict: 0 errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Config/Credentials tabs to /admin + backend admin credentials API** - `569ed94` (feat)
2. **Task 2: Create /admin/credentials page + redirects + strip Admin from /settings** - `5671adc` (feat)
3. **Task 3: Verify consolidated admin desk end-to-end** - awaiting human verification

## Files Created/Modified
- `frontend/src/app/admin/layout.tsx` - ADMIN_TABS expanded to 8 entries (Config, Credentials added before AI Builder)
- `frontend/src/app/admin/config/page.tsx` - Agent toggle UI (reuses /api/admin/config), admin layout provides nav
- `frontend/src/app/admin/credentials/page.tsx` - All-users OAuth table with optimistic revoke
- `frontend/src/app/api/admin/credentials/route.ts` - Next.js proxy for GET /api/admin/credentials
- `frontend/src/app/api/admin/credentials/[userId]/[provider]/route.ts` - Proxy for DELETE
- `backend/api/routes/admin_credentials.py` - GET/DELETE admin credentials API (registry:manage gate)
- `backend/main.py` - Registered admin_credentials.router
- `frontend/src/app/settings/page.tsx` - Removed Admin grid section
- `frontend/src/app/settings/agents/page.tsx` - Replaced with Server Component redirect to /admin/config
- `frontend/src/app/settings/integrations/page.tsx` - Replaced with Server Component redirect to /admin/mcp-servers

## Decisions Made
- Admin credential API returns only metadata — token ciphertext never in response body (security invariant)
- Next.js proxy uses `NEXT_PUBLIC_API_URL` (not `BACKEND_INTERNAL_URL`) — matches existing admin proxy pattern seen in `config/route.ts` and `mcp-servers/route.ts`
- /settings/agents and /settings/integrations files kept (not deleted) — Server Component `redirect()` returns proper HTTP redirect, not 404
- `async with session.begin():` used in admin_credentials.py read queries — prevents InFailedSQLTransactionError on pool reuse (Phase 11-live decision)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- /admin unified dashboard complete for plan 01 deliverables
- Human verification checkpoint (Task 3) remains — user must confirm all 8 tabs, toggles, credential table, redirects work end-to-end in browser
- Phase 12 plan 02 and beyond can proceed after checkpoint approval

---
*Phase: 12-unified-admin-desk*
*Completed: 2026-03-03*
