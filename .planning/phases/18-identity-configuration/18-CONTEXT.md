# Phase 18: Identity Configuration - Context

**Gathered:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Make Keycloak an optional, runtime-configurable identity provider — the platform boots and serves local auth login with no Keycloak config present, and admins can configure, test, enable, and disable SSO from the admin UI without restarting any service.

Creating/managing local users is out of scope (already in admin Users tab). Changing the local JWT algorithm or secret rotation is out of scope.

</domain>

<decisions>
## Implementation Decisions

### Config storage (IDCFG-06)
- New `platform_config` DB table with typed columns — not reusing `system_config` key/value store
- Columns: `id` (PK), `keycloak_url`, `keycloak_realm`, `keycloak_client_id`, `keycloak_client_secret_encrypted` (AES-256-GCM), `keycloak_ca_cert`, `enabled` (bool), `created_at`, `updated_at`
- Single-row table — there is only one identity provider configuration at a time
- Use existing `credential_encryption_key` + AES-256-GCM for `client_secret` encryption (same pattern as `credentials` table)
- Config resolution order: DB `platform_config` (priority) → env vars (fallback) → not configured (local-only mode)

### Backend boot behavior (IDCFG-01, IDCFG-02, IDCFG-07)
- All Keycloak fields in `Settings` become optional (default `""`) — backend starts without them
- On startup, check DB `platform_config` and env vars; if neither has Keycloak config, log `info` and set auth mode to `local-only`
- Health endpoint gains an `auth` field: `{"status": "ok", "auth": "local-only"}` or `{"auth": "local+keycloak"}`
- `security/jwt.py` `validate_token()` checks configured auth mode before attempting JWKS fetch — if Keycloak not configured, reject non-local tokens with 401

### JWKS hot-reload (IDCFG-06)
- After admin saves Keycloak config, backend invalidates the in-process JWKS cache by resetting `_JWKS_CACHE` and `_jwks_fetched_at` — next Keycloak token triggers a fresh fetch
- No restart required — the cache reset happens inline in the save endpoint

### Admin Identity tab (IDCFG-04, IDCFG-05, IDCFG-08)
- New "Identity" tab added to admin layout between "Permissions" and "Config" (security-adjacent placement)
- Tab renders a purpose-built form, not the generic system_config key/value editor
- Form fields: Issuer URL, Realm, Client ID, Client Secret (masked, with "Change" toggle to reveal input), CA Cert Path (optional), Enable SSO toggle
- Connection test button: `POST /api/admin/keycloak/test-connection` — result displayed inline below the button (not toast, not modal) — green success message or red error with detail
- Success result shows: "Connected — JWKS endpoint reachable, N keys found"
- Error result shows the specific failure reason (DNS, TLS, 401, etc.)
- "Save" and "Test Connection" are separate actions — admin can test before committing
- "Disable SSO" is a dedicated button with a confirmation dialog — not just toggling the form enable/disable field

### SSO disable behavior (IDCFG-08)
- Disable SSO affects new logins only — existing Keycloak-authenticated sessions continue until their token expires naturally (up to 8 hours)
- Rationale: Less disruptive for enterprise users; avoids mass session invalidation during business hours
- Confirmation dialog text: "Disabling SSO will prevent new Keycloak logins. Users currently logged in via SSO will remain logged in until their session expires. Continue?"
- After disable: health endpoint switches to `"auth": "local-only"`, login page hides SSO button on next load

### Login page SSO button (IDCFG-03)
- Frontend calls `GET /api/auth/config` client-side on login page mount (page is already `"use client"`)
- Response: `{"sso_enabled": bool}` — simple, no other fields needed
- During fetch (brief loading state): hide SSO button (render only local credentials form)
- No SSO config = no Keycloak provider registered in next-auth — prevents runtime errors if SSO button were clicked accidentally

### Sensitive field display policy
- `keycloak_client_secret`: displayed as masked dots ("••••••••") with a "Change secret" expand toggle that shows a new empty input field — never reveals the saved value
- `keycloak_ca_cert`: path is stored as plain text (not secret) — displayed normally
- `GET /api/admin/identity` response never includes the raw secret — only a boolean `has_secret: true/false`

### Claude's Discretion
- Exact tab ordering position (between Permissions and Config is specified; exact index in the list is Claude's call)
- Form validation rules (URL format checks, realm name character validation)
- Loading state style while `GET /api/auth/config` fetches on login page
- Whether to disable the "Save" button until "Test Connection" passes (vs. allow save without testing)
- next-auth v5 Keycloak provider registration approach (checked at auth.ts init vs. dynamic)
- Migration number for the new `platform_config` table (next after 020)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/security/jwt.py`: in-process JWKS cache (`_JWKS_CACHE`, `_jwks_fetched_at`) — expose a `reset_jwks_cache()` function for the save endpoint to call
- `backend/core/config.py`: `credential_encryption_key` + AES-256-GCM already used for `credentials` table — reuse same encryption helper for `platform_config.keycloak_client_secret_encrypted`
- `frontend/src/app/(authenticated)/admin/layout.tsx`: `ADMIN_TABS` array — add `{ label: "Identity", href: "/admin/identity" }` here
- `backend/api/routes/system_config.py`: `_require_admin` dependency (admin-only RBAC gate) — reuse for all Identity endpoints
- `backend/api/routes/health.py` + `backend/core/schemas/common.py` (`HealthResponse`) — extend to add `auth` field

### Established Patterns
- Admin form pages follow the pattern: `frontend/src/app/(authenticated)/admin/credentials/` — card with labeled fields + action buttons
- AES-256-GCM encryption/decryption: already implemented in `backend/tools/` credential helpers — same pattern for `client_secret`
- Config resolution with env fallback: `backend/core/config.py` model validators — add Keycloak optional fields with `= ""` defaults

### Integration Points
- `backend/main.py`: add `platform_config` auth mode check on startup, log the auth mode
- `backend/security/jwt.py` `validate_token()`: check if Keycloak is configured before attempting RS256 validation path
- `backend/api/routes/health.py`: add `auth` field to `HealthResponse`
- `frontend/src/app/login/page.tsx`: add `GET /api/auth/config` fetch + conditional SSO button rendering
- `frontend/src/auth.ts`: conditional Keycloak provider (checked at module init from env/config)
- `frontend/src/app/(authenticated)/admin/layout.tsx`: add Identity tab

</code_context>

<specifics>
## Specific Ideas

- JWKS cache reset should happen synchronously in the save endpoint so the next request immediately uses the new config — no async background job needed
- The `GET /api/auth/config` endpoint should be publicly accessible (no JWT required) so the login page can call it before authentication
- Connection test endpoint should also be admin-only (authenticated) — not public
- `platform_config` is a single-row table; upsert on save (no concept of multiple identity providers in v1.2)

</specifics>

<deferred>
## Deferred Ideas

- Multiple identity provider support (e.g., LDAP, SAML) — future phase
- Keycloak token revocation on SSO disable (forcing immediate logout of all SSO users) — deferred as too disruptive; graceful expiry is the v1.2 policy
- Self-service Keycloak setup wizard (step-by-step for new installations) — deferred to a UX polish phase

</deferred>

---

*Phase: 18-identity-configuration*
*Context gathered: 2026-03-06*
