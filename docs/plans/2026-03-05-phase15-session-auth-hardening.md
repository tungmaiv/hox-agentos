# Phase 15: Session & Auth Hardening — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make all authenticated routes redirect to `/login` when unauthenticated, add silent token refresh, Keycloak SSO logout, session expiry auto-redirect, and server-side token validation on the chat page.

**Architecture:** next-auth v5's `auth()` export used as Next.js middleware handles route protection. An `authorized` callback in the auth config returns `true/false` to allow/deny. A `SessionGuard` client component watches `session.error` and auto-redirects on expiry. Keycloak SSO logout is handled via the `events.signOut` hook calling Keycloak's `end_session_endpoint`.

**Tech Stack:** next-auth v5, Next.js 15.5.12 middleware, TypeScript

**Design simplification vs. original design doc:** The design doc proposed creating an `(authenticated)` route group and moving 7 directories. This is unnecessary because `SessionProvider` is already in the root layout (`layout.tsx:19`). We add `SessionGuard` alongside it — zero file moves, same security guarantees, much less risk.

---

### Task 1: Add `authorized` callback and `signOut` event to auth.ts

**Files:**
- Modify: `frontend/src/auth.ts:63-195`

**Step 1: Write the authorized callback**

Add the `authorized` callback to the existing `callbacks` object in `auth.ts`. This callback is invoked by next-auth when `auth()` is used as middleware.

Open `frontend/src/auth.ts` and add `authorized` as the first callback (before `jwt`):

```typescript
// Inside NextAuth({ ... callbacks: { ... } })
// Add this BEFORE the existing jwt callback (line ~125):

    authorized({ auth }) {
      // Middleware gate: return true if session exists, false to redirect to /login
      // next-auth automatically appends ?callbackUrl=<original-path>
      return !!auth;
    },
```

**Step 2: Add Keycloak SSO logout event**

Add an `events` property to the NextAuth config object, at the same level as `callbacks`. Insert after the `session: { strategy: "jwt" }` line (line ~123):

```typescript
  events: {
    async signOut(message) {
      // Keycloak SSO: end the Keycloak session so user must re-authenticate
      if ("token" in message && message.token?.idToken) {
        const issuer = process.env.KEYCLOAK_ISSUER;
        if (issuer) {
          const endSessionUrl = `${issuer}/protocol/openid-connect/logout`;
          const params = new URLSearchParams({
            id_token_hint: message.token.idToken as string,
            post_logout_redirect_uri:
              process.env.NEXTAUTH_URL ?? "http://localhost:3000",
          });
          try {
            await fetch(`${endSessionUrl}?${params}`, { method: "GET" });
          } catch {
            // Keycloak unreachable — local session is still cleared by next-auth
          }
        }
      }
    },
  },
```

**Step 3: Run build to verify no TypeScript errors**

Run: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm run build`
Expected: Build succeeds (no type errors from the new callback/event)

**Step 4: Commit**

```bash
git add frontend/src/auth.ts
git commit -m "feat(15-01): add authorized callback and Keycloak SSO logout event

AUTH-01: authorized callback enables middleware route protection.
AUTH-05: signOut event calls Keycloak end_session_endpoint for full SSO logout."
```

---

### Task 2: Create middleware.ts for route protection

**Files:**
- Create: `frontend/src/middleware.ts`

**Step 1: Create the middleware file**

Create `frontend/src/middleware.ts` with this exact content:

```typescript
/**
 * Next.js middleware — route protection via next-auth v5.
 *
 * Routes matched by `config.matcher` require a valid session.
 * Unauthenticated requests are redirected to /login with ?callbackUrl=<path>.
 *
 * AUTH-01: Protected route redirect
 * AUTH-02: CVE-2025-29927 mitigated — Next.js 15.5.12 (required: >=15.2.3)
 */
export { auth as middleware } from "@/auth";

export const config = {
  matcher: [
    "/chat/:path*",
    "/admin/:path*",
    "/workflows/:path*",
    "/settings/:path*",
    // Future routes (Phase 16+):
    "/profile/:path*",
    "/skills/:path*",
    "/canvas/:path*",
  ],
};
```

**Step 2: Run build to verify middleware compiles for Edge Runtime**

Run: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm run build`
Expected: Build succeeds. Middleware compiles for Edge Runtime without errors.

If build fails with Edge Runtime incompatibility, check that `auth.ts` does not import Node.js-only modules at the top level. The `authorized` callback runs in Edge Runtime, but the `events.signOut` handler runs server-side. next-auth v5 handles this separation internally.

**Step 3: Commit**

```bash
git add frontend/src/middleware.ts
git commit -m "feat(15-01): add Next.js middleware for route protection

AUTH-01: /chat, /admin, /workflows, /settings (and future /profile, /skills,
/canvas) redirect unauthenticated users to /login?callbackUrl=<path>.
AUTH-02: Next.js 15.5.12 confirmed (CVE-2025-29927 mitigated)."
```

---

### Task 3: Create SessionGuard component

**Files:**
- Create: `frontend/src/components/auth/session-guard.tsx`

**Step 1: Create the component**

```bash
ls frontend/src/components/auth/
# If the directory doesn't exist, that's fine — create it
```

Create `frontend/src/components/auth/session-guard.tsx`:

```typescript
"use client";
/**
 * SessionGuard — watches for session errors and auto-redirects to /login.
 *
 * AUTH-06: Client-side expiry detection.
 *
 * Detects two error states set by auth.ts JWT callback:
 * - "SessionExpired": local auth token past 8-hour TTL
 * - "RefreshAccessTokenError": Keycloak refresh_token grant failed
 *
 * On either error, calls signOut() which clears the session cookie and
 * redirects to /login. No modal — silent redirect per design decision.
 */
import { useSession, signOut } from "next-auth/react";
import { useEffect } from "react";

export function SessionGuard({ children }: { children: React.ReactNode }) {
  const { data: session } = useSession();

  useEffect(() => {
    if (
      session?.error === "SessionExpired" ||
      session?.error === "RefreshAccessTokenError"
    ) {
      void signOut({ callbackUrl: "/login" });
    }
  }, [session?.error]);

  return <>{children}</>;
}
```

**Step 2: Run build to verify**

Run: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm run build`
Expected: Build succeeds.

**Step 3: Commit**

```bash
git add frontend/src/components/auth/session-guard.tsx
git commit -m "feat(15-01): add SessionGuard client component

AUTH-06: watches session.error for SessionExpired and RefreshAccessTokenError,
auto-redirects to /login via signOut()."
```

---

### Task 4: Add SessionGuard to root layout

**Files:**
- Modify: `frontend/src/app/layout.tsx`

**Step 1: Add SessionGuard import and wrap children**

Current `layout.tsx` (lines 1-24):
```typescript
import type { Metadata } from "next";
import { SessionProvider } from "next-auth/react";
import { AuthErrorToasts } from "@/components/auth-error-toasts";
import "./globals.css";
// ...
        <SessionProvider>{children}</SessionProvider>
```

Add the import after line 3:
```typescript
import { SessionGuard } from "@/components/auth/session-guard";
```

Wrap `{children}` inside `SessionGuard` (line 19):
```typescript
        <SessionProvider>
          <SessionGuard>{children}</SessionGuard>
        </SessionProvider>
```

The full file should now be:
```typescript
import type { Metadata } from "next";
import { SessionProvider } from "next-auth/react";
import { SessionGuard } from "@/components/auth/session-guard";
import { AuthErrorToasts } from "@/components/auth-error-toasts";
import "./globals.css";

export const metadata: Metadata = {
  title: "Blitz AgentOS",
  description: "Enterprise AI Assistant",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <SessionProvider>
          <SessionGuard>{children}</SessionGuard>
        </SessionProvider>
        <AuthErrorToasts />
      </body>
    </html>
  );
}
```

**Step 2: Run build to verify**

Run: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm run build`
Expected: Build succeeds.

**Step 3: Commit**

```bash
git add frontend/src/app/layout.tsx
git commit -m "feat(15-01): wire SessionGuard into root layout

AUTH-06: SessionGuard wraps all pages inside SessionProvider, detects
expired sessions and redirects to /login automatically."
```

---

### Task 5: Update login page for callbackUrl support

**Files:**
- Modify: `frontend/src/app/login/page.tsx`

**Step 1: Read callbackUrl from search params and use it in signIn calls**

In `LoginForm` component, two changes:

**Change 1:** Read `callbackUrl` from search params (after line 16):
```typescript
  const callbackUrl = searchParams.get("callbackUrl") ?? "/chat";
```

**Change 2:** Use `callbackUrl` in SSO sign-in (line 53):
```typescript
  function handleSSOSignIn(): void {
    void signIn("keycloak", { callbackUrl });
  }
```

**Change 3:** Use `callbackUrl` in credentials sign-in success (line 43):
```typescript
        router.push(callbackUrl);
```

**Change 4:** Add authenticated-user redirect. Add `useSession` import and check at the top of `LoginForm`:

Add to the import on line 9:
```typescript
import { signIn, useSession } from "next-auth/react";
```

Add after the `useState` declarations (after line 21):
```typescript
  const { status } = useSession();

  // Already authenticated — redirect to target page
  if (status === "authenticated") {
    router.push(callbackUrl);
    return null;
  }
```

**Step 2: Run build to verify**

Run: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm run build`
Expected: Build succeeds.

**Step 3: Commit**

```bash
git add frontend/src/app/login/page.tsx
git commit -m "feat(15-01): login page reads callbackUrl and redirects authenticated users

AUTH-01: After login, returns to original URL via callbackUrl param.
Authenticated users visiting /login are redirected to /chat (or callbackUrl)."
```

---

### Task 6: Add server-side token validation to chat page

**Files:**
- Modify: `frontend/src/app/chat/page.tsx`

**Step 1: Modify fetchConversations to propagate 401**

The current `fetchConversations` function (lines 7-19) swallows all errors and returns `[]`. For AUTH-07, we need to detect a 401 response (token revoked or user deactivated) so the page can redirect.

Replace the `fetchConversations` function and update `ChatPage`:

```typescript
// frontend/src/app/chat/page.tsx
import { auth, signOut } from "@/auth";
import { redirect } from "next/navigation";
import { ChatLayout } from "@/components/chat/chat-layout";
import type { Conversation } from "@/components/chat/chat-layout";

/**
 * Fetch recent conversations. Returns null if token is invalid (401),
 * empty array on other errors, or the conversation list on success.
 */
async function fetchConversations(
  accessToken: string,
): Promise<Conversation[] | null> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(`${apiUrl}/api/conversations/?limit=20`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
    if (response.status === 401) return null; // Token invalid — signal to caller
    if (!response.ok) return [];
    return (await response.json()) as Conversation[];
  } catch {
    return [];
  }
}

export default async function ChatPage() {
  const session = await auth();
  if (!session) redirect("/login");

  const accessToken = (session as unknown as Record<string, unknown>)
    .accessToken as string | undefined;
  if (!accessToken) redirect("/login");

  // AUTH-07: Server-side token validation — if backend rejects the token
  // (revoked, user deactivated), force re-login
  const conversations = await fetchConversations(accessToken);
  if (conversations === null) {
    redirect("/login");
  }

  return (
    <ChatLayout
      initialConversations={conversations}
      userEmail={session.user?.email ?? ""}
    />
  );
}
```

Key changes:
- `fetchConversations` returns `null` on 401 (token invalid) vs `[]` on other errors
- `ChatPage` checks for `null` and redirects to `/login`
- Import `signOut` from auth (for future use; the redirect to `/login` will trigger middleware on next visit)

**Step 2: Run build to verify**

Run: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm run build`
Expected: Build succeeds.

**Step 3: Commit**

```bash
git add frontend/src/app/chat/page.tsx
git commit -m "feat(15-01): server-side token validation on chat page load

AUTH-07: fetchConversations detects 401 from backend (token revoked or
user deactivated) and redirects to /login. No separate validation
endpoint needed — the existing conversations API serves as the probe."
```

---

### Task 7: Full build verification and final commit

**Files:**
- No new changes — verification only

**Step 1: Run full frontend build**

Run: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm run build`
Expected: Build succeeds with no errors.

**Step 2: Run TypeScript type check**

Run: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm exec tsc --noEmit`
Expected: No type errors.

**Step 3: Run backend tests to confirm no regressions**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q`
Expected: All tests pass (no backend changes in this phase, so count should remain at baseline).

**Step 4: Verify AUTH-02 and AUTH-03**

Check Next.js version:
```bash
cd /home/tungmv/Projects/hox-agentos/frontend && cat node_modules/next/package.json | grep '"version"'
```
Expected: `"version": "15.5.12"` (≥15.2.3, CVE-2025-29927 mitigated)

AUTH-03 (cookie security) is verified by next-auth defaults — no manual action needed. Document in commit.

**Step 5: Final commit**

```bash
git commit --allow-empty -m "docs(15-01): verify AUTH-02 (Next.js 15.5.12) and AUTH-03 (next-auth cookie defaults)

AUTH-02: Next.js 15.5.12 confirmed — CVE-2025-29927 mitigated (required >=15.2.3).
AUTH-03: next-auth v5 JWT strategy sets HttpOnly, SameSite=Lax, Secure (in prod) by default."
```

---

## Requirement Coverage Summary

| Requirement | Task | How |
|-------------|------|-----|
| AUTH-01 | Tasks 1-2, 5 | `middleware.ts` + `authorized` callback + login callbackUrl |
| AUTH-02 | Task 7 | Verified: Next.js 15.5.12 ≥ 15.2.3 |
| AUTH-03 | Task 7 | Verified: next-auth defaults (HttpOnly, Secure, SameSite=Lax) |
| AUTH-04 | — | Pre-satisfied: `auth.ts` JWT callback already refreshes Keycloak tokens |
| AUTH-05 | Task 1 | `events.signOut` calls Keycloak `end_session_endpoint` |
| AUTH-06 | Tasks 3-4 | `SessionGuard` in root layout watches `session.error` |
| AUTH-07 | Task 6 | Chat page `fetchConversations` detects 401 → redirect |

## Manual Testing Checklist

After all tasks are complete, verify these scenarios manually:

1. [ ] Visit `/chat` without auth → redirected to `/login?callbackUrl=/chat`
2. [ ] Visit `/admin` without auth → redirected to `/login?callbackUrl=/admin`
3. [ ] Sign in from `/login?callbackUrl=/workflows` → land on `/workflows`
4. [ ] Sign in from `/login` (no callbackUrl) → land on `/chat`
5. [ ] Visit `/login` while authenticated → redirected to `/chat`
6. [ ] Click Sign Out (local auth) → session cleared, refreshing shows `/login`
7. [ ] Click Sign Out (Keycloak SSO) → Keycloak session also terminated
8. [ ] Deactivate user via admin → refresh chat → redirected to `/login`
9. [ ] Inspect cookies → `next-auth.session-token` has HttpOnly, SameSite=Lax
