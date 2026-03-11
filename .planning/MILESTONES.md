# Milestones

## v1.3 Production Readiness & Skill Platform (Shipped: 2026-03-11)

**Phases completed:** 9 phases, 34 plans, ~49 tasks
**Timeline:** 2026-03-05 → 2026-03-10 (6 days)
**Test suite:** 860 passed, 1 skipped
**Commits:** 67 v1.3-specific
**Files changed:** 296 (+40,942 / -1,669 lines)
**Codebase:** 80,620 LOC Python · 18,959 LOC TypeScript

**Delivered:** Production-hardened, standards-compliant agentic OS with secure session management, navigation rail, optional Keycloak runtime config, embedding sidecar, and a full-stack agentskills.io-compliant skill ecosystem (catalog, security, marketplace, enhanced builder).

**Key accomplishments:**
1. **Production session hardening** — Next.js middleware with jose Edge Runtime JWT, HttpOnly cookie stack, silent 5-min-buffer refresh, Keycloak end-session logout, multi-tab sync, CVE-2025-29927 mitigated
2. **Navigation rail + user profile** — Persistent 56px nav rail on all authenticated pages; profile page with account info, password change, custom instructions, LLM thinking mode / response style preferences injected into agent system prompt
3. **Embedding sidecar service** — bge-m3 extracted from uvicorn to dedicated Docker Compose service (infinity-emb); 10–15s cold-start eliminated; HTTP-first path with Celery fallback; dimension validation on startup
4. **Keycloak as optional runtime config** — Platform boots with local-auth-only; admin Identity tab stores encrypted Keycloak config in `platform_config` table; JWKS reloaded without restart; `GET /api/auth/config` drives SSO button toggle
5. **agentskills.io standards compliance** — 7 metadata columns (migration 022), kebab-case name validation, SKILL.md frontmatter import/export, ZIP bundle structure with MANIFEST.json
6. **Skill catalog & discovery** — PostgreSQL tsvector FTS with Vietnamese-compatible `simple` language config, GIN index, category/author/status filters, usage_count tracking, paginated external registry browse with one-click import
7. **Skill security hardening** — SecurityScanner enhanced with dependency_risk (20%) + data_flow_risk factors; `allowed-tools` enforcement pre-gate in SkillExecutor with audit logging; SHA-256 daily update checker via Celery
8. **Skill sharing & marketplace** — Promoted skills curated section; agentskills.io ZIP export for users; user-to-user sharing via `artifact_permissions`; admin promote/unpromote toggle
9. **Enhanced artifact builder** — LLM-generated `procedure_json`/`instruction_markdown`/handler_code stubs; pgvector similarity search over external repo index; Fork from external skill; SecurityScanner gate on every builder save with SecurityReportCard + admin approval flow

**Archive:** `.planning/milestones/v1.3-ROADMAP.md` · `.planning/milestones/v1.3-REQUIREMENTS.md` · `.planning/milestones/v1.3-MILESTONE-AUDIT.md`

**Known tech debt (see audit):** Builder `fill_form` doesn't populate `allowed_tools`/`category`/`tags` (builder-created skills get null metadata); Phase 19 VERIFICATION.md missing (UAT evidence present)

---

## v1.2 Developer Experience (Shipped: 2026-03-04)

**Phases completed:** 4 phases (11, 12, 13, 14) — 11 plans
**Timeline:** 2026-03-02 → 2026-03-04 (3 days)
**Test suite:** 719 passed, 1 skipped
**Commits:** ~63 v1.2-specific
**Codebase:** 83,431 LOC (Python + TypeScript)

**Delivered:** Developer experience and extensibility upgrade — unified admin desk with AI-assisted artifact creation, local user management with dual auth, platform capabilities introspection, OpenAPI-to-MCP auto-generation, and external skill repository ecosystem with agentskills.io compliance.

**Key accomplishments:**
1. Externalized all LLM prompts to `backend/prompts/*.md` with `PromptLoader` — Jinja2-style variable substitution, in-memory caching, editable without code changes
2. Unified admin desk at `/admin` with guided artifact creation wizard — AI-assisted form fill via `fill_form` co-agent tool, starter templates, live name availability check, artifact cloning
3. Local user/group management with dual-issuer JWT dispatch — local bcrypt auth + Keycloak SSO, identical RBAC/ACL behavior, NextAuth Credentials provider, admin Users tab with CRUD
4. `system.capabilities` tool with CapabilitiesCard A2UI — permission-filtered registry introspection, keyword routing, collapsed sections with count badges
5. OpenAPI-to-MCP bridge — 3-step admin wizard to parse any OpenAPI spec, select endpoints, register as `openapi_proxy` tools with runtime HTTP dispatch through full security gates
6. External skill repository ecosystem — admin repository management, browse/search with cached index, import with SecurityScanner quarantine, agentskills.io-compliant zip export

**Archive:** `.planning/milestones/v1.2-ROADMAP.md` · `.planning/milestones/v1.2-REQUIREMENTS.md` · `.planning/milestones/v1.2-MILESTONE-AUDIT.md`

**Known tech debt (see audit):** 6 informational items — orphaned sub-agent prompt files (forward-compat), dead code markers (update_agent_last_seen, serverFetch), stale docstring reference, admin layout zero-roles fallback (tightened in quick-3), test RuntimeWarning (fixed in quick-3)

---

## v1.0 MVP (Shipped: 2026-02-26)

**Phases completed:** 5 phases (1, 2, 2.1, 3, 3.1), 17 plans
**Timeline:** 2026-02-24 → 2026-02-26 (2 days)
**Codebase:** 261 files, 57,828 lines added
**Test suite:** 180 tests, 0 failures

**Delivered:** Enterprise-secure, on-premise agentic assistant with streaming AG-UI chat, 3-tier memory, email/calendar/project sub-agents, A2UI generative UI, and MCP tool framework — all behind JWT/RBAC/ACL 3-gate security.

**Key accomplishments:**
1. Docker Compose 6-service stack (PostgreSQL+pgvector, Redis, Keycloak, LiteLLM, backend, frontend) with Keycloak SSO and RS256 JWT validation — 3-gate security on every request
2. LangGraph master agent with AG-UI streaming via CopilotKit, AES-256 credential vault, per-user conversation memory with contextvar isolation
3. 3-tier memory system: short-term (SQL turns), medium-term (Celery+bge-m3 episode summaries), long-term (pgvector 1024-dim facts with cosine search)
4. Email/Calendar/Project sub-agents with keyword routing, Pydantic v2 output schemas, and A2UI generative UI cards (CalendarCard, EmailSummaryCard, ProjectStatusWidget)
5. MCP HTTP+SSE client framework with 3-gate security and hot-registration (MCPToolRegistry.refresh() on server creation) — CRM mock server live
6. Phase 3.1 gap closure: episode summaries injected into agent context, 180 tests green

**Archive:** `.planning/milestones/v1.0-ROADMAP.md` · `.planning/milestones/v1.0-REQUIREMENTS.md` · `.planning/milestones/v1.0-MILESTONE-AUDIT.md`

**Known tech debt (see audit):** MEMO-02 role bug fixed (d725066); credential management UI absent; stale system prompt; classify_intent() orphaned

---


## v1.1 Enterprise Platform (Shipped: 2026-03-02)

**Phases completed:** 9 phases (4, 4.1, 5, 5.1, 6, 7, 8, 9, 10) — 33 plans
**Timeline:** 2026-02-27 → 2026-03-02 (4 days)
**Test suite:** 586 passed, 1 skipped (pgvector isolation — SQLite limitation)
**Commits:** 154

**Delivered:** Visual workflow canvas + multi-channel presence + extensibility registries + Docker sandbox + full observability — the platform transitions from AI assistant to autonomous enterprise agentic OS.

**Key accomplishments:**
1. React Flow drag-and-drop canvas compiles to LangGraph StateGraphs; HITL approval gates; cron/webhook triggers; Morning Digest + Alert pre-built workflow templates
2. Multi-channel presence: Telegram live (end-to-end verified); WhatsApp + Teams sidecars code-complete; ChannelAdapter protocol with `isinstance()` enforcement and shared LangGraph checkpointer for conversation continuity
3. Database-backed extensibility registries for agents, tools, skills, and MCP servers; admin dashboard at `/admin` with permission matrix, multi-version support, and skill import pipeline (AST safety evaluation + security scan)
4. Docker sandbox executor for untrusted code: CPU/RAM/network/PID limits, non-root execution, capability stripping; PostgreSQL RLS on 6 tables; git history credential scan (clean — 0 verified secrets)
5. Grafana + Loki + Alloy observability stack: Prometheus instrumentation, LiteLLM cost tracking dashboard, Telegram spend-alert live-tested end-to-end
6. Tech debt closure: tool cache invalidation on status change, `blitz_llm_calls_total` wired in `get_llm()`, delivery_router unification, UAT test 12 (Admin Create Skill) passing

**Archive:** `.planning/milestones/v1.1-ROADMAP.md` · `.planning/milestones/v1.1-MILESTONE-AUDIT.md`

**Known gaps (see audit):** CHAN-03 (WhatsApp) + CHAN-04 (Teams) — code complete, live credentials unavailable

---

