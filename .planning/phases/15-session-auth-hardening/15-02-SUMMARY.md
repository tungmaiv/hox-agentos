---
phase: 15-session-auth-hardening
plan: "02"
subsystem: auth
tags: [next-auth, keycloak, session, logout, oidc, end-session]

# Dependency graph
requires:
  - phase: 15-session-auth-hardening-plan-01
    provides: middleware.ts protecting /chat, cookie secure config base

provides:
  - 5-minute Keycloak token refresh buffer (300_000ms) in auth.ts
  - Keycloak end-session endpoint integration in sign-out-button.tsx
  - idToken and authProvider fields in session for logout flow selection
  - Session error detection with auto-redirect in auth-error-toasts.tsx
  - callbackUrl support in login page for post-login navigation
  - Signed-out success banner on login page
  - Multi-tab session sync via SessionProvider refetchOnWindowFocus
  - NEXT_PUBLIC_KEYCLOAK_ISSUER env var for client-side Keycloak logout

affects:
  - session-management
  - keycloak-integration
  - logout-flows
  - session-expiry-handling

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "signOut({ redirect: false }) + window.location.href for Keycloak end-session redirect"
    - "useSession() in client component for session error detection and auto-redirect"
    - "callbackUrl pattern: /login?callbackUrl=<encoded-path>&error=<error-code>"
    - "NEXT_PUBLIC_ prefix for server-env vars needed client-side"

key-files:
  created: []
  modified:
    - frontend/src/auth.ts
    - frontend/src/components/sign-out-button.tsx
    - frontend/src/components/auth-error-toasts.tsx
    - frontend/src/app/login/page.tsx
    - frontend/src/app/layout.tsx
    - frontend/src/types/next-auth.d.ts
    - frontend/.env.local

key-decisions:
  - "No confirmation dialog on sign out — click Sign Out triggers instant logout with redirect"
  - "Full SSO logout via Keycloak end-session endpoint (id_token_hint) — not cookie-only"
  - "refetchOnWindowFocus=true for multi-tab sync — simpler than BroadcastChannel API"
  - "Session error detection uses 1.5s delay before redirect — allows toast to be visible"
  - "callbackUrl defaults to /chat when not present in URL params"
  - "NEXT_PUBLIC_KEYCLOAK_ISSUER duplicates KEYCLOAK_ISSUER — required for client-side URL construction"

patterns-established:
  - "Keycloak logout pattern: signOut({ redirect: false }) then window.location.href to end-session URL"
  - "Session error pattern: detect session.error in useEffect, skip /login path, toast + delayed redirect"
  - "callbackUrl pattern: encode current path into redirect URL for post-login return navigation"

requirements-completed: [AUTH-04, AUTH-05, AUTH-06, AUTH-07]

# Metrics
duration: 8min
completed: 2026-03-04
---

# Phase 15 Plan 02: Session Lifecycle Hardening Summary

**5-minute Keycloak token refresh buffer, full SSO end-session logout, session error detection with auto-redirect to /login, and callbackUrl post-login navigation**

## Performance

- **Duration:** 8 minutes
- **Started:** 2026-03-04T19:37:02Z
- **Completed:** 2026-03-04T19:45:00Z
- **Tasks:** 2 completed
- **Files modified:** 7

## Accomplishments

- Upgraded Keycloak token refresh from 30-second to 5-minute buffer — prevents mid-request token expiry on slow networks (AUTH-04)
- Enhanced logout to fully revoke Keycloak SSO sessions via end-session endpoint — critical security improvement for shared office machines (AUTH-05)
- Added session error detection in AuthErrorToasts — expired sessions now show toast notification and auto-redirect to /login (AUTH-06)
- Login page now supports callbackUrl — users return to their previous page after session expiry and re-login (AUTH-06)
- Login page shows "You have been signed out successfully." banner for 3 seconds after logout (AUTH-05)
- Multi-tab session sync via `refetchOnWindowFocus={true}` on SessionProvider (AUTH-06)

## Task Commits

Each task was committed atomically:

1. **Task 1: Upgrade refresh buffer, Keycloak end-session logout, multi-tab sync** - `e1c9160` (feat)
2. **Task 2: Session error detection, callbackUrl support, signed-out banner** - `348e642` (feat)

**Plan metadata:** (final docs commit — see below)

## Files Created/Modified

- `frontend/src/auth.ts` — Changed refresh buffer 30s→5min; added idToken and authProvider to session callback
- `frontend/src/types/next-auth.d.ts` — Extended Session interface with idToken and authProvider fields
- `frontend/src/components/sign-out-button.tsx` — Rewritten: Keycloak end-session for SSO users, cookie-only for local users
- `frontend/src/app/layout.tsx` — Added refetchOnWindowFocus={true} to SessionProvider
- `frontend/src/components/auth-error-toasts.tsx` — Rewritten: useSession() error detection + auto-redirect with toast
- `frontend/src/app/login/page.tsx` — Added callbackUrl support, signedOut banner, 3s auto-dismiss
- `frontend/.env.local` — Added NEXT_PUBLIC_KEYCLOAK_ISSUER alongside existing KEYCLOAK_ISSUER

## Decisions Made

- No confirmation dialog on Sign Out — instant logout for clean UX
- Keycloak logout uses id_token_hint in end-session URL — required for proper Keycloak session termination
- `signOut({ redirect: false })` first, then `window.location.href` to Keycloak end-session — clears next-auth cookies before Keycloak redirect
- `refetchOnWindowFocus` chosen over BroadcastChannel API — built into next-auth, simpler, sufficient for ~100 users
- 1.5 second delay before redirect on session error — gives toast time to be visible before navigation
- AUTH-07 (chat page validates access token) satisfied by existing middleware (Plan 15-01) + AuthErrorToasts detecting session.error — no additional changes needed to chat/page.tsx

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- `pnpm run build` fails during static pre-rendering of `/settings` page with `Cannot destructure property 'data' of useSession()` — confirmed pre-existing issue (same error present before our changes, in `/settings/chat-preferences`). This is out of scope: it's a pre-existing Server Component using client-only hooks. `pnpm exec tsc --noEmit` passes cleanly — our TypeScript changes are correct.

## User Setup Required

`NEXT_PUBLIC_KEYCLOAK_ISSUER` was added to `frontend/.env.local` for local development. For production Docker deployment, this env var must be added to `docker-compose.yml` frontend service environment alongside `KEYCLOAK_ISSUER`.

## Next Phase Readiness

- Session lifecycle hardening complete: token refresh, logout, session expiry, multi-tab sync all handled
- Phase 15 (Session & Auth Hardening) now complete — all requirements AUTH-01 through AUTH-07 satisfied
- Ready for Phase 16 (next phase in v1.3 roadmap)

---
*Phase: 15-session-auth-hardening*
*Completed: 2026-03-04*
