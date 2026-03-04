---
phase: 15-session-auth-hardening
plan: "03"
subsystem: frontend-auth
tags: [auth, session, next-auth, keycloak, middleware, multi-tab]
dependency_graph:
  requires: [15-01, 15-02]
  provides: [session-expiry-detection, multi-tab-sync, signout-ui, middleware-secret]
  affects: [frontend/src/middleware.ts, frontend/src/app/layout.tsx, frontend/src/components/auth-error-toasts.tsx, frontend/src/components/chat/conversation-sidebar.tsx]
tech_stack:
  added: []
  patterns: [useRef-status-tracking, refetchInterval-polling, getToken-explicit-secret]
key_files:
  modified:
    - frontend/src/middleware.ts
    - frontend/src/app/layout.tsx
    - frontend/src/components/auth-error-toasts.tsx
    - frontend/src/components/chat/conversation-sidebar.tsx
decisions:
  - "Pass explicit secret to getToken() — @auth/core 0.41.0 requires it, unlike next-auth v4"
  - "useRef(status) tracks previous status to avoid false Scenario B triggers on initial load"
  - "refetchInterval=300 (5 min) balances detection speed vs network overhead for 100-user scale"
  - "AuthErrorToasts moved inside SessionProvider — useSession() requires SessionProvider ancestor"
metrics:
  duration: "1 minute"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 4
  completed_date: "2026-03-04T20:50:32Z"
---

# Phase 15 Plan 03: UAT Gap Closure — Session Auth Hardening Summary

**One-liner:** Closed 4 UAT gaps: middleware explicit secret for getToken(), SignOutButton in sidebar footer, AuthErrorToasts moved inside SessionProvider with refetchInterval=300, and unauthenticated status transition detection via useRef tracking.

## What Was Built

Addressed all 4 UAT gaps identified in Phase 15 testing that prevented the session lifecycle from working end-to-end in production.

### Task 1: Middleware secret + SignOutButton in sidebar (commit 9aae560)

**Gap 1 — callbackUrl missing on stale cookie redirect:**

`frontend/src/middleware.ts` line 45 was calling `getToken({ req: request })` without the `secret` parameter. In `@auth/core` 0.41.0 (used by next-auth 5.0.0-beta), `getToken()` does NOT auto-detect `NEXTAUTH_SECRET` from environment variables, unlike next-auth v4. When a stale session cookie exists, the old call threw `MissingSecret` instead of returning `null`, causing Next.js error handling to redirect to `/login` without `callbackUrl`.

Fix: Pass `secret: process.env.NEXTAUTH_SECRET ?? process.env.AUTH_SECRET` explicitly.

**Gap 2 — Sign Out button unreachable:**

The conversation sidebar footer had only a Settings link — no sign-out affordance. Added `import { SignOutButton } from "@/components/sign-out-button"` and rendered `<SignOutButton />` below the Settings link in the footer div.

### Task 2: Session expiry detection + multi-tab sync (commit c74f0dc)

**Gap 3 — Client-side session expiry detection broken:**

`AuthErrorToasts` was rendered as a sibling of `SessionProvider` (outside its closing tag) in `layout.tsx`. `useSession()` inside `AuthErrorToasts` requires `SessionProvider` as an ancestor — it was silently falling back to a default context with no session data, so the error detection effect never fired.

Fix: Move `<AuthErrorToasts />` inside `<SessionProvider>` in `layout.tsx`.

**Gap 4 — Multi-tab session sync not working:**

`SessionProvider` had `refetchOnWindowFocus={true}` but no `refetchInterval`. While window focus handles tab switching, a tab that stays in focus indefinitely (common during work) would never re-fetch the session after server-side invalidation.

Fix: Add `refetchInterval={300}` (5-minute polling) to `SessionProvider`.

**Gap 3+4 — auth-error-toasts.tsx only checked session.error:**

The component only handled Scenario A (session.error from failed token refresh). After the layout fix, it would now receive `status="unauthenticated"` from `useSession()` when the session cookie is deleted — but had no handler for this transition.

Fix: Added Scenario B detection using `useRef(status)` to track the previous status. Only fires when transitioning from `"authenticated"` to `"unauthenticated"` — prevents false triggers on initial page load (where status starts as `"loading"`).

## Commits

| Hash | Message |
|------|---------|
| 9aae560 | fix(15-03): fix middleware getToken secret and add SignOutButton to sidebar |
| c74f0dc | fix(15-03): fix session expiry detection and multi-tab sync |

## Verification

All artifacts verified:

- `frontend/src/middleware.ts`: `secret: process.env.NEXTAUTH_SECRET ?? process.env.AUTH_SECRET` on line 47
- `frontend/src/app/layout.tsx`: `AuthErrorToasts` inside `SessionProvider`, `refetchInterval={300}` on line 19
- `frontend/src/components/auth-error-toasts.tsx`: detects `status === "unauthenticated"` transition (line 62)
- `frontend/src/components/chat/conversation-sidebar.tsx`: imports and renders `SignOutButton` (lines 7, 179)
- TypeScript: `pnpm exec tsc --noEmit` passes cleanly

## Deviations from Plan

None — plan executed exactly as written. All 4 fixes applied in 2 tasks as specified.

## Auth Gates

None encountered during execution.

## Self-Check: PASSED

- Files: middleware.ts, layout.tsx, auth-error-toasts.tsx, conversation-sidebar.tsx, 15-03-SUMMARY.md — all present
- Commits: 9aae560, c74f0dc — both found in git log
