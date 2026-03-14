# Blitz AgentOS — Developer Context

> **For AI agents:** Read this file at the start of any implementation or testing task.
> Update it immediately when you discover new endpoints, URL patterns, or service mappings.
> For actual credentials (passwords, tokens, keys), read `.dev-secrets` if it exists.

---

## 1. URL Reference — Docker-Internal vs Localhost

Containers communicate with each other using Docker service names.
Your browser and local CLI tools use `localhost`.
Ollama runs on the **host machine** — containers reach it via `host.docker.internal`.

| Service | From browser / host CLI | From inside a container |
|---------|------------------------|------------------------|
| Frontend (Next.js) | `http://localhost:3000` | `http://frontend:3000` |
| Backend (FastAPI) | `http://localhost:8000` | `http://backend:8000` |
| Keycloak | `http://localhost:8080` | `http://keycloak:8080` |
| LiteLLM Proxy | `http://localhost:4000` | `http://litellm:4000` |
| MCP CRM Server | `http://localhost:8001` | `http://mcp-crm:8001` |
| MCP Docs Server | `http://localhost:8002` | `http://mcp-docs:8002` |
| PostgreSQL | `localhost:5432` | `postgres:5432` |
| Redis | `localhost:6379` | `redis:6379` |
| Ollama | `http://localhost:11434` | `http://host.docker.internal:11434` |

> **Linux note:** `host.docker.internal` requires `extra_hosts: ["host.docker.internal:host-gateway"]`
> in the Docker Compose service definition for LiteLLM (and any other container that calls Ollama).

---

## Cloudflare Tunnel (Webhook Routing)

**Status:** Running externally — no docker-compose service needed.

The Cloudflare Tunnel for this project runs on an external machine at:
- IP: `172.16.155.118`

All three channel webhook endpoints are exposed through this tunnel:
- `POST /api/channels/telegram/webhook`
- `POST /api/channels/whatsapp/webhook`
- `POST /api/channels/teams/webhook`

INFRA-01 (webhook endpoints via Cloudflare Tunnel) and INFRA-02 (tunnel runs as service with token in .env) are satisfied externally. No `cloudflared` container exists in docker-compose.yml — the tunnel is managed on the dedicated external machine.

To verify the tunnel is routing correctly: check the Cloudflare Tunnel dashboard, or send a test Telegram message and confirm it reaches the backend webhook handler.

---

## 2. Backend API Endpoints

Base URL (local dev): `http://localhost:8000`

### Authentication
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (no auth) |
| GET | `/api/auth/me` | Current user info (requires JWT) |
| GET | `/api/auth/config` | Public auth mode info (local-only vs SSO enabled) |
| POST | `/api/auth/local/token` | Local user login — returns JWT |
| POST | `/api/auth/local/change-password` | Change local user password (requires JWT) |

### Agents
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/agents/chat` | Main AG-UI streaming endpoint |
| POST | `/api/agents/workflow/run` | Trigger a workflow manually |

### Conversations
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/conversations/` | List user's conversations (sidebar history) |
| PATCH | `/api/conversations/{id}/title` | Rename a conversation |
| DELETE | `/api/conversations/{id}` | Delete a conversation |
| GET | `/api/conversations/{id}/messages` | Get all turns in a conversation |

### Workflows (Canvas)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/workflows` | List user's workflows |
| POST | `/api/workflows` | Create new workflow |
| GET | `/api/workflows/templates` | List template workflows |
| POST | `/api/workflows/templates/{template_id}/copy` | Copy template to user's workflows |
| GET | `/api/workflows/runs/pending-hitl` | Count paused HITL runs awaiting approval |
| GET | `/api/workflows/runs/{run_id}` | Get a specific workflow run |
| POST | `/api/workflows/runs/{run_id}/approve` | Approve a HITL-paused run |
| POST | `/api/workflows/runs/{run_id}/reject` | Reject a HITL-paused run |
| GET | `/api/workflows/runs/{run_id}/events` | SSE stream of live run events |
| GET | `/api/workflows/{id}` | Get workflow by ID |
| PUT | `/api/workflows/{id}` | Update workflow definition |
| DELETE | `/api/workflows/{id}` | Delete workflow |
| POST | `/api/workflows/{id}/run` | Execute a workflow |
| GET | `/api/workflows/{id}/triggers` | List workflow triggers (cron + webhook) |
| POST | `/api/workflows/{id}/triggers` | Create a trigger for a workflow |
| DELETE | `/api/workflows/{id}/triggers/{trigger_id}` | Delete a workflow trigger |

> **Note:** There are no `/api/scheduler/*` REST routes. Scheduled jobs run as Celery tasks,
> triggered by workflow triggers (cron type stored in `workflow_triggers` table).

### Channels
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/channels/info` | Channel sidecar availability + metadata |
| GET | `/api/channels/accounts` | List user's linked channel accounts |
| POST | `/api/channels/pair` | Generate pairing code for channel link |
| DELETE | `/api/channels/accounts/{account_id}` | Unlink a channel account |
| POST | `/api/channels/telegram/webhook` | Telegram inbound webhook (Cloudflare Tunnel) |
| POST | `/api/channels/whatsapp/webhook` | WhatsApp inbound webhook |
| POST | `/api/channels/teams/webhook` | MS Teams inbound webhook |
| POST | `/api/channels/incoming` | Internal — receive InternalMessage from channel sidecar |

### User APIs
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/credentials/` | List user's connected OAuth providers |
| DELETE | `/api/credentials/{provider}` | Disconnect an OAuth provider |
| GET | `/api/user/memory/facts` | User's long-term memory facts |
| DELETE | `/api/user/memory/facts/{fact_id}` | Delete a single fact |
| DELETE | `/api/user/memory/facts` | Delete all facts (bulk clear) |
| GET | `/api/user/memory/episodes` | User's episodic memories |
| GET | `/api/user/preferences` | Get chat preferences (thinking mode, response style) |
| PUT | `/api/user/preferences` | Update chat preferences |
| GET | `/api/user/instructions` | Get custom instructions injected into agent context |
| PUT | `/api/user/instructions` | Update custom instructions |
| GET | `/api/users/me/preferences` | Get user preferences (NAV-07/08 — LLM mode, style) |
| PUT | `/api/users/me/preferences` | Update user preferences |

### Tools
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tools` | List tools available to current user (role-filtered) |
| POST | `/api/tools/call` | Execute a tool via registry (agent-facing, JWT required) |

### Skills (User-facing)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/skills` | List skills available to current user; response includes `is_promoted` and `is_shared` per item |
| GET | `/api/skills?promoted=true` | List only promoted skills (Featured Skills section) |
| GET | `/api/skills/{id}/export` | Download skill as agentskills.io ZIP (auth required) |
| POST | `/api/skills/{name}/run` | Execute a skill by name (procedural or instructional) |

### Skill Repositories
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/skill-repos` | List user's skill repositories |
| POST | `/api/skill-repos/browse` | Browse skills in an external repository |
| POST | `/api/skill-repos/import` | Import a skill from an external repository |
| GET | `/api/admin/skill-repos` | Admin: list all skill repositories |
| POST | `/api/admin/skill-repos` | Admin: add a skill repository |
| DELETE | `/api/admin/skill-repos/{id}` | Admin: remove a skill repository |

### Webhooks
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/webhooks/{webhook_id}` | Trigger a workflow via webhook (X-Webhook-Secret validation) |

### Admin — Extensibility Registries (Phase 6)

All admin endpoints require `registry:manage` permission (Gate 2 RBAC — it-admin role).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/agents` | List all agent definitions |
| POST | `/api/admin/agents` | Create agent definition |
| GET | `/api/admin/agents/check-name` | Check if agent name is available |
| GET | `/api/admin/agents/{id}` | Get agent by UUID |
| PUT | `/api/admin/agents/{id}` | Update agent fields |
| PATCH | `/api/admin/agents/{id}/status` | Enable/disable agent |
| PATCH | `/api/admin/agents/{id}/activate` | Activate version (deactivate others) |
| PATCH | `/api/admin/agents/bulk-status` | Bulk status update |
| GET | `/api/admin/tools` | List all tool definitions |
| POST | `/api/admin/tools` | Create tool definition |
| GET | `/api/admin/tools/check-name` | Check if tool name is available |
| GET | `/api/admin/tools/{id}` | Get tool by UUID |
| PUT | `/api/admin/tools/{id}` | Update tool fields |
| PATCH | `/api/admin/tools/{id}/status` | Enable/disable tool |
| PATCH | `/api/admin/tools/{id}/activate` | Activate version |
| PATCH | `/api/admin/tools/{id}/activate-stub` | Activate a pending-stub tool (Phase 25) |
| PATCH | `/api/admin/tools/bulk-status` | Bulk status update |
| GET | `/api/admin/skills` | List all skill definitions |
| POST | `/api/admin/skills` | Create skill definition (defaults to `draft` status — Phase 25) |
| GET | `/api/admin/skills/check-name` | Check if skill name is available |
| GET | `/api/admin/skills/pending` | List skills pending review |
| POST | `/api/admin/skills/import` | Import skill from URL or inline |
| POST | `/api/admin/skills/builder-save` | Save artifact builder output as skill (Phase 23) |
| POST | `/api/admin/skills/import/zip` | Import skill from agentskills.io ZIP upload (Phase 23) |
| GET | `/api/admin/skills/{id}` | Get skill by UUID |
| PUT | `/api/admin/skills/{id}` | Update skill fields |
| PATCH | `/api/admin/skills/{id}/status` | Enable/disable skill |
| PATCH | `/api/admin/skills/{id}/activate` | Activate version (422 if tool_gaps present — Phase 25) |
| PATCH | `/api/admin/skills/bulk-status` | Bulk status update |
| POST | `/api/admin/skills/{id}/validate` | Dry-run validate procedure |
| POST | `/api/admin/skills/{id}/review` | Approve/reject quarantined skill |
| GET | `/api/admin/skills/{id}/security-report` | Get security scan report |
| PATCH | `/api/admin/skills/{id}/promote` | Toggle is_promoted flag (registry:manage) |
| POST | `/api/admin/skills/{id}/share` | Share skill with user (body: {user_id}, registry:manage) |
| DELETE | `/api/admin/skills/{id}/share/{user_id}` | Revoke user share (registry:manage) |
| GET | `/api/admin/skills/{id}/shares` | List users with access to skill (registry:manage) |
| GET | `/api/admin/mcp-servers` | List registered MCP servers |
| POST | `/api/admin/mcp-servers` | Register a new MCP server |
| GET | `/api/admin/mcp-servers/check-name` | Check if MCP server name is available |
| GET | `/api/admin/mcp-servers/{id}` | Get MCP server by UUID |
| PUT | `/api/admin/mcp-servers/{id}` | Update MCP server config |
| DELETE | `/api/admin/mcp-servers/{id}` | Delete MCP server |
| PUT | `/api/admin/permissions/roles/{role}` | Set role permissions |
| PUT | `/api/admin/permissions/artifacts/{id}` | Set artifact permissions (staged) |
| POST | `/api/admin/permissions/apply` | Apply pending permissions |
| PUT | `/api/admin/permissions/users/{id}` | Set per-user permission override |

### Admin — Unified Registry (Phase 24)

All unified registry endpoints require `tool:admin` permission (Gate 2 RBAC — it-admin role).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/registry` | List registry entries (filter by type, status) |
| POST | `/api/registry` | Create registry entry |
| GET | `/api/registry/mcp-catalog` | List pre-built MCP server catalog |
| POST | `/api/registry/import` | Import skill from URL or inline |
| GET | `/api/registry/{id}` | Get entry by UUID |
| PUT | `/api/registry/{id}` | Update entry |
| DELETE | `/api/registry/{id}` | Delete entry |

### Admin — LLM Configuration (Phase 24)

All endpoints require `tool:admin` permission.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/llm/models` | List all configured LLM model aliases |
| POST | `/api/admin/llm/models` | Add or update a model alias |
| DELETE | `/api/admin/llm/models/{alias}` | Remove a model alias |

### Admin — System (Phase 24)

All endpoints require `tool:admin` permission.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/system/health` | System component health check |
| POST | `/api/admin/system/rescan-skills` | Trigger retroactive security rescan of all skills |

### Admin — Memory

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/admin/memory/reindex` | Trigger full memory reindex (re-embeds all facts/episodes) |

### Admin — Config (System Key/Value)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/config` | Get system configuration |
| PUT | `/api/admin/config/{key}` | Update a specific config key |

### Admin — Identity (Keycloak)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/keycloak/config` | Get current Keycloak config (has_secret: bool, never raw secret) |
| POST | `/api/admin/keycloak/config` | Save Keycloak config (Issuer, Client ID, Client Secret, Realm) |
| POST | `/api/admin/keycloak/config/test` | Test Keycloak connection before saving |
| POST | `/api/admin/keycloak/enable` | Enable SSO (apply saved Keycloak config) |
| POST | `/api/admin/keycloak/disable` | Disable SSO (revert to local-only auth) |
| GET | `/api/admin/keycloak/users` | List Keycloak users |
| GET | `/api/internal/keycloak/provider-config` | Internal — Next.js server fetches provider config (X-Internal-Key header) |

### Admin — Local Users

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/admin/local/users` | Create local user |
| GET | `/api/admin/local/users` | List local users |
| GET | `/api/admin/local/users/{id}` | Get local user by ID |
| PUT | `/api/admin/local/users/{id}` | Update local user |
| DELETE | `/api/admin/local/users/{id}` | Delete local user |
| POST | `/api/admin/local/users/{id}/groups` | Add user to group |
| DELETE | `/api/admin/local/users/{id}/groups/{group_id}` | Remove user from group |
| POST | `/api/admin/local/users/{id}/roles` | Assign role to user |
| DELETE | `/api/admin/local/users/{id}/roles/{role}` | Remove role from user |

### Admin — Credentials

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/credentials` | List all credential entries (admin view — no tokens) |
| DELETE | `/api/admin/credentials/{user_id}/{provider}` | Revoke a user's provider credential |

### CopilotKit
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/copilotkit` | Single-route AG-UI endpoint (JSON envelope protocol) |

**CopilotKit endpoint protocol** (`@copilotkitnext` v1.51.4, `runtimeTransport="single"`):

All requests are `POST /api/copilotkit` with a JSON envelope body:

```json
// Agent discovery (runtime sync — called on component mount)
{ "method": "info" }
// Response: { "version": "0.1.0", "agents": { "blitz_master": { "description": "..." } }, "audioFileTranscriptionEnabled": false }

// Agent execution (streaming)
{ "method": "agent/run", "params": { "agentId": "blitz_master" }, "body": <RunAgentInput> }
// Response: Server-Sent Events stream (AG-UI protocol)
```

**`RunAgentInput` body fields** (camelCase, from `ag_ui.core`):
- `threadId` — conversation UUID (maps to `thread_id`)
- `runId` — unique run UUID
- `messages` — array of chat messages
- `tools` — frontend tool definitions
- `context` — context items
- `state` — agent state dict
- `forwardedProps` — extra forwarded props

**Important:** Use `RunAgentInput.model_validate(body)` — NOT `RunAgentInput(**body)`. The model uses camelCase aliases and `validate_by_alias=True`.

**Frontend proxy**: `frontend/src/app/api/copilotkit/route.ts` injects the server-side JWT from next-auth session before forwarding to backend. The browser never sees the JWT.

---

## 3. Frontend Routes

Base URL (local dev): `http://localhost:3000`

All routes under `/(authenticated)/` require a valid session — unauthenticated access redirects to `/login`.

| Path | Description |
|------|-------------|
| `/` | Redirects to `/chat` |
| `/login` | Login page (local credentials or SSO button) |
| `/chat` | AG-UI chat interface |
| `/workflows` | Canvas workflow list |
| `/workflows/new` | Create new workflow |
| `/workflows/[id]` | Edit a specific workflow (canvas) |
| `/skills` | User skill catalog |
| `/profile` | User profile — account info, password change, preferences |
| `/settings` | Settings hub |
| `/settings/agents` | Agent settings |
| `/settings/channels` | Channel connections (Telegram, WhatsApp, Teams) |
| `/settings/chat-preferences` | Chat preference settings |
| `/settings/integrations` | OAuth integrations |
| `/settings/memory` | Memory management (view/delete facts and episodes) |
| `/admin` | Admin hub (Registry counts + navigation) |
| `/admin/agents` | Admin: agent registry |
| `/admin/tools` | Admin: tool registry |
| `/admin/skills` | Admin: skill registry list |
| `/admin/skills/[id]` | Admin: skill detail (metadata, security report) |
| `/admin/mcp-servers` | Admin: MCP server registry |
| `/admin/builder` | Artifact builder (AI-assisted skill/tool creation) |
| `/admin/skill-store` | Skill store browser (external registries) |
| `/admin/create` | Create new registry entry |
| `/admin/access` | Admin: access management hub |
| `/admin/users` | Admin: user management |
| `/admin/permissions` | Admin: role permissions |
| `/admin/credentials` | Admin: credentials viewer |
| `/admin/identity` | Admin: Keycloak SSO configuration |
| `/admin/config` | Admin: system configuration |
| `/admin/system` | Admin: system status and maintenance |
| `/admin/system/llm` | Admin: LLM model/provider configuration |
| `/admin/memory` | Admin: memory reindex |
| `/api/copilotkit` | Next.js API route — AG-UI proxy to backend (injects JWT) |

---

## 4. Keycloak

Admin console: `http://keycloak.blitz.local:8180/admin`
Realm: `blitz-internal`
OIDC discovery: `http://keycloak.blitz.local:8180/realms/blitz-internal/.well-known/openid-configuration`
Token endpoint: `http://keycloak.blitz.local:8180/realms/blitz-internal/protocol/openid-connect/token`

**Ports:** HTTP on `:8180` (external) → 8080 internal | HTTPS on `:7443` (external) → 8443 internal
**Use HTTPS `:7443`** — the issuer in the discovery document is `https://keycloak.blitz.local:7443/...`. OIDC requires exact issuer match.
**Self-signed cert:** `frontend/certs/keycloak-ca.crt` — sourced from `devops:/home/tungvm/Projects/hox-aa/infrastructure/shared/keycloak/certs/keycloak.crt`
**Node.js trust:** `NODE_EXTRA_CA_CERTS=./certs/keycloak-ca.crt` set in `frontend/package.json` dev script.
**Python/FastAPI trust:** Set `SSL_CERT_FILE` or `REQUESTS_CA_BUNDLE` env var pointing to the same cert if needed.

### Clients
| Client | Used by | Notes |
|--------|---------|-------|
| `blitz-portal` | Frontend (Next.js) | Redirect URI: `http://localhost:3000/*` |
| `blitz-backend` | Backend (FastAPI) | Server-to-server JWT validation |

### Roles
| Role | Permissions |
|------|------------|
| `admin` | All tools, all MCP, sandbox exec, user management |
| `developer` | All tools, MCP, sandbox exec |
| `employee` | Email, calendar, project tools (read/write), no sandbox |
| `viewer` | Read-only access to email and calendar |

> Test account credentials are in `.dev-secrets`.

---

## 5. Database

### Connection Strings
- **From host:** `postgresql://blitz:<POSTGRES_PASSWORD>@localhost:5432/blitz`
- **From container:** `postgresql://blitz:<POSTGRES_PASSWORD>@postgres:5432/blitz`

### Key Tables

> The tables `agent_definitions`, `skill_definitions`, `tool_definitions`, and `mcp_servers` were dropped in migration 029 (Phase 24) and replaced by `registry_entries`.

| Table | Purpose |
|-------|---------|
| `role_permissions` | RBAC role → permission mapping |
| `tool_acl` | Per-tool role allowlist (Gate 3) |
| `workflows` | Saved canvas workflows (`definition_json`, `schema_version`) |
| `workflow_runs` | Execution history + state snapshots |
| `workflow_triggers` | Cron and webhook trigger definitions per workflow |
| `user_credentials` | OAuth tokens (AES-256 encrypted) |
| `memory_conversations` | Tier 1: short-term turns (per user, per conversation) |
| `memory_episodes` | Tier 2: episodic summaries |
| `memory_facts` | Tier 3: long-term facts + `vector(1024)` (pgvector) |
| `channel_accounts` | User ↔ external platform mapping (Telegram, WhatsApp, Teams) |
| `channel_sessions` | Active channel sessions |
| `registry_entries` | Unified registry for agents, skills, tools, MCP servers (Phase 24, migration 029 `c12d84fc28f9`) |
| `mcp_server_catalog` | Pre-built MCP server definitions — catalog of installable servers (Phase 24, migration 030 `617b296e937a`) |
| `platform_config` | Runtime configuration (Keycloak config, feature flags) — typed columns |
| `system_config` | Key/value system configuration |
| `user_instructions` | Per-user custom instructions injected into agent context |
| `user_preferences` | Per-user preferences (LLM mode, response style) |
| `user_artifact_permissions` | Skill share permissions (user → artifact_type → artifact_id) |
| `artifact_permissions` | Role-based artifact permissions (staged/applied) |
| `skill_repositories` | External skill registry URLs configured by admin |
| `skill_repo_index` | Cached index of skills from external repositories (for browse + pgvector similarity) |
| `conversation_titles` | User-edited conversation titles (sidebar display) |
| `local_users` | Local auth users (when Keycloak is not configured) |
| `local_groups`, `local_user_groups`, `local_group_roles`, `local_user_roles` | Local auth RBAC |

---

## 6. MCP Servers

| Server | Docker URL | Host URL | SSE Endpoint |
|--------|-----------|----------|-------------|
| CRM | `http://mcp-crm:8001` | `http://localhost:8001` | `/sse` |
| Docs | `http://mcp-docs:8002` | `http://localhost:8002` | `/sse` |

Tools are called via the backend MCPClient — never directly from frontend.

---

## 7. LiteLLM Proxy

- **Host URL:** `http://localhost:4000`
- **Container URL:** `http://litellm:4000`
- **Ollama api_base (in litellm config):** `http://host.docker.internal:11434`
- **Model aliases:** `blitz/master`, `blitz/fast`, `blitz/coder`, `blitz/summarizer`
- **API key:** see `.dev-secrets` → `LITELLM_MASTER_KEY`

---

## 8. Common Gotchas

| Situation | Wrong | Correct |
|-----------|-------|---------|
| Running backend/frontend | `just backend` / `just frontend` / `just dev-local` (old recipes — removed) | `just up` — starts all services in Docker; old dev-local/backend/frontend recipes no longer exist |
| Scheduler REST API | `GET /api/scheduler/jobs` (does not exist) | No scheduler HTTP API — jobs run as Celery tasks triggered by `workflow_triggers` table |
| Backend calling Ollama | `http://ollama:11434` | `http://host.docker.internal:11434` |
| Browser calling backend | `http://backend:8000` | `http://localhost:8000` |
| Backend calling Keycloak | `http://localhost:8080` | `http://keycloak:8080` |
| Backend calling Redis | `redis://localhost:6379` | `redis://redis:6379` |
| Backend calling PostgreSQL | `localhost:5432` | `postgres:5432` |
| LiteLLM calling backend | `http://localhost:8000` | `http://backend:8000` |
| Test via curl from host | use `localhost` URLs | — |
| Test via exec inside container | use Docker service name URLs | — |
| CopilotKit agent discovery | GET `/info`, POST `/agent/name/run` (sub-paths) | POST `/api/copilotkit` with `{"method":"info"}` or `{"method":"agent/run",...}` or `{"method":"agent/connect",...}` |
| Instantiating RunAgentInput from JSON | `RunAgentInput(**body)` | `RunAgentInput.model_validate(body)` — uses camelCase aliases |
| Importing copilotkit in Python | `from copilotkit import LangGraphAGUIAgent` | `from copilotkit.langgraph_agui_agent import LangGraphAGUIAgent` — `__init__` imports broken middleware |
| Backend JWT validation with self-signed Keycloak cert | Default httpx (fails SSL) | Set `KEYCLOAK_CA_CERT=/path/to/keycloak-ca.crt` in `.env`; used in `security/jwt.py` |
| JWT audience validation | `audience="blitz-backend"` (fails — token has no `aud`) | `options={"verify_aud": False}` — blitz-portal tokens carry no `aud` claim; issuer + RS256 sig still enforced |
| Extracting Keycloak realm roles | `payload.get("realm_access", {}).get("roles", [])` → `[]` | `payload.get("realm_roles")` — realm uses a custom scope mapper emitting flat `realm_roles` list, not nested `realm_access.roles` |
| Backend DB tables missing on fresh install | Queries fail with 500 | Run `just migrate` (or `cd backend && .venv/bin/alembic upgrade head`) before first use |
| `justfile` + JSON list env var (e.g. `CORS_ORIGINS`) | `set dotenv-load := true` (mangles `["url"]` → `[`) | Removed — each service reads its own `.env` directly; do not add it back |
| `just *-kill` recipe self-terminates on signal 9 | Bare `pkill -9 -f "pattern"` (pattern in `sh -c '...'` cmdline) | Use `#!/usr/bin/env bash` shebang + `fuser -k <port>/tcp` fallback |
| Frontend container Keycloak SSL (Alpine Linux) | `NODE_EXTRA_CA_CERTS=/app/certs/keycloak.crt` (ignored by musl libc) | `docker-entrypoint.sh` appends cert to `/etc/ssl/certs/ca-certificates.crt` at container startup — Alpine doesn't respect Node's CA env var |

---

## 9. Update Log

> When you discover a new endpoint, URL, credential shape, or gotcha — add it here.

| Date | Change | Added by |
|------|--------|----------|
| 2026-02-24 | Initial file created | claude |
| 2026-02-25 | Keycloak: domain=keycloak.blitz.local, realm=blitz-internal, frontend client=blitz-portal, backend client=blitz-backend | claude |
| 2026-02-25 | Keycloak ports: HTTP :8180 (use this), HTTPS :7443 — default 443 is wrong | claude |
| 2026-02-25 | CopilotKit protocol: @copilotkitnext v1.51.4 uses single-route JSON envelope (method: info / agent/run), not GraphQL or REST sub-paths | claude |
| 2026-02-25 | Python deps: copilotkit 0.1.78, ag-ui-langgraph 0.0.25, ag-ui-protocol 0.1.13 — use LangGraphAGUIAgent from submodule, not __init__ | claude |
| 2026-02-25 | Keycloak SSL: backend/security/jwt.py uses KEYCLOAK_CA_CERT env var for self-signed cert trust; set in backend/.env | claude |
| 2026-02-25 | justfile created at project root — use `just <recipe>` to manage Docker/backend/frontend; `set dotenv-load` removed to prevent env var mangling | claude |
| 2026-02-25 | justfile kill recipes: must use `#!/usr/bin/env bash` shebang; bare `sh -c 'pkill -f "pattern"'` self-kills because pattern appears in shell cmdline | claude |
| 2026-02-26 | JWT: blitz-portal tokens carry no aud claim → verify_aud=False in jwt.py; realm roles emitted as flat realm_roles not realm_access.roles | claude |
| 2026-02-26 | DB tables: must run `just migrate` on fresh install before backend can serve requests; tool_acl table missing → 500 on every authenticated call | claude |
| 2026-02-26 | CopilotKit protocol: 3 methods — info, agent/run, agent/connect; connect is called on component mount to restore thread state, same RunAgentInput body/SSE response as run | claude |
| 2026-02-28 | Phase 6 endpoints: user-facing GET /api/skills, POST /api/skills/{name}/run, GET /api/tools; admin CRUD for agents/tools/skills/permissions at /api/admin/*; skill slash commands detected in master agent _pre_route | claude |
| 2026-03-02 | [Phase 11]: Added Cloudflare Tunnel documentation (172.16.155.118, external machine, INFRA-01/02 satisfied) | claude |
| 2026-03-06 | Backend and frontend run in Docker containers ONLY. No host processes. Removed host-mode justfile recipes. Justfile now uses: up/down/stop/restart/rebuild/build/reset/logs/ps/migrate/db — all accept optional service name(s). Old dev-local/up-svc/down-v/backend-rebuild/frontend-rebuild removed. | claude |
| 2026-03-07 | Frontend Alpine SSL: docker-entrypoint.sh adds Keycloak CA to system bundle at runtime; NODE_EXTRA_CA_CERTS doesn't work with musl libc | claude |
| 2026-03-09 | Phase 22: user GET /api/skills now returns is_promoted+is_shared per item; GET /api/skills?promoted=true for featured section; GET /api/skills/{id}/export ZIP download; admin PATCH /promote, POST/DELETE/GET /api/admin/skills/{id}/share* | claude |
| 2026-03-13 | Phase 24: Unified registry — registry_entries table (migration 029 c12d84fc28f9) replaces agent_definitions/skill_definitions/tool_definitions/mcp_servers; mcp_server_catalog table (migration 030 617b296e937a) added; /api/registry/* unified CRUD routes added | claude |
| 2026-03-13 | Phase 24: Admin LLM config routes at /api/admin/llm/models; admin system routes at /api/admin/system/health and /rescan-skills; check-name endpoints for agents/tools/skills/mcp-servers | claude |
| 2026-03-13 | Phase 24: Auth tokens for MCP servers stored as hex-encoded AES-256-GCM blobs in registry_entries.config['auth_token_hex'] | claude |
| 2026-03-14 | Phase 25: Skill builder tool resolver — resolve_tools LangGraph node, pending_activation status, tool_gaps in RegistryEntry.config; create_skill defaults to draft status; PATCH /{id}/activate returns 422 when tool_gaps present; PATCH /admin/tools/{id}/activate-stub for stub promotion | claude |
| 2026-03-14 | Full API audit: added missing sections — Conversations, full Workflows (templates/HITL/triggers/events), full Channels, User APIs (memory/instructions/preferences/credentials), Tools (call), Webhooks, Skill Repos, Admin (Memory/Config/Keycloak/LocalUsers/Credentials). Removed stale /api/scheduler/* section. Frontend routes fully documented. DB tables expanded. | claude |
| 2026-03-14 | Added E2E testing section — Playwright, test users (admin/admin and giangtt/BilHam30), commands, storageState pattern. Credentials in .dev-secrets as E2E_ADMIN_* and E2E_USER_*. | claude |

---

## 10. Frontend E2E Testing (Playwright)

**Tool:** Playwright (`@playwright/test`)
**Location:** `frontend/e2e/`
**Base URL:** `http://localhost:3000`

> **Prerequisite:** `just up` must be running before executing Playwright tests.
> Playwright targets the live app — it does NOT start a dev server itself.

### Test Users

Both are **local auth accounts** (created via `/api/admin/local/users`). They are NOT Keycloak SSO accounts.

| Role | Username | Password | Permissions |
|------|----------|----------|-------------|
| Administrator (`it-admin`) | `admin` | `admin` | All pages — `/chat`, `/admin/*`, `/workflows`, `/skills`, `/settings`, `/profile` |
| Normal user (`employee`) | `giangtt` | `BilHam30` | `/chat`, `/workflows`, `/skills`, `/settings`, `/profile` — cannot access `/admin/*` |

Credentials are stored in `.dev-secrets`:
```
E2E_ADMIN_USER=admin
E2E_ADMIN_PASSWORD=admin
E2E_USER_USER=giangtt
E2E_USER_PASSWORD=BilHam30
```

### Commands

```bash
cd /home/tungmv/Projects/hox-agentos/frontend

# Full suite
pnpm exec playwright test

# Specific file
pnpm exec playwright test e2e/tests/auth.spec.ts

# Headed mode (visible browser — debugging)
pnpm exec playwright test --headed

# One project only
pnpm exec playwright test --project=admin-tests
pnpm exec playwright test --project=user-tests

# HTML report after a run
pnpm exec playwright show-report
```

### Auth Pattern (storageState)

Playwright uses `storageState` to avoid re-logging-in per test:

1. `e2e/auth/admin.setup.ts` — fills `/login` form as `admin/admin`, saves session to `e2e/.auth/admin.json`
2. `e2e/auth/user.setup.ts` — fills `/login` form as `giangtt/BilHam30`, saves session to `e2e/.auth/user.json`
3. Test projects load the saved state — each test starts already authenticated

**Why:** next-auth login involves CSRF token handling and redirects — re-running per test is slow and fragile.

### Critical Gotchas

| Situation | Wrong | Correct |
|-----------|-------|---------|
| Logging in during tests | Call backend JWT API directly | Use the `/login` form — next-auth manages CSRF and session cookie |
| Auth state files | Commit `e2e/.auth/*.json` to git | Gitignore them — regenerated by setup projects on each machine |
| Admin route access | Assume any authenticated user can reach `/admin` | Only `it-admin` role — always test both: admin succeeds, `giangtt` gets redirected |
| Running without services up | `pnpm exec playwright test` on cold machine | Run `just up` first and confirm `http://localhost:3000` responds |
