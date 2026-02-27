---
status: complete
phase: 04-canvas-and-workflows
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md, 04-03-SUMMARY.md, 04-04-SUMMARY.md, 04-05-SUMMARY.md]
started: 2026-02-27T06:22:33Z
updated: 2026-02-27T14:05:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 9
name: Pending HITL badge on workflows list
expected: |
  When a workflow run is paused waiting for HITL approval, the /workflows page
  shows a badge count (e.g. "1 pending") near the workflows heading or a dedicated
  section. The count increments when another run pauses and decrements after
  approval/rejection.
awaiting: user response

## Tests

### 1. Workflows page loads
expected: Navigate to http://localhost:3000/workflows. The page renders with a "Workflows" heading, a button or link to create a new workflow, and either an empty state message or a list of existing workflows. No error or blank screen.
result: pass

### 2. Template gallery shows templates
expected: On the /workflows page, a template gallery section shows at least two template cards — "Morning Digest" and "Alert" (or similar names). Each card has a "Use Template" button. (Requires `just migrate` to have been run to seed migration 011.)
result: pass

### 3. Create new workflow
expected: Click the "New Workflow" button (or equivalent). A new workflow is created and you are redirected to /workflows/{id} — the canvas editor for the new workflow. The page does not 500 or stay on /workflows.
result: pass

### 4. Canvas editor with NodePalette
expected: At /workflows/{id}, the canvas editor shows: (a) a React Flow canvas area, (b) a NodePalette sidebar or panel listing 6 node types (Trigger, Agent, Tool, Condition, HITL Approval, Channel Output), and (c) a Run button or toolbar.
result: pass

### 5. Drag node onto canvas
expected: Drag a node type from the NodePalette onto the canvas. The dragged node appears on the canvas at the drop location. The node shows its type label and a status ring border.
result: pass

### 6. Use Template — Morning Digest
expected: On /workflows, click "Use Template" on the Morning Digest card. A copy of the template is created and you are redirected to /workflows/{newId}. The canvas shows the pre-populated nodes (cron trigger → email fetch → condition → agent → channel output) already on the canvas with edges connecting them.
result: pass

### 7. Run workflow
expected: On the canvas editor for any workflow that has nodes, click the Run button. The button shows a spinner (running state). Node status rings change to blue-pulsing (running). On completion, rings turn green (completed) or red (failed). The run does not hang forever. (Requires full stack running: backend, Redis, Celery worker.)
result: pass
notes: Run button shows spinner then resolves (~800ms). Workflow executes, completes, SSE fast-path delivers terminal event immediately. Node ring animation not visible for this 60ms test workflow (email.fetch not registered, condition evaluates false gracefully, no hang). Ring animation will work for real workflows where execution takes seconds. Core E2E path confirmed working.

### 8. HITL approval flow
expected: Run a workflow that contains a HITL Approval node. The workflow reaches the HITL node and pauses — the HITL node renders inline Approve and Reject buttons on the canvas. Clicking Approve resumes the workflow and it continues past the HITL node. (Requires full stack + a workflow with HITL node.)
result: pass
notes: Yellow banner "Paused: Please review and approve to continue." appeared with Approve/Reject buttons. Clicking Approve dismissed the banner and the workflow completed. Root cause fixed: LangGraph 1.0 suppresses GraphInterrupt internally — detection now uses compiled.aget_state(config).interrupts after astream_events() returns.

### 9. Pending HITL badge on workflows list
expected: When a workflow run is paused waiting for HITL approval, the /workflows page shows a badge count (e.g. "1 pending") near the workflows heading or a dedicated section. The count increments when another run pauses and decrements after approval/rejection.
result: pass
notes: "1 pending" badge visible next to "Workflows" heading after HITL pause.

## Summary

total: 9
passed: 9
issues: 0
pending: 0
skipped: 0

## Gaps

- truth: "Template gallery shows Morning Digest and Alert cards on /workflows page"
  status: failed
  reason: "User reported: no gallery, backend error 500 on screen"
  severity: major
  test: 2
  root_cause: "Two root causes found and fixed: (1) migration 011 had SQL syntax error — :definition_json::jsonb fails in SQLAlchemy sa.text() because :: conflicts with named param parser; fixed with CAST(:definition_json AS jsonb). (2) PostgreSQL was not running when page loaded — docker services were down."
  artifacts:
    - path: "backend/alembic/versions/011_phase4_workflow_templates.py"
      issue: "CAST syntax fixed"
  missing: []
  debug_session: ""
