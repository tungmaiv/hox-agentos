---
phase: 03-sub-agents-memory-and-integrations
plan: "04"
subsystem: agents
tags: [langgraph, pydantic, mcp, intent-router, sub-agents, delivery-router]

# Dependency graph
requires:
  - phase: 03-02
    provides: BlitzState with delivery_targets field; master_agent.py _load_memory_node/_save_memory_node
  - phase: 03-03
    provides: call_mcp_tool() 3-gate security; crm.get_project_status MCP tool; mcp-crm Docker service

provides:
  - classify_intent() intent router using blitz/fast LLM (email/calendar/project/general)
  - email_agent_node() returning mock EmailSummaryOutput JSON as AIMessage
  - calendar_agent_node() returning mock CalendarOutput JSON with conflict detection
  - project_agent_node() calling call_mcp_tool(crm.get_project_status) → ProjectStatusResult JSON
  - DeliveryRouterNode + DeliveryTarget enum (WEB_CHAT active; TELEGRAM/TEAMS/EMAIL_NOTIFY stubs)
  - Master agent graph extended: email/calendar/project/delivery_router nodes wired
  - CRM tools pre-registered in tool_registry: get_project_status (crm:read), list_projects (crm:read), update_task_status (crm:write)
  - Pydantic v2 output schemas: EmailSummaryOutput, CalendarOutput, ProjectStatusResult

affects:
  - 03-05 (A2UI components consume EmailSummaryOutput, CalendarOutput, ProjectStatusResult JSON)
  - 04-canvas (graph topology extended; delivery_targets used by Channel adapters)
  - 05-channels (DeliveryRouterNode stub implementations for TELEGRAM/TEAMS/EMAIL_NOTIFY)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sub-agent nodes: async LangGraph nodes returning dict with messages list"
    - "Intent classification: blitz/fast LLM with _VALID_LABELS guard, never raises"
    - "Pydantic v2 output schemas as JSON-encoded AIMessage content"
    - "DeliveryRouterNode: pure side-effect node, returns empty dict"
    - "Top-level import pattern for mockable functions (call_mcp_tool)"

key-files:
  created:
    - backend/core/schemas/agent_outputs.py
    - backend/agents/subagents/__init__.py
    - backend/agents/subagents/router.py
    - backend/agents/subagents/email_agent.py
    - backend/agents/subagents/calendar_agent.py
    - backend/agents/subagents/project_agent.py
    - backend/agents/delivery_router.py
    - backend/tests/agents/test_router.py
    - backend/tests/agents/test_email_agent.py
    - backend/tests/agents/test_calendar_agent.py
    - backend/tests/agents/test_project_agent.py
    - backend/tests/agents/test_master_agent_routing.py
    - backend/tests/agents/test_delivery_router.py
  modified:
    - backend/agents/master_agent.py
    - backend/gateway/tool_registry.py

key-decisions:
  - "call_mcp_tool imported at top level in project_agent.py (not lazily) — lazy import not patchable in tests (per STATE.md decision [02-02])"
  - "Disabled agent routing: when system_config disables an agent, _route_after_master returns 'delivery_router' so master agent's existing response is delivered unchanged"
  - "CRM tools pre-registered statically in tool_registry.py — idempotent when MCPToolRegistry.refresh() runs at startup"
  - "DeliveryRouterNode returns empty dict (pure side-effect) — does not modify state; WEB_CHAT delivery handled by CopilotKit AG-UI"

patterns-established:
  - "Sub-agent pattern: async def node(state: BlitzState) -> dict with messages list containing JSON-encoded AIMessage"
  - "Intent router: classify with blitz/fast, guard with _VALID_LABELS set, always return general on failure"
  - "Test patching: patch at module attribute path (agents.subagents.X.func), not at source (mcp.registry.func)"

requirements-completed:
  - AGNT-03
  - AGNT-04
  - AGNT-05
  - AGNT-06
  - AGNT-08

# Metrics
duration: 6min
completed: 2026-02-26
---

# Phase 3 Plan 04: Sub-Agents + DeliveryRouter Summary

**LangGraph sub-agent routing with email/calendar/project nodes and DeliveryRouterNode; master_agent.py extended with blitz/fast intent classifier; Pydantic v2 output schemas for A2UI consumption**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-26T12:15:17Z
- **Completed:** 2026-02-26T12:21:37Z
- **Tasks:** 3
- **Files modified:** 15

## Accomplishments

- Intent classifier (classify_intent using blitz/fast LLM) with safe fallback to "general" on bad output or LLM errors
- Three sub-agent nodes (email, calendar, project) producing structured JSON output matching A2UI Pydantic schemas
- Master agent graph extended from 3 nodes to 8 nodes with full conditional routing topology
- DeliveryRouterNode with 4-value DeliveryTarget enum: WEB_CHAT active, TELEGRAM/TEAMS/EMAIL_NOTIFY stubs for Phase 5
- CRM tools statically pre-registered in tool_registry with correct permissions
- 38 total tests passing (25 new + 13 prior)

## Task Commits

1. **Task 1: Output schemas + intent router + DeliveryRouterNode** - `843756b` (feat)
2. **Task 2: Sub-agent nodes + master graph routing + CRM tool registry** - `8f67676` (feat)
3. **Task 3: TDD tests for router, sub-agents, routing, delivery router** - `c649bbb` (test)

## Graph Topology After 03-04

```
START → load_memory → master_agent → [_route_after_master: classify_intent()]
                                          ├── "email_agent"    → email_agent_node    → delivery_router → save_memory → END
                                          ├── "calendar_agent" → calendar_agent_node → delivery_router → save_memory → END
                                          ├── "project_agent"  → project_agent_node  → delivery_router → save_memory → END
                                          └── "delivery_router" → delivery_router → save_memory → END (general intent)
```

## DeliveryTarget Enum Behavior

| Target | Phase 3 behavior |
|--------|-----------------|
| WEB_CHAT | Active — CopilotKit/AG-UI handles delivery automatically; `deliver()` logs debug only |
| EMAIL_NOTIFY | Stub — logs warning, no-op; Phase 5 ChannelAdapter plugs in |
| TELEGRAM | Stub — logs warning, no-op; Phase 5 ChannelAdapter plugs in |
| TEAMS | Stub — logs warning, no-op; Phase 5 ChannelAdapter plugs in |

## Disabled Agent Handling

When a sub-agent is disabled in `system_config` (e.g. `agent.email.enabled = false`), `_route_after_master` returns `"delivery_router"` instead of the agent node name. The master agent's existing response (already in state messages) is routed through delivery and saved to memory. No additional "disabled" message is injected — the master agent's response from the previous node is the user's response. This approach follows KISS.

## Files Created/Modified

- `backend/core/schemas/agent_outputs.py` — EmailSummaryItem, EmailSummaryOutput, CalendarEvent, CalendarOutput, ProjectStatusResult (Pydantic v2)
- `backend/agents/subagents/__init__.py` — package init
- `backend/agents/subagents/router.py` — classify_intent() using blitz/fast LLM
- `backend/agents/subagents/email_agent.py` — email_agent_node() with mock data (5 emails, 3 unread)
- `backend/agents/subagents/calendar_agent.py` — calendar_agent_node() with 4 mock events, 1 conflict
- `backend/agents/subagents/project_agent.py` — project_agent_node() calling call_mcp_tool(crm.get_project_status)
- `backend/agents/delivery_router.py` — DeliveryTarget enum + delivery_router_node()
- `backend/agents/master_agent.py` — _route_after_master() async with classify_intent; create_master_graph() with 5 new nodes + edges
- `backend/gateway/tool_registry.py` — crm.get_project_status, crm.list_projects, crm.update_task_status registered

## Decisions Made

1. **Top-level import for call_mcp_tool** — moved from lazy import inside function to top-level in project_agent.py. Lazy imports cannot be patched at `agents.subagents.project_agent.call_mcp_tool` (per STATE.md decision from 02-02: never use importlib.reload() inside patch). Top-level import is patchable at the correct module attribute path.

2. **Disabled agent routes to delivery_router not save_memory** — when system_config disables an agent, route to `delivery_router` (not `save_memory` directly). This ensures the master agent's existing response goes through the delivery routing and save_memory path consistently regardless of whether a sub-agent ran.

3. **CRM tools statically pre-registered** — registered in tool_registry.py at module load time. MCPToolRegistry.refresh() at startup will overwrite idempotently. Ensures tests and sub-agents can look up tools before MCP server connects.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] call_mcp_tool moved to top-level import**
- **Found during:** Task 3 (TDD tests for project_agent)
- **Issue:** Plan specified `from mcp.registry import call_mcp_tool` as lazy import inside function. This cannot be patched at `agents.subagents.project_agent.call_mcp_tool` — AttributeError on patch attempt.
- **Fix:** Moved `from mcp.registry import call_mcp_tool` to top-level imports in project_agent.py. Verified no circular import (mcp.registry does not import agents.subagents).
- **Files modified:** `backend/agents/subagents/project_agent.py`
- **Verification:** All 4 project_agent tests pass; `from agents.subagents.project_agent import project_agent_node` imports cleanly
- **Committed in:** `c649bbb` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug fix for lazy import preventing test patching)
**Impact on plan:** Required for correct test patching. No scope creep. project_agent.py is cleaner with top-level import.

## Issues Encountered

None beyond the auto-fixed deviation above.

## Next Phase Readiness

- Sub-agent JSON output (EmailSummaryOutput, CalendarOutput, ProjectStatusResult) ready for 03-05 A2UI component rendering
- DeliveryRouterNode wired and tested; Phase 5 Channel adapters can replace no-ops without graph changes
- 38 agent tests passing; graph topology verified via `g.nodes`
- project_agent.py calls real MCP (crm.get_project_status) when mcp-crm container is running

## Self-Check: PASSED

All 13 created files verified on disk. All 3 task commits (843756b, 8f67676, c649bbb) confirmed in git log.

---
*Phase: 03-sub-agents-memory-and-integrations*
*Completed: 2026-02-26*
