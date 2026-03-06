---
status: diagnosed
phase: 18-identity-configuration
source: 18-01-SUMMARY.md, 18-02-SUMMARY.md, 18-03-SUMMARY.md
started: 2026-03-06T11:00:00Z
updated: 2026-03-06T11:30:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: —
name: (all tests complete)
expected: n/a
awaiting: n/a

## Tests

### 1. Backend health reports local-only mode
expected: With no Keycloak configured (default empty env vars), GET http://localhost:8000/health returns {"status": "ok", "auth": "local-only"}. The `auth` field is present and its value is "local-only" (not "local+keycloak").
result: issue
reported: "curl http://localhost:8000/health returned {\"status\":\"ok\",\"auth\":\"local+keycloak\"} — expected local-only when no Keycloak env vars set"
severity: major

### 2. Auth config endpoint returns sso_enabled=false
expected: GET http://localhost:8000/api/auth/config (no JWT required — public endpoint) returns {"auth": "local-only", "sso_enabled": false}. This endpoint must be reachable without an Authorization header.
result: issue
reported: "curl http://localhost:8000/api/auth/config returned {\"detail\":\"Not Found\"} — endpoint returns 404"
severity: major

### 3. Login page hides SSO button in local-only mode
expected: Navigate to http://localhost:3000/login. The page shows only the local credentials form (email + password). There is NO "Sign in with SSO" or Keycloak button visible. No error messages about missing SSO config.
result: issue
reported: "localhost:3000/login shows 'Internal Server Error' — frontend-1 container exited with code 0: 'Couldn't find any pages or app directory'"
severity: blocker

### 4. Admin layout shows Identity tab between Permissions and Config
expected: Log in as an admin user and navigate to http://localhost:3000/admin. The left nav should show tabs in this order: Users, Permissions, Identity, Config, Credentials. "Identity" appears between "Permissions" and "Config".
result: skipped
reason: Frontend container is down (blocker from test 3)

### 5. Identity page loads with Keycloak config form
expected: Navigate to http://localhost:3000/admin/identity. The page loads showing: a status badge ("SSO Active" in green, or "Local-only" in gray), and a form with fields: Issuer URL, Client ID, Client Secret, Realm, CA Cert Path (optional). There are "Test Connection" and "Save & Apply" buttons.
result: skipped
reason: Frontend container is down (blocker from test 3)

### 6. Test Connection shows inline result
expected: On the Identity page, enter any URL in the Issuer URL field and click "Test Connection". The result appears inline below the button — not as a toast popup or modal dialog. On failure, an error message with specific failure reason is shown. On success: "Connected — JWKS endpoint reachable, N key(s) found."
result: skipped
reason: Frontend container is down (blocker from test 3)

### 7. Client Secret field shows Change-secret toggle when secret exists
expected: If there is already a saved Keycloak config with a client_secret stored, the Identity page should show the Client Secret field as masked (dots / "••••••••") with a "Change secret" expand toggle. Clicking the toggle reveals an empty input to enter a new secret. The actual saved secret value is NEVER displayed.
result: skipped
reason: Frontend container is down (blocker from test 3)

### 8. Disable SSO confirmation dialog shows exact locked text
expected: When SSO is active (enabled config in DB), the Identity page shows a "Disable SSO" section. Clicking the disable button shows a confirmation dialog with EXACTLY this text: "Disabling SSO will prevent new Keycloak logins. Users currently logged in via SSO will remain logged in until their session expires. Continue?" No other wording is acceptable.
result: skipped
reason: Frontend container is down (blocker from test 3)

### 9. Save & Apply shows restart notice
expected: On the Identity page, fill in valid-looking Keycloak config fields and click "Save & Apply". After saving, the page shows a notice indicating that the frontend will restart (or is restarting) to apply the new SSO configuration.
result: skipped
reason: Frontend container is down (blocker from test 3)

## Summary

total: 9
passed: 0
issues: 3
pending: 0
skipped: 6

## Gaps

- truth: "GET /health returns auth: \"local-only\" when no Keycloak is configured"
  status: failed
  reason: "User reported: curl returned {\"status\":\"ok\",\"auth\":\"local+keycloak\"} — expected local-only"
  severity: major
  test: 1
  root_cause: "NOT a code bug — this is correct behavior. Migration 021 (platform_config table) has not been applied. DB read fails with UndefinedTableError → resolver falls back to env vars → KEYCLOAK_URL / KEYCLOAK_CLIENT_ID in backend/.env are populated → returns valid KeycloakConfig → health returns local+keycloak. To get local-only, either (a) clear Keycloak vars from .env, or (b) run just migrate so platform_config exists with enabled=false."
  artifacts:
    - path: "backend/alembic/versions/83f730920f5a_add_platform_config.py"
      issue: "Migration 021 exists but has not been applied to the running DB"
  missing:
    - "Run: just migrate (to apply migration 021 and create platform_config table)"

- truth: "GET /api/auth/config returns {\"auth\": \"...\", \"sso_enabled\": bool} without JWT"
  status: failed
  reason: "User reported: curl returned {\"detail\":\"Not Found\"} — endpoint returns 404"
  severity: major
  root_cause: "Stale backend process. The route auth_config.py exists and is correctly registered in main.py (line 163: app.include_router(auth_config_router)), but the running backend process was started before this code was committed and has not been restarted. Fix: restart the backend."
  artifacts:
    - path: "backend/api/routes/auth_config.py"
      issue: "File exists and correct, but running process doesn't have it loaded"
    - path: "backend/main.py"
      issue: "Line 163 has app.include_router(auth_config_router) — correct, but stale process"
  missing:
    - "Run: just backend-kill && just backend (restart to pick up committed code)"

- truth: "Login page loads (no Internal Server Error)"
  status: failed
  reason: "frontend-1 container exited with code 0: Couldn't find any pages or app directory. localhost:3000/login shows Internal Server Error."
  severity: blocker
  root_cause: "Dockerfile runner stage is missing COPY commands for tsconfig.json and next.config.ts. The standalone server.js has tsconfigPath:\"tsconfig.json\" baked in. At runtime, Next.js can't find the config → falls back to looking for app/ or pages/ directory → neither exists in runner image → crashes."
  artifacts:
    - path: "frontend/Dockerfile"
      issue: "Runner stage lines 21-23 copy .next/standalone, .next/static, public — but NOT tsconfig.json or next.config.ts"
  missing:
    - "Add to frontend/Dockerfile runner stage: COPY --from=builder /app/tsconfig.json /app/next.config.ts ./"
