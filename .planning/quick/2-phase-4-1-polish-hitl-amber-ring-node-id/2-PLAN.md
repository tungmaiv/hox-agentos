---
phase: 04-canvas-and-workflows
plan: quick-2
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/scheduler/tasks/workflow_execution.py
autonomous: true
requirements: [WKFL-05]
must_haves:
  truths:
    - "When a workflow pauses at an HITL node, that canvas node turns amber (awaiting_approval ring)"
  artifacts:
    - path: "backend/scheduler/tasks/workflow_execution.py"
      provides: "hitl_paused SSE event with node_id field"
      contains: "node_id.*hitl_node_id"
  key_links:
    - from: "backend/scheduler/tasks/workflow_execution.py"
      to: "frontend/src/hooks/use-workflow-run.ts:86"
      via: "hitl_paused SSE event.node_id"
      pattern: "hitl_node_id.*state_snapshot.next"
---

<objective>
Fix the HITL canvas node amber ring visual state by adding the missing `node_id` field to the `hitl_paused` SSE event.

Purpose: When a workflow pauses for human approval, the correct canvas node should turn amber (the `awaiting_approval` ring). Currently the event fires without `node_id`, so the frontend `nodeStatuses.set(undefined, "awaiting_approval")` is a no-op and the ring never activates.

Output: One-line fix in `workflow_execution.py` — extract `hitl_node_id` from `state_snapshot.next[0]` and include it in the `publish_event` call.

Note: Gap 2 (Next.js webhook proxy) is already complete — `frontend/src/app/api/webhooks/[webhook_id]/route.ts` exists and is fully implemented. No action needed.
</objective>

<execution_context>
@/home/tungmv/.claude/get-shit-done/workflows/execute-plan.md
@/home/tungmv/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add node_id to hitl_paused SSE event</name>
  <files>backend/scheduler/tasks/workflow_execution.py</files>
  <action>
At line 195, `state_snapshot = await compiled.aget_state(config)` already captures the LangGraph checkpoint state. The `state_snapshot.next` attribute is a tuple of node names pending execution — the HITL node that triggered the interrupt is `state_snapshot.next[0]`.

After the `state_snapshot = await compiled.aget_state(config)` line (line 195) and before the `if state_snapshot.interrupts:` block, no change is needed there. Inside the `if state_snapshot.interrupts:` block, after line 203 (`message = interrupt_data.get(...)`), add:

```python
hitl_node_id = state_snapshot.next[0] if state_snapshot.next else None
```

Then update the `publish_event` call at lines 216-220 to include `"node_id": hitl_node_id`:

```python
publish_event(run_id_str, {
    "event": "hitl_paused",
    "node_id": hitl_node_id,
    "message": message,
    "interrupt_data": interrupt_data,
})
```

This is a 2-line change. Do NOT touch anything else in the file.
  </action>
  <verify>
    <automated>cd /home/tungmv/Projects/hox-agentos/backend && grep -n "hitl_node_id" scheduler/tasks/workflow_execution.py</automated>
    <manual>Confirm two lines are present: the assignment `hitl_node_id = state_snapshot.next[0] if state_snapshot.next else None` and the `"node_id": hitl_node_id` field in the publish_event dict.</manual>
  </verify>
  <done>
    `grep -n "hitl_node_id" workflow_execution.py` returns 2 lines — the assignment and the dict field. The `hitl_paused` event dict now contains `"node_id": hitl_node_id`. Backend tests still pass: `cd /home/tungmv/Projects/hox-agentos/backend && .venv/bin/pytest tests/ -x -q 2>&1 | tail -5` shows no regressions.
  </done>
</task>

</tasks>

<verification>
After Task 1:
1. `grep -n "hitl_node_id" /home/tungmv/Projects/hox-agentos/backend/scheduler/tasks/workflow_execution.py` returns exactly 2 matches.
2. `grep -A6 "hitl_paused" /home/tungmv/Projects/hox-agentos/backend/scheduler/tasks/workflow_execution.py` shows `"node_id": hitl_node_id` inside the publish_event dict.
3. Backend test suite passes without regressions.
</verification>

<success_criteria>
The `hitl_paused` SSE event published by `execute_workflow` includes `"node_id": hitl_node_id` where `hitl_node_id` is `state_snapshot.next[0]` (the pending HITL node name, or `None` as safe fallback). When the frontend `use-workflow-run.ts` receives the event, `event.node_id` is a real node ID string and `nodeStatuses.set(node_id, "awaiting_approval")` correctly marks that canvas node amber.
</success_criteria>

<output>
After completion, create `.planning/quick/2-phase-4-1-polish-hitl-amber-ring-node-id/2-SUMMARY.md` with what was done and what files were changed.
</output>
```
