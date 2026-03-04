---
phase: 13-local-auth
plan: "01"
subsystem: local-auth
tags: [auth, jwt, security, local-auth, users, groups, rbac]
dependency_graph:
  requires: []
  provides:
    - local_auth_models
    - local_jwt_creation
    - dual_issuer_jwt_dispatch
    - local_login_endpoint
    - admin_local_user_crud
    - admin_local_group_crud
  affects:
    - backend/security/jwt.py
    - backend/security/deps.py
    - backend/main.py
tech_stack:
  added:
    - bcrypt>=4.0.0 (direct bcrypt library, replaces passlib due to bcrypt 5.x incompatibility)
    - email-validator>=2.0.0 (required for Pydantic EmailStr)
  patterns:
    - HS256 JWT signing via python-jose
    - Dual-issuer JWT dispatch via iss claim peek (get_unverified_claims)
    - SQLAlchemy ORM M2M via association tables (LocalUserGroup)
    - Admin CRUD pattern with registry:manage RBAC gate
key_files:
  created:
    - backend/core/models/local_auth.py
    - backend/security/local_auth.py
    - backend/core/schemas/local_auth.py
    - backend/api/routes/auth_local.py
    - backend/api/routes/admin_local_users.py
    - backend/alembic/versions/017_local_auth_tables.py
    - backend/tests/test_local_auth.py
  modified:
    - backend/core/config.py
    - backend/core/models/__init__.py
    - backend/security/jwt.py
    - backend/security/deps.py
    - backend/main.py
    - backend/tests/conftest.py
    - backend/pyproject.toml
    - backend/alembic/env.py
decisions:
  - "Replace passlib with bcrypt directly: passlib 1.7.4 incompatible with bcrypt 5.0 (detect_wrap_bug tries >72 byte hash, rejected by bcrypt 5.x)"
  - "resolve_user_roles does NOT use begin() internally: caller manages transaction context to avoid nested begin() issues in SQLAlchemy"
  - "validate_local_token takes an AsyncSession param: allows caller (get_current_user) to reuse the request session for the is_active check"
  - "Test emails use @example.com: email-validator rejects .local and .internal as reserved domains"
  - "LOCAL_JWT_SECRET added to conftest.py _TEST_ENV: settings lru_cached at module load, env var must be set before collection"
metrics:
  duration: "18 minutes"
  completed: "2026-03-03"
  tasks_completed: 2
  files_created: 7
  files_modified: 8
---

# Phase 13 Plan 01: Backend Local Auth Summary

**One-liner:** Local username/password auth with HS256 JWT via bcrypt+python-jose, dual-issuer dispatch in validate_token(), and full admin CRUD for local users/groups with registry:manage RBAC gate.

## What Was Built

### Task 1: ORM Models, Migration, Config, Password Utilities (commit: 3778ce6)

**5 SQLAlchemy ORM models** in `backend/core/models/local_auth.py`:
- `LocalUser` — id, username, email, password_hash, is_active, timestamps
- `LocalGroup` — id, name, description, created_at
- `LocalUserGroup` — M2M join table (user_id, group_id with CASCADE FK)
- `LocalGroupRole` — group→role assignments (group_id, role with CASCADE FK)
- `LocalUserRole` — direct user→role overrides (user_id, role with CASCADE FK)

**Alembic migration 017** creates all 5 tables with unique indexes and CASCADE delete constraints.

**Config additions** to `Settings`:
- `local_jwt_secret: str = ""` — HS256 signing secret
- `local_jwt_expires_hours: int = 8` — 8-hour workday default

**`security/local_auth.py`** provides:
- `hash_password()` / `verify_password()` — direct bcrypt (not passlib)
- `create_local_token()` — HS256 JWT with claims mirroring Keycloak exactly
- `validate_local_token()` — decode HS256 + is_active DB check + returns UserContext
- `resolve_user_roles()` — SQL union of group roles + direct user roles, sorted deduplicated

### Task 2: Dual-Issuer Dispatch, Login Endpoint, Admin CRUD, Tests (commit: 0c88d7d)

**`security/jwt.py` refactored** — dual-issuer dispatcher:
```
validate_token(token, session)
  → jose_jwt.get_unverified_claims(token)  # unverified peek
  → iss == keycloak_issuer → _validate_keycloak_token()  # unchanged RS256 path
  → iss == "blitz-local"  → validate_local_token()       # new HS256 path
  → else                  → HTTPException(401, "Unknown token issuer")
```
All 7 pre-existing JWT tests pass unchanged (Keycloak RS256 path zero behavior change).

**`security/deps.py` updated** — `get_current_user` now passes DB session to `validate_token()` for local token is_active check.

**`core/schemas/local_auth.py`** — full Pydantic v2 schemas:
- Login: `LocalLoginRequest`, `LocalLoginResponse`
- User CRUD: `LocalUserCreate` (with password complexity validator), `LocalUserUpdate`, `LocalUserResponse`, `GroupBrief`
- Group CRUD: `LocalGroupCreate`, `LocalGroupUpdate`, `LocalGroupResponse`
- Assignments: `RoleAssignment`, `GroupAssignment`

**`api/routes/auth_local.py`** — `POST /api/auth/local/token`:
- Constant-time bcrypt verify (dummy hash for missing users prevents timing attacks)
- Resolves roles via resolve_user_roles()
- Returns HS256 JWT with Keycloak-mirrored claims

**`api/routes/admin_local_users.py`** — 13 endpoints:
- User: POST create, GET list, GET detail, PUT update, DELETE, POST assign-groups, DELETE remove-group, POST add-roles, DELETE remove-role
- Group: POST create, GET list, PUT update, DELETE
- All require `registry:manage` permission via `_require_registry_manager` dependency

**`tests/test_local_auth.py`** — 23 tests covering all requirements.

## Verification Results

```
PYTHONPATH=. .venv/bin/pytest tests/ -q
632 passed, 1 skipped  (610 existing + 23 new tests)

PYTHONPATH=. .venv/bin/python -c "
from core.models.local_auth import LocalUser, LocalGroup, LocalUserGroup, LocalGroupRole, LocalUserRole
from security.local_auth import create_local_token
from api.routes.auth_local import router
from api.routes.admin_local_users import router
print('All imports OK')
"

.venv/bin/alembic heads
017 (head)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Replaced passlib with bcrypt directly**
- **Found during:** Task 1 verification (test_hash_and_verify_password)
- **Issue:** passlib 1.7.4 calls `detect_wrap_bug()` during backend selection, which tries to hash a 256-byte password. bcrypt 5.0 enforces a 72-byte limit, raising `ValueError`.
- **Fix:** Removed `passlib[bcrypt]` from dependencies, used `bcrypt>=4.0.0` directly. `hash_password()` uses `bcrypt.hashpw(plain.encode(), gensalt()).decode()`. `verify_password()` uses `bcrypt.checkpw()` with try/except for invalid hash format.
- **Files modified:** `security/local_auth.py`, `pyproject.toml`
- **Commit:** 0c88d7d

**2. [Rule 3 - Blocking] Added email-validator dependency**
- **Found during:** Task 2 test_login_valid_credentials_returns_token
- **Issue:** `Pydantic EmailStr` requires `email-validator` package. Not in original deps. `LocalUserCreate` schema with `email: EmailStr` caused ImportError at module load.
- **Fix:** `uv add "email-validator>=2.0.0"`
- **Files modified:** `pyproject.toml`
- **Commit:** 0c88d7d

**3. [Rule 1 - Bug] Fixed test isolation issue: LOCAL_JWT_SECRET not set when running full suite**
- **Found during:** Task 2 full suite run
- **Issue:** `test_local_auth.py` set `LOCAL_JWT_SECRET` via `os.environ.setdefault()` at module level, but `settings` is `@lru_cache`d and instantiated when `conftest.py` first runs. Secret not present → `create_local_token()` raises 500.
- **Fix:** Added `LOCAL_JWT_SECRET` to `conftest.py`'s `_TEST_ENV` dict (same pattern as all other test env vars). Removed redundant setdefault from test file.
- **Files modified:** `tests/conftest.py`, `tests/test_local_auth.py`
- **Commit:** 0c88d7d

**4. [Rule 1 - Bug] Fixed has_permission patch target in tests**
- **Found during:** Task 2 test_create_user_success
- **Issue:** Tests patched `security.rbac.has_permission` but `admin_local_users.py` uses `from security.rbac import has_permission` (module-level binding). Patch at source module doesn't affect already-bound local name.
- **Fix:** Changed patch target to `api.routes.admin_local_users.has_permission`.
- **Files modified:** `tests/test_local_auth.py`
- **Commit:** 0c88d7d

**5. [Rule 1 - Bug] Fixed test email domains (rejected by email-validator)**
- **Found during:** Task 2 test_create_user_success (422 validation error)
- **Issue:** Test emails used `@blitz.local` and `@blitz.internal`. `email-validator` rejects `.local` (mDNS reserved) and `.internal` (special-use reserved) as invalid domains.
- **Fix:** Changed all test emails to use `@example.com` (IANA-reserved test domain, always valid).
- **Files modified:** `tests/test_local_auth.py`
- **Commit:** 0c88d7d

### Design Refinements (within plan scope)

- `resolve_user_roles()` runs queries directly on the session (no `begin()`) so callers control transaction scope — avoids nested begin() issues
- `validate_local_token()` accepts an `AsyncSession` parameter instead of opening its own connection — enables reuse of the request-scoped session in `get_current_user`

## Self-Check: PASSED

Files exist:
- `backend/core/models/local_auth.py` — FOUND
- `backend/security/local_auth.py` — FOUND
- `backend/core/schemas/local_auth.py` — FOUND
- `backend/api/routes/auth_local.py` — FOUND
- `backend/api/routes/admin_local_users.py` — FOUND
- `backend/alembic/versions/017_local_auth_tables.py` — FOUND
- `backend/tests/test_local_auth.py` — FOUND

Commits exist:
- `3778ce6` feat(13-01): add local auth ORM models... — FOUND
- `0c88d7d` feat(13-01): add dual-issuer JWT dispatch... — FOUND
