---
phase: 18-identity-configuration
plan: 02
subsystem: auth
tags: [keycloak, aes-gcm, fastapi, platform-config, admin-api, docker-sdk, internal-api]

# Dependency graph
requires:
  - phase: 18-01
    provides: PlatformConfig model, KeycloakConfigResolver with cache invalidation, keycloak_config DB table

provides:
  - Admin API for Keycloak config (GET/POST /api/admin/keycloak/config)
  - Admin test-connection endpoint (POST /api/admin/keycloak/test-connection)
  - Admin disable SSO endpoint (POST /api/admin/keycloak/disable)
  - Internal provider-config endpoint for Next.js startup (GET /api/internal/keycloak/provider-config)
  - AES-256-GCM encryption of client_secret stored in platform_config
  - Cache invalidation on config save (both JWKS and Keycloak config caches)
  - Frontend container restart via Docker SDK after config change
  - INTERNAL_API_KEY setting in core/config.py for internal endpoint auth

affects: [18-03, frontend-identity-config-ui, next-auth-dynamic-provider]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Internal endpoint auth via X-Internal-Key header (not JWT) — for Next.js server-to-backend calls"
    - "has_secret: bool display policy — never expose client_secret or masked string in admin GET response"
    - "Empty-secret keep-existing pattern — frontend sends empty string to preserve stored secret"
    - "asyncio.to_thread() for Docker SDK container restart (sync SDK, async route)"

key-files:
  created:
    - backend/api/routes/admin_keycloak.py
    - backend/tests/api/test_admin_keycloak.py
  modified:
    - backend/core/config.py
    - backend/main.py

key-decisions:
  - "GET /api/admin/keycloak/config returns has_secret: bool only — never raw or masked client_secret"
  - "POST /api/admin/keycloak/config calls asyncio.to_thread(_restart_frontend_container) — non-blocking Docker restart"
  - "Internal provider-config endpoint uses X-Internal-Key header guard (not JWT) — Next.js can't send JWTs server-side at startup"
  - "Test pattern uses app.dependency_overrides[get_current_user] — NOT patch() — consistent with memory_reindex pattern"
  - "test_encrypt_secret_roundtrip patches both api.routes.admin_keycloak.settings AND os.environ — _encrypt_secret reads settings, _decrypt_client_secret reads os.environ"

patterns-established:
  - "Admin route: Depends(_require_admin) with has_permission('tool:admin') — same as admin_memory pattern"
  - "Internal route: Header(alias='X-Internal-Key') guard at top of handler body"

requirements-completed: [IDCFG-04, IDCFG-05, IDCFG-06, IDCFG-08]

# Metrics
duration: 10min
completed: 2026-03-06
---

# Phase 18 Plan 02: Admin Keycloak Config API + JWKS Reload + Docker Restart Summary

**Admin Keycloak config API with AES-256-GCM secret storage, dual-cache invalidation, Docker frontend restart, and internal provider-config endpoint protected by X-Internal-Key**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-06T08:49:39Z
- **Completed:** 2026-03-06T09:00:10Z
- **Tasks:** 4
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- Admin CRUD API for Keycloak identity configuration (read, save, disable, test-connection)
- Client secret encrypted with AES-256-GCM before persisting to `platform_config.keycloak_client_secret_encrypted`
- Cache invalidation (JWKS + Keycloak config resolver) triggered on every config save or disable
- Frontend Docker container restart via Docker SDK after config change so Next.js picks up new credentials
- Internal endpoint `/api/internal/keycloak/provider-config` serves decrypted credentials to Next.js at startup, protected by `X-Internal-Key` shared secret
- 14 tests covering all endpoints, auth enforcement, has_secret policy, encrypt/decrypt roundtrip, and keep-existing-secret guard; 766 passing in full suite

## Task Commits

Each task was committed atomically:

1. **Task 1: Add INTERNAL_API_KEY setting** - `d6d212c` (feat)
2. **Task 2: admin_keycloak.py router + tests + main.py registration** - `e596588` (feat)
3. **Task 3: encrypt/decrypt roundtrip + keep-existing-secret guard tests** - `361e4d2` (test)
4. **Task 4: Full suite regression + completion marker** - `35a8084` (docs)

## Files Created/Modified

- `backend/api/routes/admin_keycloak.py` (420 lines) - Full admin Keycloak config router with encryption helpers, DB helpers, Docker restart, and 5 endpoints
- `backend/tests/api/test_admin_keycloak.py` (404 lines) - 14 tests covering all endpoints and edge cases
- `backend/core/config.py` - Added `internal_api_key: str = ""` setting
- `backend/main.py` - Registered `admin_keycloak_router` after `admin_memory_router`

## Decisions Made

- GET config response returns `has_secret: bool` only — never the raw or masked `client_secret` string. Frontend shows "Change secret" toggle based on this boolean.
- POST config calls `asyncio.to_thread(_restart_frontend_container)` so Docker SDK (synchronous) doesn't block the async event loop. The HTTP response returns immediately; restart happens in background thread.
- Internal endpoint uses `X-Internal-Key` header guard (not JWT) because Next.js server-side startup code can't authenticate via JWT before it has credentials from the backend.
- Test pattern follows `test_memory_reindex.py` pattern using `app.dependency_overrides[get_current_user]` with SQLite in-memory DB — not `patch()`. The plan spec had `patch()` tests but FastAPI dependency injection requires overrides at the `app` level to work.
- `test_encrypt_secret_roundtrip` patches both `api.routes.admin_keycloak.settings` (for `_encrypt_secret`) AND `os.environ` (for `_decrypt_client_secret`) because the two functions read the key from different sources.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test pattern corrected from patch() to app.dependency_overrides**
- **Found during:** Task 2 (running tests after implementing router)
- **Issue:** Plan spec tests used `patch("security.deps.get_current_user", return_value=_admin_user())` but FastAPI resolves dependencies via the dependency injection system — patching the function doesn't intercept the DI chain. All 9 JWT-gated tests returned 401.
- **Fix:** Rewrote tests using `app.dependency_overrides[get_current_user] = make_admin_ctx` pattern (consistent with existing `test_memory_reindex.py` in the codebase). Added SQLite in-memory DB fixture following the same pattern.
- **Files modified:** `backend/tests/api/test_admin_keycloak.py`
- **Verification:** All 14 tests pass
- **Committed in:** `e596588` (Task 2 commit)

**2. [Rule 1 - Bug] Encrypt roundtrip test patched both settings and os.environ**
- **Found during:** Task 3 (running encrypt roundtrip test)
- **Issue:** `_encrypt_secret` reads key from `settings.credential_encryption_key`, but `_decrypt_client_secret` reads from `os.environ.get("CREDENTIAL_ENCRYPTION_KEY")` first. Test using only `patch.dict(os.environ)` encrypted with the real (empty) settings key but decrypted with the test key — `InvalidTag` error.
- **Fix:** Added `patch("api.routes.admin_keycloak.settings")` alongside `patch.dict(os.environ)` so both encrypt and decrypt paths see the same test key.
- **Files modified:** `backend/tests/api/test_admin_keycloak.py`
- **Verification:** `test_encrypt_secret_roundtrip` passes
- **Committed in:** `361e4d2` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs in plan spec's test code)
**Impact on plan:** Both auto-fixes were necessary for the tests to work correctly. Implementation code was correct as specified; only test code required adjustment.

## Issues Encountered

None — router implementation matched the plan spec exactly. Test pattern correction was the only non-trivial deviation.

## User Setup Required

To enable the internal provider-config endpoint, add to `backend/.env`:

```bash
INTERNAL_API_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

This key must also be set in the Next.js environment as `BACKEND_INTERNAL_API_KEY` (for use in `auth.ts` startup fetch).

## Next Phase Readiness

- Admin Keycloak Config API is complete and tested (IDCFG-04, IDCFG-05, IDCFG-06, IDCFG-08)
- Plan 18-03 (Frontend admin UI for Keycloak config) can read from `GET /api/admin/keycloak/config` and save via `POST /api/admin/keycloak/config`
- `internal_api_key` setting is in place; Next.js auth.ts can call `GET /api/internal/keycloak/provider-config` to fetch runtime Keycloak credentials

## Self-Check: PASSED

- FOUND: `backend/api/routes/admin_keycloak.py`
- FOUND: `backend/tests/api/test_admin_keycloak.py`
- FOUND: `.planning/phases/18-identity-configuration/18-02-SUMMARY.md`
- FOUND commit: `d6d212c` (feat: internal_api_key)
- FOUND commit: `e596588` (feat: admin_keycloak router)
- FOUND commit: `361e4d2` (test: encrypt roundtrip + keep-existing-secret)
- FOUND commit: `35a8084` (docs: complete plan)

---
*Phase: 18-identity-configuration*
*Completed: 2026-03-06*
