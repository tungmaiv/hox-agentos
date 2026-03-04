---
phase: 13-local-auth
plan: "02"
subsystem: frontend-auth
tags: [auth, next-auth, credentials, admin, frontend, local-auth, users, groups]
dependency_graph:
  requires:
    - local_auth_models
    - local_jwt_creation
    - dual_issuer_jwt_dispatch
    - local_login_endpoint
    - admin_local_user_crud
    - admin_local_group_crud
  provides:
    - credentials_provider_nextauth
    - dual_login_page
    - admin_users_tab
    - admin_group_management
    - local_auth_proxy_routes
  affects:
    - frontend/src/auth.ts
    - frontend/src/app/login/page.tsx
    - frontend/src/app/admin/layout.tsx
tech_stack:
  added: []
  patterns:
    - next-auth Credentials provider with manual JWT decode (no verification — backend already verified)
    - 8-hour local token expiry with SessionExpired error for re-login redirect
    - Next.js 15 async params pattern in all dynamic route handlers
    - 204 body-less response handling in proxy routes
    - Copyable one-time password toast (dismissed = gone forever)
key_files:
  created:
    - frontend/src/app/login/page.tsx (redesigned — dual login with SSO button + credentials form)
    - frontend/src/app/api/auth/local/token/route.ts
    - frontend/src/app/admin/users/page.tsx
    - frontend/src/app/api/admin/local/users/route.ts
    - frontend/src/app/api/admin/local/users/[id]/route.ts
    - frontend/src/app/api/admin/local/users/[id]/groups/route.ts
    - frontend/src/app/api/admin/local/users/[id]/groups/[groupId]/route.ts
    - frontend/src/app/api/admin/local/users/[id]/roles/route.ts
    - frontend/src/app/api/admin/local/users/[id]/roles/[role]/route.ts
    - frontend/src/app/api/admin/local/groups/route.ts
    - frontend/src/app/api/admin/local/groups/[id]/route.ts
  modified:
    - frontend/src/auth.ts
    - frontend/src/app/admin/layout.tsx
decisions:
  - "Credentials provider authorize() calls backend directly (server-side fetch) — the token proxy route is supplementary for completeness only"
  - "JWT payload decoded client-side without re-verification (base64url decode only) — backend already verified HS256 signature"
  - "Local token expiry uses error='SessionExpired' (not 'RefreshAccessTokenError') so login page can show distinct message"
  - "Admin Users page is Client Component with useEffect+fetch (no SWR/React Query) — sufficient for ~100 users at MVP scale"
  - "Password toast uses clipboard API — shown once in the same render; dismissed = gone forever per CONTEXT.md design decision"
  - "Edit user dialog does not show groups/roles assignment — update is limited to username/email/password; group/role changes handled separately (keeps edit dialog simple)"
metrics:
  duration: "11 minutes"
  completed: "2026-03-03"
  tasks_completed: 2
  files_created: 11
  files_modified: 2
---

# Phase 13 Plan 02: Frontend Local Auth Summary

**One-liner:** Dual-provider NextAuth (Keycloak SSO + Credentials), redesigned /login page with credentials form, and /admin Users tab with full CRUD for local users/groups via modal dialogs and 8 proxy routes.

## What Was Built

### Task 1: NextAuth Credentials provider, login page redesign, and login proxy route (commit: f5d066f)

**`frontend/src/auth.ts` — dual-provider configuration:**
- Added `Credentials` provider that calls backend `POST /api/auth/local/token` from the server side
- JWT payload decoded client-side (base64url, no re-verification — backend verified HS256 signature)
- Extracts `id`, `name`, `email`, `accessToken`, `realmRoles` from JWT payload
- Updated `jwt()` callback:
  - `credentials` path: stores `accessToken`, `realmRoles`, 8-hour `expiresAt`, `authProvider: "credentials"` — no refresh attempt
  - `keycloak` path: unchanged RS256 refresh flow, now tagged with `authProvider: "keycloak"`
  - On local token expiry: returns `error: "SessionExpired"` for client redirect
- Updated `session()` callback: propagates `realmRoles` to session for admin layout RBAC check

**`frontend/src/app/login/page.tsx` — redesigned login page:**
- Removed auto-redirect `useEffect`
- Split layout: Keycloak SSO button + divider + credentials form (username/password)
- Session expiry notice shown when `?error=SessionExpired` query param present
- Client component wrapped in `Suspense` (required for `useSearchParams()` in Next.js 15)
- Credentials form: `signIn("credentials", { redirect: false })` + inline error message + `router.push("/chat")` on success

**`frontend/src/app/api/auth/local/token/route.ts` — proxy:**
- Pass-through POST proxy to backend `/api/auth/local/token`

### Task 2: Admin Users tab with user/group CRUD, proxy routes, and layout update (commit: 224fd49)

**`frontend/src/app/admin/layout.tsx`:**
- Added `{ label: "Users", href: "/admin/users" }` as 8th tab (between Credentials and AI Builder — 9 tabs total)

**8 Next.js proxy routes under `/api/admin/local/`:**
All follow the existing `getAccessToken()` + Authorization header pattern from `credentials/route.ts`.
- `users/route.ts` — GET list, POST create
- `users/[id]/route.ts` — GET detail, PUT update, DELETE
- `users/[id]/groups/route.ts` — POST assign groups
- `users/[id]/groups/[groupId]/route.ts` — DELETE remove from group
- `users/[id]/roles/route.ts` — POST add roles
- `users/[id]/roles/[role]/route.ts` — DELETE remove role
- `groups/route.ts` — GET list, POST create
- `groups/[id]/route.ts` — PUT update, DELETE

All routes handle Next.js 15 async params (`Promise<{ id: string }>` pattern) and return `new NextResponse(null, { status: 204 })` for 204 responses.

**`frontend/src/app/admin/users/page.tsx` — Admin Users tab:**

Two sections stacked vertically:

**Local Users section:**
- Table: Username, Email, Groups (comma-separated), Roles (resolved, comma-separated), Status (Active/Inactive badge), Actions
- Text search filters by username or email
- Create User dialog: username, email, password (with complexity hint), groups (checkbox multi-select from loaded groups), direct roles (checkbox multi-select from 5 known roles)
- Edit User dialog: username, email, password (optional — blank = keep current)
- Delete User: confirmation dialog showing username
- Password toast: appears after creation with copyable password; dismissed = gone forever

**Groups section:**
- Table: Name, Description, Roles, Members (count), Actions
- Text search filters by name or description
- Create Group dialog: name, description, roles (checkbox multi-select)
- Edit Group dialog: same fields; roles replace entire set on save
- Delete Group: confirmation dialog showing group name

## Verification Results

```
pnpm exec tsc --noEmit
# → 0 errors (Task 1 verification)

docker exec hox-agentos-frontend-1 pnpm run build
# → 0 errors, all routes built:
#   /admin/users                      4.43 kB
#   /api/admin/local/groups           250 B
#   /api/admin/local/groups/[id]      250 B
#   /api/admin/local/users            250 B
#   /api/admin/local/users/[id]       250 B
#   /api/admin/local/users/[id]/groups     250 B
#   /api/admin/local/users/[id]/groups/[groupId] 250 B
#   /api/admin/local/users/[id]/roles      250 B
#   /api/admin/local/users/[id]/roles/[role] 250 B
#   /api/auth/local/token             250 B
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Buffer.from() type error on split result**
- **Found during:** Task 1 TypeScript check
- **Issue:** `access_token.split(".")[1]` returns `string | undefined` in TypeScript strict mode. `Buffer.from(string | undefined, "base64url")` raises TS2769 — no overload matches.
- **Fix:** Extract to `const payloadPart = access_token.split(".")[1] ?? "";` before passing to `Buffer.from()`.
- **Files modified:** `frontend/src/auth.ts`
- **Commit:** f5d066f

**2. [Rule 2 - Missing Critical] Wrapped login page in Suspense**
- **Found during:** Task 1 — recognizing Next.js 15 requirement
- **Issue:** `useSearchParams()` (used to detect `?error=SessionExpired`) requires a Suspense boundary in Next.js 15. Without it, the route would fail at build time.
- **Fix:** Split into `LoginForm` inner component and `LoginPage` wrapper with `<Suspense>`.
- **Files modified:** `frontend/src/app/login/page.tsx`
- **Commit:** f5d066f

## Self-Check: PASSED

Files exist:
- `frontend/src/auth.ts` — FOUND
- `frontend/src/app/login/page.tsx` — FOUND
- `frontend/src/app/api/auth/local/token/route.ts` — FOUND
- `frontend/src/app/admin/layout.tsx` — FOUND
- `frontend/src/app/admin/users/page.tsx` — FOUND
- `frontend/src/app/api/admin/local/users/route.ts` — FOUND
- `frontend/src/app/api/admin/local/users/[id]/route.ts` — FOUND
- `frontend/src/app/api/admin/local/groups/route.ts` — FOUND
- `frontend/src/app/api/admin/local/groups/[id]/route.ts` — FOUND

Commits exist:
- `f5d066f` feat(13-02): add Credentials provider, redesign login page, add token proxy — FOUND
- `224fd49` feat(13-02): add admin Users tab with user/group CRUD and proxy routes — FOUND
