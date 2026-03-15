# Phase 26: Keycloak SSO Hardening - Context

**Gathered:** 2026-03-15
**Status:** Ready for planning

<domain>
## Phase Boundary

SSO failures never cascade into user-facing outages; admins have full visibility into SSO health. This phase adds resilience on top of the existing Keycloak configuration infrastructure (Phase 18): health monitoring with categorized diagnostics, a circuit breaker to prevent cascading SSO failures, graceful login page degradation, configurable pre-save validation, and admin notifications (in-app + Telegram) when SSO state transitions.

Creating/managing Keycloak config fields, the Identity page form, or the test-connection button is NOT in scope (already built in Phase 18). Email notifications are NOT in scope (Phase 33).

</domain>

<decisions>
## Implementation Decisions

### Health diagnostics UI (KC-01)
- Add a health status section at the TOP of the existing Admin > Identity page (not a separate page)
- Display 4 status category cards: Certificate, Config, Connectivity, Performance — each with green/yellow/red indicator and one-line detail
- Auto-refresh health checks every 30 seconds while the Identity page is open, plus a manual "Refresh" button
- Health checks run against the SAVED config (not form values)

### Pre-save configuration test (KC-02)
- Keep existing "Test Connection" button for pre-save validation against form values (already built in Phase 18)
- Add a NEW comprehensive health check system that tests DNS + TLS + OIDC discovery + client auth against the SAVED config
- Two distinct actions with clear purpose: "Test Connection" (pre-save, form values) vs health cards (post-save, saved config)

### Circuit breaker (KC-06)
- Circuit breaker logic lives in backend (security layer), with state surfaced to frontend via `/api/auth/config` response
- When circuit is open, `/api/auth/config` returns `sso_available: false` so login page hides SSO button automatically
- Admin health panel shows current circuit breaker state (closed/open/half-open)
- Default thresholds: 5 consecutive failures → circuit opens → 60s recovery timeout → half-open (1 probe) → close on success
- Thresholds are admin-configurable from the Identity page (failure_threshold, recovery_timeout_seconds, half_open_max_calls)
- Failure counts: JWKS fetch unreachable, TLS cert errors, OIDC discovery failures, token validation timeouts
- NOT counted as failures: invalid user credentials (wrong password), expired tokens (normal lifecycle)
- Existing SSO-authenticated sessions continue working when circuit is open (JWT validation is local signature check, doesn't need Keycloak)
- Circuit breaker only blocks NEW SSO login attempts

### Login page degradation (KC-03, KC-04, KC-05)
- When Keycloak is down (circuit open or SSO unavailable): hide SSO button entirely + show subtle info banner: "SSO is temporarily unavailable. Please sign in with your username and password."
- Login page fetches `/api/auth/config` once on page load (existing behavior) — backend includes circuit breaker state. No polling on login page.
- If SSO recovers, user refreshes the page to see SSO button again
- Mid-flow Keycloak errors (redirect works but Keycloak returns error): catch in next-auth callback, redirect to `/login?error=SSOUnavailable` with friendly message: "SSO sign-in failed. Please try again or use your username and password."
- User-facing error messages are GENERIC regardless of failure type (cert/config/unreachable/timeout) — technical categories only appear in admin health panel

### Admin notifications (KC-07)
- In-app notification bell in admin nav bar + Telegram message to admin users
- Notify on BOTH state transitions: healthy→unhealthy ("SSO is down: [category]") AND unhealthy→healthy ("SSO has recovered")
- In-app: red dot badge on bell icon when unread notifications exist; click opens dropdown with recent notifications (timestamp, category, message); dismiss individually or "Mark all read"
- Build a GENERIC admin notification infrastructure (admin_notifications table + bell UI) that SSO health is the first consumer of — Phase 33 and Phase 30 can reuse it
- Telegram: send to all users with it-admin role who have linked Telegram accounts (Telegram channel integration from v1.3)

### Claude's Discretion
- Exact circuit breaker implementation pattern (in-memory vs Redis-backed)
- Health check endpoint design (single endpoint returning all categories vs per-category)
- Admin notification table schema details
- Bell dropdown styling and animation
- Telegram message formatting
- How to detect certificate expiry vs certificate rejection vs certificate missing
- Exact threshold configuration UI placement within the Identity page

</decisions>

<specifics>
## Specific Ideas

- The health cards should feel like a monitoring dashboard section — compact, scannable, not overwhelming. Think of it as a mini health panel embedded in the existing Identity page.
- Circuit breaker behavior should be consistent with Phase 18's SSO disable behavior: existing sessions continue, only new logins are affected.
- The admin notification bell is the FIRST notification UI in the app — keep it simple (dropdown, not a full page) since Phase 33 will build the comprehensive notification system. But make the backend generic enough to reuse.
- Generic error messages for users ("SSO is temporarily unavailable") — admins get the technical detail in the health panel. Don't leak infrastructure details to regular users.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/security/keycloak_config.py`: KeycloakConfig resolver with 60s TTL cache — circuit breaker can wrap or extend this
- `backend/api/routes/admin_keycloak.py`: `_test_jwks_endpoint()` helper — reuse for health check connectivity test
- `backend/api/routes/admin_keycloak.py`: `_require_admin` dependency — reuse for all new admin endpoints
- `backend/api/routes/auth_config.py`: `GET /api/auth/config` — extend response to include `sso_available` (circuit breaker state)
- `backend/api/routes/health.py`: health endpoint with `auth` field — could extend with SSO health detail
- `frontend/src/app/(authenticated)/admin/identity/page.tsx`: existing Identity page (515 lines) — add health section at top
- `frontend/src/app/login/page.tsx`: already conditionally shows SSO button via `ssoEnabled` state from `/api/auth/config`
- `backend/channels/gateway.py`: Telegram channel integration — reuse for admin SSO alert messages

### Established Patterns
- Admin pages use card-based sections with rounded borders and shadow-sm (Identity page follows this)
- Backend caching uses module-level variables with TTL + asyncio.Lock (keycloak_config.py, jwt.py)
- AES-256-GCM encryption for secrets in platform_config table
- Zod schemas for frontend API response validation

### Integration Points
- `backend/security/jwt.py`: JWKS fetch is where SSO failures occur — circuit breaker wraps this
- `backend/api/routes/auth_config.py`: must return circuit breaker state alongside sso_enabled
- `frontend/src/app/login/page.tsx`: reads sso_enabled — extend to handle sso_available from circuit breaker
- `frontend/src/app/(authenticated)/admin/layout.tsx`: admin nav — add bell icon here
- New DB migration: admin_notifications table + circuit breaker config columns in platform_config
- Celery or background task: periodic SSO health check to detect issues before users hit them

</code_context>

<deferred>
## Deferred Ideas

- Full notification center page with filtering, pagination, and history — Phase 33 (Email System & Notifications)
- Email notifications for SSO health events — Phase 33
- Historical SSO health metrics / uptime tracking — future observability phase
- Auto-remediation actions (e.g., auto-disable SSO after prolonged outage) — future hardening

</deferred>

---

*Phase: 26-keycloak-sso-hardening*
*Context gathered: 2026-03-15*
