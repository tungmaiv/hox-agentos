# Blitz AgentOS — Project Context for Claude

> This file is read automatically at every Claude Code session start.
> It gives GSD agents, Superpowers skills, and raw Claude sessions
> full project context without repeating it in every prompt.

## AGENT INSTRUCTIONS — Read Before Any Task

**Step 1 — Read context files now, before doing anything else:**

1. Read **`docs/dev-context.md`** — service URLs (docker vs localhost), all API endpoints, DB tables, roles, gotchas.
2. Read **`.dev-secrets`** if it exists — actual credentials for local dev. Template at `.dev-secrets.example`.

**Step 2 — Confirm you have loaded them** by stating:
> "I have read docs/dev-context.md. The backend URL from inside a container is `http://backend:8000` and from the host is `http://localhost:8000`. Ollama is on the host at `http://host.docker.internal:11434`."

If you cannot make that statement from memory, go read `docs/dev-context.md` now.

**Step 3 — Never guess.** If you are unsure of a URL, port, endpoint path, credential, or command: stop and read `docs/dev-context.md` first. Wrong guesses are harder to fix than a 10-second file read.

**Step 4 — Update on discovery.** When you find a new endpoint, URL mapping, or gotcha during work:
- Add it to `docs/dev-context.md` immediately (correct section + Update Log at bottom).
- Never leave a discovery undocumented for the next session.

---

## DO / DON'T — Quick Reference

Scan this before writing any code. Details are in the sections below.

### Package Management
| DO | DON'T |
|----|-------|
| `uv add <pkg>` / `uv run <cmd>` | `pip install` |
| `pnpm add <pkg>` / `pnpm run <cmd>` | `npm install` / `yarn add` |
| `gh pr create` / `gh issue create` | raw `git` for GitHub operations |

### URLs & Endpoints
| DO | DON'T |
|----|-------|
| Read `docs/dev-context.md` before using any URL | Guess or hardcode a URL |
| Use Docker service names inside containers (`http://backend:8000`) | Use `localhost` inside containers |
| Use `localhost` when calling from the host / browser | Use Docker service names from host |
| Use `http://host.docker.internal:11434` to reach Ollama from containers | Use `http://ollama:11434` (Ollama is not Dockerized) |

### LLM Access
| DO | DON'T |
|----|-------|
| `from core.config import get_llm; llm = get_llm("blitz/master")` | Import `anthropic`, `openai` SDKs directly |
| Use stable aliases: `blitz/master`, `blitz/fast`, `blitz/coder` | Use provider model names like `claude-sonnet-4-6` in agent code |

### Credentials & Security
| DO | DON'T |
|----|-------|
| Load credentials from DB using `user_id` from JWT | Accept credentials in request body or query params |
| Log `user_id`, `tool`, `allowed`, `duration_ms` | Log `access_token`, `refresh_token`, `password` |
| Deny and log when ACL check fails | Silently skip a security gate |
| Read `.dev-secrets` for local test credentials | Hardcode passwords or tokens in code |

### Memory & Database
| DO | DON'T |
|----|-------|
| Always parameterize memory queries: `WHERE user_id = $1` from JWT | Accept `user_id` from request body for memory queries |
| Use pgvector in PostgreSQL for vector search | Add Qdrant, Weaviate, or any other vector DB |
| Use `async with async_session()` for DB access | Use synchronous SQLAlchemy or raw `psycopg2` |

### Python Code
| DO | DON'T |
|----|-------|
| Full type annotations on every function | Bare `dict`, `list`, untyped args |
| `structlog.get_logger(__name__)` for all logging | `print()`, `logging.info()` |
| `HTTPException` with status code in FastAPI routes | Raise bare `Exception` |
| Absolute imports (`from core.config import settings`) | Relative imports (`from ..config import settings`) |
| Pydantic v2 `BaseModel` for all tool I/O | Plain `dict` for tool inputs/outputs |

### TypeScript / Frontend Code
| DO | DON'T |
|----|-------|
| `strict: true` — always | Disable strict mode or add `// @ts-ignore` |
| `unknown` + type guard for external data | `any` |
| Server Components by default | Add `"use client"` unless you need hooks/events |
| Zod for validating API responses | Trust external data shapes without validation |

### Architecture & Scope
| DO | DON'T |
|----|-------|
| Register all tools in `gateway/tool_registry.py` | Register tools in agent code or routes |
| Get config from `core/config.py` only | Read `os.environ` directly in business logic |
| Run embedding (CPU-bound) in Celery workers | Run embedding inside a FastAPI request handler |
| Keep `schema_version` on every `definition_json` | Change canvas node schema without bumping version |
| Add new channels via `ChannelAdapter` protocol | Modify agent/tool/memory code to add a channel |
| Design for 100 users (Docker Compose, single PostgreSQL) | Add Kubernetes, connection pools, or sharding for MVP |

---

## 1. Project Identity

**Name:** Blitz AgentOS
**Type:** Enterprise-grade, on-premise Agentic Operating System
**Scale:** ~100 users (Blitz employees); design for this scale, not for millions
**Scope:** MVP running on Docker Compose; Kubernetes is post-MVP
**Inspiration:** OpenClaw architecture — local-first, multi-agent, sandboxed

**Core purpose:**
- Replace manual daily routines (email digest, calendar summaries, project status) with autonomous agents
- Let non-technical users build workflows via a visual low-code canvas
- Enforce enterprise security: no credential leakage to LLMs, per-user memory isolation, per-tool ACL

**Key docs:**
- Architecture: `docs/architecture/architecture.md` (source of truth)
- Blueprint: `docs/design/blueprint.md`
- Module breakdown: `docs/design/module-breakdown.md`
- Implementation guide: `docs/implementation/implementation-guide.md`
- **Dev context (URLs, endpoints, credentials):** `docs/dev-context.md` + `.dev-secrets`

---

## 2. Technology Stack (Locked Versions)

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend framework | Next.js | 15+ (App Router) |
| Agent UI protocol | CopilotKit (AG-UI) | Latest |
| Generative UI | A2UI / CopilotKit | Latest |
| Canvas | React Flow (Xyflow) | v12+ |
| Backend framework | FastAPI | 0.115+ |
| Agent orchestration | LangGraph | 0.2+ |
| Data validation | PydanticAI | Latest |
| Identity | Keycloak | 26+ |
| Primary database | PostgreSQL | 16+ (pgvector/pgvector:pg16 image) |
| Vector search | pgvector | 0.8+ (embedded in PostgreSQL — NO separate vector DB) |
| Embedding model | bge-m3 (BAAI) | Latest — 1024-dim, self-hosted via FlagEmbedding |
| Task queue | Celery | 5+ |
| Cache / broker | Redis | 7+ |
| LLM gateway | LiteLLM Proxy | Latest (self-hosted, port 4000) |
| Local LLM | Ollama | Latest (runs on host machine, NOT in Docker) |
| Cloud LLM (quality) | Anthropic Claude | claude-sonnet-4-6 |
| Cloud LLM (coding) | Kimi via OpenRouter | kimi-k1.5 |
| Cloud LLM (general) | OpenAI | gpt-4o |
| MCP transport | HTTP + SSE | MCP spec standard |
| Sandbox execution | Docker SDK | Latest |
| Audit logging | structlog → JSON files | Latest (Loki-compatible) |

### LLM Model Aliases (use these in agent code — never provider model names directly)

| Alias | Use Case | Backend |
|-------|----------|---------|
| `blitz/master` | Master agent, complex reasoning | Ollama/Qwen2.5:72b → Claude Sonnet 4.6 |
| `blitz/fast` | Simple sub-tasks, classification | Ollama/Llama3.2:3b → gpt-4o-mini |
| `blitz/coder` | Code generation, debugging | OpenRouter/Kimi k1.5 → Claude Sonnet 4.6 |
| `blitz/summarizer` | Memory summarization | Ollama/Llama3.2:3b → gpt-4o-mini |
| `blitz/embedder` | Not via LiteLLM — direct bge-m3 FlagModel | Local only |

> **Ollama runs on the host machine, not in Docker.**
> LiteLLM config must use `http://host.docker.internal:11434` as `api_base` for Ollama models,
> not `http://ollama:11434`. On Linux, add `extra_hosts: ["host.docker.internal:host-gateway"]`
> to the LiteLLM service in `docker-compose.yml`.

```python
# Always use this pattern — never provider-specific SDKs:
from core.config import get_llm
llm = get_llm("blitz/master")   # returns ChatOpenAI pointing at LiteLLM proxy
```

---

## 3. Development Environment

### Package Management

| Ecosystem | Tool | Notes |
|-----------|------|-------|
| Python (backend) | **uv** | Use `uv add`, `uv run`, `uv sync` — never `pip install` directly |
| Node.js (frontend) | **pnpm** | Use `pnpm add`, `pnpm install`, `pnpm run` — never `npm` or `yarn` |
| Git / GitHub | **gh** | Use `gh` CLI for PRs, issues, and repo operations |

```bash
# Python — backend dependency management
uv add fastapi                  # add a package
uv add --dev pytest             # add a dev dependency
uv sync                         # install all deps from lockfile
uv run pytest                   # run a command in the venv

# Node.js — frontend dependency management
pnpm add @copilotkit/react-core # add a package
pnpm add -D typescript          # add a dev dependency
pnpm install                    # install from lockfile
pnpm run dev                    # run a script

# GitHub CLI
gh pr create                    # open a PR
gh pr list                      # list open PRs
gh issue create                 # create an issue
gh repo clone                   # clone repo
```

### Service Port Map

| Service | Port | Notes |
|---------|------|-------|
| Frontend (Next.js) | 3000 | |
| Backend (FastAPI) | 8000 | |
| Keycloak | 8080 | Admin: `http://localhost:8080` |
| LiteLLM Proxy | 4000 | Internal only |
| MCP CRM Server | 8001 | HTTP+SSE, `/sse` endpoint |
| MCP Docs Server | 8002 | HTTP+SSE, `/sse` endpoint |
| Ollama | 11434 | **Host machine** (not Dockerized) — accessed via `host.docker.internal:11434` from containers |
| Grafana (future) | 3001 | Pre-production only |

### Common Commands

```bash
# Start all services
docker compose up -d

# Start specific service
docker compose up -d backend

# Tail backend logs
docker compose logs -f backend

# Run Celery worker manually
docker compose run --rm backend celery -A scheduler.celery_app worker --concurrency=4

# Apply DB migrations
docker compose run --rm backend alembic upgrade head

# Frontend dev
cd frontend && pnpm run dev

# Backend dev (with hot reload)
cd backend && uvicorn main:app --reload --port 8000
```

### Environment Variables

Secrets live in `.env` (never committed). Key variables:
```
DATABASE_URL=postgresql://blitz:<POSTGRES_PASSWORD>@postgres/blitz
REDIS_URL=redis://redis:6379
KEYCLOAK_URL=http://keycloak:8080
LITELLM_URL=http://litellm:4000
LITELLM_MASTER_KEY=<key>
ANTHROPIC_KEY=<key>
OPENAI_KEY=<key>
OPENROUTER_KEY=<key>
TELEGRAM_BOT_TOKEN=<token>
POSTGRES_PASSWORD=<password>
KEYCLOAK_ADMIN_PASSWORD=<password>
```

---

## 4. Coding Philosophy

Apply these principles in order — later ones do not override earlier:

### DRY (Don't Repeat Yourself)
- Extract shared logic to utilities/helpers only when used in 3+ places
- `core/config.py` is the single source of truth for settings; never duplicate config reads
- `gateway/tool_registry.py` is the single registry for all tools; never register tools elsewhere
- `get_llm()` is the only way to instantiate an LLM client

### YAGNI (You Aren't Gonna Need It)
- Design for ~100 users, not millions. No premature horizontal scaling abstractions.
- Docker Compose for MVP. Do not add Kubernetes manifests until post-MVP.
- No HashiCorp Vault for credentials (deferred post-MVP). Use DB + AES-256.
- No separate vector DB. pgvector in existing PostgreSQL is sufficient at 100-user scale.
- Do not add features, error handling, or abstractions for hypothetical future requirements.

### KISS (Keep It Simple, Stupid)
- Each module does one thing. `security/` does auth. `memory/` does memory. `agents/` orchestrates.
- Prefer explicit over implicit. No magic decorators that hide security checks.
- Prefer flat module structure over deep nesting.
- Three similar lines of code is better than a premature abstraction.

### Security-First
- Security is not an afterthought — every tool call passes all three security gates.
- When in doubt: deny access and log the denial.
- Credentials are NEVER passed to LLMs, logged, or returned to frontends — ever.

### Async-First
- All FastAPI endpoints and database operations are `async def`.
- Never block the event loop: CPU-bound operations (embedding) run in Celery workers.
- Use `asyncpg` for raw SQL, `SQLAlchemy` async for ORM.

---

## 5. Python Coding Standards

### Type Annotations
- All functions have full type annotations — no bare `dict`, `list`, `Any` unless unavoidable.
- Use `TypedDict` for agent state (`BlitzState`).
- Use Pydantic v2 `BaseModel` for all tool I/O schemas, API request/response bodies.
- Use `UUID` from `uuid` module (not `str`) for IDs in function signatures.

```python
# Correct
async def get_recent_turns(
    user_id: UUID,
    conversation_id: UUID,
    n: int = 20,
) -> list[Turn]:
    ...

# Wrong — no bare dict or str IDs
async def get_recent_turns(user_id: str, conversation_id: str, n=20):
    ...
```

### Error Handling
- Raise specific exceptions, not bare `Exception`.
- FastAPI routes: use `HTTPException` with meaningful status codes.
- Tools: return structured error results rather than raising, so agents can handle them.
- Do not add try/except for scenarios that cannot happen.

### Logging
- Use `structlog` exclusively — no `print()`, no bare `logging.info()`.
- Audit-worthy events (tool calls, ACL decisions, credential access) go to `get_audit_logger()`.
- **NEVER log:** `access_token`, `refresh_token`, `password`, any credential value.

```python
import structlog
logger = structlog.get_logger(__name__)

# Correct
logger.info("tool_call", tool="email.fetch", user_id=str(user_id), allowed=True)

# Wrong — credential in log
logger.info("fetching email", token=creds.access_token)
```

### Imports
- Absolute imports only — no relative imports.
- Group: stdlib → third-party → local, separated by blank lines.

### Async DB Pattern
```python
# Always use async sessions
async with async_session() as session:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
```

---

## 6. TypeScript / Frontend Coding Standards

### Type Safety
- `strict: true` in `tsconfig.json` — enforced, no exceptions.
- No `any` — use `unknown` and narrow with type guards.
- All component props have explicit interfaces.
- Use Zod for runtime validation of external data (API responses, user input).

### React Patterns
- Server Components by default (Next.js App Router); Client Components only when needed.
- `use client` directive only in files that use hooks, browser APIs, or event handlers.
- Custom hooks for all stateful logic (`use-copilot-provider.ts`, `use-acl.ts`, etc.).
- Never call backend APIs directly from components — always through custom hooks.

### Naming
- Files: `kebab-case.tsx` for components, `use-kebab-case.ts` for hooks.
- Components: `PascalCase`.
- Hooks: `useCamelCase`.

### AG-UI + A2UI
- AG-UI streaming: never block the main thread parsing agent tokens.
- A2UI envelopes: parse JSONL in `A2UIMessageRenderer` — never in component render functions.
- Tool calls: visualized automatically by CopilotKit — no custom rendering needed.

---

## 7. Architecture Invariants (Never Break These)

### Security Gates — Always in This Order
Every agent tool call must pass all three:
1. **Gate 1:** JWT validation (`security/jwt.py`) — verify signature, expiry, issuer, audience
2. **Gate 2:** RBAC permission check (`security/rbac.py`) — map Keycloak roles → permissions
3. **Gate 3:** Tool ACL (`gateway/agui_middleware.py`) — check `ToolAcl` table for this user's roles

### Memory Isolation — Absolute Rule
```python
# ALWAYS parameterize memory queries on user_id from JWT — never from user input
async def memory_search(user_id: UUID, query: str) -> list[Fact]:
    # user_id comes from get_current_user(), never from request body
    ...
```

### Credential Containment
```
LLM prompt   → sees: user_id, task parameters (never tokens)
Frontend     → sees: tool results as structured data (never tokens)
Audit logs   → sees: user_id, tool name, timestamp (never tokens)
DB           → stores: AES-256 encrypted tokens
Backend tool → resolves: credentials internally via user_id from JWT
```

### Tool Registration — Single Registry
All tools (backend tools, MCP wrappers, sandbox tools) are registered in `gateway/tool_registry.py` with:
- `required_permissions`: checked at Gate 2
- `sandbox_required`: routes to Docker sandbox executor
- `mcp_server` / `mcp_tool`: for MCP-backed tools

### LLM Access — Single Entry Point
```python
# The ONLY correct way to get an LLM client:
from core.config import get_llm
llm = get_llm("blitz/master")
# Never: import anthropic; anthropic.Anthropic()
# Never: from openai import OpenAI; OpenAI()
```

### Canvas Schema Versioning
`Workflow.definition_json` always has `schema_version: "1.0"`. Breaking schema changes require:
1. Increment `schema_version`
2. Write and apply a migration script for existing workflows
3. Update `compile_workflow_to_stategraph()` to handle both versions

### Scheduler Security
Celery workers run scheduled jobs as the **job owner's UserContext** — never as a service account. All tool ACL and memory isolation applies identically to scheduled jobs.

### MCP Uniformity
MCP tools go through the same Gate 3 ACL as backend tools. There is no separate security perimeter for MCP. All MCP servers expose `/sse` endpoint (HTTP+SSE transport).

---

## 8. Project Directory Structure

```
blitz-agentos/
├── CLAUDE.md                   ← this file (project context)
├── docker-compose.yml
├── .env                        ← secrets (never commit)
├── backend/
│   ├── main.py
│   ├── api/routes/             ← auth, agents, workflows, scheduler, channels, mcp
│   ├── core/
│   │   ├── config.py           ← single source of truth for settings + get_llm()
│   │   ├── db.py               ← async SQLAlchemy engine + session factory
│   │   ├── logging.py          ← structlog config + get_audit_logger()
│   │   ├── models/             ← SQLAlchemy ORM models
│   │   └── schemas/            ← Pydantic request/response schemas
│   ├── security/               ← jwt.py, rbac.py, acl.py, deps.py, keycloak_client.py
│   ├── gateway/                ← runtime.py, agui_middleware.py, tool_registry.py
│   ├── agents/
│   │   ├── master_agent.py     ← run_conversation(), run_workflow()
│   │   ├── graphs.py           ← compile_workflow_to_stategraph()
│   │   ├── state/types.py      ← BlitzState TypedDict
│   │   └── subagents/          ← email, calendar, project, channel agents
│   ├── tools/                  ← email_tools, calendar_tools, project_tools, etc.
│   ├── memory/                 ← short_term, medium_term, long_term, embeddings, indexer
│   ├── sandbox/                ← docker_client, policies, executor
│   ├── mcp/                    ← client.py + servers/
│   ├── channels/               ← gateway, models, adapters (telegram, whatsapp, teams)
│   └── scheduler/              ← celery_app, jobs, worker
├── frontend/
│   └── src/
│       ├── app/                ← Next.js App Router pages + api/copilotkit route
│       ├── components/         ← canvas/, chat/, a2ui/
│       ├── hooks/              ← use-copilot-provider, use-acl, use-co-agent, etc.
│       └── lib/                ← types.ts, a2ui-spec.ts
├── infra/
│   ├── keycloak/               ← realm config
│   ├── postgres/               ← init SQL, migrations
│   ├── litellm/config.yaml     ← LLM routing config
│   │                           (no ollama/ — Ollama runs on host, not in Docker)
│   ├── mcp-crm/                ← CRM MCP server
│   └── mcp-docs/               ← Docs MCP server
├── channel-gateways/
│   ├── telegram/
│   └── whatsapp/
├── logs/blitz/                 ← JSON audit log files (volume mounted)
└── docs/
    ├── architecture/           ← architecture.md (source of truth)
    ├── design/                 ← blueprint.md, module-breakdown.md
    ├── implementation/         ← implementation-guide.md
    └── research/               ← research papers (Vietnamese)
```

---

## 9. Key Constraints (Do Not Violate)

| Constraint | Reason |
|-----------|--------|
| On-premise only — no SaaS data processing | Enterprise security requirement |
| PostgreSQL is the sole database | No Qdrant, Weaviate, or other vector DBs |
| pgvector embedding dim = 1024 (bge-m3) | Changing requires full reindex — avoid |
| Docker Compose for MVP | Kubernetes deferred to post-MVP |
| ~100 users — do not over-engineer | YAGNI — avoid distributed systems complexity |
| `schema_version` on every workflow JSON | Required for canvas migration safety |
| Celery workers run as job owner | No privilege escalation via scheduler |
| All LLM calls via LiteLLM Proxy | Provider agnosticism + fallback routing |
| JWT stored in memory only (not localStorage) | XSS protection |
| Vietnamese language support | bge-m3 handles multilingual natively |

---

## 10. Implementation Phases

| Phase | Goal | Gate Criteria |
|-------|------|--------------|
| 1 | Identity & Skeleton | JWT validated, `/api/agents/chat` 200, SSO working |
| 2 | Agents, Tools & Memory | All tool schemas tested, memory isolation verified |
| 3 | Canvas & Workflows | 2-node workflow persists and runs end-to-end |
| 4 | Scheduler & Channels | Scheduled job creates WorkflowRun, Telegram delivers |
| 5 | Hardening & Sandboxing | Docker sandbox runs without host access, ACL 403 works |
| 6 | Observability | Grafana + Loki + Alloy; performance tested |

**Use `/gsd:progress` to check current phase status.**
**Use `/gsd:execute-phase` to begin executing a planned phase.**

---

## 11. Architecture Decision Records (Summary)

| ADR | Decision | Key Consequence |
|-----|---------|----------------|
| ADR-001 | LangGraph + PydanticAI for orchestration | Canvas `definition_json` schema must be versioned |
| ADR-002 | pgvector in PostgreSQL (no separate vector DB) | `WHERE user_id = $1` enforces memory isolation in same query |
| ADR-003 | bge-m3 as sole embedding model | `vector(1024)` column dimension locked; reindex = downtime |
| ADR-004 | LiteLLM Proxy for all LLM calls | Critical path — must be healthy before backend starts |
| ADR-005 | React Flow v12 for canvas | `definition_json` is React Flow-native (no translation layer) |
| ADR-006 | HTTP+SSE for all MCP servers | Each MCP server is a Docker service with `/sse` endpoint |
| ADR-007 | structlog JSON files for audit logs | Never log credential values; files are Loki-ready |
| ADR-008 | AES-256 encrypted DB table for credentials | No HashiCorp Vault for MVP; rotate KMS key periodically |

---

## 12. GSD + Superpowers Workflow

This project uses two complementary AI tool systems:

| Tool | Purpose | Persistence |
|------|---------|-------------|
| **GSD** | Phase planning, roadmap tracking, progress | Across sessions via `.planning/` files |
| **Superpowers** | Coding discipline: TDD, brainstorming, verification | Within session only (reads CLAUDE.md for context) |

### Key GSD Commands

```
/gsd:progress          → check current phase, get next action
/gsd:plan-phase        → create a PLAN.md for the next phase
/gsd:execute-phase     → execute phase plans with wave parallelization
/gsd:new-project       → initialize PROJECT.md + ROADMAP.md from blueprint docs
/gsd:verify-work       → validate built features against phase goals
/gsd:debug             → systematic debugging with persistent state
```

### Key Superpowers Skills

- `superpowers:brainstorming` — use BEFORE implementing any feature
- `superpowers:test-driven-development` — use BEFORE writing implementation code
- `superpowers:verification-before-completion` — use BEFORE claiming work is done
- `superpowers:dispatching-parallel-agents` — use for 2+ independent tasks
- `superpowers:systematic-debugging` — use when encountering any bug

### Recommended Workflow per Feature

```
brainstorm → discuss-phase → plan-phase → execute-phase → verify-work → code-review → complete
```
