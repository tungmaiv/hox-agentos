# Phase 15: Session & Auth Hardening — Design

**Date:** 2026-03-05
**Phase:** 15 (v1.3 Track 1 — Foundations)
**Requirements:** AUTH-01 through AUTH-07
**Depends on:** Phase 14 (v1.2 complete)

## Goal

Users have a secure, production-grade session lifecycle — unauthenticated access is impossible, sessions refresh silently, and logout works reliably.

## Current State

- **Next.js:** 15.5.12 (above CVE-2025-29927 threshold of 15.2.3)
- **Auth library:** next-auth v5 (beta.30), dual providers (Keycloak OIDC + local credentials)
- **JWT storage:** Server-side via next-auth session cookie (HttpOnly, never in localStorage)
- **Token refresh:** Keycloak tokens refresh 30s before expiry via JWT callback; local tokens have 8h fixed expiry
- **Middleware:** None — no `middleware.ts` exists; routes are unprotected at the Next.js layer
- **Session expiry:** `session.error` is set on expiry but no client-side auto-redirect exists
- **Logout:** No formalized logout flow; Keycloak SSO session not terminated on sign-out

## Design Decisions

1. **Approach A selected:** next-auth `auth()` as middleware function (vs. custom jose JWT verification or per-page Server Component checks). Rationale: least code, leverages built-in Edge Runtime support, native Keycloak provider SSO logout.

2. **Post-login redirect:** Return to original URL via `callbackUrl` search param (not always `/chat`).

3. **Session expiry UX:** Silent redirect to `/login` — no modal overlay.

4. **SSO logout scope:** Full Keycloak SSO logout via `end_session_endpoint` — user must re-authenticate with Keycloak on next login.

5. **Cookie settings:** Keep next-auth defaults (HttpOnly, Secure in production, SameSite=Lax). No custom cookie configuration.

6. **Silent refresh:** Use existing next-auth JWT callback mechanism. No separate `/api/auth/refresh` endpoint — next-auth already handles this.

7. **Server-side validation:** Chat page Server Component validates token with backend on load. Other pages rely on middleware + client-side expiry detection.

## Requirement Mapping

### AUTH-01: Protected Route Redirect

Create `frontend/src/middleware.ts` using next-auth's `auth()` export.

**Protected routes (matcher):** `/chat/:path*`, `/admin/:path*`, `/canvas/:path*`, `/profile/:path*`, `/workflows/:path*`, `/skills/:path*`, `/settings/:path*`

**Excluded (not in matcher):** `/login`, `/api/auth/*`, `/api/copilotkit`, `/_next/*`, `/favicon.ico`

**Redirect behavior:**
- Unauthenticated request to protected route → `redirect("/login?callbackUrl={originalUrl}")`
- Authenticated user visiting `/login` → redirect to `/chat`

**Implementation:**

```typescript
// frontend/src/middleware.ts
export { auth as middleware } from "@/auth";

export const config = {
  matcher: [
    "/chat/:path*",
    "/admin/:path*",
    "/canvas/:path*",
    "/profile/:path*",
    "/workflows/:path*",
    "/skills/:path*",
    "/settings/:path*",
  ],
};
```

Add `authorized` callback to `auth.ts`:

```typescript
callbacks: {
  authorized({ auth, request }) {
    const isLoggedIn = !!auth?.user;
    const isProtected = config.matcher.some(pattern =>
      request.nextUrl.pathname.startsWith(pattern.replace("/:path*", ""))
    );
    if (isProtected && !isLoggedIn) {
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("callbackUrl", request.nextUrl.pathname);
      return Response.redirect(loginUrl);
    }
    return true;
  },
}
```

Update `/login` page to read `callbackUrl` from search params and pass to `signIn()`.

### AUTH-02: Next.js Version Verification

**Status:** Pre-satisfied. Next.js is at 15.5.12 (required: ≥15.2.3).

**Action:** Document verification in this design doc. No code changes needed.

### AUTH-03: Secure Cookie Settings

**Status:** Pre-satisfied by next-auth defaults.

next-auth v5 with `strategy: "jwt"` sets:
- `HttpOnly: true` — cookie not accessible via JavaScript
- `SameSite: Lax` — CSRF protection
- `Secure: true` — when `NEXTAUTH_URL` starts with `https://` (production)

**Action:** Verify defaults are active in development/production. Document in this design.

### AUTH-04: Silent Session Refresh

**Status:** Already implemented in `auth.ts` JWT callback.

Keycloak tokens refresh 30s before expiry via `refreshAccessToken()`. Local tokens have 8h fixed expiry with no refresh (by design — local auth is a convenience fallback).

**No separate `/api/auth/refresh` endpoint needed.** next-auth handles refresh transparently on every session access.

### AUTH-05: Logout

**Local auth:** `signOut({ callbackUrl: "/login" })` — clears next-auth session cookie.

**Keycloak SSO:** next-auth's Keycloak provider supports `end_session_endpoint` natively. Configure in auth.ts:

```typescript
events: {
  async signOut(message) {
    // For Keycloak sessions, redirect through end_session_endpoint
    if ("token" in message && message.token?.idToken) {
      const issuer = process.env.KEYCLOAK_ISSUER ?? "";
      const endSessionUrl = `${issuer}/protocol/openid-connect/logout`;
      const params = new URLSearchParams({
        id_token_hint: message.token.idToken as string,
        post_logout_redirect_uri: process.env.NEXTAUTH_URL ?? "http://localhost:3000",
      });
      await fetch(`${endSessionUrl}?${params}`);
    }
  },
},
```

### AUTH-06: Client-Side Expiry Detection

Create `frontend/src/components/auth/session-guard.tsx`:

```typescript
"use client";

import { useSession, signOut } from "next-auth/react";
import { useEffect } from "react";

export function SessionGuard({ children }: { children: React.ReactNode }) {
  const { data: session } = useSession();

  useEffect(() => {
    if (session?.error === "SessionExpired" || session?.error === "RefreshAccessTokenError") {
      signOut({ callbackUrl: "/login" });
    }
  }, [session?.error]);

  return <>{children}</>;
}
```

Place inside `(authenticated)/layout.tsx` route group layout.

### AUTH-07: Server-Side Token Validation on Chat Page

In the chat page Server Component:

```typescript
// frontend/src/app/(authenticated)/chat/page.tsx
import { auth } from "@/auth";
import { redirect } from "next/navigation";

export default async function ChatPage() {
  const session = await auth();
  if (!session?.accessToken) redirect("/login");

  // Validate token with backend
  const res = await fetch(`${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/users/me`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
  });

  if (res.status === 401) {
    // Token revoked or user deactivated — force re-login
    redirect("/api/auth/signout?callbackUrl=/login");
  }

  // ... render chat UI
}
```

## Structural Changes

### Route Group: `(authenticated)`

Move protected pages into an `(authenticated)` route group:

```
frontend/src/app/
├── (authenticated)/
│   ├── layout.tsx          ← SessionProvider + SessionGuard wrapper
│   ├── chat/page.tsx
│   ├── admin/...
│   ├── canvas/...
│   ├── profile/...
│   ├── workflows/...
│   ├── skills/...
│   └── settings/...
├── login/page.tsx           ← stays outside route group
├── api/auth/[...nextauth]/  ← stays outside route group
├── api/copilotkit/          ← stays outside route group
└── layout.tsx               ← root layout (no SessionGuard)
```

The `(authenticated)/layout.tsx` wraps children with:
1. `<SessionProvider>` (next-auth/react) — enables `useSession()` in client components
2. `<SessionGuard>` — watches for session errors and auto-redirects

## Files Changed

| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/middleware.ts` | **New** | Route protection via next-auth auth() |
| `frontend/src/auth.ts` | **Modified** | Add authorized callback, signOut event for Keycloak SSO logout |
| `frontend/src/components/auth/session-guard.tsx` | **New** | Client-side session expiry detection + auto-redirect |
| `frontend/src/app/(authenticated)/layout.tsx` | **New** | Route group layout with SessionProvider + SessionGuard |
| `frontend/src/app/(authenticated)/chat/page.tsx` | **Moved** | From app/chat/page.tsx; add server-side token validation |
| `frontend/src/app/(authenticated)/admin/...` | **Moved** | From app/admin/... |
| `frontend/src/app/(authenticated)/canvas/...` | **Moved** | From app/canvas/... |
| `frontend/src/app/(authenticated)/workflows/...` | **Moved** | From app/workflows/... |
| `frontend/src/app/(authenticated)/skills/...` | **Moved** | From app/skills/... |
| `frontend/src/app/(authenticated)/settings/...` | **Moved** | From app/settings/... |
| `frontend/src/app/(authenticated)/profile/...` | **Moved** | From app/profile/... |
| `frontend/src/app/login/page.tsx` | **Modified** | Read callbackUrl from search params, pass to signIn() |

## Testing Strategy

1. **Middleware redirect:** Visit `/chat` without auth → verify redirect to `/login?callbackUrl=/chat`
2. **Post-login redirect:** Sign in from `/login?callbackUrl=/canvas` → verify landing on `/canvas`
3. **Authenticated /login redirect:** Visit `/login` while authenticated → verify redirect to `/chat`
4. **Session expiry:** Set short token TTL, wait for expiry → verify silent redirect to `/login`
5. **Keycloak SSO logout:** Sign out → verify Keycloak session is also terminated (re-login requires credentials)
6. **Local auth logout:** Sign out → verify session cookie cleared, refreshing shows `/login`
7. **Server-side validation:** Deactivate user in admin → refresh chat page → verify redirect to `/login`
8. **Cookie security:** Inspect cookies in browser DevTools → verify HttpOnly, SameSite=Lax flags

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| next-auth v5 beta middleware quirks | Test middleware.ts thoroughly; fall back to manual cookie check if needed |
| Route group migration breaks imports | Move files one directory at a time; verify `pnpm run build` after each move |
| Keycloak end_session_endpoint unreachable | signOut event uses fire-and-forget fetch; local session is cleared regardless |
| callbackUrl open redirect | Validate callbackUrl is a relative path (not external URL) before redirecting |

## Scope

~12 files affected (2 new, 3 modified, 7 moved). Focused phase with no backend changes needed.
