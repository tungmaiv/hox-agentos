---
phase: 03-sub-agents-memory-and-integrations
verified: 2026-02-26T14:30:00Z
status: gaps_found
score: 9/10 truths verified
gaps:
  - truth: "One pre-existing test fails: test_create_master_graph_has_routing_conditional checks that master_agent node has conditional branches, but Phase 3 moved routing to load_memory (_pre_route). The routing IS correct and all Phase 3 agent tests pass (42/42), but the suite reports 1 failure."
    status: partial
    reason: "Stale Phase 2 test assertion: checks `graph_builder.branches['master_agent']` but Phase 3 moved the conditional edge to 'load_memory' via _pre_route. The actual routing works correctly — email/calendar/project messages reach sub-agents — but the test was not updated to match the new graph topology."
    artifacts:
      - path: "backend/tests/agents/test_master_agent.py"
        issue: "test_create_master_graph_has_routing_conditional asserts 'master_agent' in graph_builder.branches, but routing is on 'load_memory' in the Phase 3 graph"
    missing:
      - "Update test_create_master_graph_has_routing_conditional to assert 'load_memory' (not 'master_agent') has conditional branches, matching the _pre_route architecture"

human_verification:
  - test: "Visual rendering of A2UI cards in chat"
    expected: "EmailSummaryCard, CalendarCard, ProjectStatusWidget render for appropriate intent messages"
    why_human: "Visual component rendering cannot be verified without a running browser"
  - test: "Cross-session memory recall"
    expected: "After sending 'My name is Tung', a new session asking 'What do you know about me?' returns 'Tung' in context"
    why_human: "Requires full stack with Celery worker + bge-m3 model (570MB) running"
---

# Phase 3: Sub-Agents, Memory, and Integrations — Verification Report

**Phase Goal:** Sub-agents, Memory, and Integrations — make the agent genuinely useful for daily work by delivering: Celery+bge-m3 embedding pipeline, medium/long-term memory with pgvector, HTTP+SSE MCP client with 3-gate security, email/calendar/project sub-agents with intent routing, and A2UI rich components (CalendarCard, EmailSummaryCard, ProjectStatusWidget).
**Verified:** 2026-02-26T14:30:00Z
**Status:** gaps_found (1 stale test needs update; all Phase 3 functionality verified)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Celery+bge-m3 embedding pipeline works: BGE_M3Provider.embed() returns 1024-dim vectors | VERIFIED | `BGE_M3Provider.dimension == 1024`; import succeeds; embed_and_store Celery task dispatches to Redis |
| 2 | medium/long-term memory stored in pgvector: memory_facts + memory_episodes tables with HNSW indexes | VERIFIED | Migration 008 applied; MemoryFact + MemoryEpisode ORM models with `Vector(1024)` columns, superseded_at soft-delete, HNSW indexes |
| 3 | search_facts() performs pgvector cosine search with user isolation | VERIFIED | `long_term.py` uses `cosine_distance()`, `WHERE user_id = $1`, `embedding IS NOT NULL`, `superseded_at IS NULL` |
| 4 | HTTP+SSE MCP client calls tools/list and tools/call JSON-RPC | VERIFIED | `mcp/client.py` MCPClient.list_tools() and call_tool() use POST /sse with JSON-RPC; tested with httpx mocks |
| 5 | 3-gate security enforced for MCP tool calls | VERIFIED | `mcp/registry.py` call_mcp_tool() enforces Gate 2 (RBAC has_permission) + Gate 3 (check_tool_acl) with audit logging |
| 6 | Email/calendar/project sub-agents route correctly and return structured JSON | VERIFIED | `_pre_route + _classify_by_keywords` routes to email/calendar/project_agent nodes; each returns Pydantic v2 JSON-encoded AIMessage; 42 Phase 3 agent tests pass |
| 7 | A2UI components (CalendarCard, EmailSummaryCard, ProjectStatusWidget) wire to A2UIMessageRenderer | VERIFIED | `A2UIMessageRenderer.tsx` routes on `agent` field via Zod safeParse; `chat-panel.tsx` uses `AssistantMessage={CustomAssistantMessage}` with A2UIMessageRenderer; user-verified in 03-05 checkpoint |
| 8 | useMcpTool is the ONLY way A2UI components call tools | VERIFIED | ProjectStatusWidget imports `useMcpTool` for crm.update_task_status; EmailSummaryCard imports `useMcpTool` for email.fetch_unread; no direct fetch() in card components |
| 9 | Settings → Memory and Chat Preferences pages exist with full backend API | VERIFIED | `memory_settings.py` routes at `/api/user/memory/facts`, `/api/user/memory/episodes`, `/api/user/preferences`; frontend pages with Zod validation exist |
| 10 | One test failure: test_create_master_graph_has_routing_conditional | FAILED | Stale Phase 2 test checks `master_agent` for conditional branches; Phase 3 moved routing to `load_memory` via `_pre_route`; assertion is wrong for the new (correct) topology |

**Score:** 9/10 truths verified (1 stale test failure — routing works, test assertion is outdated)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/memory/embeddings.py` | EmbeddingProvider Protocol + BGE_M3Provider with dimension=1024 | VERIFIED | `class BGE_M3Provider` with `dimension: int = 1024`, lazy load, run_in_executor |
| `backend/scheduler/celery_app.py` | Celery app with Redis broker, embedding + default queues | VERIFIED | Two queues: embedding + default; task routing configured |
| `backend/scheduler/tasks/embedding.py` | embed_and_store and summarize_episode Celery tasks | VERIFIED | Both tasks implemented with asyncio.run() pattern, retry support, structlog |
| `backend/core/models/memory_long_term.py` | MemoryEpisode + MemoryFact ORM models with vector(1024) | VERIFIED | `Vector(1024)` via pgvector.sqlalchemy; superseded_at column present |
| `backend/alembic/versions/008_phase3_memory_tables.py` | Migration: memory tables, HNSW indexes | VERIFIED | Applied cleanly; HNSW partial indexes (WHERE embedding IS NOT NULL) |
| `backend/memory/medium_term.py` | save_episode() and load_recent_episodes() | VERIFIED | Exports save_episode, load_recent_episodes; WHERE user_id = $1 |
| `backend/memory/long_term.py` | save_fact(), search_facts(), mark_fact_superseded() | VERIFIED | Cosine distance search; superseded_at soft-delete; user isolation |
| `backend/mcp/client.py` | MCPClient: list_tools() and call_tool() via HTTP+SSE | VERIFIED | JSON-RPC POST /sse; handles both success and error responses |
| `backend/mcp/registry.py` | MCPToolRegistry + call_mcp_tool() with 3-gate security | VERIFIED | startup refresh; Gate 2 + Gate 3 + audit logging |
| `backend/api/routes/mcp_servers.py` | CRUD routes for mcp_servers | VERIFIED | GET/POST/DELETE /api/admin/mcp-servers; admin-only |
| `infra/mcp-crm/main.py` | Mock CRM MCP server with 3 tools | VERIFIED | get_project_status, list_projects, update_task_status tools |
| `infra/mcp-crm/Dockerfile` | Docker image for mcp-crm service | VERIFIED | EXISTS |
| `backend/core/schemas/agent_outputs.py` | Pydantic v2 models for sub-agent outputs | VERIFIED | EmailSummaryOutput, CalendarOutput, ProjectStatusResult |
| `backend/agents/subagents/router.py` | classify_intent() using blitz/fast LLM | VERIFIED (orphaned) | EXISTS and tested; NOT used by master_agent (see Key Links) |
| `backend/agents/subagents/email_agent.py` | email_agent_node() returning EmailSummaryOutput JSON | VERIFIED | Mock data; model_dump_json() as AIMessage |
| `backend/agents/subagents/calendar_agent.py` | calendar_agent_node() returning CalendarOutput JSON | VERIFIED | Mock data with conflict detection |
| `backend/agents/subagents/project_agent.py` | project_agent_node() calling call_mcp_tool() | VERIFIED | Top-level import; calls crm.get_project_status |
| `backend/agents/delivery_router.py` | DeliveryRouterNode + DeliveryTarget enum | VERIFIED | WEB_CHAT active; TELEGRAM/EMAIL_NOTIFY/TEAMS stub with warning logs |
| `frontend/src/lib/a2ui-types.ts` | TypeScript Zod schemas for A2UI types | VERIFIED | CalendarOutputSchema, EmailSummaryOutputSchema, ProjectStatusResultSchema |
| `frontend/src/components/a2ui/A2UIMessageRenderer.tsx` | JSON parse → card routing → ReactMarkdown fallback | VERIFIED | Zod safeParse; agent field routing; react-markdown v10 compatible |
| `frontend/src/components/a2ui/CalendarCard.tsx` | Calendar events UI with conflict badge | VERIFIED | EXISTS; renders events with Conflict badge |
| `frontend/src/components/a2ui/EmailSummaryCard.tsx` | Email list UI with unread count badge | VERIFIED | EXISTS; useMcpTool for refresh; stub Reply/Archive |
| `frontend/src/components/a2ui/ProjectStatusWidget.tsx` | Kanban with useMcpTool for task moves | VERIFIED | EXISTS; useMcpTool("crm.update_task_status") wired |
| `frontend/src/hooks/use-mcp-tool.ts` | useMcpTool hook: { call, isLoading, error } | VERIFIED | Generic <TParams, TResult>; POST /api/tools/call |
| `backend/api/routes/tools.py` | POST /api/tools/call with 3-gate security | VERIFIED | Gate 1 via get_current_user; Gates 2+3 inside call_mcp_tool() |
| `backend/api/routes/memory_settings.py` | Memory facts/episodes CRUD API + preferences | VERIFIED | GET/DELETE facts; GET episodes; GET/PUT preferences |
| `frontend/src/app/settings/memory/page.tsx` | Per-user memory facts + episodes viewer | VERIFIED | Client Component; Zod validation; delete capability |
| `frontend/src/app/settings/chat-preferences/page.tsx` | Per-user rendering mode selector | VERIFIED | 3 modes; persists to backend |
| `backend/core/models/system_config.py` | SystemConfig ORM model | VERIFIED | JSON().with_variant(JSONB(), 'postgresql') for cross-dialect compatibility |
| `backend/core/models/mcp_server.py` | McpServer ORM model | VERIFIED | AES-256 encrypted auth_token (LargeBinary) |
| `backend/api/routes/system_config.py` | GET/PUT /api/admin/config routes | VERIFIED | Admin-only; has_permission(user, 'tool:admin') Gate 2 |
| `backend/alembic/versions/007_phase3_settings.py` | Migration: system_config + mcp_servers tables | VERIFIED | 5 seed rows including agent flags + memory.episode_turn_threshold |
| `frontend/src/app/settings/agents/page.tsx` | Admin Settings → Agents page with toggles | VERIFIED | 3 agent toggles; Zod validation; PUT on toggle change |
| `frontend/src/app/settings/integrations/page.tsx` | Settings → Integrations live CRUD | VERIFIED | Replaced stub with live add/delete form |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `backend/agents/master_agent.py _load_memory_node` | `backend/memory/long_term.py search_facts()` | BGE_M3Provider.embed() → cosine search | WIRED | `search_facts` called at line 121; `BGE_M3Provider` imported at top level |
| `backend/agents/master_agent.py _save_memory_node` | `scheduler.tasks.embedding.embed_and_store` | embed_and_store.delay() fire-and-forget | WIRED | `embed_and_store.delay(str(msg.content), str(user_id), "fact")` at line 324 |
| `backend/agents/master_agent.py _save_memory_node` | `scheduler.tasks.embedding.summarize_episode` | summarize_episode.delay() at threshold | WIRED | `summarize_episode.delay(str(conversation_id), str(user_id))` at line 331 |
| `backend/agents/master_agent.py _pre_route` (NOT classify_intent) | email/calendar/project_agent nodes | keyword classification _classify_by_keywords | WIRED | `_pre_route` uses `_classify_by_keywords` (not LLM `classify_intent`) — see deviation note |
| `backend/agents/subagents/project_agent.py` | `backend/mcp/registry.py call_mcp_tool()` | crm.get_project_status via MCP | WIRED | Top-level import; `call_mcp_tool("crm.get_project_status", ...)` in project_agent_node |
| `backend/mcp/registry.py call_mcp_tool()` | `backend/security/rbac.py has_permission()` | Gate 2 RBAC | WIRED | `has_permission(user, permission)` checked for each required_permission |
| `backend/mcp/registry.py call_mcp_tool()` | `backend/security/acl.py check_tool_acl()` | Gate 3 ACL | WIRED | `await check_tool_acl(user["user_id"], tool_name, db_session)` |
| `backend/main.py startup` | `backend/mcp/registry.py MCPToolRegistry.refresh()` | FastAPI lifespan event | WIRED | `await MCPToolRegistry.refresh()` in lifespan context manager |
| `frontend/src/components/chat/chat-panel.tsx` | `frontend/src/components/a2ui/A2UIMessageRenderer.tsx` | AssistantMessage={CustomAssistantMessage} | WIRED | `A2UIMessageRenderer` imported from `@/components/a2ui`; wired as `CopilotChat` AssistantMessage prop |
| `frontend/src/components/a2ui/ProjectStatusWidget.tsx` | `frontend/src/hooks/use-mcp-tool.ts` | kanban task move calls useMcpTool | WIRED | `useMcpTool<...>("crm.update_task_status")` at line 51 |
| `frontend/src/hooks/use-mcp-tool.ts` | `frontend/src/app/api/tools/call/route.ts` | POST /api/tools/call proxy | WIRED | `fetch("/api/tools/call", ...)` in useMcpTool |
| `frontend/src/app/api/tools/call/route.ts` | `backend/api/routes/tools.py POST /api/tools/call` | Next.js proxy with NEXT_PUBLIC_API_URL | WIRED | `fetch(\`${API_URL}/api/tools/call\`, ...)` with server-side Bearer injection |
| `frontend/src/app/settings/agents/page.tsx` | `GET/PUT /api/admin/config` | fetch to Next.js proxy `/api/admin/config` | WIRED | `fetch("/api/admin/config", ...)` on mount; `fetch("/api/admin/config/${key}", ...)` on toggle |
| `backend/agents/subagents/router.py classify_intent` | (master_agent routing) | NOT WIRED — orphaned module | ORPHANED | classify_intent exists + tests pass, but master_agent uses _classify_by_keywords instead. See deviation note below. |

---

## Critical Deviation: Intent Routing Implementation

**Plan specified:** `classify_intent()` using `blitz/fast` LLM for intent classification in `_route_after_master`.

**Actual implementation:** `_classify_by_keywords()` (keyword regex matching, no LLM) called from `_pre_route` in `load_memory` → conditional edge, not from `master_agent`.

**Reason (documented in 03-04-SUMMARY.md):** Routing functions run outside LangGraph nodes. LLM calls made in routing functions get streamed by CopilotKit as chat messages (e.g. "general" appearing in the chat before the real response). Keyword matching is instant, prevents spurious streaming tokens, and is sufficient for Phase 3's explicit intent vocabulary.

**Impact on goal:** The intent routing WORKS correctly — email/calendar/project messages reach the correct sub-agents. The architectural choice is an improvement over the plan. `classify_intent` in `router.py` is a fully implemented, tested module but is currently orphaned (not called by master_agent).

**Stale test:** `test_create_master_graph_has_routing_conditional` (in `test_master_agent.py`) was written in Phase 2 expecting `master_agent` to have conditional branches. Phase 3 moved the conditional to `load_memory`. The test assertion is stale — the routing IS conditional and correct, but the test checks the wrong node.

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| INTG-01 | 03-00, 03-03 | Settings infrastructure + MCP HTTP+SSE | SATISFIED | system_config table, mcp_servers table, MCPClient list_tools/call_tool |
| INTG-02 | 03-00, 03-03 | MCP server registry + CRM mock | SATISFIED | mcp_servers table; infra/mcp-crm with 3 tools |
| INTG-03 | 03-03 | 3-gate security for MCP tools | SATISFIED | call_mcp_tool() enforces JWT+RBAC+ACL with audit logging |
| INTG-05 | 03-05 | Provider-agnostic abstraction via Pydantic schemas | SATISFIED | EmailSummaryOutput, CalendarOutput, ProjectStatusResult schemas are the abstraction layer |
| MEMO-02 | 03-01, 03-02 | Celery embedding pipeline | SATISFIED | embed_and_store + summarize_episode tasks; BGE_M3Provider 1024-dim |
| MEMO-03 | 03-01, 03-02, 03-05 | pgvector long-term memory + user viewer | SATISFIED | memory_facts + memory_episodes with HNSW; Settings → Memory page |
| MEMO-04 | 03-01, 03-02 | Medium-term episode summaries | SATISFIED | MemoryEpisode table; summarize_episode task; load_recent_episodes() |
| AGNT-03 | 03-04 | Email sub-agent | SATISFIED | email_agent_node() returns EmailSummaryOutput JSON |
| AGNT-04 | 03-04 | Calendar sub-agent | SATISFIED | calendar_agent_node() returns CalendarOutput JSON with conflict detection |
| AGNT-05 | 03-04 | Project sub-agent via MCP | SATISFIED | project_agent_node() calls call_mcp_tool(crm.get_project_status) |
| AGNT-06 | 03-04 | Channel routing via DeliveryRouterNode | SATISFIED | DeliveryTarget enum; WEB_CHAT active; TELEGRAM/EMAIL_NOTIFY/TEAMS stubs |
| AGNT-08 | 03-04, 03-05 | Structured A2UI output | SATISFIED | A2UIMessageRenderer routes agent JSON to card components; human-verified |

---

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `backend/tests/agents/test_master_agent.py:108` | Stale assertion: checks `master_agent` in branches, but routing moved to `load_memory` | Warning | 1 test failure in test suite; routing is correct |
| `backend/agents/subagents/router.py` | `classify_intent` function exists but is not called by master_agent (orphaned) | Info | Not a blocker; module is tested; may confuse future developers |
| `frontend/src/components/a2ui/EmailSummaryCard.tsx` | Calls `useMcpTool("email.fetch_unread")` which is not registered (no email OAuth in Phase 3) | Warning | Refresh button will return 404; not a blocker for Phase 3 (email agent uses mock data) |

---

## Human Verification Required

The 03-05-SUMMARY.md documents that a human checkpoint was performed and all 6 scenarios passed:

| Scenario | Result |
|----------|--------|
| "summarize my unread emails" → EmailSummaryCard renders | PASSED (human-verified 2026-02-26) |
| "what's on my calendar today?" → CalendarCard with conflict badge | PASSED (human-verified 2026-02-26) |
| "Project Alpha status" → ProjectStatusWidget with active badge + 65% progress | PASSED (human-verified 2026-02-26) |
| "write me a haiku about databases" → markdown fallback | PASSED (human-verified 2026-02-26) |
| Kanban "+ Move here" → POST /api/tools/call visible in Network tab | PASSED (human-verified 2026-02-26) |
| /settings/memory and /settings/chat-preferences render without errors | PASSED (human-verified 2026-02-26) |

Additional items needing future human verification:
1. **Cross-session memory recall** — requires full stack with Celery worker + bge-m3 (570MB) model running
2. **Agent toggle persistence** — toggle Email off → reload → confirm still off (requires running backend + admin session)

---

## Gaps Summary

**One gap blocking full test suite pass:** The test `test_create_master_graph_has_routing_conditional` in `backend/tests/agents/test_master_agent.py` asserts that `master_agent` node has conditional branches. In Phase 3, routing was moved to `load_memory` via `_pre_route` (keyword classification, not LLM). The master_agent node now uses a plain edge to `delivery_router`. The test assertion is stale and needs to be updated to match the actual (correct) graph topology.

**Fix required:** Change the assertion from `assert "master_agent" in graph_builder.branches` to `assert "load_memory" in graph_builder.branches` and verify that `_pre_route` handles email/calendar/project/master_agent routing.

**Orphaned module:** `backend/agents/subagents/router.py` contains a working `classify_intent` function (LLM-based) that is fully tested but not called by master_agent. It should either be wired in as a fallback for ambiguous keyword cases, or documented as intentionally unused with a comment explaining the keyword-first approach.

**Phase 3 goal achievement:** All major deliverables are present and functional — bge-m3 pipeline, pgvector memory, MCP with 3-gate security, sub-agent routing, A2UI components — the phase goal is substantively achieved.

---

_Verified: 2026-02-26T14:30:00Z_
_Verifier: Claude (gsd-verifier)_
