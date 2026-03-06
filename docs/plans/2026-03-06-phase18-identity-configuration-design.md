# Phase 18: Identity Configuration — Design

**Date:** 2026-03-06
**Status:** Approved
**Requirements:** IDCFG-01 through IDCFG-08
**Milestone:** v1.3 Production Readiness & Skill Platform

---

## Goal

Keycloak is an optional, runtime-configurable identity provider. The platform boots and works with local auth alone. Admins can enable, configure, and disable SSO from the admin UI without a backend restart.

---

## Architecture

### Core Pattern: Layered Config Resolver with TTL Cache

A `KeycloakConfigResolver` in `security/keycloak_config.py` is the single source of truth for runtime Keycloak configuration. All Keycloak-dependent code (jwt.py, health.py, admin APIs) goes through it.

**Resolution order:**
1. `system_config` DB table — keys prefixed `keycloak.*` (admin-configured, takes priority)
2. Environment variables — `settings.*` (fallback for local dev / initial setup)
3. `None` — no Keycloak config → local-only mode

**Cache:** 60-second TTL (same pattern as JWKS cache in `jwt.py`). Invalidated on admin save.

### Config Storage

Reuse existing `system_config` table (key/JSON value store). No new migration needed.

Keys used:
- `keycloak.issuer_url` — e.g. `https://keycloak.blitz.local/realms/blitz-internal`
- `keycloak.client_id` — e.g. `blitz-portal`
- `keycloak.client_secret_enc` — AES-256-GCM encrypted client secret
- `keycloak.realm` — e.g. `blitz-internal`
- `keycloak.ca_cert_path` — path to CA cert file (optional, local dev)
- `keycloak.enabled` — boolean, can be set to false to disable SSO without removing config

### Frontend Runtime Config

When an admin saves Keycloak config, the backend:
1. Persists to `system_config` (encrypted secret)
2. Invalidates resolver cache + JWKS cache
3. Calls Docker SDK to restart the `frontend` container

On Next.js restart, `auth.ts` fetches `GET /api/internal/keycloak/provider-config` from the backend (using `X-Internal-Key` shared secret header) to get `{client_id, client_secret, issuer, enabled}`. If enabled, the Keycloak provider is included in the next-auth `providers` array.

---

## New Files

| File | Purpose |
|------|---------|
| `backend/security/keycloak_config.py` | KeycloakConfig dataclass + resolver with TTL cache |
| `backend/api/routes/admin_keycloak.py` | Admin Keycloak config/test/disable endpoints + internal provider-config endpoint |
| `frontend/src/app/(authenticated)/admin/identity/page.tsx` | Admin Identity tab UI |
| `frontend/src/app/api/admin/keycloak/[...path]/route.ts` | Next.js proxy for admin Keycloak APIs |

---

## Modified Files

| File | Change |
|------|--------|
| `backend/core/config.py` | Make keycloak_url/realm/client_id/client_secret optional (empty defaults); derive_keycloak_urls skips when empty |
| `backend/security/jwt.py` | Use get_keycloak_config() resolver instead of settings.*; skip Keycloak path when config is None |
| `backend/core/schemas/common.py` | Add auth field to HealthResponse |
| `backend/api/routes/health.py` | Populate health auth field from resolver |
| `backend/main.py` | Register admin_keycloak router |
| `frontend/src/auth.ts` | Fetch internal provider config at startup; conditionally include Keycloak provider |
| `frontend/src/app/login/page.tsx` | Fetch GET /api/auth/config; conditionally render SSO button |

---

## API Endpoints

### Public (no auth)

| Method | Path | Response |
|--------|------|----------|
| GET | `/health` | `{"status": "ok", "auth": "local-only" \| "local+keycloak"}` |
| GET | `/api/auth/config` | `{"auth": "local-only"}` or `{"auth": "local+keycloak", "sso_enabled": true}` |

### Internal (X-Internal-Key header)

| Method | Path | Response |
|--------|------|----------|
| GET | `/api/internal/keycloak/provider-config` | `{"enabled": false}` or `{"enabled": true, "client_id": "...", "client_secret": "...", "issuer": "..."}` |

### Admin (requires `admin` role)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/keycloak/config` | Read current config (secret masked) |
| POST | `/api/admin/keycloak/config` | Save config → invalidate caches → restart frontend |
| POST | `/api/admin/keycloak/test-connection` | Validate JWKS endpoint with submitted (unsaved) config |
| POST | `/api/admin/keycloak/disable` | Set keycloak.enabled=false → invalidate caches → restart frontend |

---

## New Environment Variables

| Variable | Where | Purpose |
|----------|-------|---------|
| `INTERNAL_API_KEY` | backend `.env` + frontend `.env.local` | Shared secret for internal Next.js→backend calls |
| `BACKEND_URL` | frontend `.env.local` | Internal Docker URL for backend (e.g. `http://backend:8000`) |

---

## Security Design

- Client secret stored AES-256-GCM encrypted using `CREDENTIAL_ENCRYPTION_KEY` (already in Settings)
- Internal endpoint (`/api/internal/keycloak/provider-config`) requires `X-Internal-Key` header
- Secret never logged, never returned to browser
- `test-connection` validates submitted config without saving first — admin can verify before committing
- Disable SSO requires confirmation (UI-level guard)
- Audit log entry on every config save/disable action

---

## Plan Breakdown

### Plan 18-01: Keycloak-Optional Boot + Resolver

**Goal:** Backend starts without Keycloak config; `KeycloakConfigResolver` becomes the source of truth for Keycloak config.

**Requirements satisfied:** IDCFG-01, IDCFG-02, IDCFG-03, IDCFG-07

**Tasks:**
1. Make `config.py` Keycloak fields optional (empty defaults); fix `derive_keycloak_urls`
2. Create `security/keycloak_config.py`: `KeycloakConfig` dataclass, `get_keycloak_config()` TTL resolver, `invalidate_keycloak_config_cache()`
3. Refactor `jwt.py`: use `get_keycloak_config()` instead of `settings.*`; return 401 (not 503) when Keycloak not configured and a `blitz-kc-*` token arrives
4. Update `HealthResponse` + `/health` to include `auth` field
5. Add `GET /api/auth/config` public endpoint
6. Tests: boot with no Keycloak env, env-var fallback, DB config override

### Plan 18-02: Admin Keycloak Config API + JWKS Reload + Docker Restart

**Goal:** Admin can configure, test, and disable Keycloak via API; backend hot-reloads JWKS; frontend restarts.

**Requirements satisfied:** IDCFG-04, IDCFG-05, IDCFG-06, IDCFG-08

**Tasks:**
1. Create `api/routes/admin_keycloak.py`: GET/POST config, POST test-connection, POST disable, GET internal provider-config
2. AES-256-GCM encrypt/decrypt for `keycloak.client_secret_enc` using `settings.credential_encryption_key`
3. Cache invalidation: call `invalidate_keycloak_config_cache()` + `invalidate_jwks_cache()` on save/disable
4. Docker SDK restart: `docker.from_env().containers.get("blitz-frontend").restart()` after save
5. Register router in `main.py`
6. Tests: save/load roundtrip with encryption, test-connection mock (reachable + unreachable), disable flow

### Plan 18-03: Frontend — auth.ts + Admin Identity Tab

**Goal:** Login page conditionally shows SSO; admin can configure Keycloak from admin UI.

**Requirements satisfied:** IDCFG-03, IDCFG-04 (UI), IDCFG-05 (UI), IDCFG-08 (UI)

**Tasks:**
1. `auth.ts`: async startup fetch from `BACKEND_URL/api/internal/keycloak/provider-config` with `X-Internal-Key`; conditionally include Keycloak provider
2. Login page: fetch `GET /api/auth/config`; show/hide "Sign in with SSO" button
3. `/admin/identity/page.tsx`: Keycloak config form (Issuer URL, Client ID, Client Secret, Realm, CA Cert Path), Test Connection, Save & Apply, Disable SSO with confirmation modal, status badge
4. Next.js proxy route `api/admin/keycloak/[...path]/route.ts`
5. Add `INTERNAL_API_KEY` + `BACKEND_URL` to docker-compose and `.env.local.example`

---

## IDCFG Requirements Coverage

| Req | Plan | Description |
|-----|------|-------------|
| IDCFG-01 | 18-01 | Backend boots with local auth only when no Keycloak config |
| IDCFG-02 | 18-01 | Health endpoint reports auth mode |
| IDCFG-03 | 18-01 + 18-03 | Login page conditionally shows SSO button |
| IDCFG-04 | 18-02 + 18-03 | Admin can configure Keycloak from admin UI |
| IDCFG-05 | 18-02 + 18-03 | Admin can test connection before saving |
| IDCFG-06 | 18-02 | Config stored in system_config with AES-256-GCM encrypted secret |
| IDCFG-07 | 18-01 | Config resolution: DB → env vars → local-only |
| IDCFG-08 | 18-02 + 18-03 | Admin can disable SSO with confirmation |

---

## Success Criteria

1. `PYTHONPATH=. .venv/bin/pytest tests/ -q` passes with all Keycloak env vars removed from test config
2. `GET /health` returns `{"status": "ok", "auth": "local-only"}` when no Keycloak config
3. Admin saves Keycloak config → `GET /api/auth/config` returns `sso_enabled: true` within 60s
4. Admin UI Identity tab: form saves, test connection works, disable reverts to local-only
5. After Docker restart of frontend, `auth.ts` picks up new Keycloak provider from backend API
6. Frontend build passes: `pnpm run build`
