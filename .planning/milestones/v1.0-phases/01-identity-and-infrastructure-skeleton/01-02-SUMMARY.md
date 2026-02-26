---
phase: 01-identity-and-infrastructure-skeleton
plan: "02"
subsystem: auth
tags: [jwt, rs256, keycloak, jwks, python-jose, fastapi, httpx, pytest, tdd, structlog]

# Dependency graph
requires:
  - phase: 01-01
    provides: core/config.py Settings (keycloak_issuer, keycloak_client_id, keycloak_jwks_url), structlog, FastAPI app factory
provides:
  - UserContext TypedDict in core/models/user.py (user_id, email, username, roles, groups)
  - JWKS cache + RS256 validation in security/jwt.py (validate_token, _get_jwks, _fetch_jwks_from_remote)
  - get_current_user() FastAPI dependency in security/deps.py
  - 7-test JWT validation suite covering all failure modes
  - conftest.py with minimal env vars for all unit tests
affects:
  - 01-03 (database models — no direct dependency, but all auth routes will use get_current_user())
  - 01-04 (FastAPI routes — /api/agents/chat and all protected routes use get_current_user())
  - 02+ (RBAC gate — reads UserContext.roles; Tool ACL gate — reads UserContext.user_id)
  - All agent/tool/memory operations — receive UserContext from gate 1

# Tech tracking
tech-stack:
  added:
    - cryptography>=46.0.0 (dev dep — for test RSA key generation; already transitively present via python-jose[cryptography])
  patterns:
    - JWKS cached in-process for 300s via module-level _JWKS_CACHE dict and _jwks_fetched_at monotonic timestamp
    - _fetch_jwks_from_remote() separated from _get_jwks() cache logic to enable precise cache-hit testing
    - Settings accessed at module import time in security/jwt.py (safe because conftest.py sets env vars before collection)
    - conftest.py uses os.environ.setdefault() to provide fallback env vars without overriding real .env values

key-files:
  created:
    - backend/core/models/user.py
    - backend/security/__init__.py
    - backend/security/jwt.py
    - backend/security/deps.py
    - backend/tests/test_jwt.py
    - backend/tests/conftest.py
  modified:
    - backend/pyproject.toml (added cryptography to dev deps)
    - backend/tests/test_jwt.py (make_token reads iss/aud from live settings for cross-test isolation)

key-decisions:
  - "_fetch_jwks_from_remote() is a separate function from _get_jwks() so the cache test can mock only the HTTP call, not the cache logic"
  - "conftest.py uses os.environ.setdefault() so real .env values are not overridden when present"
  - "make_token fixture reads iss/aud from core.config.settings at call time — not hardcoded — to survive test_config.py reloading modules"
  - "HTTPBearer(auto_error=False) used in deps.py so get_current_user() can return a specific 401 message when Authorization header is absent"

patterns-established:
  - "get_current_user(): all protected FastAPI routes declare Depends(get_current_user) to obtain UserContext"
  - "validate_token(): never logs the raw token — only error_type and error message"
  - "UserContext TypedDict: internal data class passed between functions (not Pydantic BaseModel)"
  - "test_jwt.py: mock _fetch_jwks_from_remote for cache tests; mock _get_jwks directly for validation logic tests"

requirements-completed:
  - AUTH-02

# Metrics
duration: 4min
completed: "2026-02-24"
---

# Phase 1 Plan 02: JWT Validation Gate (Gate 1) Summary

**RS256 JWT validation against Keycloak JWKS with 300s in-process cache, UserContext TypedDict extraction, FastAPI get_current_user() dependency, and 7-test TDD suite covering all failure modes**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-24T14:04:08Z
- **Completed:** 2026-02-24T14:08:39Z
- **Tasks:** 2 (TDD: RED then GREEN)
- **Files modified:** 7

## Accomplishments

- `UserContext` TypedDict in `core/models/user.py` with user_id (UUID from sub), email, username (preferred_username), roles (realm_access.roles), groups
- `security/jwt.py` with JWKS TTL cache (300s), `_fetch_jwks_from_remote()` (httpx call), `_get_jwks()` (cache manager), and `validate_token()` (RS256 decode + claim validation)
- `security/deps.py` with `get_current_user()` FastAPI dependency using HTTPBearer(auto_error=False) for precise 401 messaging
- 7 pytest tests covering all JWT validation paths: valid token, expired, wrong issuer, wrong audience, tampered signature, missing auth header, JWKS cache hit
- `tests/conftest.py` providing minimal env vars so all unit tests run without a real .env file

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): UserContext model and failing JWT tests** - `085ad9a` (test)
2. **Task 2 (GREEN): Implement JWT validation to pass all tests** - `11221bb` (feat)

**Plan metadata:** (see docs commit below)

_Note: TDD plan — RED commit then GREEN commit per TDD protocol_

## Files Created/Modified

- `backend/core/models/user.py` - UserContext TypedDict (user_id: UUID, email, username, roles, groups)
- `backend/security/__init__.py` - security package stub
- `backend/security/jwt.py` - JWKS cache + RS256 validation + UserContext extraction
- `backend/security/deps.py` - get_current_user() FastAPI dependency
- `backend/tests/test_jwt.py` - 7 JWT validation test cases with RSA key fixture and mock JWKS
- `backend/tests/conftest.py` - Minimal env vars (os.environ.setdefault) for test isolation
- `backend/pyproject.toml` - Added cryptography>=46.0.0 to dev deps

## JWT Claim Mapping

| UserContext Field | JWT Claim | Notes |
|---|---|---|
| `user_id` | `sub` | Cast to UUID — crashes if not valid UUID (intentional: Keycloak always uses UUID sub) |
| `email` | `email` | Defaults to empty string if claim absent |
| `username` | `preferred_username` | Defaults to empty string if claim absent |
| `roles` | `realm_access.roles` | Defaults to empty list; uses realm roles (not client roles) |
| `groups` | `groups` | Defaults to empty list; full path format e.g. "/tech" |

## JWKS Cache Strategy

```
Module-level state:
  _JWKS_CACHE: dict       — populated with Keycloak JWKS JSON on first call
  _jwks_fetched_at: float — monotonic clock timestamp of last fetch
  JWKS_TTL_SECONDS = 300  — 5-minute TTL

Cache flow:
  1. _get_jwks() checks if cache is populated AND age < TTL
  2. Cache hit: return _JWKS_CACHE immediately (no I/O)
  3. Cache miss: call _fetch_jwks_from_remote() → update cache + timestamp
  4. All validate_token() calls within 300s share the same in-process JWKS
```

Cache key insight: python-jose's `jwt.decode()` handles `kid` matching internally when given a JWKS dict — no manual key selection needed.

## python-jose Gotchas Discovered

1. **`ExpiredSignatureError` vs `JWTError`**: `ExpiredSignatureError` is a subclass of `JWTError`. It must be caught FIRST (before the `except JWTError` clause) to produce the specific "Token has expired" message.

2. **JWKS format from `jwk.construct().to_dict()`**: Returns `{"alg": "RS256", "kty": "RSA", "n": "...", "e": "..."}` — this is the correct format for `jwt.decode(token, jwks, ...)` where `jwks = {"keys": [key_dict]}`.

3. **`DeprecationWarning: datetime.utcnow()`**: python-jose uses `datetime.utcnow()` internally (deprecated in Python 3.12). This is a library issue — not actionable in our code. Warning is captured but harmless.

4. **`asyncio_default_fixture_loop_scope`**: pytest-asyncio 0.25.0 requires explicit `asyncio_default_fixture_loop_scope = "function"` in pytest config to avoid deprecation warnings with module-scoped async fixtures.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] conftest.py needed for Settings() to load without .env**

- **Found during:** Task 2 (GREEN implementation)
- **Issue:** `security/jwt.py` imports `from core.config import settings` at module level. When running tests without a `.env` file, `Settings()` raises `ValidationError` for missing required fields, preventing module import.
- **Fix:** Created `backend/tests/conftest.py` with `os.environ.setdefault()` calls for all required fields. Using `setdefault` ensures real `.env` values are not overridden when present.
- **Files modified:** backend/tests/conftest.py (new file)
- **Verification:** All 20 tests pass (7 JWT + 13 existing)
- **Committed in:** `11221bb` (Task 2 commit)

**2. [Rule 1 - Bug] make_token hardcoded iss/aud broke cross-test isolation**

- **Found during:** Task 2 (GREEN verification — full test suite run)
- **Issue:** `make_token` fixture hardcoded `iss="https://keycloak.blitz.local/realms/blitz-internal"` and `aud="blitz-agentos"`. When `test_config.py` runs first, it reloads `core.config` with `patch.dict("os.environ", env, clear=True)` + `KEYCLOAK_REALM=blitz`, leaving `settings.keycloak_issuer="http://keycloak:8080/realms/blitz"` in place. The JWT tests then fail because the hardcoded iss doesn't match the mutated settings.
- **Fix:** Changed `make_token` to read `_cfg.settings.keycloak_issuer` and `_cfg.settings.keycloak_client_id` at call time, so tokens always match the current settings state.
- **Files modified:** backend/tests/test_jwt.py
- **Verification:** Full suite runs 20/20 pass in any test order
- **Committed in:** `11221bb` (Task 2 commit)

**3. [Plan deviation] _fetch_jwks_from_remote() added as separate function**

- **Found during:** Task 1 (RED — writing cache test)
- **Issue:** Plan spec had `_get_jwks()` as both the cache manager AND the HTTP fetcher. The JWKS cache test (test 7) needed to mock only the HTTP call while letting the cache logic run. Mocking `_get_jwks` entirely would bypass the cache.
- **Fix:** Split into `_fetch_jwks_from_remote()` (HTTP call) and `_get_jwks()` (cache manager calling the former). The cache test mocks `_fetch_jwks_from_remote` and calls `validate_token` through the real cache.
- **Files modified:** backend/security/jwt.py, backend/tests/test_jwt.py
- **Impact:** Cache logic is now properly tested end-to-end. No scope change.

---

**Total deviations:** 3 auto-fixed (1 blocking, 1 bug, 1 test design improvement)
**Impact on plan:** All fixes necessary for correct testing and test isolation. No scope creep.

## Issues Encountered

None beyond what is documented in Deviations above.

## User Setup Required

None — no external service configuration required for this plan. JWT validation against a real Keycloak instance is tested in the Phase 1 end-to-end integration test (not yet implemented).

## Next Phase Readiness

- Gate 1 (JWT validation) is complete and testable
- `get_current_user()` is ready to use in any FastAPI route: `Depends(get_current_user)`
- Plan 01-03 (database models) can proceed independently — no dependency on JWT
- Plan 01-04 (FastAPI routes) will use `get_current_user()` on all protected endpoints
- Gate 2 (RBAC) and Gate 3 (Tool ACL) in Phase 2 will consume `UserContext.roles` and `UserContext.user_id` from this gate

---
*Phase: 01-identity-and-infrastructure-skeleton*
*Completed: 2026-02-24*
