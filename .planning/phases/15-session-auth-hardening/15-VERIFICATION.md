---
phase: 15-session-auth-hardening
verified: 2026-03-05T09:00:00Z
status: gaps_found
score: 11/12 must-haves verified
re_verification: false
gaps:
  - truth: "AUTH-07: Chat page server component validates access token with backend on each load — if 401, triggers signOut + redirect"
    status: failed
    reason: "chat/page.tsx calls fetchConversations() but on backend 401 returns an empty array and renders the page normally — no signOut, no redirect triggered. The middleware and AuthErrorToasts handle session errors at a different layer (session.error flag), but the specific requirement for the chat page Server Component to trigger signOut on a 401 backend response is not implemented."
    artifacts:
      - path: "frontend/src/app/chat/page.tsx"
        issue: "fetchConversations() silently returns [] on non-ok (including 401) backend response. No signOut or redirect triggered on 401."
    missing:
      - "After fetchConversations returns a 401, call signOut() or redirect('/login') from the Server Component. Options: (a) make fetchConversations return the response status and add a signOut+redirect in ChatPage, OR (b) accept that middleware+AuthErrorToasts already handle the expired-session case and update REQUIREMENTS.md to reflect the actual design decision."
human_verification:
  - test: "Verify Keycloak end-session logout fully terminates SSO session"
    expected: "After clicking Sign Out as a Keycloak SSO user, navigating back to the app should require full Keycloak re-authentication — no silent SSO re-login occurs."
    why_human: "Cannot verify Keycloak SSO session termination programmatically without a running Keycloak instance and browser session."
  - test: "Multi-tab logout sync"
    expected: "Signing out in Tab A causes Tab B to detect the session as invalid (via refetchOnWindowFocus) and redirect to /login when Tab B is focused."
    why_human: "Requires live browser interaction and timing verification."
  - test: "Signed-out banner auto-dismiss"
    expected: "After clicking Sign Out, /login?signedOut=true shows a green 'You have been signed out successfully.' banner that disappears after 3 seconds."
    why_human: "Requires browser interaction to verify timing and visual appearance."
---

# Phase 15: Session & Auth Hardening — Verification Report

**Phase Goal:** Harden frontend authentication — add Next.js middleware for route protection, secure session cookies, improve token refresh, and add proper logout with Keycloak end-session.
**Verified:** 2026-03-05T09:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | Visiting /chat without a valid session redirects to /login | VERIFIED | middleware.ts uses getToken(); no token → NextResponse.redirect to /login with callbackUrl |
| 2  | Visiting /admin without a valid session redirects to /login | VERIFIED | middleware.ts allowlist approach; /admin is not in PUBLIC_PATHS — protected by default |
| 3  | Visiting /workflows without a valid session redirects to /login | VERIFIED | Same — middleware covers all unlisted routes |
| 4  | /login page is accessible without any session | VERIFIED | PUBLIC_PATHS = ["/login"] in middleware.ts line 23 |
| 5  | /api/auth/* routes are accessible without middleware blocking | VERIFIED | PUBLIC_PATH_PREFIXES = ["/api/auth/"] in middleware.ts line 27 |
| 6  | /_next/* static assets are not blocked | VERIFIED | config.matcher excludes _next/static, _next/image, favicon.ico, image extensions |
| 7  | Next.js version is >= 15.2.3 (CVE-2025-29927 safe) | VERIFIED | package.json: "next": "15.5.12" — 15.5.12 >= 15.2.3 |
| 8  | Per-page if (!session) redirect('/login') checks removed | VERIFIED | Confirmed absent in chat/page.tsx, workflows/page.tsx, workflows/new/page.tsx, workflows/[id]/page.tsx, admin/layout.tsx, page.tsx |
| 9  | Keycloak token refresh triggers 5 minutes before expiry | VERIFIED | auth.ts line 181: `300_000` (5 minutes) replaces old 30_000 (30 seconds) |
| 10 | Clicking Sign Out clears auth state and redirects to /login | VERIFIED | sign-out-button.tsx: calls signOut({ redirect: false }) + window.location.href for Keycloak; signOut({ callbackUrl: "/login?signedOut=true" }) for local |
| 11 | Keycloak users' Sign Out calls Keycloak end-session endpoint | VERIFIED | sign-out-button.tsx lines 24-38: constructs end-session URL with id_token_hint and post_logout_redirect_uri, calls Keycloak end-session endpoint |
| 12 | AUTH-07: Chat page server component validates access token with backend — 401 triggers signOut + redirect | FAILED | chat/page.tsx line 13: `if (!response.ok) return [];` — backend 401 returns empty array, no signOut triggered |

**Score:** 11/12 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/middleware.ts` | Edge Runtime route protection with getToken() | VERIFIED | 79 lines; exports middleware function + config with matcher; uses getToken() from next-auth/jwt; PUBLIC_PATHS allowlist; redirects with callbackUrl |
| `frontend/package.json` | jose dependency | VERIFIED | "jose": "^6.1.3" present |
| `frontend/src/auth.ts` | 5-minute refresh buffer, cookie config, idToken/authProvider in session | VERIFIED | Line 181: 300_000; lines 68-81: cookie config with httpOnly/sameSite/secure; lines 206-210: idToken and authProvider propagated to session |
| `frontend/src/components/sign-out-button.tsx` | Enhanced sign-out with Keycloak end-session | VERIFIED | Uses useSession() to detect authProvider; builds Keycloak end-session URL with id_token_hint; calls signOut({ redirect: false }) then window.location.href |
| `frontend/src/components/auth-error-toasts.tsx` | Session error detection with useSession() and auto-redirect | VERIFIED | useEffect detects session.error; shows toast.error(); setTimeout(1500ms) before signOut redirect to /login with callbackUrl and error params |
| `frontend/src/app/login/page.tsx` | Logout success banner, callbackUrl redirect | VERIFIED | showSignedOut state from searchParams.get("signedOut"); callbackUrl = searchParams.get("callbackUrl") ?? "/chat"; router.push(callbackUrl) on success; SSO signIn with callbackUrl |
| `frontend/src/app/layout.tsx` | SessionProvider with refetchOnWindowFocus | VERIFIED | Line 19: `<SessionProvider refetchOnWindowFocus={true}>` |
| `frontend/src/types/next-auth.d.ts` | Session type extended with idToken and authProvider | VERIFIED | Session interface includes idToken?: string and authProvider?: "keycloak" \| "credentials" |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| middleware.ts | next-auth session cookie | getToken() from next-auth/jwt | WIRED | Line 45: `const token = await getToken({ req: request })` |
| middleware.ts | /login redirect | NextResponse.redirect on auth failure | WIRED | Lines 51-52: constructs loginUrl and redirects; also wired for token.error case lines 58-61 |
| auth.ts | Keycloak token endpoint | refreshAccessToken() with 300_000 buffer | WIRED | Line 181: buffer check; lines 23-61: refreshAccessToken function calls token endpoint |
| auth-error-toasts.tsx | /login | session.error detection triggers signOut + redirect | WIRED | Lines 32-48: useEffect checks session?.error; toast.error + setTimeout + signOut with callbackUrl |
| sign-out-button.tsx | Keycloak end-session endpoint | signOut({ redirect: false }) + window.location.href | WIRED | Lines 22-38: conditional on authProvider === "keycloak" && idToken; constructs end-session URL |
| login/page.tsx | /chat or callbackUrl | callbackUrl from searchParams | WIRED | Line 22: callbackUrl = searchParams.get("callbackUrl") ?? "/chat"; line 60: router.push(callbackUrl); line 70: signIn("keycloak", { callbackUrl }) |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| AUTH-01 | 15-01 | Protected routes redirect unauthenticated users to /login via middleware.ts using jose | SATISFIED (with note) | Middleware uses getToken() from next-auth/jwt (which uses jose internally). jose@6.1.3 installed. Functional outcome matches. REQUIREMENTS.md specifies "using jose for Edge Runtime JWT verification" — getToken() uses jose as peer dep; this is technically correct, not just raw jose.jwtVerify(). |
| AUTH-02 | 15-01 | Next.js >= 15.2.3 (CVE-2025-29927 mitigation) | SATISFIED | package.json: "next": "15.5.12" — 15.5.12 >= 15.2.3 |
| AUTH-03 | 15-01 | Session cookie with HttpOnly, Secure (production), SameSite=Lax | SATISFIED | auth.ts lines 68-81: explicit cookie config with httpOnly: true, sameSite: "lax", secure: NODE_ENV === "production", path: "/" |
| AUTH-04 | 15-02 | Session silent refresh via /api/auth/refresh when <5 min remaining | PARTIALLY SATISFIED | The 5-minute buffer is implemented in auth.ts jwt callback (300_000ms). However, REQUIREMENTS.md specifies "via /api/auth/refresh" — no such endpoint exists. Refresh happens in next-auth JWT callback on next request, not via an explicit /api/auth/refresh route. Design context (15-CONTEXT.md) explicitly chose this approach over a dedicated endpoint. The outcome (5-min buffer silent refresh) is achieved; the specific endpoint mechanism differs from the requirement literal. |
| AUTH-05 | 15-02 | Logout via POST /api/auth/logout; Keycloak path calls Keycloak logout endpoint | PARTIALLY SATISFIED | No /api/auth/logout endpoint exists. Sign-out uses next-auth signOut() client-side. Keycloak end-session IS called via window.location.href. Design context explicitly says "Cookie-only logout (no backend POST /api/auth/logout endpoint needed) — JWT is stateless." The Keycloak end-session requirement is fully met; the /api/auth/logout endpoint was deliberately omitted. |
| AUTH-06 | 15-02 | SessionProvider detects session.error and auto-redirects to /login | SATISFIED | auth-error-toasts.tsx uses useSession() to detect SessionExpired/RefreshAccessTokenError; toast + 1.5s delayed signOut redirect. SessionProvider in layout.tsx with refetchOnWindowFocus={true}. |
| AUTH-07 | 15-02 | Chat page server component validates access token — 401 triggers signOut + redirect | NOT SATISFIED | chat/page.tsx: on backend 401, fetchConversations returns [] and page renders normally. No signOut or redirect triggered. The mechanism exists (middleware + AuthErrorToasts) to handle expired sessions, but the specific AUTH-07 behavior (chat page responds to a 401 by triggering signOut) is not implemented. |

---

## Anti-Patterns Found

No blockers. Input `placeholder` strings in login/page.tsx are HTML attributes on `<input>` elements — not implementation anti-patterns.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

---

## Human Verification Required

### 1. Keycloak End-Session Logout

**Test:** Log in as a Keycloak SSO user. Open a second tab to another app sharing the Keycloak realm. Click Sign Out in Blitz. In the second tab (or a new browser tab), navigate to the Blitz app.
**Expected:** Full SSO session is terminated — re-authentication is required, no silent SSO re-login occurs.
**Why human:** Cannot verify Keycloak session termination without a running Keycloak instance and live browser session with SSO state.

### 2. Multi-Tab Logout Sync

**Test:** Open Blitz in two browser tabs (Tab A and Tab B). Sign out in Tab A. Switch focus to Tab B.
**Expected:** Tab B detects the session as invalid via refetchOnWindowFocus and redirects to /login (or shows session expired toast then redirects).
**Why human:** Requires live browser interaction with timing verification; next-auth refetchOnWindowFocus behavior depends on runtime session state.

### 3. Signed-Out Banner Auto-Dismiss

**Test:** Click Sign Out. Observe /login page.
**Expected:** Green banner "You have been signed out successfully." appears and auto-dismisses after 3 seconds.
**Why human:** Requires browser interaction to verify timing (3s auto-dismiss) and visual appearance of the green banner.

---

## Gaps Summary

One gap blocks full AUTH-07 compliance:

**AUTH-07 — Chat page 401 handling.** The requirement specification says the chat page Server Component should detect a 401 from the backend and trigger signOut + redirect. The current implementation makes `fetchConversations()` return an empty array on any non-ok response (including 401), then renders the page normally with no conversations. The expired-session case is handled at a different layer (middleware catches missing sessions; AuthErrorToasts catches session.error from failed token refresh), but these mechanisms do not cover the case where the session cookie is technically valid but the backend access token has been invalidated server-side.

**Design decision conflict:** The 15-CONTEXT.md explicitly chose a "toast + redirect" approach via AuthErrorToasts for session expiry. AUTH-07's requirement for a server-side 401-triggered redirect from the chat page was not implemented because the executor determined the middleware+AuthErrorToasts combination covered the session expiry case. This is a documented design deviation.

**Resolution options:**
1. Update `chat/page.tsx` to detect a 401 from `fetchConversations()` and call `redirect('/login?error=SessionExpired')` (matching AUTH-07 literally).
2. Accept the design deviation as intentional and update REQUIREMENTS.md AUTH-07 to reflect the actual mechanism — "session error detection via AuthErrorToasts component detects RefreshAccessTokenError/SessionExpired and redirects to /login" — then mark AUTH-07 as satisfied.

**AUTH-04 and AUTH-05 requirement literal vs. implementation:** Both AUTH-04 (no `/api/auth/refresh` endpoint) and AUTH-05 (no `/api/auth/logout` endpoint) diverge from the REQUIREMENTS.md literal wording. However, both were explicitly decided against in 15-CONTEXT.md design decisions. The functional outcomes (5-min token refresh, full Keycloak session termination) are achieved. These are documented design decisions, not gaps, and REQUIREMENTS.md should be updated to reflect the chosen implementation pattern.

---

_Verified: 2026-03-05T09:00:00Z_
_Verifier: Claude (gsd-verifier)_
