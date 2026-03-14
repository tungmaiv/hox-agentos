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

**Step 5 — Record decisions in STATE.md.** When you make a technical decision during implementation (e.g., "owner_user_id must be nullable", "use asyncio.run() in Celery tasks"):
- Add to `.planning/STATE.md` → Decisions section with format:
  `- [Phase-Plan or context]: <decision> — <rationale>`
- Commit STATE.md update with the plan's final commit.
- This ensures decisions survive context resets and are visible to all future agents.

**Step 6 — Use canonical commands only.** See Section 13 for exact test, build, and migration commands. Do NOT guess or invent variants — wrong commands either time out or produce misleading output.

---

## DO / DON'T — Quick Reference

Scan this before writing any code. Details are in the sections below.

### Package Management
| DO | DON'T |
|----|-------|
| `uv add <pkg>` / `uv run <cmd>` | `pip install` |
| `pnpm add <pkg>` / `pnpm run <cmd>` | `npm install` / `yarn add` |
| `gh pr create` / `gh issue create` | raw `git` for GitHub operations |

### Commits (GSD Tracking)
| DO | DON'T |
|----|-------|
| `feat(04-01): add workflow SQLAlchemy models` | `add workflow models` (no phase prefix) |
| `fix(04-03): handle HITL interrupt correctly` | `fix bug` (too vague for GSD spot-checks) |
| `docs(phase-04): update STATE.md position` | `update docs` |
| `test(04-01): add workflow route tests` | `add tests` |
| One atomic commit per task | Bundle multiple unrelated tasks in one commit |

**Format:** `<type>(<phase>-<plan>): <description>` — type is feat/fix/test/docs/refactor/chore; description is imperative, ≤72 chars. GSD executor spot-checks rely on this format to verify work completed.

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
| `blitz/master` | Master agent, complex reasoning | Ollama/qwen3.5:cloud (~1.4s) |
| `blitz/fast` | Simple sub-tasks, classification | Ollama/qwen3.5:cloud (~1.4s) |
| `blitz/coder` | Code generation, debugging | Ollama/qwen3.5:cloud (~1.4s) |
| `blitz/summarizer` | Memory summarization | Ollama/qwen3.5:cloud (~1.4s) |
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
| Keycloak | 8180 (HTTP) / 7443 (HTTPS) | Admin: `http://keycloak.blitz.local:8180` — use HTTPS `https://keycloak.blitz.local:7443` for OIDC (issuer match); internal container-to-container is port 8080 |
| LiteLLM Proxy | 4000 | Internal only |
| MCP CRM Server | 8001 | HTTP+SSE, `/sse` endpoint |
| MCP Docs Server | 8002 | HTTP+SSE, `/sse` endpoint |
| Ollama | 11434 | **Host machine** (not Dockerized) — accessed via `host.docker.internal:11434` from containers |
| Grafana (future) | 3001 | Pre-production only |

### Common Commands

Use `just` (project-root `justfile`) as the primary task runner. Run `just` with no args to list all recipes.

```bash
# ── Docker services (all accept optional service name(s)) ─────
just up [svc...]           # start all or specific services (detached)
just down [svc...]         # stop all or specific services
just stop [svc...]         # alias for down
just restart [svc...]      # restart all or specific services
just rebuild [svc...]      # build + start (all or specific)
just build [svc...]        # build only, no start
just reset                 # DESTRUCTIVE: stop + wipe volumes + fresh start
just logs [svc]            # tail logs (all or specific service)
just ps                    # service status

# ── Database ──────────────────────────────────────────────────
just migrate               # run Alembic migrations
just db                    # open psql shell

# ── One-off docker/uv/pnpm commands ──────────────────────────
docker compose run --rm backend celery -A scheduler.celery_app worker --concurrency=4
uv add <pkg>               # add Python dep (run from backend/)
pnpm add <pkg>             # add JS dep (run from frontend/)
```

> **Gotcha — `justfile` and `.env` files:** `set dotenv-load` was intentionally removed.
> Each service manages its own `.env`: backend via pydantic-settings (`backend/.env`),
> frontend via Next.js (`frontend/.env.local`). Do NOT add `set dotenv-load := true`
> back — it causes `just`'s dotenv parser to mangle JSON list values like
> `CORS_ORIGINS=["http://..."]` → `[` → pydantic-settings `JSONDecodeError`.
>
> **Gotcha — container-only dev:** Backend and frontend run EXCLUSIVELY in Docker containers.
> Do NOT start them on the host with uvicorn or pnpm. Use `just up` for the full stack.
> Running host processes causes container→host URL resolution failures and port conflicts.

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

> **Current milestone:** v1.3 shipped 2026-03-14 (Phases 15–25). Run `/gsd:new-milestone` to define v1.4.

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

| Tool | Purpose | Persistence | Entry Point |
|------|---------|-------------|-------------|
| **GSD** | Project lifecycle: milestones → phases → plans → execution | Across sessions via `.planning/` files | `/gsd:progress` |
| **Superpowers** | Session discipline: TDD, brainstorming, verification | Within session (reads CLAUDE.md for context) | Skill tool: `superpowers:X` |

### Mandatory Invocation Rule

> **If there is even a 1% chance a Superpowers skill applies to your task, invoke it via the Skill tool BEFORE doing anything — including asking clarifying questions.**

This is not optional. Common rationalizations to reject:
- "Too simple to need a skill" — simple code breaks in complex ways
- "I need context first" — skills tell you HOW to gather context
- "Just this once" — discipline only works when it's unconditional

**Skill priority:** Process skills (brainstorming, debugging) first → Implementation skills second.

### Key GSD Commands

```
/gsd:progress          → ALWAYS start here — loads state, routes to next action
/gsd:discuss-phase N   → Capture design decisions → NN-CONTEXT.md
/gsd:plan-phase N      → Research + create PLAN.md files (with verification loop)
/gsd:execute-phase N   → Parallel wave execution of all plans in phase
/gsd:verify-work N     → Conversational UAT, creates NN-UAT.md with gap list
/gsd:quick <desc>      → Quick fix with GSD guarantees (no research/checker agents)
/gsd:debug <desc>      → Systematic debug with persistent state across /clear
```

### Key Superpowers Skills

```
superpowers:brainstorming                → BEFORE any feature implementation
superpowers:writing-plans                → After brainstorming, before coding
superpowers:test-driven-development      → BEFORE writing implementation code
superpowers:systematic-debugging         → BEFORE proposing any fix
superpowers:verification-before-completion → BEFORE claiming work is done
superpowers:dispatching-parallel-agents  → For 2+ independent tasks in parallel
superpowers:subagent-driven-development  → Execute plan in current session
superpowers:executing-plans              → Execute plan in new parallel session
superpowers:using-git-worktrees          → Before any implementation begins
superpowers:finishing-a-development-branch → After all tasks complete
```

### Artifact Sharing Protocol

GSD and Superpowers exchange artifacts through specific files. Produce and consume them correctly:

```
Superpowers → GSD:
  docs/plans/YYYY-MM-DD-design.md  →  gsd-planner reads for design intent
  docs/plans/YYYY-MM-DD-plan.md    →  gsd-executor can execute directly
  git commits (atomic, per task)   →  GSD spot-checks for existence

GSD → Superpowers:
  .planning/PROJECT.md             →  brainstorming reads for project context
  .planning/NN-PLAN.md             →  subagent-driven-development executes
  .planning/NN-RESEARCH.md         →  writing-plans uses for technical context
  .planning/NN-CONTEXT.md          →  writing-plans uses for design decisions

Both read:
  CLAUDE.md                        →  shared project conventions (this file)
  docs/dev-context.md              →  URLs, endpoints, gotchas
```

### Context Continuity Protocol

**Before every `/clear`:**
1. `STATE.md` has current position and all decisions made this session
2. Design docs (`docs/plans/`) are committed to git
3. If mid-task: run `/gsd:pause-work` to create `.planning/RESUME.md`

**After `/clear` (new session start):**
1. ALWAYS run `/gsd:progress` first — reloads full state from files
2. If RESUME.md exists: run `/gsd:resume-work` instead

### Recommended Workflow per Feature

```
[Session 1 — Design]
superpowers:brainstorming       → docs/plans/YYYY-MM-DD-design.md
/gsd:discuss-phase N            → .planning/NN-CONTEXT.md
/clear

[Session 2 — Planning]
/gsd:plan-phase N               → .planning/NN-0X-PLAN.md files
/clear

[Session 3 — Execution]
superpowers:using-git-worktrees → isolated branch
/gsd:execute-phase N            → SUMMARY.md + atomic commits per task
/clear

[Session 4 — Validation]
superpowers:verification-before-completion  → fresh test suite evidence
/gsd:verify-work N              → UAT.md
superpowers:finishing-a-development-branch  → merge or PR
/gsd:progress                   → confirm completion, get next phase routing
```

---

## 13. Canonical Verification Commands

**Always use these exact commands.** `uv run pytest` and `uv run alembic` time out on this machine — use `.venv/bin/` paths directly.

### Backend Tests

```bash
# Full test suite (canonical — always use this exact form)
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q

# Specific file
PYTHONPATH=. .venv/bin/pytest tests/api/test_workflow_routes.py -v

# With stdout (debugging)
PYTHONPATH=. .venv/bin/pytest tests/ -v -s

# Current baseline: 946 tests — a commit that drops this count unexpectedly is a red flag
```

### Frontend Build + Type Check

```bash
# Full build — catches TypeScript errors (canonical)
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build

# TypeScript check only (no output files)
pnpm exec tsc --noEmit
```

### Frontend E2E Tests (Playwright)

**Prerequisites:** `just up` must be running — Playwright targets `http://localhost:3000`.

**Test users** (local auth accounts — NOT Keycloak SSO):

| Role | Username | Password | Access |
|------|----------|----------|--------|
| Administrator (`it-admin`) | `admin` | `admin` | All pages including `/admin/*` |
| Normal user (`employee`) | `giangtt` | `BilHam30` | `/chat`, `/workflows`, `/skills`, `/settings`, `/profile` — no `/admin/*` |

Credentials are also stored in `.dev-secrets` as `E2E_ADMIN_USER`, `E2E_ADMIN_PASSWORD`, `E2E_USER_USER`, `E2E_USER_PASSWORD`.

```bash
cd /home/tungmv/Projects/hox-agentos/frontend

# Full E2E suite
pnpm exec playwright test

# Specific test file
pnpm exec playwright test e2e/tests/auth.spec.ts

# Run headed (visible browser — useful for debugging)
pnpm exec playwright test --headed

# Open HTML report after a run
pnpm exec playwright show-report

# Run only admin-context tests
pnpm exec playwright test --project=admin-tests

# Run only normal-user-context tests
pnpm exec playwright test --project=user-tests
```

**Test file structure** (once scaffolded):
```
frontend/e2e/
  auth/
    admin.setup.ts      # logs in as admin, saves storageState to e2e/.auth/admin.json
    user.setup.ts       # logs in as giangtt, saves storageState to e2e/.auth/user.json
  fixtures/
    index.ts            # typed test() with adminPage / userPage fixtures
  tests/
    auth.spec.ts        # login, logout, protected route redirect to /login
    admin-access.spec.ts # admin sees /admin, normal user gets 403/redirect
    chat.spec.ts        # chat page loads, message input present
    skills.spec.ts      # skills catalog loads for both users
```

**Critical gotcha:** Always authenticate via the login form at `/login` (POST to `/api/auth/local/token` via next-auth). Do NOT try to set cookies or call the backend JWT endpoint directly — next-auth manages the session cookie and CSRF token internally.

### Alembic Migrations

```bash
cd /home/tungmv/Projects/hox-agentos/backend

# Check current state
.venv/bin/alembic heads         # current head(s)
.venv/bin/alembic current       # current DB revision
.venv/bin/alembic check         # pending migrations

# Create new migration (autogenerate from ORM models)
.venv/bin/alembic revision --autogenerate -m "NNN_short_description"
# Next migration number: 031
# Current heads (two active heads — merge required for new migrations):
#   617b296e937a — migration 030 mcp_server_catalog (Phase 24)
#   83f730920f5a — platform_config (Phase 18)
# New migrations must merge from both heads: .venv/bin/alembic merge 617b296e937a 83f730920f5a -m "031_..."
# Note: hex IDs (autogenerated); do NOT rename — breaks revision chain.

# Migration chain (do NOT create branching without merge migration):
# 001 → 002+003 (parallel) → merge(9754fd080ee2) → 004 → ... → 021 → 83f730920f5a
# Also: 021 → ... → 028 → c12d84fc28f9 (029_registry_entries) → 617b296e937a (030_mcp_catalog)

# Apply migrations — CANNOT run from host (.env not present outside Docker)
# Method 1: via justfile (requires host .env)
just migrate
# Method 2: via docker exec (always works)
docker exec -it blitz-postgres psql -U blitz blitz -c "<SQL statements>"
```

### Service Health

```bash
just ps                          # all Docker services status
just logs backend                # tail backend logs
curl http://localhost:8000/health # backend health (no JWT needed)
curl http://localhost:4000/health # LiteLLM proxy health
```

---

## 14. Critical Gotchas (Know Before Writing Code)

Hard-won discoveries from prior sessions. Knowing these saves hours of debugging.

### Python / Backend

| Gotcha | Symptom | Fix |
|--------|---------|-----|
| `uv run pytest` times out | Hangs indefinitely | Use `.venv/bin/pytest` directly |
| `uv run alembic` times out | Hangs indefinitely | Use `.venv/bin/alembic` directly |
| Missing `PYTHONPATH` in pytest | `ModuleNotFoundError: core` | Prefix: `PYTHONPATH=. .venv/bin/pytest` |
| Two Alembic migrations branch from same revision | `alembic heads` shows 2 | Create merge: `.venv/bin/alembic merge <rev1> <rev2> -m "merge"` |
| `FlagEmbedding` / `transformers` import error | `is_torch_fx_available` removed | `transformers<5.0` pinned — do NOT upgrade |
| Celery tasks must use `asyncio.run()` | `async def` task silently fails | Wrap: `asyncio.run(_async_body())` inside each task body |
| No FK on `user_id` columns | Intentional — users live in Keycloak, not PostgreSQL | Never add FK constraint to a `users` table (doesn't exist) |
| JSONB columns need variant for SQLite tests | `VECTOR` / `JSONB` DDL fails in aiosqlite | Use `JSON().with_variant(JSONB(), 'postgresql')` on all JSONB columns |
| Lazy imports not patchable in tests | `patch('module.func')` silently no-ops | Import at module top level; patch at definition site |
| `importlib.reload()` inside `patch()` | Reload rebinds from real source, bypasses patch | Patch the module-level name directly without reload |

### Frontend / TypeScript

| Gotcha | Symptom | Fix |
|--------|---------|-----|
| Next.js 15 async params | `params.id` type error in page components | Type as `Promise<{id: string}>` and `await params` before use |
| FastAPI route ordering | String literal `/templates` matched as UUID | Declare `/templates`, `/runs/*`, etc. BEFORE `/{workflow_id}` |
| `pnpm run build` fails on `any` | TypeScript strict mode enforced | Use `unknown` + type guard — never cast to `any` |
| CopilotKit agent name must match exactly | Agent not found on frontend | Backend name `'blitz_master'` must match `useCoAgent` reference |
| `react-markdown` v10 removed `className` prop | TypeScript error on `<ReactMarkdown className>` | Wrap in `<div className="..."><ReactMarkdown>` instead |
| `@copilotkit/shared` not importable as direct dep | pnpm virtual store isolation | Define local `ChatMessage` interface instead of importing |

### Security / Auth

| Gotcha | Symptom | Fix |
|--------|---------|-----|
| Keycloak self-signed TLS cert | JWKS HTTP fetch fails with SSL error | Set `KEYCLOAK_CA_CERT=frontend/certs/keycloak-ca.crt` in `backend/.env` |
| No `aud` claim in `blitz-portal` tokens | `JWTError` → 401 on all requests | Decode with `options={"verify_aud": False}` |
| Roles in `realm_roles` not `realm_access.roles` | Empty roles → 403 for all users | Check both: `payload.get("realm_roles") or payload.get("realm_access", {}).get("roles", [])` |
| CopilotKit sends camelCase body | `RunAgentInput(**body)` raises `TypeError` | Use `RunAgentInput.model_validate(body)` |
| `BlitzState` user_id/conversation_id always `None` via LangGraph | Memory not saved | Use contextvar fallback: `user_id = user_id_ctx.get(None)` |

### GSD / Agents

| Gotcha | Symptom | Fix |
|--------|---------|-----|
| `classifyHandoffIfNeeded` error in executor return | Executor reports "failed" with runtime error | Claude Code bug — spot-check SUMMARY.md + commits; if present, treat as success |
| `docker compose restart <svc>` does NOT reload env vars | New docker-compose.yml env value silently ignored; old value still active | Use `docker compose up -d <svc>` to recreate container and pick up new env vars |
| `alembic.ini` script_location must be relative | Portability fails across machines | Use `script_location = alembic` (relative), not absolute path |
| `conftest.py` must call `configure_logging()` at session start | structlog config order failures in full suite | Add to session-scoped fixture in `conftest.py` |
| `os.environ.setdefault()` in conftest for test env vars | Real `.env` values overridden in tests | Use `setdefault()` not `os.environ[key] = value` |

---

## 15. Context Continuity Protocol

How to ensure no context is lost across sessions when using GSD and Superpowers together.

### Before Every `/clear`

```
□ STATE.md updated — current position, any new decisions added to Decisions section
□ Design docs committed — docs/plans/YYYY-MM-DD-*.md in git
□ Technical discoveries added — new URLs/gotchas in docs/dev-context.md
□ Blockers noted — new blockers in STATE.md → Blockers section
□ Mid-task? — run /gsd:pause-work to create .planning/RESUME.md
```

### After `/clear` (New Session)

```bash
# Step 1 — ALWAYS start with this:
/gsd:progress
# Reads STATE.md + ROADMAP.md → shows position + routes to next action

# Step 2 — If RESUME.md exists:
/gsd:resume-work
# Restores exact stopping point

# Step 3 — Confirm context before coding
# Never start implementation without knowing the current phase and position
```

### Decision Recording Format

When making a technical decision during implementation, add to `.planning/STATE.md`:

```markdown
### Decisions
- [04-01]: owner_user_id on workflows is NULLABLE — template rows have owner_user_id=NULL
- [04-02]: compile_workflow_to_stategraph() returns uncompiled builder — caller injects checkpointer
- [03-01]: Pin transformers<5.0 (4.57.6) — FlagEmbedding 1.3.x breaks on transformers 5.0
```

Format: `- [phase-plan or context]: <decision> — <rationale>`

### What Lives Where

| Context type | Canonical location | Read by |
|-------------|-------------------|---------|
| Technical decisions (per plan) | `.planning/STATE.md` Decisions | All GSD agents, any new session |
| Blockers / concerns | `.planning/STATE.md` Blockers | `/gsd:progress`, all agents |
| Pending todos | `.planning/STATE.md` Pending Todos | `/gsd:check-todos` |
| Phase design decisions | `.planning/phases/NN-slug/NN-CONTEXT.md` | gsd-planner, gsd-plan-checker |
| Technical research | `.planning/phases/NN-slug/NN-RESEARCH.md` | gsd-planner |
| URL / endpoint / port gotchas | `docs/dev-context.md` | Every agent (AGENT INSTRUCTIONS Step 1) |
| Cross-cutting critical gotchas | `CLAUDE.md` Section 14 | Every agent, every session |
| Design intent and architecture | `docs/plans/YYYY-MM-DD-design.md` | brainstorming, writing-plans |
| Implementation plans | `docs/plans/YYYY-MM-DD-plan.md` | executing-plans, subagent-driven-development |
