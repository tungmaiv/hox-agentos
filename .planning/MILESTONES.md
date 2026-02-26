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

