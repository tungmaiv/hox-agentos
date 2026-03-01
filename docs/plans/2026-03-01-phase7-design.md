# Phase 7 Design: Hardening, Sandbox & User Experience

**Authored:** 2026-03-01
**Phase:** 07-hardening-sandbox-ux
**Status:** Approved — ready for planning

---

## Overview

Phase 7 closes the remaining v1.1 milestone gaps and adds the final hardening and UX polish layer. Five distinct areas of work:

1. **Docker Sandbox** — SBOX-01, SBOX-02, SBOX-03 (core requirements)
2. **Workflow → Channel Delivery Fix** — closes WKFL-03, WKFL-04 (broken external_chat_id)
3. **agent_node Real Dispatch** — wires canvas workflow agent_node to real sub-agents
4. **Credential Management UI** — settings page + provider-agnostic OAuth stub
5. **Session Management** — logout button + silent token refresh + session expiry handling

Gate criteria: Docker sandbox runs without host access; canvas workflow delivers to Telegram end-to-end; users can log out and sessions auto-refresh.

---

## 1. Docker Sandbox (SBOX-01, SBOX-02, SBOX-03)

### Architecture: DooD (Docker out of Docker)

The backend container mounts the host's Docker socket. When sandbox_required=True tools are invoked, the executor calls the **host Docker daemon** to spawn sibling sandbox containers. Sandbox containers are peers to the backend container — they run at the host level, not nested inside the backend.

```
Host Docker Daemon
├── backend container (mounts /var/run/docker.sock)
├── postgres container
├── redis container
└── blitz-sandbox-XXXX container  ← spawned by backend, sibling on host daemon
```

### docker-compose.yml change

Add to the `backend` service:

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

### New files

```
backend/sandbox/
├── __init__.py
├── docker_client.py    # Docker SDK wrapper: create, exec, kill, rm container
├── policies.py         # SandboxPolicy: resource limits, image map, ACL
└── executor.py         # SandboxExecutor.run(code, lang, timeout) → SandboxResult
```

### Resource limits (SBOX-01)

| Resource | Limit |
|----------|-------|
| CPU | 0.5 CPU (`nano_cpus=500_000_000`) |
| Memory | 128 MB (`mem_limit="128m"`, `memswap_limit="128m"`) |
| Network | None (`network_mode="none"`) |
| Timeout | 30s default (configurable per policy) |
| User inside container | `nobody` (non-root) |

### Host filesystem isolation (SBOX-02)

No volume mounts on sandbox containers. Containers are created with:
- No `binds` or `volumes` parameters
- `read_only=True` on container root filesystem

Code is passed as an environment variable or stdin, not via mounted file.

### Cleanup (SBOX-03)

- Primary: `auto_remove=True` on container — Docker removes it immediately on exit
- Secondary: `executor.py` kills container after timeout via `container.kill()` then `container.remove()`
- Belt-and-suspenders: Celery periodic task (`sandbox_cleanup`) runs every 5 minutes, removes any `blitz-sandbox-*` containers older than 5 minutes (catches crashed/leaked containers)

### Custom base image

```
infra/sandbox-runtime/python/Dockerfile
```

Extends `python:3.12-slim` with pre-installed common libraries:
- pandas, numpy, requests, httpx
- beautifulsoup4, lxml
- python-dateutil, pytz
- jinja2, pydantic

Built once via `docker compose build` or `just build-sandbox`. Container startup is ~200ms (no runtime pip install).

Future images: `blitz-sandbox-data` (scipy, sklearn), `blitz-sandbox-browser` (Playwright) as needed.

### Tool registrations

Register two new tools in the migration seed or `startup_seed()`:

```python
"code.python_exec": {
    "description": "Execute Python code in an isolated container",
    "required_permissions": ["tool:sandbox.exec"],
    "handler_type": "sandbox",
    "sandbox_required": True,
}
"code.bash_exec": {
    "description": "Execute a bash script in an isolated container",
    "required_permissions": ["tool:sandbox.exec"],
    "handler_type": "sandbox",
    "sandbox_required": True,
}
```

Default ACL: `admin` and `developer` roles get `tool:sandbox.exec`. `employee` and `viewer` do not.

### Dispatch path

In `gateway/tool_registry.py`, when a tool with `sandbox_required=True` is dispatched, route to `SandboxExecutor.run()` instead of calling the local Python function.

```python
# executor.py
@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    timed_out: bool
```

---

## 2. Workflow → Channel Delivery Fix (WKFL-03, WKFL-04)

### Root cause

`_handle_channel_output_node` in `backend/agents/node_handlers.py` (lines 218–223) builds an `InternalMessage` with `external_chat_id=None` because the workflow execution context (`user_context`) contains only `user_id`, `email`, `username`, `roles`, `groups` — no channel account info.

### Fix

In `_handle_channel_output_node`, before sending to the channel gateway:

1. Query `channel_accounts` table: `WHERE user_id = $user_context.user_id AND channel = $output_config.channel`
2. If no account found: log a warning and return gracefully (skip delivery)
3. If found: set `external_chat_id = account.external_user_id` on the `InternalMessage`

This is a ~20-line targeted fix in `node_handlers.py`. No schema changes needed.

### Files changed

- `backend/agents/node_handlers.py` — `_handle_channel_output_node()` function

---

## 3. agent_node Real Dispatch

### Root cause

`_handle_agent_node` in `node_handlers.py` (lines 54–66) returns hardcoded stub output. Plan 04-03 wired `tool_node` correctly but left `agent_node` as a mock.

### Design

The canvas node config includes `agent_id` and `instruction`. When agent_node runs:

1. If `agent_id` is set and matches a known sub-agent: dispatch to that sub-agent directly
2. If no `agent_id` or `agent_id = "master"`: dispatch to the master agent with `instruction` as the user message

This is the "master agent with sub-agent hint" approach: direct when possible, fallback to master otherwise.

The agent receives the workflow's `user_context` (user_id, roles) via contextvar so memory isolation and tool ACL apply normally.

### Files changed

- `backend/agents/node_handlers.py` — `_handle_agent_node()` function
- `backend/agents/master_agent.py` — expose a `run_as_subgraph(instruction, user_context)` helper if not already available

---

## 4. Credential Management UI

### Backend additions

The existing API has:
- `GET /api/credentials` — list connected providers (returns provider name + connected_at; never tokens)
- `DELETE /api/credentials/{provider}` — disconnect a provider

Phase 7 adds:
- `POST /api/credentials/connect/{provider}` — returns an OAuth authorization URL. For providers without configured OAuth app credentials, returns `{"url": null, "message": "OAuth not configured for this provider"}` with HTTP 200.
- `GET /api/credentials/callback/{provider}` — OAuth callback. For unconfigured providers, returns HTTP 501. When credentials are configured, exchanges code for tokens, encrypts, stores in DB.

Provider enum: `google`, `microsoft`

### Frontend — `/settings/integrations`

New tab under `/settings`. Shows all supported providers in a card grid:

```
Connected Accounts

[Google Workspace]
Status: Connected (2026-02-10)
[Disconnect]

[Microsoft 365]
Status: Not connected
[Connect →]
```

- "Connect" button: calls `POST /api/credentials/connect/{provider}`, follows the returned URL. If URL is null, shows a modal: "Google Workspace OAuth is not configured yet. Contact your admin."
- "Disconnect" button: confirmation dialog → `DELETE /api/credentials/{provider}` → removes card connected state

### Files added/changed

- `backend/api/routes/credentials.py` — add connect + callback endpoints
- `frontend/src/app/settings/integrations/page.tsx` — new page
- `frontend/src/components/settings/provider-card.tsx` — reusable provider card component

---

## 5. Session Management

### Logout

Add a logout button to the app header/sidebar (wherever the user avatar/name is displayed).

- Calls `signOut({ callbackUrl: '/login' })` from NextAuth
- NextAuth clears the session and redirects to `/login`
- The login page redirects to Keycloak for re-authentication

Optional: also call Keycloak's `end_session_endpoint` to terminate the SSO session (full SSO logout). Without this, logging out of the app doesn't log the user out of Keycloak — they'd be silently re-authenticated on next visit.

### Silent token refresh

NextAuth's `jwt` callback handles token refresh. Update `auth.ts` to:

1. Track `expires_at` on the session token (compute as `Date.now() + expires_in * 1000` from Keycloak's token response)
2. In the `jwt` callback: if `Date.now() > token.expires_at - 60_000` (1 minute buffer), call Keycloak's `token_endpoint` with `grant_type=refresh_token`
3. If refresh succeeds: update `access_token`, `expires_at` on the session token
4. If refresh fails (refresh token expired): set `error: "RefreshAccessTokenError"` on the token

### Session expiry handling

In `frontend/src/components/auth/session-guard.tsx` (new component, wraps the app):

- Read `session.error` via `useSession()`
- If `error === "RefreshAccessTokenError"`: show a modal overlay: "Your session has expired. Please log in again." with a single "Log in" button that calls `signOut({ callbackUrl: '/login' })`
- This prevents the user from making API calls with an expired token

### Files added/changed

- `frontend/src/app/api/auth/[...nextauth]/auth.ts` — add `expires_at` tracking + refresh logic in `jwt` callback
- `frontend/src/components/auth/session-guard.tsx` — new: wraps app, shows expiry modal
- `frontend/src/app/layout.tsx` — wrap with `SessionGuard`
- App header/sidebar component — add logout button

---

## Implementation Phases (suggested plan structure)

| Plan | Scope | Dependencies |
|------|-------|--------------|
| 07-01 | Docker sandbox: base image + executor + policies | None |
| 07-02 | Sandbox tool registration + dispatch routing + tests | 07-01 |
| 07-03 | Workflow channel delivery fix (external_chat_id) | None |
| 07-04 | agent_node real dispatch | None |
| 07-05 | Credential management UI (backend endpoints + frontend page) | None |
| 07-06 | Session management (logout + token refresh + expiry modal) | None |

Plans 07-01/03/04/05/06 can execute in Wave 1 (parallel). Plan 07-02 waits on 07-01.

---

## Non-Goals

- Full OAuth production setup for Google/Microsoft (stubs only)
- WhatsApp and Teams live testing (deferred, credentials not available)
- Playwright / browser sandbox image (deferred to Phase 8 or post-MVP)
- Kubernetes deployment (post-MVP)

---

*Approved: 2026-03-01*
*Designed by: Claude Code (claude-sonnet-4-6) + human review*
