---
phase: 18
plan: "03"
subsystem: frontend
tags: [identity, auth, keycloak, admin-ui, next-auth, idcfg]
dependency_graph:
  requires: [18-02]
  provides: [IDCFG-03, IDCFG-04, IDCFG-05, IDCFG-08]
  affects: [frontend/src/auth.ts, frontend/src/app/login/page.tsx, frontend/src/app/(authenticated)/admin/identity]
tech_stack:
  added: []
  patterns: [next-auth dynamic provider loading, conditional SSO button, admin proxy route pattern]
key_files:
  created:
    - frontend/src/app/api/auth/config/route.ts
    - frontend/src/app/api/admin/keycloak/[...path]/route.ts
    - frontend/src/app/(authenticated)/admin/identity/page.tsx
  modified:
    - frontend/src/auth.ts
    - frontend/src/app/login/page.tsx
    - frontend/src/app/(authenticated)/admin/layout.tsx
    - docker-compose.yml
    - .dev-secrets.example
decisions:
  - "[18-03]: Remove explicit providers type annotation from auth.ts — let TypeScript infer, avoids Parameters<typeof NextAuth>[0]['providers'] resolution failure"
  - "[18-03]: Identity tab placed between Permissions and Config in ADMIN_TABS — locked by CONTEXT.md decision"
  - "[18-03]: /api/admin/keycloak/[...path] created as specific proxy alongside existing catch-all — explicit routing for keycloak admin routes"
metrics:
  duration: "16 minutes"
  completed_date: "2026-03-06"
  tasks: 4
  files: 7
requirements: [IDCFG-03, IDCFG-04, IDCFG-05, IDCFG-08]
---

# Phase 18 Plan 03: Frontend — auth.ts Dynamic Provider + Admin Identity Tab Summary

**One-liner:** auth.ts conditionally loads Keycloak provider via backend API at startup; admin Identity tab provides full SSO configuration UI with test-connection and disable-SSO actions.

## What Was Built

### Task 1: auth.ts dynamic Keycloak provider (IDCFG-03)

`frontend/src/auth.ts` now fetches Keycloak provider configuration from the backend at Next.js module initialization:

- `fetchKeycloakProviderConfig()` calls `GET /api/internal/keycloak/provider-config` using `X-Internal-Key: ${INTERNAL_API_KEY}`
- Falls back gracefully to `{ enabled: false }` when `INTERNAL_API_KEY` is missing or backend is unreachable
- `providers` array conditionally includes the Keycloak provider only when `enabled: true`
- `refreshAccessToken()` uses `keycloakProviderConfig.issuer/client_id/client_secret` instead of env vars
- `INTERNAL_API_KEY` added to `docker-compose.yml` frontend service environment and documented in `.dev-secrets.example`

### Task 2: Login page conditional SSO button (IDCFG-03)

`frontend/src/app/login/page.tsx`:
- Added `ssoEnabled: boolean | null` state (null = loading, hidden by design)
- `useEffect` fetches `/api/auth/config` on mount to determine SSO availability
- SSO button and divider hidden when `null` or `false` — shown only when `true`
- Created `frontend/src/app/api/auth/config/route.ts` — public Next.js proxy to backend `/api/auth/config`

### Task 3: Admin Keycloak API proxy (IDCFG-04, IDCFG-05, IDCFG-08)

`frontend/src/app/api/admin/keycloak/[...path]/route.ts`:
- Catch-all proxy for `GET` and `POST` to `/api/admin/keycloak/*`
- Injects `Authorization: Bearer <accessToken>` from server-side session
- Follows same pattern as existing `api/admin/memory/reindex/route.ts`
- Routes: `/config` (GET/POST), `/test-connection` (POST), `/disable` (POST)

### Task 4: Admin Identity page + layout tab (IDCFG-04, IDCFG-05, IDCFG-08)

`frontend/src/app/(authenticated)/admin/identity/page.tsx` (486 lines):
- Status badge: "SSO Active" (green) or "Local-only" (gray)
- Keycloak config form: Issuer URL, Client ID, Client Secret (toggle), Realm, CA Cert Path
- "Change secret" toggle when `has_secret=true` — never reveals saved secret value
- Test Connection: inline result (not toast, not modal) — `Connected — JWKS endpoint reachable, N key(s) found.`
- Save & Apply: saves config, refreshes state, shows restart notice
- Disable SSO section: only shown when SSO is active; confirmation dialog with locked text
- Locked confirmation text: "Disabling SSO will prevent new Keycloak logins. Users currently logged in via SSO will remain logged in until their session expires. Continue?"

`frontend/src/app/(authenticated)/admin/layout.tsx`:
- Identity tab inserted between Permissions and Config (locked position per CONTEXT.md)

## Commits

| Hash | Description |
|------|-------------|
| 371f5e1 | feat(18-03): add INTERNAL_API_KEY to frontend env in docker-compose |
| 245f26d | feat(18-03): auth.ts fetches Keycloak provider config from backend at startup (IDCFG-03) |
| bfdea7a | feat(18-03): login page conditionally shows SSO button based on auth config (IDCFG-03) |
| 0b19354 | feat(18-03): add Next.js proxy for admin Keycloak API (IDCFG-04, IDCFG-05, IDCFG-08) |
| 224963c | feat(18-03): admin Identity tab with Keycloak config form + test + disable (IDCFG-04, IDCFG-05, IDCFG-08) |

## Verification

- `pnpm exec tsc --noEmit` — passes after each task
- `pnpm run build` — passes; `/admin/identity` (2.66 kB) and `/api/admin/keycloak/[...path]` present in build output
- Identity tab appears between Permissions and Config in ADMIN_TABS
- SSO button hidden during load (null) and when sso_enabled=false
- Client secret field shows toggle when has_secret=true; never reveals saved value
- Disable SSO confirmation dialog text matches CONTEXT.md exactly

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] providers type annotation incompatible with next-auth**
- **Found during:** Task 1 TypeScript check
- **Issue:** `Parameters<typeof NextAuth>[0]["providers"]` failed to resolve — NextAuth accepts `NextAuthConfig | ((request) => NextAuthConfig)` so `[0]` resolves to a union, not a single config type
- **Fix:** Removed explicit type annotation; TypeScript infers correct type from the array literal
- **Files modified:** `frontend/src/auth.ts`
- **Commit:** 245f26d

## Self-Check: PASSED

All 7 required files exist. All min_lines requirements met (486/200, 71/40, 23/20). All 5 commits verified. Build passes.
