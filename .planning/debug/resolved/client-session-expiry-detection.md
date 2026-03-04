---
status: resolved
trigger: "Client-side session expiry detection not working — no toast, no auto-redirect after cookie deletion"
created: 2026-03-05T10:00:00Z
updated: 2026-03-05T10:05:00Z
---

## Current Focus

hypothesis: CONFIRMED — Two root causes: (1) AuthErrorToasts outside SessionProvider, (2) no refetchInterval for active polling
test: Code inspection complete
expecting: N/A
next_action: Return diagnosis

## Symptoms

expected: After clearing session cookies, AuthErrorToasts detects session.error via useSession(), shows toast, auto-redirects to /login within ~1.5s
actual: /chat page stays displayed indefinitely, no toast, no redirect. Only manual navigation triggers middleware redirect.
errors: None visible — silent failure
reproduction: Clear session cookies on /chat page, observe no toast/redirect
started: Since AuthErrorToasts was implemented

## Eliminated

## Evidence

- timestamp: 2026-03-05T10:00:00Z
  checked: frontend/src/app/layout.tsx lines 11-24
  found: AuthErrorToasts is rendered OUTSIDE the SessionProvider closing tag (line 20) — it is a sibling of SessionProvider (line 19), not a child
  implication: useSession() inside AuthErrorToasts has no SessionProvider context

- timestamp: 2026-03-05T10:02:00Z
  checked: next-auth/react.js useSession() source (lines 70-101)
  found: useSession() checks React.useContext(SessionContext). If value is falsy AND NODE_ENV !== "production", it THROWS. In production, value would be undefined — session?.error would always be undefined.
  implication: In dev mode, AuthErrorToasts would throw a React error on render (swallowed by error boundary or RSC). In production, it silently does nothing.

- timestamp: 2026-03-05T10:03:00Z
  checked: next-auth/react.js SessionProvider source (lines 304-315, 319-328)
  found: refetchOnWindowFocus (line 305-314) only triggers on visibilitychange event (tab switch). It does NOT detect cookie deletion while the tab is active. refetchInterval (lines 320-328) would poll periodically, but it requires a numeric prop (seconds) — layout.tsx does NOT pass refetchInterval.
  implication: Even if AuthErrorToasts were inside SessionProvider, cookie deletion while the tab is active would NOT be detected until the user switches tabs and comes back.

- timestamp: 2026-03-05T10:04:00Z
  checked: frontend/src/auth.ts JWT callback (lines 141-193) and session callback (lines 194-218)
  found: session.error is set in the session callback (line 214) from token.error. token.error is set when (a) local credentials token expires (line 174) or (b) Keycloak refresh fails (line 59). Cookie deletion is a DIFFERENT scenario — next-auth session endpoint returns null/empty when cookie is missing, not an error-flagged session.
  implication: Even with periodic polling, cookie deletion would result in session=null (status="unauthenticated"), NOT session.error="SessionExpired". AuthErrorToasts only checks for session.error, not for session becoming null.

## Resolution

root_cause: |
  THREE compounding issues prevent client-side session expiry detection:

  1. CRITICAL — AuthErrorToasts rendered outside SessionProvider (layout.tsx:20 vs :19):
     AuthErrorToasts is a sibling of SessionProvider, not a child. useSession() has no provider
     context. In dev mode, this throws "[next-auth]: useSession must be wrapped in a <SessionProvider />".
     In production, it silently returns undefined — session?.error is always undefined.

  2. SIGNIFICANT — No refetchInterval configured (layout.tsx:19):
     SessionProvider only has refetchOnWindowFocus={true}, which triggers on tab visibility change.
     There is no refetchInterval prop, so the session is NEVER actively polled while the tab
     is focused. Cookie deletion on an active tab is invisible to next-auth until navigation.

  3. DESIGN GAP — Cookie deletion produces null session, not session.error:
     AuthErrorToasts checks session?.error === "SessionExpired", but cookie deletion causes
     next-auth to return a null session (status="unauthenticated"), not an error-flagged session.
     session.error is only set when the JWT callback detects token expiry or refresh failure on
     a still-existing cookie. The component needs to also handle the null-session case.

fix:
verification:
files_changed: []
