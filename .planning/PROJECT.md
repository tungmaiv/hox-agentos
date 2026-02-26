# Blitz AgentOS

## What This Is

An enterprise-grade, on-premise Agentic Operating System for Blitz employees (~100 users). It acts as a personal chief of staff — automating daily routines (email digests, calendar summaries, project status), orchestrating multi-step workflows via a visual low-code canvas, and connecting to internal systems via MCP. Employees interact through web chat, Telegram, WhatsApp, and MS Teams. The platform is designed to be extensible: admins and developers can register new agents, tools, skills, and MCP servers over time without modifying core application code.

## Core Value

Every Blitz employee gets an intelligent, context-aware assistant that automates their daily work routines and lets them build custom automations without writing code — all within an enterprise-secure, on-premise environment where data never leaves the company.

## Requirements

### Validated (v1.0)

- ✓ Keycloak SSO integration (existing Keycloak instance, new realm/client) — v1.0
- ✓ JWT validation with 3-gate security (JWT → RBAC → Tool ACL) — v1.0
- ✓ Master agent with planning and sub-agent delegation (LangGraph) — v1.0
- ✓ Sub-agents: email, calendar, project, channel — v1.0 (mock data; real OAuth Phase 4+)
- ✓ Hierarchical memory: short-term (verbatim), medium-term (summaries), long-term (pgvector) — v1.0
- ✓ Per-user memory isolation enforced at query level — v1.0
- ✓ MCP integration framework with CRM mock server (HTTP+SSE + hot-registration) — v1.0
- ✓ AG-UI streaming chat with CopilotKit frontend — v1.0
- ✓ A2UI generative UI (CalendarCard, EmailSummaryCard, ProjectStatusWidget) — v1.0
- ✓ Credential management: AES-256 encrypted in DB, never exposed to LLMs — v1.0
- ✓ Audit logging: structlog JSON, every tool call logged with user_id/tool/allowed/duration — v1.0
- ✓ All LLM calls routed through LiteLLM Proxy with model aliases — v1.0
- ✓ Embedding via self-hosted bge-m3 (1024-dim) in Celery workers — v1.0

### Active (v1.1+)

- [ ] Visual workflow canvas (React Flow v12) with drag-and-drop node building
- [ ] Canvas workflows compile to LangGraph StateGraphs and execute
- [ ] Morning digest workflow: Email Fetch → Summarize → Send to Channel, schedulable
- [ ] Alert workflow: Trigger (keyword) → Create Task → Notify, event-driven
- [ ] HITL (human-in-the-loop) approval nodes in workflows via A2UI
- [ ] Celery-based job scheduler with cron expressions
- [ ] Multi-channel presence: web chat + Telegram + WhatsApp + MS Teams
- [ ] Channel adapter pattern (pluggable ChannelAdapter protocol)
- [ ] Extensible artifact registries — database-backed registries for agents, tools, skills, MCP servers
- [ ] Docker sandbox for untrusted code execution with resource limits
- [ ] Observability: Grafana + Loki + Alloy dashboards
- [ ] Credential management UI — frontend Settings page to view/disconnect OAuth providers (v1.0 tech debt)

### Out of Scope

- SaaS/cloud hosting — enterprise on-premise requirement, no external data processing
- Kubernetes — Docker Compose only for MVP; K8s is post-MVP
- HashiCorp Vault — AES-256 DB encryption sufficient at ~100 user scale
- Separate vector database (Qdrant, Weaviate, etc.) — pgvector in PostgreSQL is sufficient
- User self-service MCP registration — admin-managed only for MVP
- Admin UI for artifact management — code/config-first; admin dashboard is post-MVP
- Mobile native apps — web-first with responsive design; mobile apps are post-MVP
- Real-time collaborative editing of workflows — single-user canvas editing for MVP
- OAuth social login (Google/GitHub) — Keycloak SSO is sufficient

## Context

**Current state (v1.0 shipped 2026-02-26):**
- 261 files, ~57K LOC across FastAPI backend + Next.js 15.5 frontend
- 180 backend tests passing (pytest); frontend strict TypeScript
- Docker Compose stack live: PostgreSQL+pgvector, Redis, LiteLLM, Keycloak, backend, frontend, Celery workers
- Alembic migrations 001–008 applied; pgvector `vector(1024)` columns in production schema
- Known tech debt from v1.0 audit: credential management UI absent; stale chat system prompt; classify_intent() orphaned module

**What shipped in v1.0:** Full security foundation (3-gate JWT/RBAC/ACL), streaming AG-UI chat, 3-tier memory with bge-m3 embeddings, email/calendar/project sub-agents with A2UI cards, MCP HTTP+SSE framework with hot-registration.

**What's next (v1.1):** Visual workflow canvas (Phase 4), scheduler + multi-channel presence (Phase 5), extensibility registries (Phase 6), hardening + sandbox (Phase 7), observability (Phase 8).

**Inspiration:** OpenClaw architecture — local-first, multi-agent, sandboxed execution. Adapted for enterprise multi-tenancy with per-user isolation, RBAC, and audit compliance.

**Existing infrastructure:**
- Keycloak instance already running — `blitz-internal` realm, `blitz-portal` and `blitz-backend` clients configured
- Ollama running on host machine (not Dockerized) — LiteLLM routes to it via `host.docker.internal:11434`
- PostgreSQL 16 with pgvector extension for both relational data and vector search

**Email/calendar integration:** Provider-agnostic abstraction layer with Pydantic v2 schemas (EmailSummaryOutput, CalendarOutput). Actual provider (Google Workspace, Microsoft 365) plugged in Phase 4+.

**CRM:** Mock MCP server live (mcp-crm Docker service). Real CRM connected when available.

**Vietnamese language support:** bge-m3 embedding model handles multilingual natively.

## Constraints

- **Scale**: ~100 users (Blitz employees) — do not over-engineer for millions
- **Deployment**: Docker Compose on-premise; no cloud dependencies
- **Security**: 3-gate security on every tool call (JWT → RBAC → Tool ACL); credentials never reach LLMs
- **Memory isolation**: All memory queries parameterized on `user_id` from JWT — no cross-user reads
- **Embedding dimension**: pgvector `vector(1024)` locked to bge-m3 — changing requires full reindex
- **Schema versioning**: Every `definition_json` (canvas workflows) carries `schema_version`
- **LLM access**: All calls through LiteLLM Proxy using model aliases (`blitz/master`, `blitz/fast`, `blitz/coder`, `blitz/summarizer`) — never provider SDKs directly
- **Package managers**: `uv` for Python, `pnpm` for Node.js — no pip/npm/yarn
- **Ollama**: Runs on host machine, accessed from containers via `host.docker.internal:11434`

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| LangGraph + PydanticAI for orchestration | Canvas workflows compile directly to StateGraphs; Pydantic enforces tool I/O | ✓ Good — LangGraph 0.4.10 stable; graph topology scales to sub-agents cleanly |
| pgvector in PostgreSQL (no separate vector DB) | `WHERE user_id = $1` enforces memory isolation in same query; simpler ops at 100-user scale | ✓ Good — HNSW indexes on memory_facts + memory_episodes; isolation holds at 180 tests |
| bge-m3 as sole embedding model | 1024-dim, multilingual (Vietnamese), self-hosted for data privacy | ✓ Good — transformers<5.0 pin required (4.57.6); FlagEmbedding 1.3.x stable |
| LiteLLM Proxy for all LLM calls | Provider agnosticism + fallback routing; single config point | ✓ Good — all 4 aliases (blitz/master/fast/coder/summarizer) routing correctly |
| React Flow v12 for canvas | definition_json is React Flow-native; no translation layer needed | — Pending (Phase 4) |
| HTTP+SSE for all MCP servers | Standard MCP transport; each server is a Docker service with `/sse` endpoint | ✓ Good — MCPClient + MCPToolRegistry live; hot-registration confirmed |
| CopilotKit (AG-UI/A2UI) for frontend | Real-time agent streaming + generative UI components out of the box | ✓ Good — CopilotKit 0.1.78 + copilotkit/__init__.py venv patch required |
| Database-backed artifact registries | Extensibility: agents/tools/skills/MCP are data, not just code — enables runtime management | — Pending (Phase 6) |
| Code-first registration, admin UI later | Ship faster; admin dashboard adds complexity without blocking core functionality | ✓ Good — no friction in v1.0; revisit in Phase 6 |
| All 3 channels in MVP (Telegram + WhatsApp + Teams) | Company uses all three; ChannelAdapter pattern makes each one incremental | — Pending (Phase 5); WhatsApp Business verification should start now (1-4 weeks) |
| Existing Keycloak instance | Reduces setup work; add realm/client rather than deploy from scratch | ✓ Good — blitz-internal realm + blitz-portal/blitz-backend clients running; self-signed cert required (KEYCLOAK_CA_CERT) |
| _classify_by_keywords for intent routing (v1.0 deviation)_ | LLM-based classify_intent() was over-engineered for 3 intents; keyword matching is faster and free | ⚠ Revisit — classify_intent() orphaned in router.py; delete or wire to _pre_route in Phase 4 |

---
*Last updated: 2026-02-26 after v1.0 milestone*
