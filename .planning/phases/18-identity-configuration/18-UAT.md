---
status: diagnosed
phase: 18-identity-configuration
source: 18-01-SUMMARY.md, 18-02-SUMMARY.md, 18-03-SUMMARY.md
started: 2026-03-06T11:00:00Z
updated: 2026-03-06T14:30:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 9
name: Save & Apply shows restart notice
expected: After saving, page shows notice that frontend is restarting
awaiting: fix (same root cause as test 8 disable issue)

## Tests

### 1. Backend health reports auth mode
expected: GET http://localhost:8000/health returns {"status": "ok", "auth": "<mode>"} where mode reflects current config. Returns "local+keycloak" when Keycloak vars are in .env (correct fallback behavior).
result: pass

### 2. Auth config endpoint returns sso_enabled
expected: GET http://localhost:8000/api/auth/config (no JWT required — public endpoint) returns JSON with auth and sso_enabled fields.
result: pass

### 3. Login page SSO button visibility
expected: Login page shows SSO button when sso_enabled=true, hides it when false.
result: issue
reported: "SSO button not shown on fresh /login load (only appears after signout redirect ?signedOut=true). Login with admin/admin took 5 minutes on first attempt, fast on subsequent logins."
severity: minor
root_cause: "Cold-start timing issue. SSO button: useEffect fetches /api/auth/config asynchronously after mount. On first container start, fetch is slow (backend cold start) so button appears with delay after user has already started interacting. After signout, backend is warm → fetch completes fast → button shows immediately. Login speed: first request to http://backend:8000/api/auth/local/token triggers backend initialization (DB connection pool, module-level bcrypt hash); subsequent calls fast. Both are cold-start latency, not functional bugs. SSO button does appear; login does work."

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
result: issue
reported: "Dialog text and inline placement are correct. Clicking 'Yes, Disable SSO' throws RuntimeError 'Failed to fetch'. SSO IS disabled in DB (functional), but client receives a network error instead of success response."
severity: major

### 9. Save & Apply shows restart notice
expected: On the Identity page, fill in valid-looking Keycloak config fields and click "Save & Apply". After saving, the page shows a notice indicating that the frontend will restart (or is restarting) to apply the new SSO configuration.
result: issue
reported: "Not yet re-tested after fix — same root cause as test 8."
severity: major

## Summary

total: 9
passed: 6
issues: 2 (tests 3, 8/9 share one root cause — tests 8 and 9 need re-test after fix)
pending: 0
skipped: 0

## Gaps

- truth: "Disable SSO / Save & Apply return success response before restarting frontend"
  status: open
  reason: "Both endpoints call await asyncio.to_thread(_restart_frontend_container) BEFORE returning the HTTP response. Since the frontend container IS making the proxy request, Docker kills it mid-await, dropping the connection. Client receives 'Failed to fetch' instead of the JSON response."
  severity: major
  tests: [8, 9]
  root_cause: "_restart_frontend_container() is awaited synchronously in the request handler. FastAPI BackgroundTasks fires after the response is sent — the restart must be moved there."
  artifacts:
    - path: "backend/api/routes/admin_keycloak.py"
      issue: "save_keycloak_config line 338: await asyncio.to_thread(_restart_frontend_container) — awaited before return; kills requesting container"
      fix: "Use background_tasks: BackgroundTasks = Depends(); background_tasks.add_task(_restart_frontend_container)"
    - path: "backend/api/routes/admin_keycloak.py"
      issue: "disable_sso line 381: await asyncio.to_thread(_restart_frontend_container) — same issue"
      fix: "Same fix: background_tasks.add_task(_restart_frontend_container)"
  missing:
    - "Add BackgroundTasks import from fastapi"
    - "Add background_tasks: BackgroundTasks parameter to save_keycloak_config and disable_sso"
    - "Replace await asyncio.to_thread(_restart_frontend_container) with background_tasks.add_task(_restart_frontend_container)"

- truth: "GET /health returns auth: \"local-only\" when no Keycloak is configured"
  status: resolved
  reason: "Migration 021 was not applied. After just migrate, platform_config table exists with no enabled row → correct resolver behavior."
  test: 1

- truth: "GET /api/auth/config returns {\"auth\": \"...\", \"sso_enabled\": bool} without JWT"
  status: resolved
  reason: "Stale backend process — resolved via hot-reload after migration."
  test: 2

- truth: "Login page loads (no Internal Server Error)"
  status: resolved
  reason: "Dockerfile runner stage issue was a false diagnosis — dev mode uses Dockerfile.dev with volume mounts, not the production Dockerfile. Container recovered after restart."
  test: 3
