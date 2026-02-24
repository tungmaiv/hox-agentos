# Blitz AgentOS

## What This Is

An enterprise-grade, on-premise Agentic Operating System for Blitz employees (~100 users). It acts as a personal chief of staff — automating daily routines (email digests, calendar summaries, project status), orchestrating multi-step workflows via a visual low-code canvas, and connecting to internal systems via MCP. Employees interact through web chat, Telegram, WhatsApp, and MS Teams. The platform is designed to be extensible: admins and developers can register new agents, tools, skills, and MCP servers over time without modifying core application code.

## Core Value

Every Blitz employee gets an intelligent, context-aware assistant that automates their daily work routines and lets them build custom automations without writing code — all within an enterprise-secure, on-premise environment where data never leaves the company.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Keycloak SSO integration (existing Keycloak instance, new realm/client)
- [ ] JWT validation with 3-gate security (JWT → RBAC → Tool ACL)
- [ ] Master agent with planning and sub-agent delegation (LangGraph)
- [ ] Sub-agents: email, calendar, project, channel
- [ ] Backend tools with Pydantic I/O schemas (email, calendar, project, sandbox)
- [ ] Hierarchical memory: short-term (verbatim), medium-term (summaries), long-term (facts + pgvector embeddings)
- [ ] Per-user memory isolation enforced at query level
- [ ] Visual workflow canvas (React Flow v12) with drag-and-drop node building
- [ ] Canvas workflows compile to LangGraph StateGraphs and execute
- [ ] Morning digest workflow: Email Fetch → Summarize → Send to Channel, schedulable
- [ ] Alert workflow: Trigger (keyword) → Create Task → Notify, event-driven
- [ ] HITL (human-in-the-loop) approval nodes in workflows via A2UI
- [ ] Celery-based job scheduler with cron expressions
- [ ] Multi-channel presence: web chat + Telegram + WhatsApp + MS Teams
- [ ] Channel adapter pattern (pluggable ChannelAdapter protocol)
- [ ] MCP integration framework with CRM mock server (HTTP+SSE transport)
- [ ] Extensible artifact registries — database-backed registries for agents, tools, skills, MCP servers with CRUD, enable/disable, permission assignment
- [ ] Admin + developer roles can register new agents, tools, skills, MCP servers via code/config
- [ ] Docker sandbox for untrusted code execution with resource limits
- [ ] AG-UI streaming chat with CopilotKit frontend
- [ ] A2UI generative UI (cards, tables, forms, progress)
- [ ] Credential management: AES-256 encrypted in DB, never exposed to LLMs
- [ ] Audit logging: structlog JSON, every tool call logged with user_id/tool/allowed/duration
- [ ] All LLM calls routed through LiteLLM Proxy with model aliases
- [ ] Embedding via self-hosted bge-m3 (1024-dim) in Celery workers
- [ ] Observability: Grafana + Loki + Alloy dashboards

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

**Inspiration:** OpenClaw architecture — local-first, multi-agent, sandboxed execution. Adapted for enterprise multi-tenancy with per-user isolation, RBAC, and audit compliance.

**Existing infrastructure:**
- Keycloak instance already running — add a `blitz` realm and client
- Ollama running on host machine (not Dockerized) — LiteLLM routes to it via `host.docker.internal:11434`
- PostgreSQL 16 with pgvector extension for both relational data and vector search

**Design documents completed:**
- Architecture: `docs/architecture/architecture.md` (comprehensive, 65KB)
- Blueprint: `docs/design/blueprint.md`
- Module breakdown: `docs/design/module-breakdown.md`
- Backend capabilities: `docs/design/backend-capabilities.md`
- Channel integration: `docs/design/channel-integration.md`
- Memory subsystem: `docs/design/memory-sub-system.md`
- Implementation guide: `docs/implementation/implementation-guide.md`

**Extensibility model:**
- Agents, tools, skills, and MCP servers are registered in database-backed registries
- Each artifact has metadata: name, description, version, status (enabled/disabled), required permissions
- Admins and developers can add/edit/disable/remove artifacts and assign role-based permissions
- Code-first registration for MVP; admin UI planned for future phase
- MCP servers are admin-managed only

**Email/calendar integration:** Provider-agnostic abstraction layer. Actual provider (Google Workspace, Microsoft 365) plugged in during integration — not locked to a specific provider.

**CRM:** Mock MCP server for MVP. Real CRM connected when available.

**Vietnamese language support:** bge-m3 embedding model handles multilingual natively. System should support Vietnamese in chat, summaries, and memory search.

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
| LangGraph + PydanticAI for orchestration | Canvas workflows compile directly to StateGraphs; Pydantic enforces tool I/O | — Pending |
| pgvector in PostgreSQL (no separate vector DB) | `WHERE user_id = $1` enforces memory isolation in same query; simpler ops at 100-user scale | — Pending |
| bge-m3 as sole embedding model | 1024-dim, multilingual (Vietnamese), self-hosted for data privacy | — Pending |
| LiteLLM Proxy for all LLM calls | Provider agnosticism + fallback routing; single config point | — Pending |
| React Flow v12 for canvas | definition_json is React Flow-native; no translation layer needed | — Pending |
| HTTP+SSE for all MCP servers | Standard MCP transport; each server is a Docker service with `/sse` endpoint | — Pending |
| CopilotKit (AG-UI/A2UI) for frontend | Real-time agent streaming + generative UI components out of the box | — Pending |
| Database-backed artifact registries | Extensibility: agents/tools/skills/MCP are data, not just code — enables runtime management | — Pending |
| Code-first registration, admin UI later | Ship faster; admin dashboard adds complexity without blocking core functionality | — Pending |
| All 3 channels in MVP (Telegram + WhatsApp + Teams) | Company uses all three; ChannelAdapter pattern makes each one incremental | — Pending |
| Existing Keycloak instance | Reduces setup work; add realm/client rather than deploy from scratch | — Pending |

---
*Last updated: 2026-02-24 after initialization*
