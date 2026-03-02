# Blitz AgentOS

## What This Is

An enterprise-grade, on-premise Agentic Operating System for Blitz employees (~100 users). It acts as a personal chief of staff — automating daily routines (email digests, calendar summaries, project status), orchestrating multi-step workflows via a visual low-code canvas, and connecting to internal systems via MCP. Employees interact through web chat, Telegram, WhatsApp, and MS Teams. Admins and developers can extend the platform at runtime by registering new agents, tools, skills, and MCP servers through database-backed registries — no restarts required. Untrusted code executes safely in Docker sandboxes, all operations are observable via Grafana, and data never leaves the company.

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

### Validated (v1.1)

- ✓ Visual workflow canvas (React Flow v12) with drag-and-drop node building — v1.1
- ✓ Canvas workflows compile to LangGraph StateGraphs and execute — v1.1
- ✓ Morning digest workflow: Email Fetch → Summarize → Send to Channel, schedulable — v1.1
- ✓ Alert workflow: Trigger (keyword) → Create Task → Notify, event-driven — v1.1
- ✓ HITL (human-in-the-loop) approval nodes in workflows via A2UI — v1.1
- ✓ Celery-based job scheduler with cron expressions — v1.1
- ✓ Multi-channel presence: web chat + Telegram (live) + WhatsApp + MS Teams (code complete) — v1.1
- ✓ Channel adapter pattern (pluggable ChannelAdapter protocol with runtime isinstance enforcement) — v1.1
- ✓ Extensible artifact registries — database-backed registries for agents, tools, skills, MCP servers — v1.1
- ✓ Admin dashboard at /admin: tabbed UI, permission matrix, multi-version, skill import pipeline — v1.1
- ✓ Docker sandbox for untrusted code execution with resource limits — v1.1
- ✓ Observability: Grafana + Loki + Alloy dashboards, LiteLLM cost tracking, Telegram alerting — v1.1
- ✓ Tool cache invalidation on status/version change (immediate, not 60s TTL) — v1.1
- ✓ LLM call metrics wired (blitz_llm_calls_total incremented in get_llm()) — v1.1
- ✓ Credential management UI — frontend Settings page to view/disconnect OAuth providers — v1.1

### Active (v1.2 — Developer Experience)

**Goal:** Make AgentOS easier to extend, explore, and operate — unified admin desk, guided artifact creation, capabilities introspection, API→MCP generation, external skill repositories, local auth, and infrastructure hardening.

- [ ] Consolidate all admin features from /settings into /admin (single admin desk)
- [ ] Guided artifact creation wizard for agents, tools, skills, MCP servers (templates, validation, name conflict check)
- [ ] System capabilities explorer tool (`system.capabilities`) queryable from chat and agents
- [ ] API→MCP auto-generation skill: scan OpenAPI spec → generate + register MCP server
- [ ] External skill/tool repository management (add/remove repos, search, import, agentskills.io compliance)
- [ ] Local user & group management with dual auth (local username/password + Keycloak SSO)
- [ ] Replace ngrok with Cloudflare Tunnel for stable webhook exposure (Telegram, WhatsApp, Teams only)
- [ ] Externalize all LLM prompts from Python files to markdown files with `PromptLoader` utility
- [ ] Clean up orphaned `classify_intent()` in router.py (v1.1 tech debt)

### Out of Scope

- SaaS/cloud hosting — enterprise on-premise requirement, no external data processing
- Kubernetes — Docker Compose only for MVP; K8s is post-MVP
- HashiCorp Vault — AES-256 DB encryption sufficient at ~100 user scale
- Separate vector database (Qdrant, Weaviate, etc.) — pgvector in PostgreSQL is sufficient
- Mobile native apps — web-first with responsive design; mobile apps are post-MVP
- Real-time collaborative editing of workflows — single-user canvas editing for MVP
- OAuth social login (Google/GitHub) — Keycloak SSO is sufficient
- WhatsApp Business live testing — code complete; deferred until Meta credentials available
- MS Teams live testing — code complete; deferred until Azure Bot Service registration

## Context

**Current state (v1.1 shipped 2026-03-02):**
- Full enterprise agentic platform live on Docker Compose
- 586 backend tests passing (pytest), 1 skipped (pgvector isolation — SQLite limitation); TypeScript strict 0 errors
- Alembic migrations 001–017 applied; pgvector `vector(1024)`, RLS on 6 tables
- Grafana + Loki + Alloy observability stack live; Telegram spend alerting verified
- Telegram channel live (end-to-end); WhatsApp + Teams sidecars code-complete, credentials pending
- Admin dashboard at `/admin` with artifact management, permission matrix, skill import
- Docker sandbox executor live; git history credential scan clean (0 verified secrets)

**What shipped in v1.1:** Visual workflow canvas (React Flow → LangGraph); HITL approval gates; cron/webhook triggers; pre-built workflow templates; multi-channel presence (Telegram live, WhatsApp/Teams code-complete); ChannelAdapter protocol with runtime enforcement and LangGraph checkpointer continuity; database-backed extensibility registries for agents/tools/skills/MCP; admin dashboard; skill import pipeline with AST safety; Docker sandbox execution; PostgreSQL RLS; Grafana observability with LiteLLM cost tracking and Telegram alerting.

**What's next (v1.2):** TBD — run `/gsd:new-milestone` to define requirements and phases. Likely candidates: real OAuth email/calendar integration, WhatsApp/Teams live credentials, mobile PWA improvements, workflow sharing/templates marketplace.

**Known tech debt from v1.1 audit:**
- `MemoryFact` isolation pen test permanently skipped in SQLite (must run against live PostgreSQL)
- WhatsApp (CHAN-03) + Teams (CHAN-04): code complete, live credentials not yet available
- `classify_intent()` orphaned in `router.py` — delete or wire to `_pre_route` in v1.2

**Inspiration:** OpenClaw architecture — local-first, multi-agent, sandboxed execution. Adapted for enterprise multi-tenancy with per-user isolation, RBAC, and audit compliance.

**Existing infrastructure:**
- Keycloak instance running — `blitz-internal` realm, `blitz-portal` and `blitz-backend` clients configured
- Ollama running on host machine (not Dockerized) — LiteLLM routes via `host.docker.internal:11434`
- PostgreSQL 16 with pgvector extension, RLS enabled on 6 user-scoped tables
- Grafana + Loki + Alloy + Prometheus + cAdvisor observability stack in Docker Compose

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
| LangGraph + PydanticAI for orchestration | Canvas workflows compile directly to StateGraphs; Pydantic enforces tool I/O | ✓ Good — LangGraph 1.0.1 stable; graph topology scales to sub-agents and canvas workflows cleanly |
| pgvector in PostgreSQL (no separate vector DB) | `WHERE user_id = $1` enforces memory isolation in same query; simpler ops at 100-user scale | ✓ Good — HNSW indexes on memory_facts + memory_episodes; RLS added as defense-in-depth in v1.1 |
| bge-m3 as sole embedding model | 1024-dim, multilingual (Vietnamese), self-hosted for data privacy | ✓ Good — transformers<5.0 pin required (4.57.6); FlagEmbedding 1.3.x stable |
| LiteLLM Proxy for all LLM calls | Provider agnosticism + fallback routing; single config point | ✓ Good — all 4 aliases routing correctly; cost tracking dashboard live in v1.1 |
| React Flow v12 for canvas | definition_json is React Flow-native; no translation layer needed | ✓ Good — canvas compiler working; `schema_version` on all definition_json; langgraph upgraded to 1.0.1 for checkpoint-postgres 3.0.4 |
| HTTP+SSE for all MCP servers | Standard MCP transport; each server is a Docker service with `/sse` endpoint | ✓ Good — MCPClient + MCPToolRegistry live; hot-registration confirmed; DB-backed registry in v1.1 |
| CopilotKit (AG-UI/A2UI) for frontend | Real-time agent streaming + generative UI components out of the box | ✓ Good — CopilotKit 0.1.78 + venv patch maintained; A2UI cards working |
| Database-backed artifact registries | Extensibility: agents/tools/skills/MCP are data, not just code — enables runtime management | ✓ Good — 6 registry tables; admin dashboard at /admin; skill import pipeline with AST safety; no restart required |
| All 3 channels in MVP (Telegram + WhatsApp + Teams) | Company uses all three; ChannelAdapter pattern makes each one incremental | ⚠ Partial — Telegram live; WhatsApp/Teams code-complete, awaiting live credentials; ChannelAdapter protocol enforced at runtime |
| Existing Keycloak instance | Reduces setup work; add realm/client rather than deploy from scratch | ✓ Good — blitz-internal realm + blitz-portal/blitz-backend clients running; self-signed cert required (KEYCLOAK_CA_CERT) |
| _classify_by_keywords for intent routing_ | LLM-based classify_intent() was over-engineered for 3 intents; keyword matching is faster and free | ⚠ Revisit — classify_intent() still orphaned in router.py; /command dispatch now via skill_executor node; clean up in v1.2 |
| Docker sandbox for untrusted code | Security requirement: skill execution must be isolated from host and other users | ✓ Good — CPU/RAM/network/PID limits; non-root; cap_drop=ALL; no resource leaks; RLS as defense-in-depth |
| Grafana + Loki + Alloy for observability | Prometheus-compatible; structured JSON logs from structlog pipe directly to Loki | ✓ Good — full stack live; Telegram spend alerting verified end-to-end; datasource UIDs stable |

## Current Milestone: v1.2 Developer Experience

**Goal:** Make AgentOS easier to extend, explore, and operate — unified admin, guided artifact creation, ecosystem integrations, local auth, and infrastructure hardening.

**Target features:**
- Unified admin desk at /admin (migrate /settings admin features)
- Guided artifact creation wizard (agents, tools, skills, MCP)
- System capabilities explorer (`system.capabilities` tool)
- API→MCP auto-generation skill
- External skill/tool repository management + agentskills.io compliance
- Local user & group management with dual auth (local + Keycloak)
- Cloudflare Tunnel replacing ngrok for webhook exposure
- Prompt externalization to markdown files

---
*Last updated: 2026-03-02 after v1.2 milestone start*
