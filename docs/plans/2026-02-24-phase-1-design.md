# Phase 1 Design: Identity and Infrastructure Skeleton

**Date:** 2026-02-24
**Phase:** 1 of 8
**Status:** Approved

---

## Goal

Every request to the platform is authenticated, authorized, and audit-logged; all infrastructure services are healthy and communicating.

---

## Context

- **Keycloak:** Running on a remote server at `keycloak.blitz.local` (Cloudflare tunnel). Realm: `blitz-internal`. This instance is NOT included in Blitz AgentOS's Docker Compose — it is external shared infrastructure.
- **Realm state:** Already has 5 roles (`employee`, `manager`, `team-lead`, `it-admin`, `executive`), 14 groups, 15 initial users.
- **New Keycloak client:** `blitz-agentos` must be registered in the `blitz-internal` realm.
- **Developer environment:** Single developer, local machine only. No multi-dev coordination needed.
- **Roles:** Used directly from Keycloak — no translation layer, no new roles for Phase 1.

---

## Section 1: Infrastructure — Docker Compose

### Services

| Service | Image | Port (host) | Notes |
|---------|-------|-------------|-------|
| `postgres` | `pgvector/pgvector:pg16` | 5432 | Blitz app DB with pgvector extension |
| `redis` | `redis:7-alpine` | 6379 | Cache + Celery broker |
| `litellm` | `ghcr.io/berriai/litellm:main-latest` | 4000 | LLM proxy (internal only) |
| `backend` | Build from `./backend` | 8000 | FastAPI application |
| `frontend` | Build from `./frontend` | 3000 | Next.js application |
| `celery-worker` | Same image as backend | — | Celery embedding worker |

### Networking

- Single `blitz-net` bridge network for all Blitz services.
- Inter-service calls use Docker service names: `http://backend:8000`, `http://litellm:4000`, `redis://redis:6379`, `postgresql+asyncpg://postgres/blitz`.
- Keycloak is external: backend reaches it at `https://keycloak.blitz.local` (no `extra_hosts` needed — dev machine DNS resolves this).
- Ollama runs on the host machine (not Dockerized). LiteLLM config uses `http://host.docker.internal:11434`. Backend and celery-worker need `extra_hosts: ["host.docker.internal:host-gateway"]` (Linux requirement).

### Secrets

- All credentials in `.env` (gitignored).
- `.env.example` committed as template.

### Health Checks & Startup Order

```
postgres (healthcheck: pg_isready)
redis (healthcheck: redis-cli ping)
litellm (depends_on: postgres) → healthcheck: /health
backend (depends_on: postgres ✓, redis ✓, litellm ✓)
frontend (depends_on: backend started)
celery-worker (depends_on: postgres ✓, redis ✓)
```

---

## Section 2: Keycloak Client Registration & JWT Validation

### New Client: `blitz-agentos`

| Field | Value |
|-------|-------|
| Client ID | `blitz-agentos` |
| Secret | Generated — stored in `.env` as `KEYCLOAK_CLIENT_SECRET` |
| Redirect URIs | `http://localhost:3000/*` |
| Web Origins | `http://localhost:3000` |
| Protocol | `openid-connect`, Standard Flow (OIDC) |
| Scopes | `roles`, `profile`, `email`, `groups` |

### JWT Validation — Gate 1

Implementation in `security/jwt.py` and `security/deps.py`:

1. Frontend sends `Authorization: Bearer <token>` on every API request.
2. `get_current_user()` FastAPI dependency:
   - Fetches JWKS from `https://keycloak.blitz.local/realms/blitz-internal/protocol/openid-connect/certs` (in-process cache with TTL).
   - Validates: signature (RS256), `exp`, `iss` == `https://keycloak.blitz.local/realms/blitz-internal`, `aud` includes `blitz-agentos`.
   - Extracts and returns `UserContext`.
3. Returns `401` for: missing header, expired token, invalid signature, wrong issuer/audience.

### UserContext

```python
class UserContext(TypedDict):
    user_id: UUID        # from JWT `sub`
    email: str           # from JWT `email`
    username: str        # from JWT `preferred_username`
    roles: list[str]     # from JWT `realm_access.roles`
    groups: list[str]    # from JWT `groups` (full paths, e.g. "/tech")
```

### Token Storage (Frontend)

- JWT stored **in-memory only** via `next-auth` server-side session — never in `localStorage` or `sessionStorage`.
- XSS cannot steal the token.

---

## Section 3: RBAC, Tool ACL, and Audit Logging

### RBAC — Gate 2 (`security/rbac.py`)

Maps Keycloak realm roles to Blitz permission sets. Users with multiple roles receive the union of all permissions.

| Keycloak Role | Blitz Permissions |
|---|---|
| `employee` | `chat`, `tool:email`, `tool:calendar`, `tool:project` |
| `manager` | All `employee` + `tool:reports`, `workflow:create` |
| `team-lead` | All `manager` + `workflow:approve` |
| `it-admin` | All permissions + `tool:admin`, `sandbox:execute`, `registry:manage` |
| `executive` | `chat`, `tool:reports` (read-only) |

API: `has_permission(user_context: UserContext, permission: str) -> bool`

### Tool ACL — Gate 3 (`security/acl.py`)

Per-user, per-tool overrides stored in PostgreSQL. Checked after RBAC. Enables granting or revoking tool access for individual users beyond their role.

**`ToolAcl` table:**

```sql
CREATE TABLE tool_acl (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    tool_name   VARCHAR(128) NOT NULL,
    allowed     BOOLEAN NOT NULL,
    granted_by  UUID,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, tool_name)
);
```

### Security Gate Execution Order

**Always in this order — no exceptions:**
1. `get_current_user()` — JWT validation → `UserContext`
2. `check_permission(user_context, required_permission)` — RBAC → deny with 403 if fails
3. `check_tool_acl(user_context, tool_name)` — DB ACL → deny with 403 if fails
4. Log result (allowed/denied), then proceed or return 403

### Audit Logging

Every tool call attempt logged via `get_audit_logger()` to structlog JSON files:

```json
{"ts": "2026-02-24T10:00:00Z", "event": "tool_call", "user_id": "...", "tool": "email.fetch", "allowed": true, "duration_ms": 42}
```

**Never logged:** `access_token`, `refresh_token`, `password`, any credential value.

---

## Section 4: FastAPI + Next.js Application Skeletons

### FastAPI Backend Structure

```
backend/
├── pyproject.toml           # uv-managed dependencies
├── main.py                  # app factory, CORS, middleware, router registration
├── core/
│   ├── config.py            # Settings (pydantic-settings), get_llm() factory
│   ├── db.py                # async SQLAlchemy engine + session factory
│   └── logging.py           # structlog config, get_audit_logger()
├── core/models/
│   ├── user.py              # UserContext TypedDict
│   └── tool_acl.py          # ToolAcl SQLAlchemy ORM model
├── core/schemas/
│   └── common.py            # Base Pydantic response schemas
├── security/
│   ├── jwt.py               # JWKS fetch + RS256 token validation
│   ├── rbac.py              # role → permission mapping + has_permission()
│   ├── acl.py               # ToolAcl DB check
│   └── deps.py              # get_current_user() FastAPI dependency
├── gateway/
│   └── tool_registry.py     # stub registry (populated in Phase 2+)
├── alembic/
│   └── versions/            # DB migrations
│       └── 001_initial.py   # ToolAcl table + base tables
└── api/routes/
    ├── health.py            # GET /health → {"status": "ok"}
    └── agents.py            # POST /api/agents/chat → 501 stub (Phase 2)
```

### Next.js Frontend Structure

```
frontend/
├── package.json             # pnpm-managed dependencies
└── src/
    ├── app/
    │   ├── layout.tsx           # Root layout, providers
    │   ├── page.tsx             # Redirect to /chat if authenticated, /login otherwise
    │   ├── login/page.tsx       # Keycloak OIDC login initiation
    │   └── chat/page.tsx        # Chat UI stub
    ├── hooks/
    │   └── use-auth.ts          # OIDC token management (in-memory via next-auth)
    └── lib/
        └── types.ts             # Shared TypeScript interfaces
```

**Auth library:** `next-auth` v5 with Keycloak provider.
**Token storage:** Server-side session only — never `localStorage`.
**API calls:** Fetch wrapper that injects `Authorization: Bearer` from session.

### Phase 1 Success Gate

| Test | Expected |
|------|----------|
| `GET /health` | `200 {"status": "ok"}` |
| `POST /api/agents/chat` with valid JWT | `501` (stub, not yet implemented) |
| `POST /api/agents/chat` with no JWT | `401` |
| `POST /api/agents/chat` with expired JWT | `401` |
| `POST /api/agents/chat` with `viewer`/`executive` role | `403` (no `chat` permission... actually executive has `chat`) |
| Employee logs in via web browser | Keycloak SSO → session → redirected to `/chat` |
| Tool call logged | JSON log entry with user_id, tool, allowed, no credentials |

---

## Key Constraints (Phase 1 Specific)

- **Keycloak is external** — Blitz AgentOS Docker Compose does NOT include Keycloak.
- **Roles used as-is** — No translation layer. `realm_access.roles` from JWT → permissions mapping in `rbac.py`.
- **uv** for Python deps, **pnpm** for Node deps — no pip/npm/yarn.
- **JWT in memory only** — `next-auth` server-side session, never `localStorage`.
- **Absolute imports only** in Python — no relative imports.
- **structlog everywhere** — no `print()` or bare `logging`.

---

## Phase 1 Sub-tasks

| # | Task | Deliverable |
|---|------|-------------|
| 01-01 | Docker Compose and infrastructure services | `docker-compose.yml`, `.env.example`, health checks passing |
| 01-02 | Keycloak client registration + JWT validation | `blitz-agentos` client in Keycloak, `security/jwt.py`, `security/deps.py` |
| 01-03 | RBAC, Tool ACL, and audit logging | `security/rbac.py`, `security/acl.py`, `ToolAcl` migration, audit log output |
| 01-04 | FastAPI and Next.js application skeletons | `/health` → 200, `/api/agents/chat` → 401 without JWT, `/chat` → login redirect |
