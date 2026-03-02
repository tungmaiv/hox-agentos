---
phase: 04-canvas-and-workflows
plan: "04"
subsystem: ui
tags: [react-flow, langgraph, hitl, sse, canvas, workflow, postgres, psycopg]

# Dependency graph
requires:
  - phase: 04-03
    provides: execute_workflow Celery task, Redis pub/sub SSE, approve/reject API endpoints, MemorySaver stub

provides:
  - AsyncPostgresSaver replaces MemorySaver for cross-process HITL persistence
  - Resume path: aupdate_state() injects hitl_result, ainvoke(None) continues from checkpoint
  - use-workflow-run hook: SSE EventSource subscription, Map<node_id, NodeStatus>
  - use-pending-hitl hook: 30s polling for nav badge count
  - 6 canvas node renderers with status rings (trigger, agent, tool, condition, hitl-approval, channel-output)
  - NodePalette: 6 draggable node entries with dataTransfer
  - WorkflowCanvas: ReactFlow with drag-drop, status overlay, save handler
  - RunControls: run button with spinner
  - CanvasEditor: full canvas editor wired with hooks, HITL/error banners
  - PendingBadge: client component for workflow list page
affects:
  - 04-05 (templates — shares canvas UI components)
  - Phase 5 channels (RunControls/SSE patterns reused)

# Tech tracking
tech-stack:
  added:
    - langgraph-checkpoint-postgres>=3.0.4 (AsyncPostgresSaver)
    - psycopg[binary]>=3.3.3 (psycopg3 for AsyncPostgresSaver)
    - langgraph upgraded 0.4.10 -> 1.0.1 (checkpoint-postgres compatibility)
  patterns:
    - AsyncPostgresSaver.from_conn_string() as async context manager
    - checkpointer.setup() idempotently creates LangGraph checkpoint tables
    - Resume: aupdate_state(config, {hitl_result}) then astream_events(None, config)
    - NodeStatusRing drives visual feedback via Tailwind ring colors
    - useWorkflowRun: EventSource + useState Map<node_id, NodeStatus>
    - WorkflowCanvas receives nodeStatuses prop, injects into node data on each render
    - NodePalette uses dataTransfer "application/reactflow" for drag-drop interop

key-files:
  created:
    - backend/tests/scheduler/test_hitl_resume.py
    - frontend/src/lib/workflow-types.ts
    - frontend/src/hooks/use-workflow-run.ts
    - frontend/src/hooks/use-pending-hitl.ts
    - frontend/src/components/canvas/nodes/node-status-ring.tsx
    - frontend/src/components/canvas/nodes/trigger-node.tsx
    - frontend/src/components/canvas/nodes/agent-node.tsx
    - frontend/src/components/canvas/nodes/tool-node.tsx
    - frontend/src/components/canvas/nodes/condition-node.tsx
    - frontend/src/components/canvas/nodes/hitl-approval-node.tsx
    - frontend/src/components/canvas/nodes/channel-output-node.tsx
    - frontend/src/components/canvas/run-controls.tsx
    - frontend/src/app/workflows/[id]/canvas-editor.tsx
    - frontend/src/app/workflows/_pending-badge.tsx
  modified:
    - backend/scheduler/tasks/workflow_execution.py
    - backend/pyproject.toml
    - backend/uv.lock
    - frontend/src/components/canvas/workflow-canvas.tsx
    - frontend/src/components/canvas/node-palette.tsx
    - frontend/src/app/workflows/[id]/page.tsx
    - frontend/src/app/workflows/page.tsx

key-decisions:
  - "AsyncPostgresSaver.from_conn_string() used as async context manager — setup() called inside to create checkpoint tables idempotently (no separate migration needed)"
  - "pg_conn_str replaces postgresql+asyncpg:// with postgresql:// — psycopg3 does not accept asyncpg-flavored connection strings"
  - "Resume path: aupdate_state(config, {hitl_result}) then ainvoke(None, config) — not astream_events(None) — aligns with LangGraph 1.0 checkpoint resume semantics"
  - "langgraph upgraded 0.4.10->1.0.1 to resolve checkpoint-postgres DeprecationWarning about incompatible versions"
  - "NodeStatus type defined in use-workflow-run.ts (not workflow-types.ts) — nodes import from hook directly; workflow-types.ts provides complementary WorkflowNodeData/RunEvent"
  - "WorkflowCanvas injects nodeStatuses on every render pass (not via useEffect) — avoids re-render loop with useNodesState; Map comparison is referential"
  - "CanvasEditor client component wraps WorkflowCanvas + NodePalette + RunControls — page.tsx remains a pure Server Component fetching data"
  - "HitlApprovalNode receives onApprove/onReject callbacks via data prop — set by WorkflowCanvas when building nodesWithStatus"

patterns-established:
  - "Status ring pattern: border-2 + Tailwind color classes driven by NodeStatus string literal"
  - "EventSource lifecycle: opened in _subscribeToRun(), closed on workflow_completed/failed/unmount"
  - "HITL resume: POST /approve sets isRunning=true, clears pendingHitlNodeId, re-subscribes to SSE"
  - "Node data injection: WorkflowCanvas.nodesWithStatus merges status + callbacks into node.data on render"

requirements-completed:
  - WKFL-01
  - WKFL-05

# Metrics
duration: 8min
completed: 2026-02-27
---

# Phase 04 Plan 04: HITL Approval + Canvas UI Summary

**AsyncPostgresSaver replaces MemorySaver for cross-process HITL persistence, with full canvas UI — 6 node renderers with status rings, drag-drop NodePalette, SSE-driven useWorkflowRun hook, and wired CanvasEditor**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-27T04:27:19Z
- **Completed:** 2026-02-27T04:35:30Z
- **Tasks:** 6 (all complete)
- **Files modified:** 22

## Accomplishments

- AsyncPostgresSaver replaces MemorySaver — HITL graph state persists across Celery worker restarts; resume path injects `hitl_result` via `aupdate_state()` then continues via `ainvoke(None)`
- All 6 canvas node renderers built with colored status rings (gray/blue-pulse/green/red/amber) driven by `NodeStatus` from SSE events; `hitl-approval-node` renders inline Approve/Reject buttons
- Full canvas editor wired: `useWorkflowRun` subscribes to SSE stream and maintains `Map<node_id, NodeStatus>` passed to `WorkflowCanvas`; `NodePalette` drag sources; `RunControls` run button; `CanvasEditor` HITL/error banners

## Task Commits

Each task was committed atomically:

1. **Task 1: Install deps + AsyncPostgresSaver HITL persistence** - `7a679ed` (feat)
2. **Task 2: Frontend deps + TypeScript types** - `a46a810` (feat)
3. **Task 3: use-workflow-run hook + use-pending-hitl hook** - `d966a1b` (feat)
4. **Task 4: All 6 node renderers with status rings** - `6a931c1` (feat)
5. **Task 5: WorkflowCanvas, NodePalette, RunControls + canvas editor** - `9988908` (feat)
6. **Task 6: Full backend suite green** - no new commit (248 passed, 0 failures)

## Files Created/Modified

- `backend/scheduler/tasks/workflow_execution.py` - AsyncPostgresSaver + resume path
- `backend/tests/scheduler/test_hitl_resume.py` - TDD test for HITL resume
- `backend/pyproject.toml` - Added langgraph-checkpoint-postgres, psycopg[binary]
- `backend/uv.lock` - Updated lockfile
- `frontend/src/lib/workflow-types.ts` - NodeStatus, WorkflowNodeData, RunEvent types
- `frontend/src/hooks/use-workflow-run.ts` - EventSource SSE + nodeStatuses Map
- `frontend/src/hooks/use-pending-hitl.ts` - 30s polling for pending HITL count
- `frontend/src/components/canvas/nodes/node-status-ring.tsx` - Status ring component
- `frontend/src/components/canvas/nodes/trigger-node.tsx` - Trigger node renderer
- `frontend/src/components/canvas/nodes/agent-node.tsx` - Agent node renderer
- `frontend/src/components/canvas/nodes/tool-node.tsx` - Tool node renderer
- `frontend/src/components/canvas/nodes/condition-node.tsx` - Condition node with true/false handles
- `frontend/src/components/canvas/nodes/hitl-approval-node.tsx` - HITL node with Approve/Reject buttons
- `frontend/src/components/canvas/nodes/channel-output-node.tsx` - Channel output node renderer
- `frontend/src/components/canvas/workflow-canvas.tsx` - ReactFlow canvas with drag-drop + status overlay
- `frontend/src/components/canvas/node-palette.tsx` - 6 draggable node entries
- `frontend/src/components/canvas/run-controls.tsx` - Run button with spinner
- `frontend/src/app/workflows/[id]/canvas-editor.tsx` - Full canvas editor client component
- `frontend/src/app/workflows/[id]/page.tsx` - Uses CanvasEditor instead of stub
- `frontend/src/app/workflows/_pending-badge.tsx` - Pending HITL count badge
- `frontend/src/app/workflows/page.tsx` - Adds PendingBadge to heading

## Decisions Made

- `pg_conn_str` strips `postgresql+asyncpg://` to `postgresql://` — psycopg3 doesn't accept asyncpg-flavored connection strings
- `langgraph` upgraded from 0.4.10 to 1.0.1 to resolve `DeprecationWarning: incompatible versions of langgraph and checkpoint-postgres`
- `NodeStatus` type lives in `use-workflow-run.ts` (imported by all node components) — workflow-types.ts provides complementary `WorkflowNodeData`/`RunEvent`
- `WorkflowCanvas` syncs `nodeStatuses` on every render (not useEffect) to avoid re-render loops with `useNodesState`
- `HitlApprovalNode` receives `onApprove`/`onReject` via `data` prop — injected by WorkflowCanvas's `nodesWithStatus` mapping

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed DeprecationWarning by upgrading langgraph**
- **Found during:** Task 1 (TDD GREEN phase)
- **Issue:** `langgraph-checkpoint-postgres` 3.0.4 requires langgraph >= 1.0.0; 0.4.10 triggered `DeprecationWarning: incompatible versions`
- **Fix:** Ran `uv add "langgraph>=0.4.11"` which resolved to langgraph 1.0.1
- **Files modified:** backend/pyproject.toml, backend/uv.lock
- **Verification:** Test passed with no deprecation warnings, 248 tests green
- **Committed in:** 7a679ed (Task 1 commit)

**2. [Rule 3 - Blocking] page.tsx broke on WorkflowCanvas signature change**
- **Found during:** Task 5 (build verification)
- **Issue:** page.tsx still imported WorkflowCanvas with old `workflow` prop; new signature uses `initialNodes`, `initialEdges`, etc.
- **Fix:** Created CanvasEditor client component; updated page.tsx to import/use CanvasEditor
- **Files modified:** frontend/src/app/workflows/[id]/page.tsx, canvas-editor.tsx (new)
- **Verification:** pnpm run build: 0 TypeScript errors, /workflows/[id] route 60.5 kB
- **Committed in:** 9988908 (Task 5 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking dependency version, 1 blocking signature mismatch)
**Impact on plan:** Both fixes were necessary and aligned with plan intent. No scope creep.

## Issues Encountered

- `astream_events` AsyncMock coroutine warning in test — harmless; mock returns `_aiter([])` correctly but the unawaited mock body triggers `RuntimeWarning`. Does not affect test correctness.

## User Setup Required

None - no external service configuration required. AsyncPostgresSaver will auto-create LangGraph checkpoint tables on first workflow execution via `checkpointer.setup()`.

## Next Phase Readiness

- HITL persistence: real cross-process pause/resume via PostgreSQL checkpoint tables
- Canvas UI: full interactive editor at `/workflows/[id]` with status rings, drag-drop, and run controls
- Ready for Plan 04-05: Pre-built workflow templates (JSON fixtures + Alembic data migration + template gallery wiring)

## Self-Check: PASSED

All 18 files verified present. All 5 task commits verified in git log.

---
*Phase: 04-canvas-and-workflows*
*Completed: 2026-02-27*
