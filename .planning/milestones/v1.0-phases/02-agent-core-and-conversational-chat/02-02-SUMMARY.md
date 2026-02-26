---
phase: 02-agent-core-and-conversational-chat
plan: "02"
subsystem: api
tags: [langgraph, copilotkit, langgraph-agent, blitz-state, master-agent, tdd, fastapi, security]

# Dependency graph
requires:
  - phase: 02-01
    provides: get_llm('blitz/master') contract verified; LiteLLM proxy routing confirmed
  - phase: 01-04
    provides: 3-gate security chain (get_current_user, has_permission, check_tool_acl, log_tool_call)
  - phase: 01-02
    provides: UserContext TypedDict, get_current_user() FastAPI dependency
provides:
  - BlitzState TypedDict with add_messages reducer (agents/state/types.py)
  - create_master_graph() factory returning CompiledStateGraph with routing conditional stub
  - gateway/runtime.py with CopilotKitRemoteEndpoint holding blitz_master LangGraphAgent
  - POST /api/copilotkit + GET|POST /api/copilotkit/{path:path} with full 3-gate security
  - current_user_ctx ContextVar for user access inside graph nodes without arg threading
  - 8 TDD tests covering BlitzState, master graph, AST SDK check, conditional routing, 3 security gates
affects:
  - 02-03 (frontend CopilotKit wiring — must target POST /api/copilotkit, agent name 'blitz_master')
  - 02-04 (tool registration — tools will be invoked from inside LangGraph nodes)
  - 02-05 (slash commands, message editing — uses the same blitz_master graph)
  - 03+ (memory, sub-agents — extend BlitzState + update _route_after_master routing conditional)

# Tech tracking
tech-stack:
  added:
    - langgraph==0.4.10 (was constrained >=0.2.0 — installed latest)
    - langgraph-checkpoint==3.0.1
    - langgraph-prebuilt==1.0.1
    - langgraph-sdk==0.3.9
    - copilotkit==0.1.54
    - langchain==0.3.26 (transitive via langgraph)
  patterns:
    - "BlitzState TypedDict with Annotated[list[BaseMessage], add_messages] — nodes return partial dicts, LangGraph merges"
    - "CompiledStateGraph: StateGraph.compile() called once at module load in runtime.py"
    - "CopilotKitRemoteEndpoint (not deprecated CopilotKitSDK) registers LangGraphAgent(name, graph)"
    - "Security-first routing: router POST /api/copilotkit enforces Gate 1+2+3 before delegating to copilotkit_handler"
    - "ContextVar current_user_ctx: set in endpoint, accessible in graph nodes without arg threading"

key-files:
  created:
    - backend/agents/__init__.py
    - backend/agents/state/__init__.py
    - backend/agents/state/types.py
    - backend/agents/master_agent.py
    - backend/gateway/runtime.py
    - backend/tests/agents/__init__.py
    - backend/tests/agents/test_master_agent.py
    - backend/tests/test_runtime.py
  modified:
    - backend/pyproject.toml (added langgraph>=0.2.0 and copilotkit>=0.1.54)
    - backend/uv.lock (updated)
    - backend/main.py (added from gateway import runtime + app.include_router(runtime.router))

key-decisions:
  - "CopilotKitSDK is deprecated since 0.1.31 — use CopilotKitRemoteEndpoint instead (no API difference, just name)"
  - "copilotkit.integrations.fastapi.handler() used directly as delegate inside secured FastAPI route — avoids bypassing auth"
  - "LangGraph 0.4.10 uses compiled.builder.branches (not compiled.graph.branches) to inspect conditional edges"
  - "importlib.reload() approach for mocking get_llm removed — patch agents.master_agent.get_llm directly (no reload needed)"
  - "Subpath route GET|POST /api/copilotkit/{path:path} added to cover agent/blitz_master, info, agents/execute sub-paths"
  - "Plan had 4 master_agent tests; adapted to 5 (test_create_master_graph_has_routing_conditional was always in the file)"

patterns-established:
  - "LangGraph module-level compiled graph: _master_graph = create_master_graph() at module load (avoid recompilation per request)"
  - "CopilotKit agent name 'blitz_master' — frontend useCopilotAction/useCoAgent must reference this exact name"
  - "3-gate CopilotKit security: Depends(get_current_user) [Gate 1] → has_permission(user, 'chat') [Gate 2] → check_tool_acl [Gate 3]"
  - "_check_gates() helper DRY-enforces Gate 2+3 for both root and subpath CopilotKit routes"

requirements-completed:
  - AGNT-01
  - AGNT-02
  - AGNT-07

# Metrics
duration: 23min
completed: 2026-02-25
---

# Phase 2 Plan 02: LangGraph Master Agent and CopilotKit Runtime Summary

**BlitzState TypedDict + create_master_graph() ReAct graph + POST /api/copilotkit with 3-gate JWT->RBAC->ACL security — LangGraph 0.4.10 + CopilotKitRemoteEndpoint 0.1.54 wired, 83 backend tests pass**

## Performance

- **Duration:** 23 min
- **Started:** 2026-02-25T03:43:47Z
- **Completed:** 2026-02-25T04:06:56Z
- **Tasks:** 2 (both TDD — RED+GREEN+verify)
- **Files modified:** 10 (8 created, 2 modified)

## Accomplishments

- Installed langgraph 0.4.10 and copilotkit 0.1.54 — both import cleanly, correct API discovered via source inspection
- Created `agents/state/types.py` with `BlitzState` TypedDict using `Annotated[list[BaseMessage], add_messages]` reducer
- Created `agents/master_agent.py` with `create_master_graph()`: single master_agent node → `_route_after_master` conditional → END (Phase 2 stub, Phase 3 extensible)
- Created `gateway/runtime.py` with `CopilotKitRemoteEndpoint` (not deprecated `CopilotKitSDK`) registering `LangGraphAgent(name="blitz_master", graph=_master_graph)`
- POST `/api/copilotkit` + catch-all subpath route: Gate 1 (JWT via Depends) → Gate 2 (RBAC 'chat') → Gate 3 (ACL 'agents.chat') → CopilotKit handler
- 8 new TDD tests: 5 master_agent + 3 runtime — all pass; 83 total tests, zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Install langgraph+copilotkit, TDD BlitzState and master agent graph** - `dc0fa3a` (feat)
2. **Task 2: TDD CopilotKit runtime gateway and /api/copilotkit endpoint** - `42a773a` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `backend/agents/__init__.py` - agents package init
- `backend/agents/state/__init__.py` - state subpackage init
- `backend/agents/state/types.py` - BlitzState TypedDict with add_messages reducer
- `backend/agents/master_agent.py` - create_master_graph() with _master_node and _route_after_master conditional
- `backend/gateway/runtime.py` - CopilotKitRemoteEndpoint + blitz_master LangGraphAgent + secured POST /api/copilotkit router
- `backend/tests/agents/__init__.py` - test agents subpackage init
- `backend/tests/agents/test_master_agent.py` - 5 TDD tests for BlitzState and master graph
- `backend/tests/test_runtime.py` - 3 TDD tests for /api/copilotkit security gates
- `backend/pyproject.toml` - added langgraph>=0.2.0 and copilotkit>=0.1.54
- `backend/main.py` - added `from gateway import runtime` + `app.include_router(runtime.router)`

## CopilotKit SDK Version and Import Paths

| Item | Value |
|------|-------|
| Package version | `copilotkit==0.1.54` |
| Primary import | `from copilotkit import CopilotKitRemoteEndpoint, LangGraphAgent` |
| FastAPI handler | `from copilotkit.integrations.fastapi import handler as copilotkit_handler` |
| Agent name | `blitz_master` (frontend must use this exact name) |
| Deprecated class | `CopilotKitSDK` (deprecated since 0.1.31 — do not use) |

## LangGraph Version Discovery

| Item | Value |
|------|-------|
| Package version | `langgraph==0.4.10` |
| Graph structure | `compiled.builder.branches` (not `compiled.graph.branches` — attribute does not exist in 0.4.10) |
| State schema | `BlitzState(TypedDict)` with `Annotated[list[BaseMessage], add_messages]` |
| Compilation | `StateGraph(BlitzState).compile()` → `CompiledStateGraph` |

## Decisions Made

- **CopilotKitRemoteEndpoint over CopilotKitSDK:** CopilotKitSDK emits a `DeprecationWarning` since 0.1.31. The replacement `CopilotKitRemoteEndpoint` has identical API. Adopted immediately.
- **Direct copilotkit_handler delegation:** Instead of calling `add_fastapi_endpoint()` (which bypasses security by registering routes directly to FastAPI), the secured router calls `copilotkit.integrations.fastapi.handler(request, _sdk)` after all gates pass.
- **compiled.builder.branches (not compiled.graph):** LangGraph 0.4.10 removed the `.graph` attribute from `CompiledStateGraph`. The original StateGraph is accessible via `.builder`. The conditional routing test was updated to check `compiled.builder.branches["master_agent"]`.
- **No importlib.reload() in tests:** The plan's mock pattern used `importlib.reload(ma_module)` inside `with patch(...)`. This fails because reload re-executes `from core.config import get_llm`, creating a new binding. Fix: patch `agents.master_agent.get_llm` directly (the module-level name) without reload — the mock is active during `ainvoke()`.
- **Subpath route:** Added `GET|POST /api/copilotkit/{path:path}` alongside the root route so CopilotKit sub-paths (`/agent/blitz_master`, `/info`, `/agents/execute`) also enforce 3-gate security.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CopilotKitSDK deprecated — switched to CopilotKitRemoteEndpoint**

- **Found during:** Task 2 (inspecting CopilotKit SDK source to find correct API)
- **Issue:** Plan specified `from copilotkit import CopilotKitSDK` but this class emits `DeprecationWarning: CopilotKitSDK is deprecated since version 0.1.31. Use CopilotKitRemoteEndpoint instead.`
- **Fix:** Used `CopilotKitRemoteEndpoint` in runtime.py — identical API, no deprecation warning
- **Files modified:** `backend/gateway/runtime.py`
- **Committed in:** `42a773a` (Task 2)

**2. [Rule 1 - Bug] `compiled.graph.branches` does not exist in LangGraph 0.4.10**

- **Found during:** Task 1 (running initial tests, discovered `CompiledStateGraph` has no `.graph` attribute)
- **Issue:** Plan test `test_create_master_graph_has_routing_conditional` accessed `graph.graph.branches`. LangGraph 0.4.10 removed this attribute.
- **Fix:** Updated test to use `compiled.builder.branches` (the original StateGraph is accessible at `.builder`)
- **Files modified:** `backend/tests/agents/test_master_agent.py`
- **Committed in:** `dc0fa3a` (Task 1)

**3. [Rule 1 - Bug] importlib.reload() mock pattern broke due to re-binding**

- **Found during:** Task 1 (test_master_graph_calls_blitz_master_and_returns_ai_message failed — mock not applied)
- **Issue:** `importlib.reload(ma_module)` inside `with patch("agents.master_agent.get_llm")` re-executes `from core.config import get_llm` in the module, creating a NEW binding that bypasses the patch
- **Fix:** Removed reload; patch `agents.master_agent.get_llm` directly — the mock is active at `ainvoke()` call time
- **Files modified:** `backend/tests/agents/test_master_agent.py`
- **Committed in:** `dc0fa3a` (Task 1)

**4. [Rule 2 - Missing Critical] Added /api/copilotkit/{path:path} subpath route**

- **Found during:** Task 2 (inspecting CopilotKit fastapi integration source)
- **Issue:** CopilotKit's frontend SDK sends requests to sub-paths: `/agent/{name}`, `/info`, `/agents/execute`. Plan only specified the root POST `/api/copilotkit`. Without the subpath route, these would be unprotected or unregistered.
- **Fix:** Added `@router.api_route("/copilotkit/{path:path}", ...)` with same 3-gate security and CopilotKit handler delegation
- **Files modified:** `backend/gateway/runtime.py`
- **Committed in:** `42a773a` (Task 2)

---

**Total deviations:** 4 auto-fixed (2 bugs, 1 bug+fix, 1 missing critical)
**Impact on plan:** All fixes necessary for correctness and security. No scope creep. Test count is 8 total (plan said "4 master_agent + 3 runtime = 7 new" but test file always had 5 master_agent tests).

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None — no external service configuration required. LangGraph and CopilotKit are installed packages. The `/api/copilotkit` endpoint only functions when LiteLLM is running (Docker stack up).

## Notes for 02-03 (Frontend Proxy Route)

The Next.js proxy route (`frontend/src/app/api/copilotkit/route.ts`) must:

1. **Forward** all requests to `POST http://backend:8000/api/copilotkit` (from container) or `http://localhost:8000/api/copilotkit` (from browser dev)
2. **Inject** the server-side Bearer token from `auth()` into the `Authorization` header
3. **Use agent name** `blitz_master` in the CopilotKit client configuration: `useCopilotAgent("blitz_master")`
4. **Forward sub-paths** if CopilotKit client makes requests to `/api/copilotkit/agent/blitz_master` or similar

## Next Phase Readiness

- **02-03 (Frontend streaming UI):** Backend endpoint ready. Frontend proxy route needs to inject Bearer token and forward to `POST /api/copilotkit`. Agent name is `blitz_master`.
- **02-04 (Tool registration):** `_master_node` in `master_agent.py` currently calls LLM directly. Phase 3 adds `bind_tools()` to expose tools in the graph — no restructuring needed.
- **02-05 (Slash commands, export, edit):** Same graph and endpoint — add CopilotKit actions alongside the agent.
- **03+ (Memory, sub-agents):** Extend `BlitzState` with `user_id`, `loaded_memory` fields; update `_route_after_master` conditional; add sub-agent nodes to `create_master_graph()`.

---
*Phase: 02-agent-core-and-conversational-chat*
*Completed: 2026-02-25*
