# Phase 15: Session & Auth Hardening - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Users have a secure, production-grade session lifecycle — unauthenticated access is impossible, sessions refresh silently, and logout works reliably. This phase covers Next.js middleware for route protection, cookie security, silent token refresh, logout flow, and session error handling. Navigation UI (nav rail, profile page) is Phase 16. Identity configuration (Keycloak-optional boot) is Phase 18.

</domain>

<decisions>
## Implementation Decisions

### Session expiry experience
- Toast notification + auto-redirect to /login (no pre-expiry warning modal or countdown)
- No draft/message preservation on session expiry — losing a partially typed chat message is acceptable
- Generic message only: "Your session has expired. Please sign in again." — same message regardless of expiry reason (expired, revoked, error)
- Return user to their previous page after re-login via `?callbackUrl=<current-path>` on /login redirect

### Logout flow
- No confirmation dialog — click "Sign Out" → instant logout → redirect to /login
- Full SSO logout: call Keycloak's end-session endpoint for Keycloak users (revoke Keycloak session, not just Blitz cookie)
- Brief success banner on /login page: "You have been signed out successfully." — shown for a few seconds
- Cookie-only logout (no backend POST /api/auth/logout endpoint needed) — JWT is stateless, no server-side session to revoke; Keycloak end-session is called client-side via next-auth's signOut

### Session duration & refresh
- Local session duration: 8 hours (keep current) — covers a full workday
- No "Remember me" option — enterprise security: fixed session duration, no persistent login across browser restarts
- Keycloak token refresh buffer: 5 minutes before expiry (upgrade from current 30s buffer) — matches AUTH-04 requirement
- Multi-tab session sync: supported via next-auth's refetchOnWindowFocus or BroadcastChannel API — logout in one tab clears all tabs

### Protected routes (middleware strategy)
- Allowlist approach: everything is protected by default. Public routes explicitly listed: /login, /api/auth/*, /_next/*, /favicon.ico, static assets
- JWT signature verification in middleware via `jose` library (Edge Runtime compatible) — not just cookie existence check
- Auth-only in middleware (no RBAC role checks) — role checks remain in page components where they already work
- Remove per-page `if (!session) redirect('/login')` checks — middleware is the single gate; no redundant per-page auth checks

### Claude's Discretion
- Exact toast styling and duration (works with existing Sonner Toaster from AuthErrorToasts)
- BroadcastChannel vs refetchOnWindowFocus for multi-tab sync — pick whichever next-auth v5 supports cleanly
- Whether to add `/api/auth/session` to the public route allowlist (next-auth needs it)
- Middleware matcher config specifics (Next.js matcher patterns)
- How to handle the transition from per-page auth to middleware (order of removal)

</decisions>

<specifics>
## Specific Ideas

- Session expiry should feel unobtrusive — toast + redirect, not a scary modal. Enterprise users understand session expiry.
- Keycloak SSO logout should be full (end-session endpoint) since this is an enterprise app on shared office machines. Partial logout is a security risk.
- The 5-minute refresh buffer is important — 30s is too tight for slow internal networks and can cause mid-request token expiry.
- Middleware should use allowlist (secure-by-default) — any new page added to the app is automatically protected without remembering to add it to a denylist.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `auth.ts`: next-auth v5 config with Keycloak + Credentials providers, JWT callbacks, token refresh logic — extend refresh buffer here
- `AuthErrorToasts` component: renders Sonner Toaster at app root — add session error detection logic here
- `SignOutButton` component: exists for auth header — enhance with Keycloak end-session call
- Login page (`/login/page.tsx`): already handles `?error=SessionExpired` and `RefreshAccessTokenError` query params

### Established Patterns
- Server Components call `auth()` for session access — this pattern continues in middleware
- CopilotKit proxy (`/api/copilotkit/route.ts`) injects JWT server-side — already returns 401 if no session
- Root `/` page redirects based on session state — middleware will handle this instead
- `next-auth/react` `SessionProvider` wraps the entire app in root layout

### Integration Points
- `middleware.ts` (new file) — intercepts all requests before page rendering
- `auth.ts` JWT callback — change refresh buffer from 30s to 5 min
- `AuthErrorToasts` — add session.error detection and redirect logic
- Root layout `SessionProvider` — may need `refetchOnWindowFocus` or `refetchInterval` config
- All page-level `if (!session) redirect('/login')` checks — to be removed after middleware is in place

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-session-auth-hardening*
*Context gathered: 2026-03-05*
