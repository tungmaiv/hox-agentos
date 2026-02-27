---
phase: quick-2
plan: quick-2
subsystem: scheduler/workflow-execution
tags: [hitl, sse, canvas, node-status, amber-ring]
dependency_graph:
  requires: []
  provides: [hitl_paused.node_id field in SSE event]
  affects: [frontend/src/hooks/use-workflow-run.ts]
tech_stack:
  added: []
  patterns: [SSE event enrichment]
key_files:
  modified:
    - backend/scheduler/tasks/workflow_execution.py
decisions:
  - "Extract hitl_node_id from state_snapshot.next[0] — this is the LangGraph pending node after interrupt"
  - "Use None as safe fallback when state_snapshot.next is empty to avoid IndexError"
metrics:
  duration: "<1 min"
  completed: "2026-02-27T15:22:39Z"
  tasks_completed: 1
  files_modified: 1
---

# Quick Task 2: Fix HITL Canvas Amber Ring — Add node_id to hitl_paused SSE Event

**One-liner:** Two-line fix adds `hitl_node_id` (from `state_snapshot.next[0]`) to the `hitl_paused` SSE event so the frontend amber ring activates on the correct canvas node.

## What Was Done

The `hitl_paused` SSE event published by `execute_workflow` was missing the `node_id` field. The frontend hook `use-workflow-run.ts` calls `nodeStatuses.set(event.node_id, "awaiting_approval")` to render the amber ring on the paused canvas node — without a valid `node_id`, the call was a no-op and no node turned amber.

**Root cause:** After `astream_events()` returns normally in LangGraph 1.0, the graph runner suppresses `GraphInterrupt` internally. HITL detection is done via `aget_state()` which returns a snapshot with `state_snapshot.interrupts` and `state_snapshot.next` (the tuple of pending node names). The code was correctly detecting the interrupt and extracting the message, but was not reading `state_snapshot.next[0]` to get the node ID.

**Fix (2 lines):**

```python
# Line 204 — after extracting message:
hitl_node_id = state_snapshot.next[0] if state_snapshot.next else None

# Line 219 — inside publish_event dict:
"node_id": hitl_node_id,
```

## Files Changed

| File | Change |
|------|--------|
| `backend/scheduler/tasks/workflow_execution.py` | Added `hitl_node_id` assignment + `"node_id"` field in `publish_event` |

## Verification

```
$ grep -n "hitl_node_id" backend/scheduler/tasks/workflow_execution.py
204:            hitl_node_id = state_snapshot.next[0] if state_snapshot.next else None
219:                "node_id": hitl_node_id,
```

Backend test suite: 258 passed, 12 warnings (no regressions).

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | ee2d3fd | fix(quick-2): add node_id to hitl_paused SSE event |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] `backend/scheduler/tasks/workflow_execution.py` modified with both lines
- [x] `grep -n "hitl_node_id"` returns exactly 2 matches
- [x] `publish_event` dict contains `"node_id": hitl_node_id`
- [x] 258 backend tests pass, no regressions
- [x] Commit ee2d3fd exists
