# Stack Research: Blitz AgentOS

**Domain:** Enterprise on-premise agentic operating system
**Researched:** 2026-02-24
**Confidence:** HIGH (core stack verified via official docs and PyPI/npm; supporting libraries MEDIUM)

---

## Recommended Stack

### Agent Orchestration

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| LangGraph | 1.0.9 | Agent graph orchestration, multi-agent workflows | v1.0 GA (stable); graph-based design maps directly to visual canvas workflows; built-in persistence, HITL, and checkpointing; adopted by Uber, LinkedIn, Klarna; pre-built patterns for Supervisor/Swarm architectures | HIGH |
| PydanticAI | 1.63.0 | Tool I/O validation, structured LLM output | Type-safe tool schemas with automatic LLM retry on validation failure; strict JSON schema enforcement for Anthropic/OpenAI; natural fit with FastAPI's Pydantic ecosystem | HIGH |
| langgraph-prebuilt | latest | Pre-built agent patterns (Supervisor, Swarm) | Reduces boilerplate for common multi-agent architectures; official LangChain package | MEDIUM |

**Rationale:** LangGraph is the clear winner for this project because canvas `definition_json` (React Flow nodes/edges) compiles directly to LangGraph StateGraphs -- no translation layer needed. LangGraph v1.0 provides durable state persistence, human-in-the-loop `interrupt()`, and conditional branching that maps 1:1 to the visual workflow builder. PydanticAI complements LangGraph by enforcing tool I/O contracts, which is critical for enterprise reliability (malformed tool calls get retried automatically rather than silently failing).

### Frontend Framework

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Next.js | 15.5+ (consider 16.x) | Frontend framework (App Router) | Server Components by default reduces client bundle; Turbopack stable for dev/build; typed routes in 15.5+; React 19 support; dominant framework for React apps | HIGH |
| CopilotKit | 1.51.x | AG-UI streaming, agent chat UI, CoAgents | The definitive AG-UI protocol implementation; adopted by Google, Microsoft, LangChain, AWS; real-time agent streaming with tool call visualization; `useCoAgent` for bidirectional state sync between frontend and backend StateGraph | HIGH |
| React Flow (@xyflow/react) | 12.10.x | Visual workflow canvas | Only production-grade React node-based editor; SSR support; `definition_json` stored natively as React Flow format (nodes/edges); workflow editor template with auto-layout available; v12 is stable with active maintenance | HIGH |

**Version note on Next.js:** The architecture doc specifies Next.js 15+. Next.js 16 is now GA with Turbopack as default bundler and React Compiler stable. Recommend starting with 15.5 (LTS, battle-tested) and upgrading to 16.x when CopilotKit confirms full compatibility. Check CopilotKit release notes before upgrading -- AG-UI streaming relies on Next.js API routes and Server Actions that may have behavioral changes between major versions.

### Generative UI

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| A2UI (Google) | 0.8.x (Public Preview) | Declarative agent-driven UI specification | Open standard by Google; declarative JSON (not executable code) -- security-safe for enterprise; flat component list is LLM-friendly for incremental generation; CopilotKit has first-class A2UI support | MEDIUM |
| CopilotKit Generative UI | 1.51.x | Runtime rendering of agent-generated components | Agents can render custom React components in chat; A2UI envelopes parsed in `A2UIMessageRenderer`; works with AG-UI protocol natively | HIGH |

**Rationale:** A2UI is the emerging standard (backed by Google, integrated with CopilotKit) but is still in Public Preview (v0.8). The project should use CopilotKit's generative UI capabilities as the stable foundation, with A2UI as the declarative format for agent responses. This is the approach documented in the architecture -- `A2UIMessageRenderer` parses JSONL envelopes containing widget descriptors (Card, Table, Form, Progress).

### Backend Framework

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| FastAPI | 0.115.13+ | REST API, WebSocket, async HTTP server | Async-first; native Pydantic v2 integration; automatic OpenAPI docs; dependency injection for security gates; streaming response support for AG-UI | HIGH |
| SQLAlchemy | 2.0.46 | Async ORM + raw SQL | Production-stable async support since 2.0; `async_session()` pattern; works with asyncpg for PostgreSQL | HIGH |
| asyncpg | latest | PostgreSQL async driver | Fastest Python PostgreSQL driver; native connection pooling; required by SQLAlchemy async | HIGH |
| Alembic | latest | Database migrations | Official SQLAlchemy migration tool; async support; required for schema evolution | HIGH |

### Identity & SSO

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Keycloak | 26.5.x | Identity provider, SSO, RBAC | Existing infrastructure (already running); v26.5 adds JWT Authorization Grants, FAPI 2.0, Organizations (multi-tenancy), Passkey support; CNCF project; OpenTelemetry integration for observability; fine-grained admin permissions v2 | HIGH |

**Rationale:** Keycloak is a non-negotiable choice -- the existing instance means zero new infrastructure cost. The `blitz` realm/client approach is standard Keycloak multi-tenancy. v26.5 brings mature features that align perfectly: JWT auth grants for service-to-service, Organizations for potential future multi-tenant expansion, and OpenTelemetry for the observability phase.

### Database & Vector Search

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| PostgreSQL | 16+ (pgvector/pgvector:pg16 image) | Primary database + vector search | Single database for relational + vector data; `WHERE user_id = $1` enforces memory isolation in the same query as vector search; eliminates sync complexity of a separate vector DB | HIGH |
| pgvector | 0.8.x | Vector similarity search extension | v0.8 adds iterative index scans (prevents over-filtering), HNSW index improvements (9x faster queries reported on Aurora); `vector(1024)` for bge-m3 embeddings; supports cosine, L2, and inner product distance | HIGH |

**Rationale:** pgvector 0.8 in PostgreSQL 16 is the correct choice at ~100 user scale. The critical advantage is memory isolation -- a single `SELECT` with `WHERE user_id = $1 ORDER BY embedding <=> $2` gives both security and search in one query. Adding Qdrant/Weaviate/Milvus would require a separate security perimeter, sync logic, and operational overhead that is unjustified for 100 users.

### Embedding Model

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| bge-m3 (BAAI) | latest | Text embeddings (1024-dim) | Multilingual (100+ languages including Vietnamese); 8192 token input; dense + sparse + multi-vector retrieval; self-hosted via FlagEmbedding for on-premise compliance; top MTEB scores for multilingual | HIGH |
| FlagEmbedding | 1.3.5 | Python library for bge-m3 inference | Official BAAI library; `BGEM3FlagModel` class with fp16 support; handles all three retrieval modes | HIGH |

**Rationale:** bge-m3 is the only embedding model that simultaneously satisfies all project constraints: (1) multilingual with strong Vietnamese support, (2) self-hostable for on-premise, (3) 1024-dim is compact enough for pgvector HNSW indices at scale, (4) hybrid retrieval (dense + sparse) improves search quality. The 1024-dim column is locked once deployed -- changing requires full reindex.

### LLM Gateway

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| LiteLLM Proxy | 1.81.x | Unified LLM gateway, routing, fallback | OpenAI-compatible API for 100+ providers; 8ms P95 latency at 1k RPS; cost tracking + guardrails + load balancing; model aliases (`blitz/master`, `blitz/fast`, etc.) route to different backends transparently; JWT auth built-in; Docker-deployable with `-stable` tag | HIGH |

**Rationale:** LiteLLM Proxy is the sole entry point for all LLM calls. This is critical for: (1) provider agnosticism -- swap Claude for GPT-4o without code changes, (2) fallback routing -- if Ollama is down, fall back to cloud, (3) cost tracking across all models, (4) single config file for model routing. Use the `-stable` Docker tag (load-tested for 12 hours before publish).

### MCP Integration

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| MCP Python SDK | 1.26.x | MCP server/client implementation | Official Anthropic SDK; supports Streamable HTTP transport (recommended) and legacy SSE; FastMCP helper for rapid server creation | HIGH |

**MCP Transport Decision:** The MCP spec deprecated SSE in favor of Streamable HTTP in the 2025-03-26 specification update. Streamable HTTP uses a single endpoint (vs. SSE's two), supports standard load balancers, and simplifies CORS/auth. **Recommendation: Use Streamable HTTP for all new MCP servers.** The architecture doc specifies HTTP+SSE -- this should be updated to Streamable HTTP. The MCP Python SDK 1.26.x supports both transports, so migration is backward-compatible.

### Task Queue & Scheduler

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Celery | 5.6.2 | Task queue, scheduled jobs, background workers | Battle-tested for Python async workloads; Redis as broker (already in stack); cron-style scheduling via Celery Beat; runs as job owner's UserContext (not service account); sufficient for 100-user scale | HIGH |
| Redis | 7.x (or 8.x) | Cache, message broker, Celery backend | Fast, simple, proven as Celery broker; pub/sub for real-time notifications; session cache | HIGH |

**Why not Temporal:** Temporal is architecturally superior for complex stateful workflows, but adds significant operational overhead (Temporal Server cluster, separate DB, new SDK paradigm). At 100-user scale with Docker Compose, Celery + Redis is dramatically simpler to deploy and maintain. Temporal becomes relevant post-MVP if workflows need multi-day durability or cross-service orchestration. For now, LangGraph handles workflow state (checkpointing), and Celery handles scheduling -- this separation is clean and sufficient.

**Redis version note:** Redis 7.x is specified in the architecture. Redis 8.x is now GA. Either works -- Redis 7.8.x is the last 7.x release under the older BSD license. Redis 8.x uses RSALv2/SSPLv1 dual license. For on-premise enterprise use, both licenses are acceptable (RSALv2 restricts competing managed services, not internal use). Recommend Redis 7.8.x to stay on the BSD-licensed version unless Redis 8 features are needed.

### Observability & Logging

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| structlog | 25.5.0 | Structured JSON logging | Production-proven since 2013; JSON output is Loki-compatible; asyncio context variable support; type hints; audit logger pattern via `get_audit_logger()` | HIGH |
| Grafana | latest | Dashboards, alerting | De facto standard for observability dashboards; Loki integration for log queries | HIGH |
| Loki | latest | Log aggregation | Lightweight log aggregation that indexes labels (not full text); pairs with structlog JSON output; much simpler than ELK at 100-user scale | MEDIUM |
| Alloy (Grafana) | latest | Telemetry collector | Replaces Promtail; collects logs, metrics, traces; ships to Loki/Prometheus | MEDIUM |

### Sandbox Execution

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Docker SDK (Python) | latest | Sandbox container lifecycle | Create/exec/destroy containers for untrusted code; resource limits (CPU, memory, network); official Docker Python API | HIGH |

### Channel Gateways

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| python-telegram-bot | latest | Telegram bot integration | Official Telegram bot API wrapper; webhook mode for production | MEDIUM |
| WhatsApp Business API | Cloud API | WhatsApp messaging | Meta's official API; webhook-based | MEDIUM |
| Microsoft Bot Framework | latest | MS Teams integration | Official Microsoft SDK for Teams bots | MEDIUM |

---

## Supporting Libraries

### Backend (Python)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | 2.11+ | Data validation, settings | Every schema, config, request/response body |
| pydantic-settings | 2.x | Environment-based configuration | `core/config.py` settings class |
| uvicorn | latest | ASGI server | Running FastAPI in production |
| httpx | latest | Async HTTP client | Calling external APIs (Keycloak, MCP servers) |
| python-jose | latest | JWT decode/verify | `security/jwt.py` JWKS validation |
| cryptography | latest | AES-256 encryption | `user_credentials` table encryption |
| celery[redis] | 5.6.2 | Task queue with Redis broker | Background jobs, scheduled workflows |

### Frontend (TypeScript)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @copilotkit/react-core | 1.51.x | AG-UI React provider, chat hooks | Every page that uses agent chat |
| @copilotkit/react-ui | 1.51.x | Pre-built chat UI components | Chat interface, message rendering |
| @copilotkit/runtime | 1.51.x | Server-side AG-UI runtime | Next.js API route for CopilotKit |
| @xyflow/react | 12.10.x | Canvas node editor | Workflow builder page |
| zod | latest | Runtime schema validation | All API response validation |
| zustand | latest | Lightweight state management | Canvas state, UI state (not agent state) |

---

## Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Python package management | `uv add`, `uv run`, `uv sync` -- never pip |
| pnpm | Node.js package management | `pnpm add`, `pnpm install` -- never npm/yarn |
| gh | GitHub CLI | PRs, issues, repo operations |
| Docker Compose | Local development orchestration | All services defined in single compose file |
| Alembic | Database migrations | `alembic upgrade head` for schema changes |
| pytest | Python testing | `uv run pytest` for all backend tests |
| Vitest | Frontend testing | Fast, Vite-native test runner for TypeScript |

---

## Installation

### Backend (Python)

```bash
# Core framework
uv add fastapi uvicorn[standard] pydantic pydantic-settings

# Database
uv add sqlalchemy[asyncio] asyncpg alembic pgvector

# Agent orchestration
uv add langgraph pydantic-ai

# LLM gateway client (OpenAI-compatible, points at LiteLLM)
uv add openai

# Security
uv add python-jose[cryptography] httpx cryptography

# Task queue
uv add "celery[redis]"

# Logging
uv add structlog

# Embedding
uv add FlagEmbedding

# MCP
uv add mcp

# Dev dependencies
uv add --dev pytest pytest-asyncio httpx ruff mypy
```

### Frontend (TypeScript)

```bash
# Core framework
pnpm add next react react-dom

# Agent UI
pnpm add @copilotkit/react-core @copilotkit/react-ui @copilotkit/runtime

# Canvas
pnpm add @xyflow/react

# Validation & state
pnpm add zod zustand

# Dev dependencies
pnpm add -D typescript @types/react @types/node vitest
```

### Infrastructure (Docker)

```yaml
# docker-compose.yml services:
# - postgres (pgvector/pgvector:pg16)
# - redis (redis:7.8-alpine)
# - keycloak (quay.io/keycloak/keycloak:26.5)
# - litellm (ghcr.io/berriai/litellm:main-stable)
# - backend (custom Dockerfile)
# - frontend (custom Dockerfile)
# - celery-worker (same image as backend)
# - celery-beat (same image as backend)
# - mcp-crm (custom MCP server)
# - mcp-docs (custom MCP server)
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Agent orchestration | LangGraph | CrewAI | Role-based model doesn't map to visual canvas; no graph-as-data representation; less control over state transitions |
| Agent orchestration | LangGraph | AutoGen (AG2) | Conversation-centric design is wrong abstraction for workflow canvas; less mature persistence/checkpointing |
| Agent orchestration | LangGraph | OpenAI Agents SDK | Vendor lock-in to OpenAI; no on-premise LLM support; no visual graph representation |
| Frontend agent UI | CopilotKit (AG-UI) | Vercel AI SDK | AI SDK is provider-to-frontend only; no agent protocol, no CoAgent state sync, no generative UI; complements rather than replaces CopilotKit |
| Generative UI | A2UI + CopilotKit | MCP Apps | MCP Apps is even earlier stage than A2UI; less ecosystem support |
| Visual canvas | React Flow v12 | JointJS | JointJS is commercial (Rappid); React Flow is open-source with larger community; v12 has first-party workflow editor template |
| Visual canvas | React Flow v12 | Cytoscape.js | Designed for data visualization, not interactive node editing; no drag-and-drop node palette |
| Identity | Keycloak | Auth0 | SaaS-only defeats on-premise requirement; Keycloak already deployed |
| Identity | Keycloak | Zitadel | Less mature; Keycloak already deployed with organizational knowledge |
| Vector search | pgvector | Qdrant/Milvus/Weaviate | Adds separate infrastructure; breaks memory isolation (can't do `WHERE user_id` in same vector query); unjustified at 100-user scale |
| Embedding | bge-m3 | OpenAI text-embedding-3 | Requires external API calls; violates on-premise constraint; English-optimized (weaker Vietnamese) |
| Embedding | bge-m3 | Cohere embed-multilingual-v3 | SaaS-only; can't self-host |
| LLM gateway | LiteLLM Proxy | Portkey | SaaS-first; self-hosted version less mature; fewer community contributions |
| LLM gateway | LiteLLM Proxy | AI Gateway (Kong) | Heavier infrastructure; less Python-native; overkill for 100 users |
| Task queue | Celery | Temporal | Significant operational overhead (Temporal Server, separate DB); overkill for simple cron scheduling at 100-user scale; consider post-MVP |
| Task queue | Celery | Dramatiq | Smaller ecosystem; fewer scheduling features; Celery + Redis is the proven Python standard |
| MCP transport | Streamable HTTP | SSE (legacy) | SSE deprecated in MCP spec 2025-03-26; requires two endpoints; harder to load balance; Streamable HTTP is the standard going forward |
| Logging | structlog | loguru | loguru is simpler but less structured; structlog's JSON output is Loki-ready without transformation |
| Frontend framework | Next.js 15.5+ | Remix | Smaller ecosystem; CopilotKit is built for Next.js; less enterprise adoption |
| Database | PostgreSQL 16 | PostgreSQL 17 | PG17 is fine but PG16 has broader pgvector testing; pgvector/pgvector Docker image targets pg16 |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `pip install` | Breaks lockfile reproducibility; uv is faster and deterministic | `uv add` / `uv sync` |
| `npm` / `yarn` | Project standardized on pnpm for consistent lockfiles | `pnpm add` / `pnpm install` |
| `import anthropic` / `import openai` directly | Bypasses LiteLLM proxy; loses fallback routing, cost tracking, model aliases | `from core.config import get_llm` |
| Qdrant / Weaviate / Milvus | Separate vector DB adds infrastructure, breaks memory isolation query pattern | pgvector in PostgreSQL |
| HashiCorp Vault | Over-engineered for 100-user MVP; adds significant operational complexity | AES-256 encrypted DB column |
| Kubernetes | Not needed for MVP; Docker Compose is sufficient at this scale | Docker Compose |
| LangChain (legacy chains) | Deprecated in favor of LangGraph for agent workflows; chains are too linear | LangGraph StateGraph |
| `print()` / `logging.info()` | Not structured; not Loki-compatible; no context variables | `structlog.get_logger(__name__)` |
| `any` in TypeScript | Type-unsafe; defeats strict mode | `unknown` + type guards |
| Relative imports in Python | Fragile; breaks when modules move | Absolute imports only |
| `localStorage` for JWT | XSS vulnerability | Memory-only JWT storage |
| SSE transport for new MCP servers | Deprecated in MCP spec 2025-03-26 | Streamable HTTP |

---

## Version Compatibility Matrix

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| LangGraph 1.0.x | PydanticAI 1.x | Both use Pydantic v2 for tool schemas; LangGraph tools can wrap PydanticAI agents |
| FastAPI 0.115.x | Pydantic 2.11+ | FastAPI 0.115.10+ explicitly supports Pydantic 2.11 |
| Next.js 15.5+ | CopilotKit 1.51.x | CopilotKit tested against Next.js 15 App Router; verify before upgrading to 16.x |
| React Flow 12.10.x | React 18/19 | v12 supports both; Next.js 15 uses React 19 RC |
| pgvector 0.8.x | PostgreSQL 16 | Confirmed compatible; use `pgvector/pgvector:pg16` Docker image |
| Celery 5.6.x | Redis 7.x/8.x | Both broker configurations supported |
| SQLAlchemy 2.0.46 | asyncpg latest | Fully async with `async_session()` pattern |
| MCP SDK 1.26.x | FastAPI 0.115.x | MCP servers can mount as FastAPI sub-applications |
| structlog 25.5.0 | Python 3.9+ | Supports asyncio context variables natively |

---

## Stack Patterns by Variant

**If adding a new MCP server:**
- Use MCP Python SDK with `FastMCP` helper and Streamable HTTP transport
- Register tools in `gateway/tool_registry.py` with `mcp_server` and `mcp_tool` metadata
- Same Gate 3 ACL applies as backend tools

**If adding a new sub-agent:**
- Create in `agents/subagents/` as a LangGraph node
- Register tools in `gateway/tool_registry.py` with `required_permissions`
- Use PydanticAI for tool I/O validation

**If adding a new channel:**
- Implement `ChannelAdapter` protocol
- Create inbound webhook in `api/routes/channels.py`
- Create outbound adapter in `channels/`
- Do NOT modify agent/tool/memory code

**If CPU-bound work (embedding, file processing):**
- Run in Celery worker, never in FastAPI request handler
- Use `celery.shared_task` with explicit `user_id` for memory isolation

---

## Critical Architecture Constraint: MCP Transport Update

The architecture document specifies HTTP+SSE for MCP transport. **The MCP specification deprecated SSE in favor of Streamable HTTP** (spec version 2025-03-26). Key changes:

- **SSE (deprecated):** Two endpoints (`/sse` for streaming, POST for messages); persistent connection; harder to load balance
- **Streamable HTTP (recommended):** Single endpoint; standard HTTP POST with optional SSE upgrade; works with standard ALBs, CORS, auth middleware

**Recommendation:** Update the architecture to use Streamable HTTP for all MCP servers. The MCP Python SDK 1.26.x supports both transports, and the `FastMCP` helper makes Streamable HTTP the default. Existing SSE-based code can be migrated by changing the transport parameter.

---

## Sources

### HIGH Confidence (Official docs, PyPI, npm)
- LangGraph 1.0 announcement: https://blog.langchain.com/langchain-langgraph-1dot0/
- LangGraph PyPI (v1.0.9): https://pypi.org/project/langgraph/
- PydanticAI PyPI (v1.63.0): https://pypi.org/project/pydantic-ai/
- CopilotKit npm (v1.51.x): https://www.npmjs.com/package/@copilotkit/react-core
- React Flow v12 release: https://xyflow.com/blog/react-flow-12-release
- React Flow npm (v12.10.x): https://www.npmjs.com/package/@xyflow/react
- FastAPI release notes: https://fastapi.tiangolo.com/release-notes/
- Keycloak 26.5 releases: https://www.keycloak.org/2026/02/keycloak-2653-released
- pgvector 0.8.0 announcement: https://www.postgresql.org/about/news/pgvector-080-released-2952/
- pgvector GitHub: https://github.com/pgvector/pgvector
- LiteLLM PyPI (v1.81.x): https://pypi.org/project/litellm/
- LiteLLM docs: https://docs.litellm.ai/
- Celery PyPI (v5.6.2): https://pypi.org/project/celery/
- MCP spec transports: https://modelcontextprotocol.io/specification/2025-03-26/basic/transports
- MCP Python SDK: https://pypi.org/project/mcp/
- FlagEmbedding PyPI (v1.3.5): https://pypi.org/project/FlagEmbedding/
- bge-m3 Hugging Face: https://huggingface.co/BAAI/bge-m3
- structlog PyPI (v25.5.0): https://pypi.org/project/structlog/
- SQLAlchemy 2.0 async docs: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

### MEDIUM Confidence (WebSearch verified with multiple sources)
- AG-UI protocol: https://docs.ag-ui.com/
- A2UI specification: https://github.com/google/A2UI
- MCP SSE deprecation analysis: https://blog.fka.dev/blog/2025-06-06-why-mcp-deprecated-sse-and-go-with-streamable-http/
- CopilotKit A2UI integration: https://www.copilotkit.ai/blog/build-with-googles-new-a2ui-spec-agent-user-interfaces-with-a2ui-ag-ui
- LangGraph multi-agent guide: https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/
- Celery vs Temporal comparison: https://pedrobuzzi.hashnode.dev/celery-vs-temporalio
- Next.js 16 blog: https://nextjs.org/blog/next-16

---
*Stack research for: Blitz AgentOS -- Enterprise on-premise agentic operating system*
*Researched: 2026-02-24*
