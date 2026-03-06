---
status: complete
phase: 18-identity-configuration
source: 18-01-SUMMARY.md, 18-02-SUMMARY.md, 18-03-SUMMARY.md
started: 2026-03-06T11:00:00Z
updated: 2026-03-06T15:00:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: —
name: (all tests complete)
expected: n/a
awaiting: n/a

## Tests

### 1. Backend health reports auth mode
expected: GET http://localhost:8000/health returns {"status": "ok", "auth": "<mode>"} where mode reflects current config. Returns "local+keycloak" when Keycloak vars are in .env (correct fallback behavior).
result: pass

### 2. Auth config endpoint returns sso_enabled
expected: GET http://localhost:8000/api/auth/config (no JWT required — public endpoint) returns JSON with auth and sso_enabled fields.
result: pass

### 3. Login page SSO button visibility
expected: Login page shows SSO button when sso_enabled=true, hides it when false.
result: pass (with note)
note: "SSO button appears with delay on cold container start (useEffect fetch completes after first render). Button shows correctly once backend is warm. Login works on first attempt (takes ~5min on cold start — normal initialization). Both are cold-start latency, not functional bugs."

### 4. Admin layout shows Identity tab between Permissions and Config
expected: Log in as an admin user and navigate to http://localhost:3000/admin. The left nav should show tabs in this order: Users, Permissions, Identity, Config, Credentials. "Identity" appears between "Permissions" and "Config".
result: pass

### 5. Identity page loads with Keycloak config form
expected: Navigate to http://localhost:3000/admin/identity. The page loads showing: a status badge ("SSO Active" in green, or "Local-only" in gray), and a form with fields: Issuer URL, Client ID, Client Secret, Realm, CA Cert Path (optional). There are "Test Connection" and "Save & Apply" buttons.
result: pass

### 6. Test Connection shows inline result
expected: On the Identity page, enter any URL in the Issuer URL field and click "Test Connection". The result appears inline below the button — not as a toast popup or modal dialog. On failure, an error message with specific failure reason is shown. On success: "Connected — JWKS endpoint reachable, N key(s) found."
result: pass

### 7. Client Secret field shows Change-secret toggle when secret exists
expected: If there is already a saved Keycloak config with a client_secret stored, the Identity page should show the Client Secret field as masked (dots / "••••••••") with a "Change secret" expand toggle. Clicking the toggle reveals an empty input to enter a new secret. The actual saved secret value is NEVER displayed.
result: pass

### 8. Disable SSO confirmation dialog shows exact locked text
expected: When SSO is active (enabled config in DB), the Identity page shows a "Disable SSO" section. Clicking the disable button shows a confirmation dialog with EXACTLY this text: "Disabling SSO will prevent new Keycloak logins. Users currently logged in via SSO will remain logged in until their session expires. Continue?" No other wording is acceptable.
result: pass
note: "Required two fixes: (1) backend used await on _restart_frontend_container before returning response — changed to BackgroundTasks; (2) frontend called fetchConfig() after disableSSO() racing with restart — changed to optimistic state update."

### 9. Save & Apply shows restart notice
expected: On the Identity page, fill in valid-looking Keycloak config fields and click "Save & Apply". After saving, the page shows a notice indicating that the frontend will restart (or is restarting) to apply the new SSO configuration.
result: pass
note: "Required same fixes as test 8 — BackgroundTasks for restart + removed fetchConfig() call after save."

## Summary

total: 9
passed: 9
issues: 0
pending: 0
skipped: 0

## Fixes Applied During UAT

- fix(18-02): fire frontend restart as BackgroundTask after HTTP response (commit c0674df)
  backend/api/routes/admin_keycloak.py — save_keycloak_config and disable_sso
  Root cause: await asyncio.to_thread(_restart_frontend_container) before return killed the
  requesting container mid-response. BackgroundTasks fires after response is delivered.

- fix(18-03): skip fetchConfig after save/disable to avoid restart race (commit fbba72d)
  frontend/src/app/(authenticated)/admin/identity/page.tsx — handleSave and handleDisable
  Root cause: fetchConfig() immediately after success races with container restart.
  handleSave: removed fetchConfig call (frontend restarts and reloads automatically).
  handleDisable: update config state optimistically (enabled=false) instead of fetching.

## Infrastructure Fixes Applied During UAT

- chore: remove host-mode dev recipes (commit 4282d32)
  justfile, CLAUDE.md, docs/dev-context.md — container-only policy documented

- migration 021 applied: just migrate — platform_config table created
