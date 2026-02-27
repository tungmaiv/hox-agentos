---
phase: 04-canvas-and-workflows
verified: 2026-02-27T05:15:00Z
status: gaps_found
score: 7/9 must-haves verified
re_verification: false
gaps:
  - truth: "Webhook endpoint creates a WorkflowRun and enqueues execute_workflow when X-Webhook-Secret validates"
    status: failed
    reason: "webhooks.py creates a WorkflowRun row but never calls execute_workflow_task.delay() — a comment says 'Execution is wired in plan 04-03' but it was not done. WKFL-07 requires the webhook to actually trigger execution."
    artifacts:
      - path: "backend/api/routes/webhooks.py"
        issue: "Line 62: comment 'Execution is wired in plan 04-03' present; no execute_workflow_task.delay() call exists in the file. Webhook triggers are orphaned — they accept the request and create the run row but execution never starts."
    missing:
      - "Add 'from scheduler.tasks.workflow_execution import execute_workflow_task' import to webhooks.py"
      - "After session.commit() + await session.refresh(run), call 'execute_workflow_task.delay(str(run.id))'"
      - "Return run_id in response (already done)"

  - truth: "condition_node compiles to add_conditional_edges with true/false branches (for template JSON files)"
    status: partial
    reason: "The compiler reads edge['data']['branch'] to detect true/false branches. The actual morning_digest.json and alert.json template files use the React Flow native 'sourceHandle' field at the edge top level (not nested in 'data'). When these templates are copied and run, the condition edges are treated as plain edges — add_conditional_edges is never called. Conditional routing for pre-built templates is broken. The test suite uses separate in-test fixtures with the correct 'data.branch' format, so tests pass but real template execution won't branch correctly."
    artifacts:
      - path: "backend/agents/graphs.py"
        issue: "Lines 148-149: checks edge.get('data', {}).get('branch') == 'true'. Template JSON uses top-level 'sourceHandle': 'true' not 'data': {'branch': 'true'}."
      - path: "backend/data/workflow_templates/morning_digest.json"
        issue: "Line 67: edge e3-4 has 'sourceHandle': 'true' at top level — compiler won't detect this as a conditional branch."
      - path: "backend/data/workflow_templates/alert.json"
        issue: "Line 66: edge e3-4 has 'sourceHandle': 'true' at top level — same mismatch."
    missing:
      - "Either: update compiler to also check edge.get('sourceHandle') in addition to edge.get('data', {}).get('branch')"
      - "Or: update both template JSON files to use 'data': {'branch': 'true'} format for the condition-to-true-branch edge"
      - "Regression test: verify that morning_digest.json loaded directly from disk produces conditional edges in the compiled graph"
---

# Phase 4: Canvas and Workflows Verification Report

**Phase Goal:** Users can visually build multi-step automations on a drag-and-drop canvas that compile to executable agent workflows with human approval gates
**Verified:** 2026-02-27T05:15:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Canvas drag-and-drop builds multi-step workflows | VERIFIED | WorkflowCanvas + NodePalette onDrop creates nodes at drop position; onConnect adds edges |
| 2 | Workflows compile to LangGraph StateGraphs | VERIFIED | compile_workflow_to_stategraph() in graphs.py — topological sort + StateGraph[WorkflowState] |
| 3 | Workflows execute end-to-end via Celery | VERIFIED | execute_workflow_task in workflow_execution.py uses astream_events() loop |
| 4 | HITL approval pauses graph and waits for human input | VERIFIED | hitl_approval_node calls interrupt(); AsyncPostgresSaver persists state; approve/reject API resumes via aupdate_state() |
| 5 | Cron triggers fire via Celery beat every 60 seconds | VERIFIED | fire_cron_triggers_task registered in celery_app beat_schedule at 60.0s; croniter checks window |
| 6 | Webhook triggers fire execution on external event | PARTIAL | webhooks.py creates WorkflowRun but never calls execute_workflow_task.delay() — run is created, execution never starts |
| 7 | schema_version is enforced on all workflow definitions | VERIFIED | WorkflowCreate.require_schema_version validator raises ValueError if != "1.0" |
| 8 | Pre-built templates available as starting points | VERIFIED | morning_digest.json and alert.json fixtures; migration 011 inserts as is_template=true; TemplateCard copies and navigates |
| 9 | Condition node routes true/false branches correctly | PARTIAL | Compiler checks edge.get("data", {}).get("branch") but template JSON files use top-level "sourceHandle": "true" — mismatch means templates won't branch correctly at runtime |

**Score:** 7/9 truths fully verified

---

## Required Artifacts

### Plan 04-01 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/core/models/workflow.py` | Workflow, WorkflowRun, WorkflowTrigger ORM models | VERIFIED | All 3 models present; owner_user_id nullable on Workflow |
| `backend/alembic/versions/010_phase4_workflows.py` | Creates 3 tables; owner_user_id nullable | VERIFIED | owner_user_id nullable=True confirmed; 3 tables created |
| `backend/api/routes/workflows.py` | 15 CRUD + HITL + SSE endpoints with JWT | VERIFIED | 15 endpoints; all require get_current_user; ownership enforced |
| `backend/api/routes/webhooks.py` | Public endpoint validates X-Webhook-Secret | VERIFIED (partial) | Secret validation works; WorkflowRun created; but execution not enqueued |
| `backend/core/schemas/workflow.py` | schema_version == "1.0" enforced | VERIFIED | field_validator on WorkflowCreate and WorkflowUpdate |
| `frontend/src/components/canvas/workflow-canvas.tsx` | ReactFlow with all 6 node types, drag-drop | VERIFIED | 6 node types registered in NODE_TYPES; onDrop creates nodes |
| `frontend/src/components/canvas/node-palette.tsx` | 6 draggable entries | VERIFIED | 6 PALETTE items with draggable + onDragStart(dataTransfer) |
| `frontend/src/hooks/use-workflow.ts` | CRUD hook | VERIFIED | Exists and is used by canvas-editor.tsx |

### Plan 04-02 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/agents/workflow_state.py` | WorkflowState TypedDict with 5 fields | VERIFIED | run_id, user_context, node_outputs, current_output, hitl_result |
| `backend/agents/condition_evaluator.py` | Sandboxed evaluator, no eval() | VERIFIED | regex-based parsing; no eval/exec calls; ValueError for unsupported |
| `backend/agents/node_handlers.py` | HANDLER_REGISTRY with 6 node types; call_mcp_tool() in tool_node | VERIFIED | All 6 handlers; real call_mcp_tool() with UserContext; interrupt() in HITL handler |
| `backend/agents/graphs.py` | compile_workflow_to_stategraph() with topological sort | VERIFIED (partial) | Function exists and compiles; but condition edge routing only works with data.branch format, not sourceHandle |

### Plan 04-03 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/scheduler/tasks/workflow_execution.py` | execute_workflow Celery task + Redis publish + AsyncPostgresSaver | VERIFIED | AsyncPostgresSaver in use; astream_events loop; publish_event calls; resume via aupdate_state |
| `backend/workflow_events.py` | Redis pub/sub event bus | VERIFIED | publish_event (sync) and subscribe_events (async) |
| `backend/scheduler/tasks/cron_trigger.py` | fire_cron_triggers Celery beat task | VERIFIED | croniter check within 60s window; creates WorkflowRun; enqueues execute_workflow_task |
| `backend/scheduler/celery_app.py` | beat_schedule with cron trigger task | VERIFIED | fire_cron_triggers_task at 60.0s in beat_schedule |

### Plan 04-04 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/hooks/use-workflow-run.ts` | EventSource SSE + Map<node_id, NodeStatus> | VERIFIED | useWorkflowRun hook; EventSource lifecycle; nodeStatuses Map; approve/reject calls |
| `frontend/src/hooks/use-pending-hitl.ts` | 30s polling for pending HITL count | VERIFIED | Exists; polling hook |
| `frontend/src/components/canvas/nodes/hitl-approval-node.tsx` | Approve/Reject buttons when awaiting_approval | VERIFIED | isAwaiting check; green Approve + red Reject buttons rendered |
| `frontend/src/components/canvas/nodes/trigger-node.tsx` | Status ring | VERIFIED | NodeStatusRing used |
| `frontend/src/components/canvas/nodes/condition-node.tsx` | Two output handles true/false | VERIFIED | Exists |
| `frontend/src/components/canvas/run-controls.tsx` | Run button + spinner | VERIFIED | isRunning spinner; onRun callback |
| `frontend/src/app/workflows/[id]/canvas-editor.tsx` | Full wired editor with hooks | VERIFIED | useWorkflowRun wired; HITL banner; RunControls; WorkflowCanvas |
| `frontend/src/lib/workflow-types.ts` | NodeStatus, WorkflowNodeData, RunEvent types | VERIFIED | Exists |

### Plan 04-05 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/data/workflow_templates/morning_digest.json` | 5 nodes, schema_version 1.0 | VERIFIED | 5 nodes (cron trigger → email.fetch → condition → agent → telegram), correct edges |
| `backend/data/workflow_templates/alert.json` | 5 nodes, schema_version 1.0 | VERIFIED | 5 nodes (webhook → keyword_match → condition → create_task → telegram), correct edges |
| `backend/alembic/versions/011_phase4_workflow_templates.py` | Inserts both templates as is_template=true, owner_user_id=NULL | VERIFIED | ON CONFLICT DO NOTHING; owner_user_id=NULL in INSERT |
| `frontend/src/components/canvas/TemplateCard.tsx` | Use Template → copy API → navigate | VERIFIED | POST .../copy → router.push(/workflows/{newId}); loading + error states |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/api/routes/workflows.py` | `backend/main.py` | `app.include_router(workflows_router)` | WIRED | Confirmed on line 114 |
| `backend/api/routes/webhooks.py` | `backend/main.py` | `app.include_router(webhooks_router)` | WIRED | Confirmed on line 118 |
| `backend/agents/graphs.py` | `backend/agents/node_handlers.py` | `from agents.node_handlers import get_handler` | WIRED | Line 27 confirmed |
| `hitl_approval_node handler` | `langgraph.types.interrupt()` | `from langgraph.types import interrupt; interrupt(...)` | WIRED | Lines 164-175 in node_handlers.py |
| `workflow_execution.py` | `compile_workflow_to_stategraph` | `from agents.graphs import compile_workflow_to_stategraph` | WIRED | Line 35 |
| `workflow_execution.py` | `Redis pub/sub` via `publish_event(run_id_str, ...)` | `workflow:events:{run_id}` channel | WIRED | publish_event called on all node events |
| `GET /runs/{run_id}/events` | `Redis pub/sub subscribe` | `subscribe_events(run_id_str)` | WIRED | Line 401 in workflows.py |
| `use-workflow-run.ts` | `workflow-canvas.tsx` | `nodeStatuses` prop passed | WIRED | canvas-editor.tsx passes nodeStatuses={nodeStatuses} |
| `TemplateCard Use Template` | `POST /api/workflows/templates/{id}/copy` | `fetch('/api/workflows/templates/{id}/copy', {method: 'POST'})` | WIRED | Line 36-39 in TemplateCard.tsx |
| `webhooks.py` | `execute_workflow_task.delay()` | should call after creating WorkflowRun | NOT WIRED | Missing — webhook run created but never enqueued |
| `morning_digest.json condition edge` | `compiler add_conditional_edges` | `edge["data"]["branch"] == "true"` | NOT WIRED | Template uses `"sourceHandle": "true"` at top level; compiler checks `edge.get("data", {}).get("branch")` |

---

## Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| WKFL-01 | 04-01, 04-04 | User can build workflows by dragging and dropping nodes | SATISFIED | WorkflowCanvas onDrop creates nodes; NodePalette has 6 draggable entries; all node types render with status rings |
| WKFL-02 | 04-02, 04-03 | Canvas workflows compile to LangGraph StateGraphs and execute end-to-end | SATISFIED | compile_workflow_to_stategraph() + execute_workflow Celery task + astream_events loop |
| WKFL-03 | 04-05 | Morning digest workflow template available | SATISFIED | morning_digest.json exists; migration 011 inserts it; TemplateCard copies it |
| WKFL-04 | 04-05 | Alert workflow template available | SATISFIED | alert.json exists; migration 011 inserts it; TemplateCard copies it |
| WKFL-05 | 04-04 | HITL approval nodes pause and wait for human input | SATISFIED | interrupt() in hitl_approval_node; AsyncPostgresSaver persists; approve/reject API resumes; Approve/Reject buttons in UI |
| WKFL-06 | 04-03 | Cron schedule triggers | SATISFIED | fire_cron_triggers_task in celery_app beat_schedule; croniter evaluates expressions |
| WKFL-07 | 04-03 | Webhook triggers fire execution | BLOCKED | webhooks.py creates WorkflowRun but does not call execute_workflow_task.delay() — webhook triggers don't actually execute workflows |
| WKFL-08 | 04-01, 04-02 | schema_version on every workflow definition_json | SATISFIED | WorkflowCreate validator enforces schema_version == "1.0"; compile_workflow_to_stategraph raises ValueError if wrong |
| WKFL-09 | 04-05 | Pre-built workflow templates available | SATISFIED | 2 templates seeded via migration 011; TemplateCard gallery on /workflows |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/api/routes/webhooks.py` | 62 | `# Execution is wired in plan 04-03` comment with no wiring | BLOCKER | Webhook-triggered workflows create a run record but never execute — the run stays in `pending` status forever |
| `backend/agents/node_handlers.py` | 55, 65 | `# Stub — 04-03 wires real dispatch` in agent_node (channel_output_node has similar) | WARNING | agent_node still returns a stub result — real sub-agent dispatch was not wired in 04-03. The plan doc scoped this as acceptable for now (04-03 only wired tool_node). channel_output_node is also still a stub. These are known limitations, not new gaps. |

---

## Human Verification Required

### 1. Canvas Drag-and-Drop Full Flow

**Test:** Open `/workflows/new`, drag nodes from the left palette onto the canvas, connect them with edges, click Save, and verify the definition_json is persisted to the database.
**Expected:** Nodes appear at drop position; edges connect when dragging between handles; Save button calls PUT /api/workflows/{id}; topology is persisted.
**Why human:** Drop position calculation, ReactFlow edge rendering, and debounced save behavior require browser interaction.

### 2. HITL Approval Flow (End-to-End)

**Test:** Create a 2-node workflow (trigger → hitl_approval_node), click Run, observe node status ring turns amber and Approve/Reject buttons appear, click Approve, observe node turns green.
**Expected:** SSE events update node status rings in real time; HITL banner appears with message; Approve resumes execution via aupdate_state(); node rings turn green on completion.
**Why human:** Requires a running Celery worker, Redis, and PostgreSQL with the LangGraph checkpoint tables created. Visual status ring transitions cannot be verified programmatically.

### 3. Template Gallery Navigation

**Test:** Navigate to `/workflows`, observe Morning Digest and Alert template cards, click "Use Template" on one, observe redirect to `/workflows/{newId}` canvas editor.
**Expected:** Template gallery shows both pre-built templates; clicking "Use template" copies the workflow and navigates to the new canvas.
**Why human:** Requires running database with migration 011 applied; navigation behavior needs browser verification.

### 4. Condition Routing at Runtime

**Test:** Copy the Morning Digest template, trigger execution with a mock email tool returning `{"count": 0}`, verify the graph does NOT proceed to the agent_node (false branch goes to END). Then trigger with `{"count": 5}` and verify it DOES reach agent_node.
**Why human:** The condition edge routing gap (sourceHandle vs data.branch) means this may fail. This test distinguishes whether the gap actually causes incorrect behavior or whether the fallback to plain_edges accidentally routes correctly.

---

## Gaps Summary

Two gaps block full goal achievement:

**Gap 1 — WKFL-07 (Webhook Execution): Critical** — The webhook endpoint (`backend/api/routes/webhooks.py`) was supposed to enqueue `execute_workflow_task` after creating the `WorkflowRun` row. The code has a comment "Execution is wired in plan 04-03" but the 04-03 plan only wired the `/run` manual trigger endpoint and the SSE events endpoint. The webhooks router was never updated to call `execute_workflow_task.delay(str(run.id))`. One line of code is missing; the fix is straightforward.

**Gap 2 — Condition edge routing for template JSON (Partial WKFL-02/WKFL-03/WKFL-04):** The compiler (`graphs.py`) uses `edge.get("data", {}).get("branch")` to detect conditional branches. The actual template JSON files (`morning_digest.json`, `alert.json`) use the React Flow native format `"sourceHandle": "true"` at the edge's top level. When a user copies a template and runs it, the condition_node's edge to the true branch will be treated as a plain edge, breaking the conditional routing. The test suite uses in-test fixtures with the correct `data.branch` format, so no test catches this mismatch. Fix: update the compiler to also check `edge.get("sourceHandle")` as a fallback, or update both template JSON files to use the `data.branch` format the compiler expects.

These two gaps are independent (same root cause class: plan implementation missed a step). They do not affect each other. The rest of Phase 4 — CRUD API, compiler core, HITL persistence, SSE streaming, canvas UI, cron triggers, and template gallery — is fully implemented and wired.

**Backend test suite: 254 passed, 0 failed** (verified at time of inspection)

---

_Verified: 2026-02-27T05:15:00Z_
_Verifier: Claude (gsd-verifier)_
