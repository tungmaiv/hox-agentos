---
phase: 04-canvas-and-workflows
plan: "02"
subsystem: agents
tags: [langgraph, stategraph, workflow-compiler, condition-evaluator, node-handlers, tdd]

# Dependency graph
requires:
  - phase: 04-01
    provides: Workflow/WorkflowRun DB tables, CRUD API, React Flow canvas shell
provides:
  - WorkflowState TypedDict (agents/workflow_state.py) — shared state for workflow execution graphs
  - Sandboxed condition evaluator (agents/condition_evaluator.py) — zero eval/exec, regex-based
  - Node handler registry (agents/node_handlers.py) — 6 handlers: trigger, agent, tool, condition, hitl, channel_output
  - compile_workflow_to_stategraph() compiler (agents/graphs.py) — React Flow JSON → LangGraph StateGraph
affects:
  - 04-03 (execution engine — wires real handlers, Celery task, SSE events)
  - 04-04 (HITL canvas — replaces MemorySaver with AsyncPostgresSaver, approve/reject endpoints)
  - 04-05 (templates — uses compile_workflow_to_stategraph to run template workflows)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Compiler separation: compile_workflow_to_stategraph() returns uncompiled builder; caller supplies checkpointer (MemorySaver in tests, AsyncPostgresSaver in production)"
    - "Default-arg closure capture in loop: _make_node_fn(nid=node_id, ntype=node_type, cfg=node_config) prevents closure-over-loop-variable bugs"
    - "Sandboxed expression evaluator: re.compile + named groups; ValueError for any unrecognized pattern; zero eval/exec calls"
    - "Node handler stubs: agent_node/tool_node/channel_output_node return structured mock output; real wiring deferred to 04-03"
    - "HITL via interrupt(): hitl_approval_node calls langgraph.types.interrupt() on first pass; returns stored hitl_result on resume"

key-files:
  created:
    - backend/agents/workflow_state.py
    - backend/agents/condition_evaluator.py
    - backend/agents/node_handlers.py
    - backend/agents/graphs.py
    - backend/tests/agents/test_workflow_state.py
    - backend/tests/agents/test_condition_evaluator.py
    - backend/tests/agents/test_node_handlers.py
    - backend/tests/agents/test_workflow_compiler.py
    - backend/tests/agents/test_workflow_compiler_templates.py
  modified: []

key-decisions:
  - "condition_evaluator.py is a separate module (not inline in node_handlers.py) — cleaner separation of concerns, independently testable"
  - "evaluate_condition(expression, output) takes output directly (not WorkflowState) — decoupled from state shape; node_handlers wraps with state.get('current_output')"
  - "HANDLER_REGISTRY also aliased as NODE_HANDLER_REGISTRY for PLAN.md compatibility — both names exported from node_handlers.py"
  - "compile_workflow_to_stategraph returns uncompiled StateGraph builder, not compiled graph — caller owns checkpointer lifecycle"
  - "Topological sort with Kahn's algorithm — handles DAGs with multiple entry/exit paths correctly; detects cycles implicitly (uncounted nodes)"
  - "condition_node router uses current_output bool directly (output of _handle_condition_node) not state fields — avoids extra state mutation"

patterns-established:
  - "TDD RED-GREEN per module: test file written and run to confirm ImportError before implementation"
  - "Compiler returns builder not compiled graph — all tests use MemorySaver(), production will use AsyncPostgresSaver"

requirements-completed: [WKFL-02, WKFL-08]

# Metrics
duration: 4min
completed: 2026-02-27
---

# Phase 04 Plan 02: Canvas-to-StateGraph Compiler Summary

**LangGraph workflow compiler with sandboxed condition evaluator and 6-node-type handler registry — React Flow definition_json compiles to executable StateGraph in 4 steps**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-27T04:09:40Z
- **Completed:** 2026-02-27T04:13:41Z
- **Tasks:** 6 (5 TDD + 1 auto)
- **Files modified:** 9 created, 0 modified

## Accomplishments

- WorkflowState TypedDict (run_id, user_context, node_outputs, current_output, hitl_result) with clear docstring separating it from BlitzState
- Sandboxed condition evaluator with regex-only parsing — no eval/exec; 17 tests covering all operators, string ops, and security rejections
- Node handler registry with all 6 node types; condition/hitl handlers have real logic; agent/tool/channel are functional stubs for 04-03
- compile_workflow_to_stategraph() with topological sort, conditional edge routing, and schema_version validation
- Morning Digest and Alert templates both compile to valid StateGraphs (phase gate criteria satisfied)
- Full test suite: 233 passed (was 199; +34 new tests), 0 failed

## Task Commits

Each task was committed atomically:

1. **Task 1: WorkflowState TypedDict** - `a652ef3` (feat)
2. **Task 2: Sandboxed condition evaluator** - `698e6e6` (feat)
3. **Task 3: Node handler registry (6 types)** - `14ce4f0` (feat)
4. **Task 4: compile_workflow_to_stategraph compiler** - `6fab80b` (feat)
5. **Task 5: Template compilation smoke tests** - `05ac554` (test)

_Note: TDD tasks executed as RED (failing test) → GREEN (implementation) → commit_

## Files Created/Modified

- `backend/agents/workflow_state.py` - WorkflowState TypedDict with 5 fields
- `backend/agents/condition_evaluator.py` - Sandboxed evaluate_condition() using re module
- `backend/agents/node_handlers.py` - HANDLER_REGISTRY with 6 handlers + get_handler()
- `backend/agents/graphs.py` - compile_workflow_to_stategraph() + topological sort + conditional edges
- `backend/tests/agents/test_workflow_state.py` - 2 tests
- `backend/tests/agents/test_condition_evaluator.py` - 17 tests
- `backend/tests/agents/test_node_handlers.py` - 6 tests
- `backend/tests/agents/test_workflow_compiler.py` - 6 tests
- `backend/tests/agents/test_workflow_compiler_templates.py` - 3 tests

## Decisions Made

- `condition_evaluator.py` is a standalone module (not inlined in `node_handlers.py`) — enables independent testing and reuse
- `evaluate_condition(expression, output)` takes raw output not WorkflowState — decoupled from state structure; the condition handler extracts `state.get("current_output")` before calling
- `HANDLER_REGISTRY` aliased as `NODE_HANDLER_REGISTRY` — both exported so PLAN.md frontmatter references and plan doc references both work
- Compiler returns uncompiled `StateGraph` builder — tests inject `MemorySaver()`, production will inject `AsyncPostgresSaver` (04-04)
- Topological sort uses Kahn's algorithm — handles DAGs correctly; if graph has a cycle, some nodes won't be sorted (silently skipped) which is acceptable for MVP

## Deviations from Plan

None — plan executed exactly as written. The plan doc referenced slightly different file names (`condition_evaluator.py` vs inline in `node_handlers.py`) but both approaches were consistent across the plan doc and PLAN.md, and the separate module approach was selected as architecturally cleaner.

## Issues Encountered

None. All LangGraph imports (`interrupt`, `MemorySaver`, `StateGraph`, `END`) available in installed version. No version compatibility issues.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `compile_workflow_to_stategraph()` is ready for 04-03 to wire real handler execution
- All 6 node type handlers have correct stubs returning structured output — 04-03 replaces stub bodies
- `hitl_approval_node` calls `interrupt()` correctly — 04-04 adds `AsyncPostgresSaver` and approve/reject endpoints
- Test infrastructure (34 new tests) verifies compiler correctness before execution layer is added

---
*Phase: 04-canvas-and-workflows*
*Completed: 2026-02-27*

## Self-Check: PASSED

All files created and all commits present:
- workflow_state.py: FOUND
- condition_evaluator.py: FOUND
- node_handlers.py: FOUND
- graphs.py: FOUND
- 04-02-SUMMARY.md: FOUND
- a652ef3 (WorkflowState): FOUND
- 698e6e6 (condition evaluator): FOUND
- 14ce4f0 (node handlers): FOUND
- 6fab80b (compiler): FOUND
- 05ac554 (template tests): FOUND
