---
phase: 18-identity-configuration
plan: "01"
subsystem: auth
tags: [keycloak, jwt, fastapi, alembic, postgresql, security, platform-config]

# Dependency graph
requires:
  - phase: 17-performance-embedding-sidecar
    provides: RequestSessionMiddleware and session management used by DB resolver
  - phase: 15-auth-hardening
    provides: local auth (validate_local_token) that jwt.py still dispatches to

provides:
  - Keycloak-optional backend boot (keycloak_url defaults to empty string)
  - platform_config ORM model + migration 021 (single-row identity provider config)
  - KeycloakConfigResolver with 60s TTL cache (DB → env → None resolution order)
  - GET /health returns auth field ("local-only" or "local+keycloak")
  - GET /api/auth/config returns auth mode + sso_enabled (public endpoint)

affects: [19-admin-identity-config, 18-03-sso-login-page]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Resolution order pattern: DB (runtime) → env vars (startup) → None (local-only)"
    - "Module-level TTL cache with monotonic clock (same pattern as JWKS cache)"
    - "Single-row table invariant: always upsert id=1, all keycloak fields nullable"
    - "KeycloakConfig dataclass is frozen (immutable) — safe to cache and pass around"

key-files:
  created:
    - backend/core/models/platform_config.py
    - backend/alembic/versions/83f730920f5a_add_platform_config.py
    - backend/security/keycloak_config.py
    - backend/api/routes/auth_config.py
    - backend/tests/security/test_keycloak_config.py
  modified:
    - backend/core/config.py
    - backend/core/models/__init__.py
    - backend/security/jwt.py
    - backend/api/routes/health.py
    - backend/core/schemas/common.py
    - backend/main.py
    - backend/tests/test_jwt.py
    - backend/tests/test_health.py
    - backend/tests/test_local_auth.py
    - backend/tests/security/test_jwks_lock.py

key-decisions:
  - "IDCFG-06: platform_config uses typed columns (not system_config key/value) — type safety + simpler queries"
  - "Single-row invariant: id=1 always, no multi-row support in v1.2"
  - "client_secret stored AES-256-GCM encrypted as JSON string (not JSONB) — avoids JSONB variant issues in SQLite tests"
  - "TTL cache is 60s (vs JWKS 300s) — shorter because admin config changes should propagate quickly"
  - "Resolver returns None on any DB error — safe fallback to local-only, never raises"
  - "invalidate_keycloak_config_cache() + invalidate_jwks_cache() both exported for Plan 18-02 admin save workflow"

patterns-established:
  - "get_keycloak_config() is the single source of truth for Keycloak config — jwt.py and routes both import from security.keycloak_config"
  - "Public endpoints (no JWT) patched via api.routes.health.get_keycloak_config and api.routes.auth_config.get_keycloak_config"
  - "Test pattern: patch get_keycloak_config at import site; use TEST_KC_CONFIG constant"

requirements-completed: [IDCFG-01, IDCFG-02, IDCFG-03, IDCFG-06, IDCFG-07]

# Metrics
duration: 45min
completed: 2026-03-06
---

# Phase 18 Plan 01: Keycloak-Optional Boot + Resolver Summary

**Optional Keycloak boot via platform_config DB table with KeycloakConfigResolver (TTL cache, DB→env→None), jwt.py refactored to use resolver, health and auth/config endpoints reflect live auth mode**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-03-06T08:20:00Z
- **Completed:** 2026-03-06T09:05:00Z
- **Tasks:** 4
- **Files modified:** 14

## Accomplishments
- Backend starts with no Keycloak env vars — all four Keycloak fields now default to empty string
- PlatformConfig ORM model (single-row, id=1) with typed Keycloak columns + Alembic migration 021
- KeycloakConfigResolver reads platform_config DB first, falls back to env vars, returns None for local-only mode; 60s TTL cache; invalidation function for admin workflows
- jwt.py refactored: _get_jwks/_validate_keycloak_token accept KeycloakConfig, validate_token calls get_keycloak_config() per request
- GET /health returns auth field; GET /api/auth/config returns auth + sso_enabled (public endpoint for frontend login page)
- 752 tests passing (up from 743 — 9 new tests added)

## Task Commits

Each task was committed atomically:

1. **Task 1: Keycloak optional config + PlatformConfig ORM + migration** - `da302ad` (feat)
2. **Task 2: KeycloakConfigResolver (keycloak_config.py + tests)** - `6315045` (feat)
3. **Task 3: Refactor jwt.py to use resolver** - `49a007b` (feat)
4. **Task 4: Health endpoint auth field + /api/auth/config route** - `4d21554` (feat)

## Files Created/Modified
- `backend/core/config.py` - Make keycloak_url/realm/client_id/client_secret optional (default "")
- `backend/core/models/platform_config.py` - Single-row ORM model for runtime Keycloak config
- `backend/core/models/__init__.py` - Register PlatformConfig for Alembic autogenerate
- `backend/alembic/versions/83f730920f5a_add_platform_config.py` - Migration 021 (revises 020)
- `backend/security/keycloak_config.py` - KeycloakConfig dataclass + async resolver with TTL cache
- `backend/security/jwt.py` - Refactored to use get_keycloak_config(); _get_jwks/_validate_keycloak_token accept config
- `backend/api/routes/health.py` - Updated to return auth field via get_keycloak_config()
- `backend/api/routes/auth_config.py` - New public endpoint GET /api/auth/config
- `backend/core/schemas/common.py` - HealthResponse gains auth field
- `backend/main.py` - Register auth_config_router
- `backend/tests/security/test_keycloak_config.py` - 4 tests for resolver (resolution order, TTL, invalidation)
- `backend/tests/test_jwt.py` - Updated to patch get_keycloak_config; TEST_KC_CONFIG constant; new local-only test
- `backend/tests/test_health.py` - 5 new tests for auth field and /api/auth/config
- `backend/tests/test_local_auth.py` - Updated test_validate_token_routes_keycloak_issuer to match new signature
- `backend/tests/security/test_jwks_lock.py` - Updated _get_jwks() call to pass config arg

## Decisions Made
- IDCFG-06: typed-column platform_config table chosen over system_config key/value — type safety, simpler queries, explicit migration path
- Single-row invariant (id=1) — no multi-row support needed for v1.2, simplifies all code
- client_secret encrypted as JSON string (not JSONB) — avoids JSONB variant issues across SQLite test + PostgreSQL prod
- 60s TTL vs JWKS 300s — admin config changes should propagate within 1 minute
- Resolver never raises on DB failure — returns None (local-only fallback), always safe
- Both invalidate functions exported for Plan 18-02 (admin config save invalidates both caches)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_jwks_lock.py: _get_jwks() now requires config argument**
- **Found during:** Task 3 (jwt.py refactor)
- **Issue:** After refactoring _get_jwks(config: KeycloakConfig), the existing JWKS lock test called _get_jwks() without args → TypeError
- **Fix:** Updated test to pass _TEST_CONFIG; updated slow_fetch() mock signature to accept config arg
- **Files modified:** backend/tests/security/test_jwks_lock.py
- **Verification:** test_concurrent_jwks_refresh_calls_remote_once PASSED
- **Committed in:** 49a007b (Task 3 commit)

**2. [Rule 1 - Bug] Fixed test_local_auth.py: test_validate_token_routes_keycloak_issuer assertion mismatch**
- **Found during:** Task 4 (full test suite run)
- **Issue:** test asserted mock_kc.assert_called_once_with(token) but _validate_keycloak_token now called with (token, kc_config)
- **Fix:** Added get_keycloak_config mock; updated assert to assert_called_once_with(token, mock_kc_config); used TEST_ISSUER constant
- **Files modified:** backend/tests/test_local_auth.py
- **Verification:** test_validate_token_routes_keycloak_issuer PASSED; 752 tests passing
- **Committed in:** 4d21554 (Task 4 commit)

**3. [Rule 1 - Bug] Alembic autogenerate included unrelated schema diffs**
- **Found during:** Task 1 (migration generation)
- **Issue:** autogenerate detected checkpoint table removals, index changes, nullable column diffs — all pre-existing DB drift, not related to platform_config
- **Fix:** Manually rewrote migration to only include create_table("platform_config") + downgrade drop_table
- **Files modified:** backend/alembic/versions/83f730920f5a_add_platform_config.py
- **Verification:** Migration file only contains platform_config DDL; no unrelated ops
- **Committed in:** da302ad (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (3 Rule 1 bugs)
**Impact on plan:** All auto-fixes were direct consequences of the refactor changing function signatures. No scope creep.

## Issues Encountered
- Alembic autogenerate produced noisy diffs from pre-existing DB drift (checkpoint tables, indexes). Manually cleaned migration to keep only platform_config DDL.

## Next Phase Readiness
- Plan 18-02 (Admin Config API) can use get_keycloak_config(), invalidate_keycloak_config_cache(), invalidate_jwks_cache() directly
- Plan 18-03 (SSO login page) can call GET /api/auth/config to determine whether to show SSO button
- platform_config migration 021 must be applied before admin config save endpoints work

---
*Phase: 18-identity-configuration*
*Completed: 2026-03-06*

## Self-Check: PASSED

All created files verified present:
- FOUND: backend/core/models/platform_config.py
- FOUND: backend/alembic/versions/83f730920f5a_add_platform_config.py
- FOUND: backend/security/keycloak_config.py
- FOUND: backend/api/routes/auth_config.py
- FOUND: backend/tests/security/test_keycloak_config.py

All task commits verified in git history:
- FOUND: da302ad (Task 1)
- FOUND: 6315045 (Task 2)
- FOUND: 49a007b (Task 3)
- FOUND: 4d21554 (Task 4)

Test suite: 752 passed, 1 skipped — all passing.
