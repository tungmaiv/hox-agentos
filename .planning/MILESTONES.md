# Milestones

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

