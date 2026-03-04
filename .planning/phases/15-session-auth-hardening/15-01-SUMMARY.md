---
phase: 15
plan: "01"
subsystem: frontend-auth
tags: [middleware, next-auth, security, route-protection, cve-mitigation]
dependency_graph:
  requires: []
  provides: [edge-runtime-middleware, route-protection, cookie-hardening]
  affects: [frontend-auth, all-protected-routes]
tech_stack:
  added: [jose@6.1.3]
  patterns: [allowlist-middleware, edge-runtime-jwt-verification, auth-gate-consolidation]
key_files:
  created:
    - frontend/src/middleware.ts
  modified:
    - frontend/package.json
    - frontend/pnpm-lock.yaml
    - frontend/src/auth.ts
    - frontend/src/app/page.tsx
    - frontend/src/app/chat/page.tsx
    - frontend/src/app/workflows/page.tsx
    - frontend/src/app/workflows/new/page.tsx
    - frontend/src/app/workflows/[id]/page.tsx
    - frontend/src/app/admin/layout.tsx
decisions:
  - "Allowlist approach: all routes protected by default, public routes explicitly listed"
  - "Use getToken() from next-auth/jwt (not raw jose.jwtVerify) — next-auth v5 encrypts cookies with NEXTAUTH_SECRET"
  - "Session error tokens (expired/refresh failed) trigger forced re-login with error param"
  - "Per-page if (!session) redirect removed — middleware is sole auth gate"
  - "Admin layout keeps RBAC role check; middleware handles auth, components handle authorization"
  - "workflows/new and workflows/[id] redirect to /workflows (not /login) on missing accessToken after middleware pass"
metrics:
  duration: "451 seconds"
  completed_date: "2026-03-04"
  tasks_completed: 2
  files_modified: 9
---

# Phase 15 Plan 01: Middleware Route Protection Summary

**One-liner:** Next.js Edge Runtime middleware with allowlist approach using `getToken()` from next-auth/jwt, consolidating all route protection into a single gate while removing redundant per-page auth checks.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Verify Next.js version (CVE-2025-29927), install jose, create middleware.ts, add AUTH-03 cookie config | 348e642 (15-02 session carried this work) |
| 2 | Remove per-page auth checks from 6 pages, simplify root redirect, fix TypeScript errors | bf557f9 |

Note: Task 1 (middleware.ts creation + auth.ts cookie config) was completed by a prior execution session under 15-02 commits. This session completed Task 2 (per-page auth check removal) and created this SUMMARY.

## What Was Built

### middleware.ts (Edge Runtime route protection)

Created `frontend/src/middleware.ts` with an allowlist approach:

- **Public routes:** `/login`, `/api/auth/*` pass through without authentication
- **Protected routes:** All other routes require valid next-auth session token
- **Redirect behavior:** Unauthenticated users redirected to `/login?callbackUrl=<original-path>`
- **Error handling:** Session error tokens (`SessionExpired`, `RefreshAccessTokenError`) trigger forced re-login with error param preserved
- **Static asset exclusion:** `config.matcher` excludes `_next/static`, `_next/image`, favicon, and image extensions

```typescript
export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
```

### jose@6.1.3 Installation

Installed `jose` as required Edge Runtime peer dependency of `next-auth/jwt`. The `getToken()` function uses `jose` internally for Edge Runtime JWT operations.

### AUTH-03: Cookie Security Config

Added explicit cookie security configuration to `auth.ts`:

```typescript
cookies: {
  sessionToken: {
    name: process.env.NODE_ENV === "production"
      ? "__Secure-authjs.session-token"
      : "authjs.session-token",
    options: { httpOnly: true, sameSite: "lax", path: "/", secure: process.env.NODE_ENV === "production" },
  },
},
```

### Per-Page Auth Check Removal

Removed `if (!session) redirect("/login")` from all 5 pages:

| File | Change |
|------|--------|
| `app/page.tsx` | Simplified to unconditional `redirect("/chat")` — middleware handles unauthenticated |
| `app/chat/page.tsx` | Removed auth guard; kept `auth()` for access token |
| `app/workflows/page.tsx` | Removed both `!session` and `!accessToken` guards; use `accessToken ?? ""` fallback |
| `app/workflows/new/page.tsx` | Removed `!session` guard; `!accessToken` now redirects to `/workflows` |
| `app/workflows/[id]/page.tsx` | Removed `!session` guard; `!accessToken` now redirects to `/workflows` |
| `app/admin/layout.tsx` | Removed "Authentication Required" no-session branch; kept RBAC role check |

## Verification Results

| Check | Result |
|-------|--------|
| `pnpm exec tsc --noEmit` | PASS — zero TypeScript errors |
| middleware.ts exists with getToken-based verification | PASS |
| jose in package.json | PASS — `"jose": "^6.1.3"` |
| Next.js version >= 15.2.3 | PASS — 15.5.12 (CVE-2025-29927 mitigated) |
| No `if (!session) redirect` in target pages | PASS |
| Admin layout RBAC check preserved | PASS — ADMIN_ROLES, hasAdminRole still present |
| config.matcher excludes static assets | PASS |

## Deviations from Plan

### Pre-existing Build Failure (Out of Scope)

The `pnpm run build` command fails on `/settings/memory` and `/settings/channels` pages with:
```
TypeError: Cannot destructure property 'data' of '(0 , e.wV)(...)' as it is undefined.
```

This error is pre-existing (confirmed by testing against HEAD before any Task 2 changes — it was already failing on `/settings/integrations`). These pages are unrelated to the middleware and route protection work.

Logged to deferred items — not fixed as it is out of scope per deviation rules.

### Task 1 Pre-committed by Prior Session

The previous execution agent (which ran 15-02 work) already committed the middleware.ts creation and auth.ts cookie config as part of commit `348e642`. This session confirmed those artifacts are correct and proceeded with Task 2.

## Security Properties Achieved

- **CVE-2025-29927 mitigation:** Next.js 15.5.12 >= 15.2.3 — safe from middleware bypass via `x-middleware-subrequest` header
- **Single auth gate:** Middleware is the sole route protection layer — no redundant per-page checks that could be missed or drift
- **Session error propagation:** Expired and failed refresh tokens are caught at the edge before page code runs
- **Cookie hardening (AUTH-03):** HttpOnly, SameSite=Lax, Secure (production), explicit cookie name

## Self-Check: PASSED

**Files exist:**
- `frontend/src/middleware.ts` — confirmed present
- `frontend/package.json` contains `"jose": "^6.1.3"` — confirmed

**Commits:**
- `bf557f9` — feat(15-01): remove per-page auth checks — confirmed
- `348e642` — feat(15-02): session error detection (includes middleware.ts creation) — confirmed
