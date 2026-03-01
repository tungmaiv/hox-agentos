---
phase: 10-optional-tech-debt-closure
plan: "01"
subsystem: channels
tags: [channels, langgraph, memorysaver, delivery_router, channel_adapter, gateway]

# Dependency graph
requires:
  - phase: 05-scheduler-and-channels
    provides: ChannelGateway, ChannelAdapter protocol, sidecar delivery pattern
  - phase: 05.1-workflow-execution-wiring
    provides: delivery_router_node, format_for_channel module-level function
provides:
  - register_adapter() with isinstance(ChannelAdapter) enforcement at registration time
  - _channel_graph_savers module-level dict for per-conversation MemorySaver reuse
  - _invoke_agent() returning None; response delivered via delivery_router_node
  - create_master_graph() accepting optional checkpointer parameter
affects: [channels, agents, future-channel-adapters]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Module-level saver dict keyed by conversation_id for multi-turn channel continuity
    - Protocol isinstance enforcement at registration boundary (fail fast)
    - Delivery unification: channel invocations use delivery_targets to flow through delivery_router_node

key-files:
  created: []
  modified:
    - backend/channels/gateway.py
    - backend/agents/master_agent.py
    - backend/tests/channels/test_gateway.py
    - backend/tests/channels/test_gateway_agent.py

key-decisions:
  - "10-01: _invoke_agent() returns None — delivery flows through delivery_router_node via delivery_targets=[msg.channel.upper()]; no post-processing of agent result needed"
  - "10-01: lazy imports in _invoke_agent() (fetch_user_realm_roles, create_master_graph, current_user_ctx) must be patched at definition site — patch('security.keycloak_client.fetch_user_realm_roles') not 'channels.gateway.fetch_user_realm_roles'"
  - "10-01: _channel_graph_savers dict is module-level and process-lifetime; acceptable at single-node MVP scale per YAGNI"
  - "10-01: create_master_graph() checkpointer param uses 'or MemorySaver()' default — preserves backward compat for all existing callers"

patterns-established:
  - "Registration-time protocol enforcement: isinstance(adapter, ChannelAdapter) in register_adapter() raises TypeError immediately rather than deferring to call time"
  - "Saver-dict pattern: module-level dict[str, MemorySaver] keyed by conversation_id; create once, reuse on subsequent _invoke_agent() calls for same session"

requirements-completed: [CHAN-05, CHAN-02]

# Metrics
duration: 3min
completed: 2026-03-02
---

# Phase 10 Plan 01: Channel Tech Debt Closure Summary

**ChannelGateway register_adapter() with ChannelAdapter isinstance enforcement, per-conversation MemorySaver reuse dict, and delivery_targets unification through delivery_router_node**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-02T08:47:25Z
- **Completed:** 2026-03-02T08:51:17Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `register_adapter()` to `ChannelGateway` — validates conformance to `ChannelAdapter` protocol via `isinstance()` at registration time, raising `TypeError` immediately for non-conforming objects (CHAN-05)
- Added module-level `_channel_graph_savers: dict[str, MemorySaver]` — reuses same `MemorySaver` instance per `conversation_id` across `_invoke_agent()` calls, enabling multi-turn continuity for channel sessions (CHAN-02)
- Refactored `_invoke_agent()` to return `None` and set `delivery_targets=[msg.channel.upper()]` in initial state — response is now delivered directly by `delivery_router_node` via `send_outbound()`, eliminating special-case AI text extraction code path
- Extended `create_master_graph()` with optional `checkpointer` parameter — channel gateway passes its per-conversation saver; web chat continues to use default `MemorySaver()` (backward compat)
- Added 3 new tests covering isinstance enforcement, conforming adapter acceptance, and saver reuse across repeated invocations

## Task Commits

Each task was committed atomically:

1. **Task 1: Add register_adapter(), _channel_graph_savers, refactor _invoke_agent()** - `bebed5b` (feat)
2. **Task 2: Add 3 new tests for register_adapter and saver reuse** - `216be09` (test)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `backend/channels/gateway.py` — Added MemorySaver import, _channel_graph_savers dict, register_adapter() method, refactored _invoke_agent() to None return + delivery_targets + saver reuse, updated handle_inbound() call site
- `backend/agents/master_agent.py` — Added optional `checkpointer: MemorySaver | None = None` parameter to create_master_graph(); last line uses `checkpointer or MemorySaver()`
- `backend/tests/channels/test_gateway.py` — Added 3 new tests: test_register_adapter_raises_type_error_for_non_conforming, test_register_adapter_accepts_conforming_adapter, test_invoke_agent_reuses_saver_for_same_conversation
- `backend/tests/channels/test_gateway_agent.py` — Updated all 4 existing tests to match new _invoke_agent() -> None contract; added test_invoke_agent_sets_delivery_targets; now 5 tests total

## Decisions Made

- `_invoke_agent()` returns `None` — delivery flows through `delivery_router_node` via `delivery_targets=[msg.channel.upper()]`; eliminates the old pattern of extracting AI text from graph result and calling `send_outbound()` separately
- Lazy imports inside `_invoke_agent()` (`fetch_user_realm_roles`, `create_master_graph`, `current_user_ctx`) must be patched at definition site — `patch('security.keycloak_client.fetch_user_realm_roles')` not `'channels.gateway.fetch_user_realm_roles'` (per CLAUDE.md lazy import patchability gotcha)
- `_channel_graph_savers` is module-level and process-lifetime; acceptable at single-node MVP scale per YAGNI
- `create_master_graph()` checkpointer param uses `or MemorySaver()` default — preserves backward compat for all existing callers without passing a saver

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_gateway_agent.py tests to match new _invoke_agent() contract**
- **Found during:** Task 2 (adding new tests)
- **Issue:** 4 existing tests in `test_gateway_agent.py` tested the old `_invoke_agent()` return value (an `InternalMessage` with AI text). After Task 1 changed the return type to `None`, these tests failed with `AttributeError`
- **Fix:** Rewrote all 4 tests to assert `result is None` and capture `send_outbound()` calls for error path assertions. Added `test_invoke_agent_sets_delivery_targets` to cover the new `delivery_targets` initial state field
- **Files modified:** `backend/tests/channels/test_gateway_agent.py`
- **Verification:** 5 tests pass, full suite 606 passed
- **Committed in:** `216be09` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — outdated test contract)
**Impact on plan:** Necessary correction — tests must match the new API contract. No scope creep.

## Issues Encountered

- `patch("channels.gateway.fetch_user_realm_roles")` failed with `AttributeError` because the import is lazy inside `_invoke_agent()` — fixed by patching at definition site `security.keycloak_client.fetch_user_realm_roles` (per CLAUDE.md lazy import gotcha, same pattern as `call_mcp_tool` in `project_agent.py`)
- `patch("channels.gateway.current_user_ctx")` also failed (lazy import) — resolved by removing the mock entirely and letting the real contextvar `set()`/`reset()` run (safe in test context)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CHAN-05 (ChannelAdapter isinstance enforcement) formally satisfied
- CHAN-02 (multi-turn channel continuity via MemorySaver) formally satisfied
- Channel invocations now flow through the same delivery_router_node path as web chat — no special-casing
- Phase 10 Plan 01 complete; check ROADMAP.md for remaining optional plans

## Self-Check: PASSED

All artifacts verified:
- Files exist: gateway.py, master_agent.py, test_gateway.py, test_gateway_agent.py, 10-01-SUMMARY.md
- Commits exist: bebed5b (Task 1), 216be09 (Task 2)
- Code artifacts present: _channel_graph_savers, register_adapter(), delivery_targets, checkpointer param, 3 new test functions

---
*Phase: 10-optional-tech-debt-closure*
*Completed: 2026-03-02*
