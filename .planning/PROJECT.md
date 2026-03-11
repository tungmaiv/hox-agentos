# Blitz AgentOS

## What This Is

An enterprise-grade, on-premise Agentic Operating System for Blitz employees (~100 users). It acts as a personal chief of staff — automating daily routines (email digests, calendar summaries, project status), orchestrating multi-step workflows via a visual low-code canvas, and connecting to internal systems via MCP. Employees interact through web chat, Telegram, WhatsApp, and MS Teams. Admins and developers can extend the platform at runtime through a unified admin desk with AI-assisted artifact creation wizards, OpenAPI-to-MCP auto-generation, and external skill repository imports. The platform supports dual authentication (Keycloak SSO + local credentials), exposes its capabilities via a queryable `system.capabilities` tool, and exports skills in agentskills.io-compliant format. Untrusted code executes safely in Docker sandboxes, all operations are observable via Grafana, and data never leaves the company.

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

### Validated (v1.2)

- ✓ Consolidated all admin features from /settings into unified /admin desk — v1.2
- ✓ Guided artifact creation wizard with AI-assisted form fill, templates, name check, clone — v1.2
- ✓ `system.capabilities` tool with CapabilitiesCard A2UI for platform introspection — v1.2
- ✓ OpenAPI-to-MCP auto-generation: parse spec → select endpoints → register as tools — v1.2
- ✓ External skill/tool repository management with browse, import (security scan), agentskills.io export — v1.2
- ✓ Local user & group management with dual-issuer JWT dispatch (local bcrypt + Keycloak SSO) — v1.2
- ✓ Cloudflare Tunnel for stable webhook exposure (replaces ngrok) — v1.2
- ✓ All LLM prompts externalized to `backend/prompts/*.md` with `PromptLoader` utility — v1.2
- ✓ `classify_intent()` dead code removed, `router.py` deleted — v1.2

### Validated (v1.3)

- ✓ Next.js middleware route protection with jose Edge Runtime JWT; CVE-2025-29927 mitigated — v1.3
- ✓ Silent session refresh (5-min buffer), Keycloak end-session logout, multi-tab sync — v1.3
- ✓ Persistent navigation rail (56px, role-gated admin tab, all authenticated pages) — v1.3
- ✓ User profile page: account info, password change, custom instructions, LLM preferences — v1.3
- ✓ LLM preferences (thinking mode, response style) injected into agent system prompt — v1.3
- ✓ Embedding sidecar service (bge-m3 Docker Compose service, HTTP-first, warm, dimension-validated) — v1.3
- ✓ 7 critical-path duration_ms instrumentation + single DB session per request + TTL caches — v1.3
- ✓ Keycloak as optional runtime config (admin Identity tab, JWKS hot-reload, local-auth-first boot) — v1.3
- ✓ agentskills.io standards compliance: 7 metadata columns, kebab-case validation, SKILL.md/ZIP import/export — v1.3
- ✓ Skill catalog with tsvector FTS (Vietnamese-compatible), category/author/status filters, usage tracking — v1.3
- ✓ External skill registry browse with paginated index and one-click import — v1.3
- ✓ SecurityScanner: dependency_risk + data_flow_risk factors + hard veto for undeclared imports — v1.3
- ✓ allowed-tools enforcement pre-gate in SkillExecutor + audit logging — v1.3
- ✓ SHA-256 skill update checker via Celery daily task — v1.3
- ✓ Promoted skills curated section + user ZIP export + user-to-user sharing — v1.3
- ✓ Builder generates procedure_json / instruction_markdown / handler_code stubs via LLM — v1.3
- ✓ pgvector similarity search over external skill repo index (HNSW cosine) + Fork capability — v1.3
- ✓ SecurityScanner gate on every builder save; SecurityReportCard A2UI + admin approval flow — v1.3

### Active

- [ ] Real OAuth email/calendar integration (replace mock sub-agents with live Google/Microsoft OAuth)
- [ ] WhatsApp Business live end-to-end (pending Meta Business API verification)
- [ ] MS Teams live end-to-end (pending Azure Bot Service registration)
- [ ] Builder fill_form metadata: populate `allowed_tools`/`category`/`tags` in artifact draft (v1.3 tech debt)

### Out of Scope

- SaaS/cloud hosting — enterprise on-premise requirement, no external data processing
- Kubernetes — Docker Compose only for MVP; K8s is post-MVP
- HashiCorp Vault — AES-256 DB encryption sufficient at ~100 user scale
- Separate vector database (Qdrant, Weaviate, etc.) — pgvector in PostgreSQL is sufficient
- Mobile native apps — web-first with responsive design; mobile apps are post-MVP
- Real-time collaborative editing of workflows — single-user canvas editing for MVP
- OAuth social login (Google/GitHub) — Keycloak SSO + local auth is sufficient
- Skill auto-publish to external agentskills.io registry — export is sufficient for MVP
- Skill/tool repository auto-sync via Celery — manual sync is sufficient for MVP

## Context

**Current state (v1.3 shipped 2026-03-11):**
- Production-hardened agentic OS with secure sessions, standards-compliant skill ecosystem live on Docker Compose
- 860 backend tests passing (pytest), 1 skipped; TypeScript strict 0 errors
- Alembic migrations 001–027 applied; pgvector `vector(1024)` for memory + skill_repo_index (HNSW cosine)
- 80,620 LOC Python · 18,959 LOC TypeScript (99,579 total)
- Embedding runs in dedicated bge-m3 sidecar service (HTTP-first, warm, no cold-start delay)
- Keycloak is optional: platform boots with local-auth-only; admin can enable SSO at runtime
- Full skill ecosystem: catalog (FTS), security hardening, sharing/marketplace, enhanced builder with security gate
- agentskills.io-compliant skill format: 7 metadata fields, SKILL.md/ZIP import+export
- All authenticated pages behind Next.js middleware (jose Edge Runtime); session refresh, logout, multi-tab sync working

**What shipped in v1.3:** Session hardening (middleware, refresh, logout); navigation rail + profile page + LLM preferences; embedding sidecar; 7-path perf instrumentation; Keycloak runtime config; agentskills.io standards compliance; skill catalog with FTS + external registry browse; SecurityScanner enhanced with dependency+data_flow risk; allowed-tools enforcement; daily update checker; promoted skills + ZIP export + sharing; LLM-generated skill content in builder; pgvector similarity search + Fork; SecurityScanner gate on all builder saves.

**What's next:** Run `/gsd:new-milestone` to define v1.4. Priority candidates: real OAuth email/calendar integration, builder metadata fields fix, WhatsApp/Teams live credentials.

**Known tech debt (accumulated):**
- `MemoryFact` isolation pen test permanently skipped in SQLite (must run against live PostgreSQL)
- WhatsApp + Teams: code complete, live credentials not yet available
- Sub-agent prompt `.md` files pre-provisioned but not loaded (sub-agents are Phase 3 mocks)
- Keycloak custom flat mapper corrupts service account tokens — forces admin/admin-cli credentials
- Builder `fill_form` doesn't populate `allowed_tools`/`category`/`tags` — builder-created skills get null metadata

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
| _classify_by_keywords for intent routing_ | LLM-based classify_intent() was over-engineered for 3 intents; keyword matching is faster and free | ✓ Good — classify_intent() and router.py deleted in v1.2; keyword routing extended with `capabilities` intent |
| Dual-issuer JWT (local + Keycloak) | Employees need auth without Keycloak dependency; identical RBAC for both paths | ✓ Good — HS256 local tokens + RS256 Keycloak tokens dispatched by `iss` claim; same UserContext for both |
| PromptLoader for LLM prompts | Editable prompts without code changes; Jinja2-style substitution + in-memory caching | ✓ Good — 6 prompts externalized; template caching eliminates disk reads after first load |
| OpenAPI-to-MCP bridge (handler_type=openapi_proxy) | Any REST API can become an MCP tool without writing adapter code | ✓ Good — runtime HTTP proxy through security gates; admin wizard for endpoint selection |
| External skill repos with SecurityScanner | Ecosystem extensibility; quarantine imported skills until admin review | ✓ Good — AST safety check + dependency scan; cached index avoids remote HTTP on browse |
| agentskills.io-compliant export | Standard skill format for sharing across AgentOS instances | ✓ Good — SKILL.md + MANIFEST.json + assets/ zip format; 7 frontmatter fields; ZIP import with structure validation |
| Docker sandbox for untrusted code | Security requirement: skill execution must be isolated from host and other users | ✓ Good — CPU/RAM/network/PID limits; non-root; cap_drop=ALL; no resource leaks; RLS as defense-in-depth |
| Grafana + Loki + Alloy for observability | Prometheus-compatible; structured JSON logs from structlog pipe directly to Loki | ✓ Good — full stack live; Telegram spend alerting verified end-to-end; datasource UIDs stable |
| Embedding sidecar (v1.3) | Extract bge-m3 from uvicorn process to eliminate 10-15s cold-start; keep model warm | ✓ Good — infinity-emb Docker Compose service; HTTP-first with Celery fallback; dimension validation on startup |
| Keycloak as optional runtime config (v1.3) | Enterprises need auth flexibility without requiring restart; local-auth as fallback | ✓ Good — platform_config table + admin Identity tab; JWKS reloaded on save; local-auth-first boot confirmed |
| PostgreSQL tsvector FTS for skill catalog (v1.3) | No need for external search engine at 100-user scale; 'simple' language for Vietnamese | ✓ Good — GIN index on migration 023; plainto_tsquery('simple') in user_skills.py; category/author exact-match filters |
| SecurityScanner as central trust gate (v1.3) | All skill acquisition paths (import, builder, registry) go through one scanner | ✓ Good — same SecurityScanner used in ZIP import, one-click registry import, and builder-save; Phase 21 enhancements apply everywhere |

---
*Last updated: 2026-03-11 after v1.3 milestone*
