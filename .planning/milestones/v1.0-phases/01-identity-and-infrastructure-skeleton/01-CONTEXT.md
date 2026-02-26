# Phase 1: Identity and Infrastructure Skeleton - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Stand up all Docker Compose infrastructure services, register `blitz-agentos` client in external Keycloak (`keycloak.blitz.local`), implement 3-gate security (JWT validation -> RBAC permission check -> Tool ACL), create FastAPI + Next.js application skeletons with audit logging. Every request to the platform must be authenticated, authorized, and audit-logged after this phase.

Keycloak is external shared infrastructure (NOT in Docker Compose). Realm `blitz-internal` already exists with 5 roles, 14 groups, 15 users.

</domain>

<decisions>
## Implementation Decisions

### Frontend Auth UX Flow
- Auto-redirect to Keycloak login when unauthenticated — no Blitz-branded landing page. User hits `/` -> immediately redirected to Keycloak SSO -> lands on `/chat` after auth.
- Silent token refresh in background when session nears expiry. Only redirect to Keycloak login if refresh token is also expired. User should not notice token rotation.
- Toast notifications for auth errors: 401 -> "Session expired, re-authenticating..." (non-blocking toast). 403 -> "You don't have permission for this action" (non-blocking toast). No inline chat messages for auth errors in Phase 1.
- Minimal header with user info: top bar showing user's name/email from JWT + logout button. No avatar, no settings page — just enough to confirm identity.

### RBAC Permission Granularity
- 5-role permission mapping is final as designed:
  - `employee`: chat, tool:email, tool:calendar, tool:project
  - `manager`: all employee + tool:reports, workflow:create
  - `team-lead`: all manager + workflow:approve
  - `it-admin`: all permissions + tool:admin, sandbox:execute, registry:manage
  - `executive`: chat, tool:reports (read-only)
- Multiple roles = union of all permissions. No deny mechanism in RBAC. Tool ACL (Gate 3) is the only way to explicitly deny.
- 403 responses include specific information: which permission is missing, what roles the user has, and a hint to contact IT admin. Example: "Permission denied: requires tool:email. Your roles: [executive]. Contact IT admin."
- Seed test ACL entries in Phase 1 for dev testing — e.g., explicitly deny one tool for a test user to verify Gate 3 works end-to-end.

### Dev Workflow & Testing
- **Local dev mode:** Run backend (`uvicorn --reload`) and frontend (`pnpm dev`) on the host machine. Only infrastructure services (postgres, redis, litellm) run in Docker Compose. Faster reload, easier debugging.
- **JWT testing:** Use real tokens from `keycloak.blitz.local` — no mock JWKS. Tests prove real integration works. Requires network access to Keycloak during test runs.
- **Automated tests:** Pytest suite covering security gates — JWT validation (valid/invalid/expired), RBAC permission checks, Tool ACL checks, health endpoint. Not full TDD, but critical security paths must be tested.
- **Secrets management:** `.env` (gitignored) for Docker Compose and app config. `.dev-secrets` (gitignored) for Keycloak admin password, test user passwords, and other credentials Claude agents need. `.env.example` committed as template. `.dev-secrets.example` committed as template.

### Claude's Discretion
- Loading/spinner design during Keycloak redirect
- Exact toast notification styling and positioning
- Test file organization within `backend/tests/`
- Alembic migration naming convention
- Docker Compose health check intervals and retry counts

</decisions>

<specifics>
## Specific Ideas

- Design doc and implementation plan already exist at `docs/plans/2026-02-24-phase-1-design.md` and `docs/plans/2026-02-24-phase-1-implementation.md` — these contain detailed file structures, code patterns, and task breakdowns that should be used as the primary reference.
- Keycloak realm is `blitz-internal` (not `blitz` as in some docs) at `keycloak.blitz.local` — this is external, accessed over network, not localhost.
- `next-auth` v5 with Keycloak provider for frontend auth — JWT stored in server-side session only, never localStorage.
- Docker Compose uses `blitz-net` bridge network. Services: postgres, redis, litellm, backend, frontend, celery-worker.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-identity-and-infrastructure-skeleton*
*Context gathered: 2026-02-24*
