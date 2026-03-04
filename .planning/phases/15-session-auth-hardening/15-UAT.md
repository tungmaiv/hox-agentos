---
status: diagnosed
phase: 15-session-auth-hardening
source: [15-01-SUMMARY.md, 15-02-SUMMARY.md]
started: 2026-03-05T10:00:00Z
updated: 2026-03-05T10:35:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Route Protection — Unauthenticated Redirect
expected: Open a private/incognito browser window. Navigate to http://localhost:3000/chat directly. You should be redirected to /login with ?callbackUrl=%2Fchat in the URL.
result: issue
reported: "Redirect to /login works, but callbackUrl query parameter is missing from the URL — just http://localhost:3000/login"
severity: major

### 2. Public Route Access
expected: In the same incognito window, navigate to http://localhost:3000/login. The login page loads without any redirect loop or error.
result: pass

### 3. Sign Out — Full SSO Logout
expected: Log in normally. Click the Sign Out button. You should be redirected to /login. If you then try to visit /chat, you should NOT be auto-logged-in (Keycloak session was fully terminated, not just browser cookies cleared).
result: issue
reported: "Sign Out button is not reachable in the UI. AuthHeader component (which contains SignOutButton) is defined but never imported into any page layout."
severity: blocker

### 4. Signed-Out Success Banner
expected: After clicking Sign Out (from test 3), the login page shows a "You have been signed out successfully." banner. It auto-dismisses after about 3 seconds.
result: skipped
reason: Depends on Test 3 — Sign Out button not reachable

### 5. Session Expiry Detection
expected: While logged in on /chat, wait for the session to expire (or manually clear the session cookie). A toast notification should appear indicating the session expired, and you are auto-redirected to /login.
result: issue
reported: "After clearing session cookies and dispatching focus events, the page stays on /chat indefinitely. No toast appears, no auto-redirect. Only navigating manually triggers middleware redirect to /login."
severity: major

### 6. CallbackUrl Post-Login Return
expected: After being redirected to /login due to session expiry (from /chat), log back in. You should be returned to /chat (not the default page), because callbackUrl was preserved in the redirect.
result: skipped
reason: Depends on Test 1 — callbackUrl not present in redirect URL

### 7. Multi-Tab Session Sync
expected: Open the app in two tabs. Sign out in one tab. Switch to the other tab (click on it / focus it). The second tab should detect the session change — either redirecting to /login or showing the session expired toast.
result: issue
reported: "refetchOnWindowFocus does not trigger session recheck — same root cause as Test 5. Focus events after cookie deletion do not cause redirect or toast."
severity: major

## Summary

total: 7
passed: 1
issues: 4
pending: 0
skipped: 2

## Gaps

- truth: "Middleware redirect to /login includes ?callbackUrl=<original-path>"
  status: failed
  reason: "User reported: Redirect to /login works, but callbackUrl query parameter is missing from the URL — just http://localhost:3000/login"
  severity: major
  test: 1
  root_cause: "getToken() in middleware.ts:45 missing `secret` parameter. When stale session cookie exists, getToken() throws MissingSecret instead of returning null, causing middleware to error and Next.js falls back to bare /login redirect without callbackUrl."
  artifacts:
    - path: "frontend/src/middleware.ts"
      issue: "getToken({ req: request }) missing secret param at line 45"
  missing:
    - "Pass secret: process.env.NEXTAUTH_SECRET ?? process.env.AUTH_SECRET to getToken()"
  debug_session: ".planning/debug/callbackurl-missing-middleware.md"

- truth: "Sign Out button is visible and accessible in the authenticated UI"
  status: failed
  reason: "User reported: Sign Out button is not reachable in the UI. AuthHeader component (which contains SignOutButton) is defined but never imported into any page layout."
  severity: blocker
  test: 3
  root_cause: "AuthHeader, SignOutButton, and useAuth hook are all dead code — defined but never imported into any rendered page or layout. ConversationSidebar footer (conversation-sidebar.tsx:168-177) is the natural placement."
  artifacts:
    - path: "frontend/src/components/auth-header.tsx"
      issue: "Never imported into any page/layout"
    - path: "frontend/src/components/sign-out-button.tsx"
      issue: "Only imported by unused AuthHeader"
    - path: "frontend/src/components/chat/conversation-sidebar.tsx"
      issue: "Sidebar footer has Settings link but no sign-out button (lines 168-177)"
  missing:
    - "Import and render SignOutButton in conversation-sidebar.tsx footer"
  debug_session: ".planning/debug/sign-out-button-unreachable.md"

- truth: "Client-side session error detection shows toast and auto-redirects to /login when session expires"
  status: failed
  reason: "User reported: After clearing session cookies and dispatching focus events, the page stays on /chat indefinitely. No toast appears, no auto-redirect."
  severity: major
  test: 5
  root_cause: "Three compounding issues: (1) AuthErrorToasts rendered OUTSIDE SessionProvider in layout.tsx:20 — useSession() has no context. (2) No refetchInterval on SessionProvider — only refetchOnWindowFocus which fires on visibilitychange, not focus. (3) Cookie deletion produces null session (status=unauthenticated), not session.error — AuthErrorToasts only checks session.error, misses null transition."
  artifacts:
    - path: "frontend/src/app/layout.tsx"
      issue: "AuthErrorToasts is sibling of SessionProvider, not child (line 20); no refetchInterval prop (line 19)"
    - path: "frontend/src/components/auth-error-toasts.tsx"
      issue: "useSession() outside provider context (line 25); only checks session.error, not unauthenticated status (lines 32-35)"
  missing:
    - "Move AuthErrorToasts inside SessionProvider"
    - "Add refetchInterval={300} to SessionProvider"
    - "Detect status=unauthenticated transition in AuthErrorToasts, not just session.error"
  debug_session: ".planning/debug/client-session-expiry-detection.md"

- truth: "Multi-tab session sync detects logout in other tabs via refetchOnWindowFocus"
  status: failed
  reason: "User reported: refetchOnWindowFocus does not trigger session recheck — same root cause as Test 5."
  severity: major
  test: 7
  root_cause: "Same root cause as Test 5 — AuthErrorToasts outside SessionProvider context, plus cookie deletion produces null session not session.error. refetchOnWindowFocus itself works (fires visibilitychange), but the detection component cannot see the session state change."
  artifacts:
    - path: "frontend/src/app/layout.tsx"
      issue: "AuthErrorToasts outside SessionProvider"
    - path: "frontend/src/components/auth-error-toasts.tsx"
      issue: "Cannot detect session changes from outside provider"
  missing:
    - "Same fixes as Test 5 will resolve this"
  debug_session: ".planning/debug/client-session-expiry-detection.md"
