---
phase: 24-unified-registry-mcp-platform-enhancement-skill-import-adapters
plan: "01"
subsystem: auth
tags: [pydantic, next-auth, keycloak, fastapi, typescript, aes-256, retry-backoff]

# Dependency graph
requires:
  - phase: 18-identity-configuration
    provides: Keycloak config resolver, platform_config table, internal provider-config endpoint
provides:
  - CREDENTIAL_ENCRYPTION_KEY model_validator with clear error on invalid length/non-hex
  - fetchWithRetry (3-attempt exponential backoff) in auth.ts for Keycloak SSO startup resilience
  - JWKS pre-warm + keycloak_config cache pre-warm at backend lifespan startup
  - Cache-Control: max-age=60 on internal provider-config endpoint
  - 14 passing config tests (4 new: encryption key validation)
affects: [phase 24 plans, oauth-credential-storage, keycloak-sso]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pydantic model_validator(mode='after') for post-init settings validation"
    - "fetchWithRetry pattern in auth.ts for resilient startup fetches"
    - "Non-fatal lifespan pre-warm pattern in FastAPI main.py"

key-files:
  created: []
  modified:
    - backend/core/config.py
    - backend/tests/test_config.py
    - frontend/src/auth.ts
    - backend/api/routes/admin_keycloak.py
    - backend/main.py

key-decisions:
  - "[24-01]: validate_encryption_key is a second model_validator(mode='after') — Pydantic runs multiple validators in declaration order; derive_keycloak_urls runs first"
  - "[24-01]: Empty CREDENTIAL_ENCRYPTION_KEY allowed (optional) — key is not required for local-only setups without OAuth credential storage"
  - "[24-01]: fetchWithRetry falls back to null (not throw) on all-retries-exhausted — auth.ts must never throw on startup, or Next.js reports Server error Configuration"
  - "[24-01]: Cache-Control on provider-config endpoint header-only (not response_model) — FastAPI response_model does not support headers; inject via Response parameter"
  - "[24-01]: SessionProvider confirmed at root layout.tsx — no per-page session SSR round-trips for authenticated route group"
  - "[24-01]: JWKS pre-warm calls _fetch_jwks_from_remote directly (not get_jwks) — skips cache to actually warm the cache on boot"

patterns-established:
  - "Non-fatal startup pre-warm: wrap in try/except, log warning, yield regardless"
  - "Pydantic Settings validation: model_validator(mode='after') for derived/cross-field validation"

requirements-completed:
  - 24-01-DEBT

# Metrics
duration: 3min
completed: 2026-03-12
---

# Phase 24 Plan 01: Tech Debt Clearance Summary

**AES-256 key validation + Keycloak SSO retry/backoff + 5 startup performance fixes across backend and frontend**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-12T02:01:40Z
- **Completed:** 2026-03-12T02:05:05Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- `CREDENTIAL_ENCRYPTION_KEY` now validated at backend startup — invalid length or non-hex chars raise `ValueError` with clear message (enables safe AES-256-GCM credential storage)
- `auth.ts` now retries Keycloak provider-config fetch up to 3 times with 500ms/1s/2s backoff; returns `null` (not throws) on exhaustion — eliminates "Server error — Configuration" on Keycloak startup lag
- Backend lifespan now pre-warms both keycloak_config TTL cache and JWKS cache at startup — first auth request served from cache, not Keycloak
- `Cache-Control: max-age=60, s-maxage=60` added to internal provider-config endpoint — reduces repeated startup round-trips
- `SessionProvider` confirmed at root `layout.tsx` (not per-page) — no SSR waterfall for authenticated route group

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix SWR/Server Component build failure + CREDENTIAL_ENCRYPTION_KEY validation (RED)** - `4fc5afa` (test)
2. **Task 1: Fix SWR/Server Component build failure + CREDENTIAL_ENCRYPTION_KEY validation (GREEN)** - `8653537` (feat)
3. **Task 2: Keycloak SSO error + page load performance (5 hypotheses)** - `8da94e1` (fix)

**Plan metadata:** (docs commit follows)

_Note: TDD task 1 has two commits: test (RED) and implementation (GREEN)_

## Files Created/Modified
- `backend/core/config.py` - Added `validate_encryption_key` model_validator
- `backend/tests/test_config.py` - 4 new tests for encryption key validation
- `frontend/src/auth.ts` - Added `fetchWithRetry` helper, replaced bare `fetch` in `fetchKeycloakProviderConfig`
- `backend/api/routes/admin_keycloak.py` - Added `Cache-Control` header to internal provider-config endpoint
- `backend/main.py` - Added keycloak_config pre-warm (Hyp 1) and JWKS pre-warm (Hyp 5) in lifespan

## Decisions Made
- `validate_encryption_key` uses `model_validator(mode="after")` as second validator after `derive_keycloak_urls` — Pydantic runs both in declaration order
- `fetchWithRetry` returns `null` (not throws) after all retries — auth.ts must never throw or Next.js reports "Server error — Configuration"
- Cache-Control header injected via FastAPI `Response` parameter (not response_model) — response_model handles body only
- `SessionProvider` confirmed in root `layout.tsx` (wraps all pages) — no additional per-authenticated-page wrapping needed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing] SWR/prerender pages were already fixed**
- **Found during:** Task 1 investigation
- **Issue:** `settings/integrations/page.tsx` was just a redirect (no SWR). `settings/memory/page.tsx` already had `"use client"` directive. `tsc --noEmit` already passed.
- **Fix:** No fix needed — tech debt was pre-resolved. Verified tsc passes.
- **Impact:** Task 1 scope reduced to CREDENTIAL_ENCRYPTION_KEY validation only.

---

**Total deviations:** 1 (pre-resolved tech debt discovered — no action needed)
**Impact on plan:** Plan objective fully met. tsc passes, validator implemented, retry/backoff implemented, 5 performance hypotheses addressed.

## Issues Encountered
None — all changes implemented cleanly.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `CREDENTIAL_ENCRYPTION_KEY` validated at startup — OAuth credential storage (Phase 24+ plans) can now safely use AES-256-GCM encryption
- Keycloak SSO startup timing issue resolved — auth.ts will not fail on temporary Keycloak unavailability
- Backend test suite at 873 passing (1 skipped) — baseline maintained

---
*Phase: 24-unified-registry-mcp-platform-enhancement-skill-import-adapters*
*Completed: 2026-03-12*

## Self-Check: PASSED

- config.py: FOUND
- auth.ts: FOUND
- SUMMARY.md: FOUND
- RED commit 4fc5afa: FOUND
- GREEN commit 8653537: FOUND
- Task 2 commit 8da94e1: FOUND
- validate_encryption_key in config.py: FOUND
- fetchWithRetry in auth.ts: FOUND
