---
phase: 26-keycloak-sso-hardening
plan: 02
subsystem: ui
tags: [react, next-auth, sso, health-monitor, notifications, zod, tailwind]

# Dependency graph
requires:
  - phase: 26-01
    provides: SSO health API, admin notifications API, auth config extension, circuit breaker
provides:
  - SSO health monitor panel with 4 categorized diagnostic cards on Identity page
  - Circuit breaker threshold configuration UI
  - Admin notification bell component with dropdown
  - Login page graceful degradation when SSO unavailable
  - Mid-flow SSO error handling via next-auth
  - Zod schemas for SSO health and notification API responses
  - useSSOHealth and useAdminNotifications custom hooks
affects: [27-mcp-marketplace, 29-ux-polish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Admin health panel pattern: 4-card grid with status indicators + collapsible config"
    - "Dual notification bell pattern: domain-specific bells until unified notification system"
    - "Login degradation pattern: sso_available flag hides SSO button with info banner"

key-files:
  created:
    - frontend/src/components/admin/sso-health-panel.tsx
    - frontend/src/components/admin/notification-bell.tsx
    - frontend/src/hooks/use-sso-health.ts
    - frontend/src/hooks/use-admin-notifications.ts
  modified:
    - frontend/src/lib/api-types.ts
    - frontend/src/app/(authenticated)/admin/identity/page.tsx
    - frontend/src/app/(authenticated)/admin/layout.tsx
    - frontend/src/app/login/page.tsx
    - frontend/src/auth.ts

key-decisions:
  - "Keep BOTH notification bells (skills + admin) side by side until Phase 30+ unifies them"
  - "Flat circuit breaker response shape in Zod schema matches backend API (no nested thresholds wrapper)"

patterns-established:
  - "Admin health panel: 4-card responsive grid with color-coded status dots (green/yellow/red)"
  - "Hook-driven admin UI: useSSOHealth and useAdminNotifications encapsulate fetch + polling + mutations"
  - "Login degradation: fetch /api/auth/config on mount, check sso_available flag separately from sso_enabled"

requirements-completed: [KC-01, KC-03, KC-04, KC-05, KC-07]

# Metrics
duration: 15min
completed: 2026-03-15
---

# Phase 26 Plan 02: SSO Frontend Health Monitor Summary

**SSO health dashboard with 4 diagnostic cards, circuit breaker threshold config, admin notification bell, and login page graceful degradation**

## Performance

- **Duration:** 15 min (across continuation sessions)
- **Started:** 2026-03-15T10:25:00Z
- **Completed:** 2026-03-15T10:48:43Z
- **Tasks:** 3 (2 auto + 1 human-verify checkpoint)
- **Files modified:** 9

## Accomplishments
- SSO Health Monitor panel on Identity page with 4 categorized cards (Certificate, Config, Connectivity, Performance) showing color-coded status indicators
- Circuit breaker threshold configuration form with Save and Reset buttons, pre-populated from current API values
- Admin notification bell with unread count badge and dropdown, integrated alongside existing skills bell in admin layout
- Login page hides SSO button when sso_available=false with friendly info banner, handles SSOUnavailable error param
- Mid-flow SSO errors caught by next-auth signIn callback and redirected to /login?error=SSOUnavailable

## Task Commits

Each task was committed atomically:

1. **Task 1: SSO health panel + threshold config + hooks + login page degradation** - `02c5e8b` (feat)
2. **Task 2: Admin layout notification bell integration + next-auth SSO error handler** - `cecc5f1` (feat)
3. **Task 3: Visual verification checkpoint** - approved by user (no commit)

**Orchestrator fix:** `38c921f` (fix) - Aligned Zod schema with flat circuit breaker response shape

## Files Created/Modified
- `frontend/src/components/admin/sso-health-panel.tsx` - 4-card health dashboard with threshold config form
- `frontend/src/components/admin/notification-bell.tsx` - Bell icon with unread badge and dropdown
- `frontend/src/hooks/use-sso-health.ts` - Hook for SSO health data with auto-refresh and threshold mutations
- `frontend/src/hooks/use-admin-notifications.ts` - Hook for notification CRUD with polling
- `frontend/src/lib/api-types.ts` - Zod schemas for SSO health, circuit breaker, notifications
- `frontend/src/app/(authenticated)/admin/identity/page.tsx` - Added SSOHealthPanel at top of page
- `frontend/src/app/(authenticated)/admin/layout.tsx` - Added NotificationBell alongside existing skills bell
- `frontend/src/app/login/page.tsx` - Added sso_available check and SSOUnavailable error handling
- `frontend/src/auth.ts` - Added signIn callback to catch mid-flow SSO errors

## Decisions Made
- Keep BOTH notification bells (skills pending + admin notifications) side by side -- they serve different purposes and poll different endpoints until a unified notification system in Phase 30+
- Flat circuit breaker response shape in Zod schema -- backend returns thresholds at top level of circuit_breaker object, not nested

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Aligned Zod schema with actual API response shape**
- **Found during:** Post-Task 2 (orchestrator fix)
- **Issue:** Zod CircuitBreakerStateSchema expected nested `thresholds` object, but backend returns flat structure with threshold fields at circuit_breaker level
- **Fix:** Updated Zod schema to match flat response shape
- **Files modified:** frontend/src/lib/api-types.ts
- **Verification:** Frontend build passes
- **Committed in:** 38c921f

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Schema alignment necessary for correctness. No scope creep.

## Issues Encountered
None beyond the Zod schema alignment handled above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 26 (Keycloak SSO Hardening) is fully complete with both backend (Plan 01) and frontend (Plan 02)
- SSO health monitoring is operational end-to-end
- Ready to proceed to Phase 27 (MCP Server Marketplace)

## Self-Check: PASSED

All 5 key files verified present. All 3 commits (02c5e8b, cecc5f1, 38c921f) verified in git log.

---
*Phase: 26-keycloak-sso-hardening*
*Completed: 2026-03-15*
