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

## 2. Backend API Endpoints

Base URL (local dev): `http://localhost:8000`

### Authentication
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/auth/me` | Current user info (requires JWT) |

### Agents
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/agents/chat` | Main AG-UI streaming endpoint |
| POST | `/api/agents/workflow/run` | Trigger a workflow manually |

### Workflows (Canvas)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/workflows` | List user's workflows |
| POST | `/api/workflows` | Create new workflow |
| GET | `/api/workflows/{id}` | Get workflow by ID |
| PUT | `/api/workflows/{id}` | Update workflow definition |
| DELETE | `/api/workflows/{id}` | Delete workflow |
| POST | `/api/workflows/{id}/run` | Execute a workflow |

### Scheduler
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/scheduler/jobs` | List scheduled jobs |
| POST | `/api/scheduler/jobs` | Create scheduled job |
| PUT | `/api/scheduler/jobs/{id}` | Update job |
| DELETE | `/api/scheduler/jobs/{id}` | Delete job |
| GET | `/api/scheduler/runs` | List workflow run history |

### Channels
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/channels` | List connected channel accounts |
| POST | `/api/channels/telegram/webhook` | Telegram inbound webhook |
| POST | `/api/channels/whatsapp/webhook` | WhatsApp inbound webhook |
| POST | `/api/channels/teams/webhook` | MS Teams inbound webhook |

### MCP
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/mcp/servers` | List registered MCP servers |
| GET | `/api/mcp/servers/{name}/tools` | List tools on a server |

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

| Path | Description |
|------|-------------|
| `/` | Main app (redirects to `/chat`) |
| `/chat` | AG-UI chat interface |
| `/canvas` | Low-code workflow canvas |
| `/canvas/[id]` | Edit a specific workflow |
| `/scheduler` | Scheduled jobs management |
| `/settings` | User settings, channel connections |
| `/api/copilotkit` | Next.js API route — AG-UI proxy to backend |

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
| Table | Purpose |
|-------|---------|
| `users` | Blitz user registry (synced from Keycloak) |
| `roles`, `permissions`, `role_permissions`, `user_roles` | RBAC |
| `tool_acl` | Per-tool role allowlist (Gate 3) |
| `workflows` | Saved canvas workflows (`definition_json`) |
| `workflow_runs` | Execution history + state snapshots |
| `scheduled_jobs` | Cron job definitions |
| `user_credentials` | OAuth tokens (AES-256 encrypted) |
| `memory_conversations` | Tier 1: short-term turns |
| `memory_episodes` | Tier 2: episodic summaries |
| `memory_facts` | Tier 3: long-term facts + vector(1024) |
| `memory_files`, `memory_chunks` | File-based memory |
| `channel_accounts` | User ↔ external platform mapping |
| `channel_sessions` | Active channel sessions |
| `mcp_servers` | Registered MCP server config |

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
| Backend calling Ollama | `http://ollama:11434` | `http://host.docker.internal:11434` |
| Browser calling backend | `http://backend:8000` | `http://localhost:8000` |
| Backend calling Keycloak | `http://localhost:8080` | `http://keycloak:8080` |
| Backend calling Redis | `redis://localhost:6379` | `redis://redis:6379` |
| Backend calling PostgreSQL | `localhost:5432` | `postgres:5432` |
| LiteLLM calling backend | `http://localhost:8000` | `http://backend:8000` |
| Test via curl from host | use `localhost` URLs | — |
| Test via exec inside container | use Docker service name URLs | — |
| CopilotKit agent discovery | GET `/info`, POST `/agent/name/run` (sub-paths) | POST `/api/copilotkit` with `{"method":"info"}` or `{"method":"agent/run",...}` |
| Instantiating RunAgentInput from JSON | `RunAgentInput(**body)` | `RunAgentInput.model_validate(body)` — uses camelCase aliases |
| Importing copilotkit in Python | `from copilotkit import LangGraphAGUIAgent` | `from copilotkit.langgraph_agui_agent import LangGraphAGUIAgent` — `__init__` imports broken middleware |
| Backend JWT validation with self-signed Keycloak cert | Default httpx (fails SSL) | Set `KEYCLOAK_CA_CERT=/path/to/keycloak-ca.crt` in `.env`; used in `security/jwt.py` |
| JWT audience validation | `audience="blitz-backend"` (fails — token has no `aud`) | `options={"verify_aud": False}` — blitz-portal tokens carry no `aud` claim; issuer + RS256 sig still enforced |
| Extracting Keycloak realm roles | `payload.get("realm_access", {}).get("roles", [])` → `[]` | `payload.get("realm_roles")` — realm uses a custom scope mapper emitting flat `realm_roles` list, not nested `realm_access.roles` |
| Backend DB tables missing on fresh install | Queries fail with 500 | Run `just migrate` (or `cd backend && .venv/bin/alembic upgrade head`) before first use |
| `justfile` + JSON list env var (e.g. `CORS_ORIGINS`) | `set dotenv-load := true` (mangles `["url"]` → `[`) | Removed — each service reads its own `.env` directly; do not add it back |
| `just *-kill` recipe self-terminates on signal 9 | Bare `pkill -9 -f "pattern"` (pattern in `sh -c '...'` cmdline) | Use `#!/usr/bin/env bash` shebang + `fuser -k <port>/tcp` fallback |

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
