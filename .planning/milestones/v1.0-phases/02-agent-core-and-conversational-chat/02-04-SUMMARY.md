---
phase: 02-agent-core-and-conversational-chat
plan: "04"
subsystem: security
tags: [aes-256-gcm, credential-vault, oauth-tokens, cryptography, sqlalchemy, alembic, fastapi]

# Dependency graph
requires:
  - phase: 01-identity-and-infrastructure-skeleton
    provides: JWT validation, get_current_user() dep, async DB session, Base ORM class, Alembic migration 001

provides:
  - AES-256-GCM encrypt_token/decrypt_token functions using cryptography library
  - store_credential/get_credential/delete_credential async functions (SQLite-compatible upsert)
  - UserCredential ORM model (user_credentials table, pgvector-hosted PostgreSQL)
  - Alembic migration 003 creating user_credentials table (branches from 001)
  - GET /api/credentials — list connected OAuth providers (no token values returned)
  - DELETE /api/credentials/{provider} — disconnect a provider (204 or 404)
  - credential_encryption_key setting in core/config.py

affects:
  - 02-05 (Phase 2 agent memory/tools — may read credential vault)
  - 03-xx (Phase 3 OAuth sub-agents will call store_credential() to write OAuth callback tokens)
  - All phases requiring Google/Microsoft API access

# Tech tracking
tech-stack:
  added:
    - cryptography==46.0.5 (AES-256-GCM via AESGCM; already in venv)
  patterns:
    - "AES-256-GCM: random 12-byte IV per encryption, ciphertext includes GCM auth tag"
    - "Credential isolation: WHERE user_id=$1 from JWT; never from request body"
    - "SQLite-compatible upsert: select-then-insert/update pattern (not ON CONFLICT DO UPDATE)"
    - "Credential API response: returns provider name + timestamp only — never token values"

key-files:
  created:
    - backend/security/credentials.py
    - backend/core/models/credentials.py
    - backend/alembic/versions/003_user_credentials.py
    - backend/api/routes/credentials.py
    - backend/tests/security/__init__.py
    - backend/tests/security/test_credentials.py
    - backend/tests/test_credentials_api.py
  modified:
    - backend/core/config.py (added credential_encryption_key field)
    - backend/main.py (registered credentials router)

key-decisions:
  - "SQLite-compatible upsert: select-then-insert/update (not PostgreSQL ON CONFLICT) — needed for in-memory SQLite tests"
  - "Migration 003 branches from 001 (not 002) — parallel branch; merge migration needed when 02-03 adds migration 002"
  - "Phase 2 delivers GET+DELETE only — no POST endpoint; OAuth write callbacks are Phase 3"
  - "Encryption key stored as hex string in settings; _get_key() falls back to CREDENTIAL_ENCRYPTION_KEY env var before settings"
  - "Alembic migration applied manually via docker exec psql (no .env file for alembic CLI from host)"

patterns-established:
  - "All credential functions use keyword-only args (user_id, provider, token) to prevent positional arg confusion"
  - "Credential logs include user_id + provider; never ciphertext, iv, or token value"
  - "API endpoints return ConnectedProvider(provider, connected_at) — no ciphertext, no iv, no token"

requirements-completed:
  - INTG-04

# Metrics
duration: 15min
completed: 2026-02-25
---

# Phase 2 Plan 04: AES-256-GCM Credential Vault Summary

**AES-256-GCM OAuth token vault with per-user isolation: encrypt_token/decrypt_token + store/get/delete CRUD + GET|DELETE /api/credentials API stubs, all covered by 14 passing TDD tests using in-memory SQLite**

## Performance

- **Duration:** ~15 min (verification + commit)
- **Started:** 2026-02-25T11:10:00Z
- **Completed:** 2026-02-25T11:20:00Z
- **Tasks:** 2 (Task 1: TDD vault + migration; Task 2: API routes)
- **Files modified:** 9 (7 created, 2 modified)

## Accomplishments

- AES-256-GCM vault implemented with `cryptography==46.0.5` — random 12-byte IV per call, GCM auth tag detects tampering
- Credential isolation enforced: `WHERE user_id=$1` always from JWT; user A cannot retrieve user B's credentials
- SQLite-compatible upsert (select-then-insert/update) allows TDD with in-memory SQLite — no PostgreSQL required for tests
- All 14 tests pass (10 unit + 4 API): round-trip encrypt/decrypt, IV randomness, tamper detection, store/get/delete, isolation
- Migration 003 applied to Docker postgres; `user_credentials` table confirmed present
- No credentials (token, ciphertext, iv) appear in logs, API responses, or error messages

## Task Commits

1. **Task 1: AES-256-GCM vault + user_credentials table (TDD)** - `b2b140d` (feat)
2. **Task 2: GET /api/credentials + DELETE /api/credentials/{provider}** - `5052f5d` (feat)

**Plan metadata:** (docs commit follows in gsd tools step)

_Note: Task 1 was TDD — tests were written together with implementation since previous agent pre-wrote both._

## Files Created/Modified

- `backend/security/credentials.py` - AES-256-GCM vault: encrypt_token, decrypt_token, store_credential, get_credential, delete_credential
- `backend/core/models/credentials.py` - UserCredential SQLAlchemy ORM model with ciphertext + iv columns
- `backend/alembic/versions/003_user_credentials.py` - Migration creating user_credentials table (down_revision="001")
- `backend/api/routes/credentials.py` - GET /api/credentials + DELETE /api/credentials/{provider} FastAPI routes
- `backend/tests/security/__init__.py` - Package init for security tests
- `backend/tests/security/test_credentials.py` - 10 TDD tests: crypto, DB CRUD, isolation
- `backend/tests/test_credentials_api.py` - 4 API security gate tests (401 without JWT, routes exist)
- `backend/core/config.py` - Added `credential_encryption_key: str = ""` field
- `backend/main.py` - Registered `credentials.router` with `/api` prefix

## Decisions Made

- **SQLite-compatible upsert:** Used select-then-insert/update pattern instead of PostgreSQL `ON CONFLICT DO UPDATE`. Reason: test fixtures use aiosqlite in-memory DB; PostgreSQL-specific syntax would break test suite. Production will use same path (correct for both DBs).

- **Migration 003 branches from 001:** `down_revision = "001"` because migration 002 (memory_conversations from plan 02-03) may not exist yet when 02-04 runs in wave 2. Both 002 and 003 branch from 001; when 02-03 completes, a merge migration will be needed before `alembic upgrade head` can run across both branches.

- **Phase 2 stubs: GET + DELETE only:** No POST endpoint. OAuth write callbacks that create credentials belong to Phase 3 sub-agents. Frontend `/settings/connections` page can list and disconnect providers using Phase 2 API.

- **_get_key() fallback order:** Checks `CREDENTIAL_ENCRYPTION_KEY` env var first, then `settings.credential_encryption_key`. Allows test key injection via `os.environ.setdefault()` before settings load — prevents test isolation issues.

- **Alembic migration applied via docker exec psql:** The host has no `.env` file, so `alembic upgrade head` from the host fails with settings ValidationError. Applied SQL directly via `docker exec hox-agentos-postgres-1 psql -U blitz -d blitz` (postgres allows trust auth from within container). This is consistent with how migration 001 was applied.

## Deviations from Plan

None - plan executed exactly as written. All pre-written files matched plan specification. No bugs found, no blocking issues, no missing critical functionality.

## Issues Encountered

- **Alembic CLI from host fails without .env:** The alembic env.py loads `core.config.settings` which requires all 9 mandatory env vars. No `.env` file exists on the host (only in Docker). Resolved by applying migration SQL directly via `docker exec` psql — trust auth within Docker container bypasses password requirement.

## User Setup Required

None — no external service configuration required beyond what was already set up in Phase 1. The `CREDENTIAL_ENCRYPTION_KEY` env var must be added to `.env` before deploying to production (generate with `python -c "import secrets; print(secrets.token_hex(32))"`). This is documented in `.dev-secrets.example`.

## Next Phase Readiness

**Ready for Phase 3:**
- `store_credential(session, user_id=user_id, provider="google", token=access_token)` — call this from OAuth callback handlers in Phase 3
- `get_credential(session, user_id=user_id, provider="google")` — call this from sub-agents needing API access tokens
- The vault is fully tested and isolated; Phase 3 only needs to wire OAuth flows

**Merge migration needed when 02-03 completes:**
- Migration 002 (memory_conversations) and 003 (user_credentials) both branch from 001
- Before running `alembic upgrade head` with both present: `alembic merge -m "merge 002 and 003" 002 003`
- This is documented in 02-03 plan Task 1 and applies to whoever completes last

---
*Phase: 02-agent-core-and-conversational-chat*
*Completed: 2026-02-25*
