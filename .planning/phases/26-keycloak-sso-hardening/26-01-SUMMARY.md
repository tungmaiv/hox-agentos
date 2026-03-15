---
phase: 26-keycloak-sso-hardening
plan: 01
subsystem: auth
tags: [circuit-breaker, sso, keycloak, health-check, notifications, telegram]

# Dependency graph
requires:
  - phase: 18-identity-config
    provides: KeycloakConfig resolver, platform_config table, admin_keycloak routes
provides:
  - SSOCircuitBreaker with CLOSED/OPEN/HALF_OPEN state machine
  - SSO health checker with 4 diagnostic categories
  - AdminNotification generic model and CRUD API
  - Auth config sso_available field driven by circuit breaker
  - Telegram alerts on SSO state transitions
affects: [26-02-frontend-sso-resilience, 30-skill-activation, 33-email-notifications]

# Tech tracking
tech-stack:
  added: []
  patterns: [in-memory circuit breaker with configurable thresholds, generic admin notification model]

key-files:
  created:
    - backend/security/circuit_breaker.py
    - backend/security/sso_health.py
    - backend/security/sso_notifications.py
    - backend/core/models/admin_notification.py
    - backend/api/routes/admin_sso_health.py
    - backend/api/routes/admin_notifications.py
    - backend/alembic/versions/031_sso_circuit_breaker_and_notifications.py
  modified:
    - backend/core/models/platform_config.py
    - backend/api/routes/auth_config.py
    - backend/security/jwt.py
    - backend/main.py
    - backend/core/models/__init__.py

key-decisions:
  - "Circuit breaker is in-memory singleton with asyncio.Lock — sufficient for single-process MVP"
  - "AdminNotification has no user_id — visible to ALL admins (system-wide alerts)"
  - "Circuit breaker only blocks new SSO logins when no cached JWKS available — existing sessions unaffected"
  - "Telegram alerts sent via sidecar /send endpoint, same pattern as channel gateway"

patterns-established:
  - "Circuit breaker pattern: get_circuit_breaker() singleton with register_transition_callback()"
  - "Admin notification pattern: generic category/severity model, reusable across phases"

requirements-completed: [KC-01, KC-02, KC-06, KC-07]

# Metrics
duration: 20min
completed: 2026-03-15
---

# Phase 26 Plan 01: SSO Backend Resilience Summary

**In-memory circuit breaker preventing cascading SSO failures, 4-category health diagnostics, generic admin notification CRUD, and Telegram alert dispatch on state transitions**

## Performance

- **Duration:** 20 min
- **Started:** 2026-03-15T10:05:12Z
- **Completed:** 2026-03-15T10:25:32Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments
- SSOCircuitBreaker with full CLOSED/OPEN/HALF_OPEN lifecycle, configurable thresholds, transition callbacks
- SSO health checker returning certificate, config, connectivity, performance diagnostics
- AdminNotification model + CRUD API (list, count, mark-read, mark-all-read) with admin-only gating
- GET /api/auth/config extended with sso_available field reflecting circuit breaker state
- Circuit breaker integrated into jwt.py JWKS fetch path with failure/success recording
- Telegram alerts dispatched to it-admin users on state transitions via sidecar
- 28 new tests (10 circuit breaker + 6 health + 3 SSO health API + 9 notifications + 3 auth config) — 967 total passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Circuit breaker + SSO health checker + admin notification model + migration** - `eeb1986` (feat)
2. **Task 2: API endpoints — SSO health, auth config extension, admin notifications, Telegram alerts** - `40ac926` (feat)

## Files Created/Modified
- `backend/security/circuit_breaker.py` - SSOCircuitBreaker class with state machine, thresholds, callbacks
- `backend/security/sso_health.py` - check_sso_health() with 4 diagnostic categories
- `backend/security/sso_notifications.py` - Transition callback: DB notification + Telegram dispatch
- `backend/core/models/admin_notification.py` - Generic AdminNotification ORM model
- `backend/core/models/platform_config.py` - Added cb_failure_threshold, cb_recovery_timeout, cb_half_open_max_calls
- `backend/api/routes/admin_sso_health.py` - SSO health + circuit breaker config endpoints
- `backend/api/routes/admin_notifications.py` - Notification CRUD endpoints (admin-only)
- `backend/api/routes/auth_config.py` - Extended with sso_available field
- `backend/security/jwt.py` - Circuit breaker wired into JWKS fetch path
- `backend/main.py` - Router registration + callback setup at startup
- `backend/alembic/versions/031_sso_circuit_breaker_and_notifications.py` - Migration for admin_notifications table + cb_* columns

## Decisions Made
- Circuit breaker is in-memory (no Redis) — sufficient for single-process Docker Compose MVP
- AdminNotification is visible to ALL admins (no user_id FK) — system-wide alerts
- Circuit breaker blocks new SSO logins only when no cached JWKS exists — preserves existing sessions
- Telegram alerts use sidecar /send endpoint (same as channel gateway pattern)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- AsyncMock.json() returns coroutine in SSO health tests — fixed by using MagicMock for httpx response objects

## User Setup Required

None - no external service configuration required. Migration must be applied via `just migrate`.

## Next Phase Readiness
- Backend API surface complete for Plan 02 (frontend) to consume
- GET /api/admin/sso/health returns all data needed for health dashboard cards
- GET /api/auth/config returns sso_available for login page degradation
- GET /api/admin/notifications/* ready for notification bell UI

---
*Phase: 26-keycloak-sso-hardening*
*Completed: 2026-03-15*
