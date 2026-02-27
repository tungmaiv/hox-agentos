# Phase 4 — Plan 04-04: HITL Approval + Canvas UI

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the `MemorySaver` stub with `AsyncPostgresSaver` for real HITL pause/resume, then build the complete canvas UI — node renderers with status rings, `WorkflowCanvas`, `NodePalette`, `RunControls`, and the client hooks that drive them.

**Architecture:** Backend: `AsyncPostgresSaver` persists graph state to PostgreSQL so a paused workflow can be resumed in a new Celery worker process. Resume injects `hitl_result` into the saved state via `aupdate_state()` before re-invoking the graph. Frontend: `use-workflow-run` subscribes to the SSE stream and maintains a `Map<node_id, NodeStatus>` that all node renderers read. `hitl_approval_node` renders Approve/Reject buttons when its status is `awaiting_approval`. `NodePalette` is a drag source; `WorkflowCanvas` handles drop to create new nodes.

**Tech Stack:** `langgraph-checkpoint-postgres`, `psycopg[binary]`, `@xyflow/react`, React 19, Tailwind v4.

---

## Task 1: AsyncPostgresSaver — Real HITL Persistence

**Files:**
- Modify: `backend/scheduler/tasks/workflow_execution.py`
- Test: `backend/tests/scheduler/test_hitl_resume.py`

**Step 1: Install dependencies**

```bash
cd backend && uv add langgraph-checkpoint-postgres "psycopg[binary]"
```

**Step 2: Write failing test**

```python
# backend/tests/scheduler/test_hitl_resume.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4


@pytest.mark.asyncio
async def test_execute_workflow_with_hitl_result_calls_update_state():
    """
    When hitl_result is not None (resume path), the execution task must:
    1. Re-compile the graph with AsyncPostgresSaver
    2. Call aupdate_state() to inject hitl_result into saved checkpoint
    3. Re-invoke the graph with None input (continues from checkpoint)
    """
    run_id = str(uuid4())

    mock_run = MagicMock()
    mock_run.id = uuid4()
    mock_run.workflow_id = uuid4()
    mock_run.owner_user_id = uuid4()
    mock_run.status = "paused_hitl"
    mock_run.checkpoint_id = run_id

    mock_workflow = MagicMock()
    mock_workflow.definition_json = {
        "schema_version": "1.0",
        "nodes": [],
        "edges": [],
    }

    mock_compiled = AsyncMock()
    mock_compiled.aupdate_state = AsyncMock()
    mock_compiled.astream_events = AsyncMock(return_value=_aiter([]))

    mock_checkpointer = AsyncMock()
    mock_checkpointer.__aenter__ = AsyncMock(return_value=mock_checkpointer)
    mock_checkpointer.__aexit__ = AsyncMock(return_value=False)

    with patch("scheduler.tasks.workflow_execution.async_session") as mock_sf, \
         patch("scheduler.tasks.workflow_execution.compile_workflow_to_stategraph") as mock_compile, \
         patch("scheduler.tasks.workflow_execution.AsyncPostgresSaver") as mock_pg_cls, \
         patch("scheduler.tasks.workflow_execution.publish_event"):

        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_workflow)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),
        ])
        mock_session.commit = AsyncMock()

        mock_builder = MagicMock()
        mock_builder.compile = MagicMock(return_value=mock_compiled)
        mock_compile.return_value = mock_builder
        mock_pg_cls.from_conn_string = MagicMock(return_value=mock_checkpointer)

        from scheduler.tasks.workflow_execution import execute_workflow
        await execute_workflow(run_id, hitl_result="approved")

        # aupdate_state must be called with hitl_result="approved"
        mock_compiled.aupdate_state.assert_called_once()
        update_call_args = mock_compiled.aupdate_state.call_args
        updated_state = update_call_args[0][1]  # second positional arg is the state dict
        assert updated_state.get("hitl_result") == "approved"


async def _aiter(items):
    for item in items:
        yield item
```

**Step 3: Run to verify it fails**

```bash
cd backend && .venv/bin/pytest tests/scheduler/test_hitl_resume.py -v
```
Expected: FAIL — `aupdate_state` never called (MemorySaver path doesn't do this)

**Step 4: Update `execute_workflow` in `backend/scheduler/tasks/workflow_execution.py`**

Replace the checkpointer section (the `# TODO(04-04)` block) with:

```python
# ── 4. Attach checkpointer and execute ────────────────────────────────────────
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from core.config import get_settings

_settings = get_settings()
# AsyncPostgresSaver uses psycopg3 — strip the +asyncpg driver prefix
pg_conn_str = _settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

async with AsyncPostgresSaver.from_conn_string(pg_conn_str) as checkpointer:
    await checkpointer.setup()  # creates LangGraph checkpoint tables if not exist
    compiled = builder.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": run_id_str}}

    if hitl_result is not None:
        # Resume path: inject hitl_result into the saved checkpoint state
        await compiled.aupdate_state(config, {"hitl_result": hitl_result})
        input_state = None  # graph resumes from the saved checkpoint
    else:
        # Fresh execution
        input_state = initial_state

    final_output: Any = None

    try:
        async for event in compiled.astream_events(input_state, config=config, version="v1"):
            # ... (rest of event handling — unchanged from 04-03)
```

**Important:** The `async with AsyncPostgresSaver.from_conn_string(...)` block must wrap the entire `astream_events` loop and the error handler. Move the existing `final_output`, `try/except` block inside the `async with` block.

**Step 5: Run test**

```bash
cd backend && .venv/bin/pytest tests/scheduler/test_hitl_resume.py -v
```
Expected: PASS

**Step 6: Run full backend test suite to check for regressions**

```bash
cd backend && .venv/bin/pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: All tests pass.

**Step 7: Commit**

```bash
git add backend/scheduler/tasks/workflow_execution.py backend/tests/scheduler/test_hitl_resume.py
git commit -m "feat(04-04): replace MemorySaver with AsyncPostgresSaver for HITL persistence"
```

---

## Task 2: Frontend Hooks

**Files:**
- Create: `frontend/src/hooks/use-workflow-run.ts`
- Create: `frontend/src/hooks/use-pending-hitl.ts`

No tests for hooks (browser-only APIs). Verify by running `pnpm run build` after each file.

### `use-workflow-run.ts`

`frontend/src/hooks/use-workflow-run.ts`:

```typescript
"use client";

import { useState, useCallback, useRef, useEffect } from "react";

export type NodeStatus =
  | "idle"
  | "running"
  | "completed"
  | "failed"
  | "awaiting_approval";

export interface WorkflowRunState {
  runId: string | null;
  isRunning: boolean;
  nodeStatuses: Map<string, NodeStatus>;
  pendingHitlNodeId: string | null;
  hitlMessage: string | null;
  error: string | null;
}

export interface WorkflowRunActions {
  startRun: () => Promise<void>;
  approve: () => Promise<void>;
  reject: () => Promise<void>;
  reset: () => void;
}

const INITIAL_STATE: WorkflowRunState = {
  runId: null,
  isRunning: false,
  nodeStatuses: new Map(),
  pendingHitlNodeId: null,
  hitlMessage: null,
  error: null,
};

export function useWorkflowRun(
  workflowId: string
): WorkflowRunState & WorkflowRunActions {
  const [state, setState] = useState<WorkflowRunState>(INITIAL_STATE);
  const esRef = useRef<EventSource | null>(null);

  // Clean up EventSource on unmount
  useEffect(() => {
    return () => {
      esRef.current?.close();
    };
  }, []);

  const _subscribeToRun = useCallback((runId: string) => {
    esRef.current?.close();
    const es = new EventSource(`/api/workflows/runs/${runId}/events`);
    esRef.current = es;

    es.onmessage = (e: MessageEvent<string>) => {
      let event: Record<string, unknown>;
      try {
        event = JSON.parse(e.data) as Record<string, unknown>;
      } catch {
        return;
      }

      const eventType = event.event as string;
      const nodeId = event.node_id as string | undefined;

      setState((prev) => {
        const next: WorkflowRunState = { ...prev, nodeStatuses: new Map(prev.nodeStatuses) };

        switch (eventType) {
          case "node_started":
            if (nodeId) next.nodeStatuses.set(nodeId, "running");
            break;

          case "node_completed":
            if (nodeId) next.nodeStatuses.set(nodeId, "completed");
            break;

          case "hitl_paused":
            if (nodeId) next.nodeStatuses.set(nodeId, "awaiting_approval");
            next.pendingHitlNodeId = nodeId ?? null;
            next.hitlMessage = (event.message as string) ?? "Approval required";
            next.isRunning = false;
            break;

          case "workflow_completed":
            next.isRunning = false;
            es.close();
            break;

          case "workflow_failed":
            next.isRunning = false;
            next.error = (event.error as string) ?? "Workflow failed";
            es.close();
            break;

          case "workflow_rejected":
            next.isRunning = false;
            es.close();
            break;
        }

        return next;
      });
    };

    es.onerror = () => {
      setState((prev) => ({ ...prev, isRunning: false }));
      es.close();
    };
  }, []);

  const startRun = useCallback(async () => {
    setState({
      ...INITIAL_STATE,
      isRunning: true,
    });

    const res = await fetch(`/api/workflows/${workflowId}/run`, {
      method: "POST",
    });

    if (!res.ok) {
      setState((prev) => ({
        ...prev,
        isRunning: false,
        error: `Failed to start run: ${res.status}`,
      }));
      return;
    }

    const data = (await res.json()) as { id: string };
    setState((prev) => ({ ...prev, runId: data.id }));
    _subscribeToRun(data.id);
  }, [workflowId, _subscribeToRun]);

  const approve = useCallback(async () => {
    if (!state.runId) return;
    setState((prev) => ({
      ...prev,
      isRunning: true,
      pendingHitlNodeId: null,
      hitlMessage: null,
    }));
    await fetch(`/api/workflows/runs/${state.runId}/approve`, { method: "POST" });
    _subscribeToRun(state.runId);
  }, [state.runId, _subscribeToRun]);

  const reject = useCallback(async () => {
    if (!state.runId) return;
    await fetch(`/api/workflows/runs/${state.runId}/reject`, { method: "POST" });
    setState((prev) => ({
      ...prev,
      isRunning: false,
      pendingHitlNodeId: null,
      hitlMessage: null,
    }));
  }, [state.runId]);

  const reset = useCallback(() => {
    esRef.current?.close();
    setState(INITIAL_STATE);
  }, []);

  return { ...state, startRun, approve, reject, reset };
}
```

### `use-pending-hitl.ts`

`frontend/src/hooks/use-pending-hitl.ts`:

```typescript
"use client";

import { useEffect, useState } from "react";

/**
 * Polls /api/workflows/runs/pending-hitl every `intervalMs` milliseconds.
 * Returns the count of workflow runs currently waiting for human approval.
 * Used to show a badge in the navigation.
 */
export function usePendingHitl(intervalMs = 30_000): number {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const res = await fetch("/api/workflows/runs/pending-hitl");
        if (res.ok && !cancelled) {
          const data = (await res.json()) as { count: number };
          setCount(data.count);
        }
      } catch {
        // Network error — keep previous count
      }
    };

    poll();
    const id = setInterval(poll, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [intervalMs]);

  return count;
}
```

**Build check:**

```bash
cd frontend && pnpm run build 2>&1 | grep -E "error|Error|✓" | tail -10
```
Expected: ✓ Compiled successfully (no TypeScript errors)

**Commit:**

```bash
git add frontend/src/hooks/use-workflow-run.ts frontend/src/hooks/use-pending-hitl.ts
git commit -m "feat(04-04): add use-workflow-run and use-pending-hitl hooks"
```

---

## Task 3: Node Status Ring + Node Renderers

**Files:**
- Create: `frontend/src/components/canvas/nodes/node-status-ring.tsx`
- Create: `frontend/src/components/canvas/nodes/trigger-node.tsx`
- Create: `frontend/src/components/canvas/nodes/agent-node.tsx`
- Create: `frontend/src/components/canvas/nodes/tool-node.tsx`
- Create: `frontend/src/components/canvas/nodes/condition-node.tsx`
- Create: `frontend/src/components/canvas/nodes/hitl-approval-node.tsx`
- Create: `frontend/src/components/canvas/nodes/channel-output-node.tsx`

### Step 1: Node status ring

`frontend/src/components/canvas/nodes/node-status-ring.tsx`:

```typescript
import type { NodeStatus } from "@/hooks/use-workflow-run";

const RING: Record<NodeStatus, string> = {
  idle:              "border-gray-200 bg-white",
  running:           "border-blue-400 bg-blue-50 animate-pulse",
  completed:         "border-green-500 bg-green-50",
  failed:            "border-red-500 bg-red-50",
  awaiting_approval: "border-yellow-400 bg-yellow-50",
};

interface Props {
  status: NodeStatus;
  children: React.ReactNode;
  className?: string;
}

export function NodeStatusRing({ status, children, className = "" }: Props) {
  return (
    <div className={`border-2 rounded-lg p-3 min-w-40 shadow-sm transition-colors ${RING[status]} ${className}`}>
      {children}
    </div>
  );
}
```

### Step 2: Trigger node

`frontend/src/components/canvas/nodes/trigger-node.tsx`:

```typescript
"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { NodeStatusRing } from "./node-status-ring";
import type { NodeStatus } from "@/hooks/use-workflow-run";

interface TriggerConfig {
  trigger_type?: "cron" | "webhook";
  cron_expression?: string;
}

interface TriggerNodeData {
  label?: string;
  status?: NodeStatus;
  config?: TriggerConfig;
}

export function TriggerNode({ data }: NodeProps) {
  const d = data as TriggerNodeData;
  const config = d.config ?? {};
  return (
    <NodeStatusRing status={d.status ?? "idle"}>
      <p className="text-[10px] font-semibold text-orange-500 uppercase tracking-wide mb-1">
        ⚡ Trigger
      </p>
      <p className="text-sm font-medium text-gray-800">{d.label ?? "Trigger"}</p>
      <p className="text-xs text-gray-400 mt-1">
        {config.trigger_type === "cron"
          ? `⏰ ${config.cron_expression ?? "schedule"}`
          : "🔗 Webhook"}
      </p>
      <Handle type="source" position={Position.Bottom} />
    </NodeStatusRing>
  );
}
```

### Step 3: Agent node

`frontend/src/components/canvas/nodes/agent-node.tsx`:

```typescript
"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { NodeStatusRing } from "./node-status-ring";
import type { NodeStatus } from "@/hooks/use-workflow-run";

const AGENT_LABELS: Record<string, string> = {
  email_agent:    "Email Agent",
  calendar_agent: "Calendar Agent",
  project_agent:  "Project Agent",
};

interface AgentNodeData {
  label?: string;
  status?: NodeStatus;
  config?: { agent?: string; instruction?: string };
}

export function AgentNode({ data }: NodeProps) {
  const d = data as AgentNodeData;
  const agentName = d.config?.agent ?? "email_agent";
  return (
    <NodeStatusRing status={d.status ?? "idle"}>
      <Handle type="target" position={Position.Top} />
      <p className="text-[10px] font-semibold text-blue-500 uppercase tracking-wide mb-1">
        🤖 Agent
      </p>
      <p className="text-sm font-medium text-gray-800">
        {d.label ?? AGENT_LABELS[agentName] ?? agentName}
      </p>
      {d.config?.instruction && (
        <p className="text-xs text-gray-400 mt-1 truncate max-w-36">
          {d.config.instruction}
        </p>
      )}
      <Handle type="source" position={Position.Bottom} />
    </NodeStatusRing>
  );
}
```

### Step 4: Tool node

`frontend/src/components/canvas/nodes/tool-node.tsx`:

```typescript
"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { NodeStatusRing } from "./node-status-ring";
import type { NodeStatus } from "@/hooks/use-workflow-run";

interface ToolNodeData {
  label?: string;
  status?: NodeStatus;
  config?: { tool_name?: string };
}

export function ToolNode({ data }: NodeProps) {
  const d = data as ToolNodeData;
  return (
    <NodeStatusRing status={d.status ?? "idle"}>
      <Handle type="target" position={Position.Top} />
      <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
        🔧 Tool
      </p>
      <p className="text-sm font-medium text-gray-800">{d.label ?? "Tool"}</p>
      {d.config?.tool_name && (
        <code className="text-xs bg-gray-100 px-1 rounded text-gray-500">
          {d.config.tool_name}
        </code>
      )}
      <Handle type="source" position={Position.Bottom} />
    </NodeStatusRing>
  );
}
```

### Step 5: Condition node

`frontend/src/components/canvas/nodes/condition-node.tsx`:

```typescript
"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { NodeStatusRing } from "./node-status-ring";
import type { NodeStatus } from "@/hooks/use-workflow-run";

interface ConditionNodeData {
  label?: string;
  status?: NodeStatus;
  config?: { expression?: string };
}

export function ConditionNode({ data }: NodeProps) {
  const d = data as ConditionNodeData;
  return (
    <NodeStatusRing status={d.status ?? "idle"}>
      <Handle type="target" position={Position.Top} />
      <p className="text-[10px] font-semibold text-purple-500 uppercase tracking-wide mb-1">
        ◈ Condition
      </p>
      <p className="text-sm font-medium text-gray-800">{d.label ?? "Condition"}</p>
      {d.config?.expression && (
        <code className="text-xs bg-purple-50 text-purple-700 px-1 rounded block mt-1 max-w-36 truncate">
          {d.config.expression}
        </code>
      )}
      {/* Two output handles: true (left) and false (right) */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="true"
        style={{ left: "30%" }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="false"
        style={{ left: "70%" }}
      />
      <div className="flex justify-between text-[10px] text-gray-400 mt-2 px-1">
        <span>true</span>
        <span>false</span>
      </div>
    </NodeStatusRing>
  );
}
```

### Step 6: HITL approval node

`frontend/src/components/canvas/nodes/hitl-approval-node.tsx`:

```typescript
"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { NodeStatusRing } from "./node-status-ring";
import type { NodeStatus } from "@/hooks/use-workflow-run";

interface HitlNodeData {
  label?: string;
  status?: NodeStatus;
  config?: { message?: string };
  onApprove?: () => void;
  onReject?: () => void;
}

export function HitlApprovalNode({ data }: NodeProps) {
  const d = data as HitlNodeData;
  const isAwaiting = d.status === "awaiting_approval";

  return (
    <NodeStatusRing status={d.status ?? "idle"}>
      <Handle type="target" position={Position.Top} />
      <p className="text-[10px] font-semibold text-yellow-600 uppercase tracking-wide mb-1">
        ✋ Approval
      </p>
      <p className="text-sm font-medium text-gray-800">{d.label ?? "Approval Required"}</p>
      {d.config?.message && (
        <p className="text-xs text-gray-500 mt-1 max-w-40">{d.config.message}</p>
      )}
      {isAwaiting && (
        <div className="flex gap-2 mt-3">
          <button
            onClick={d.onApprove}
            className="flex-1 py-1 text-xs font-medium bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
          >
            Approve
          </button>
          <button
            onClick={d.onReject}
            className="flex-1 py-1 text-xs font-medium bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
          >
            Reject
          </button>
        </div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </NodeStatusRing>
  );
}
```

### Step 7: Channel output node

`frontend/src/components/canvas/nodes/channel-output-node.tsx`:

```typescript
"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { NodeStatusRing } from "./node-status-ring";
import type { NodeStatus } from "@/hooks/use-workflow-run";

const CHANNEL_ICON: Record<string, string> = {
  telegram: "✈️",
  teams:    "💼",
  web:      "🌐",
};

interface ChannelOutputNodeData {
  label?: string;
  status?: NodeStatus;
  config?: { channel?: string; template?: string };
}

export function ChannelOutputNode({ data }: NodeProps) {
  const d = data as ChannelOutputNodeData;
  const channel = d.config?.channel ?? "web";
  return (
    <NodeStatusRing status={d.status ?? "idle"}>
      <Handle type="target" position={Position.Top} />
      <p className="text-[10px] font-semibold text-green-600 uppercase tracking-wide mb-1">
        {CHANNEL_ICON[channel] ?? "📤"} Output
      </p>
      <p className="text-sm font-medium text-gray-800">{d.label ?? "Send"}</p>
      <p className="text-xs text-gray-400 mt-1 capitalize">{channel}</p>
    </NodeStatusRing>
  );
}
```

**Build check:**

```bash
cd frontend && pnpm run build 2>&1 | grep -E "error TS|Error|✓" | tail -10
```
Expected: ✓ Compiled successfully

**Commit:**

```bash
git add frontend/src/components/canvas/nodes/
git commit -m "feat(04-04): add node status ring and 6 node renderers"
```

---

## Task 4: WorkflowCanvas Component

**Files:**
- Create: `frontend/src/components/canvas/workflow-canvas.tsx`

`frontend/src/components/canvas/workflow-canvas.tsx`:

```typescript
"use client";

import { useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { TriggerNode }      from "./nodes/trigger-node";
import { AgentNode }        from "./nodes/agent-node";
import { ToolNode }         from "./nodes/tool-node";
import { ConditionNode }    from "./nodes/condition-node";
import { HitlApprovalNode } from "./nodes/hitl-approval-node";
import { ChannelOutputNode } from "./nodes/channel-output-node";
import type { NodeStatus }  from "@/hooks/use-workflow-run";

const NODE_TYPES = {
  trigger_node:       TriggerNode,
  agent_node:         AgentNode,
  tool_node:          ToolNode,
  condition_node:     ConditionNode,
  hitl_approval_node: HitlApprovalNode,
  channel_output_node: ChannelOutputNode,
} as const;

interface WorkflowCanvasProps {
  initialNodes: Node[];
  initialEdges: Edge[];
  nodeStatuses: Map<string, NodeStatus>;
  onApprove: () => void;
  onReject: () => void;
  onSave: (nodes: Node[], edges: Edge[]) => void;
}

export function WorkflowCanvas({
  initialNodes,
  initialEdges,
  nodeStatuses,
  onApprove,
  onReject,
  onSave,
}: WorkflowCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(
    _injectStatus(initialNodes, nodeStatuses, onApprove, onReject)
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync node statuses into node data whenever they change
  // (useEffect would cause a re-render loop with useNodesState — update on every render is fine
  // because Map comparison is referential and React Flow batches updates)
  const nodesWithStatus = nodes.map((n) => ({
    ...n,
    data: {
      ...n.data,
      status: nodeStatuses.get(n.id) ?? ("idle" as NodeStatus),
      onApprove: n.type === "hitl_approval_node" ? onApprove : undefined,
      onReject:  n.type === "hitl_approval_node" ? onReject  : undefined,
    },
  }));

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges]
  );

  // Drag-and-drop: accept drops from NodePalette
  const onDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      const nodeType = event.dataTransfer.getData("application/reactflow");
      if (!nodeType) return;

      // Approximate canvas position from drop coordinates
      const rect = event.currentTarget.getBoundingClientRect();
      const position = {
        x: event.clientX - rect.left - 80,
        y: event.clientY - rect.top  - 40,
      };

      const newNode: Node = {
        id: crypto.randomUUID(),
        type: nodeType,
        position,
        data: {
          label: _defaultLabel(nodeType),
          config: {},
          status: "idle" as NodeStatus,
        },
      };
      setNodes((nds) => nds.concat(newNode));
    },
    [setNodes]
  );

  const handleSave = useCallback(() => {
    onSave(nodes, edges);
  }, [nodes, edges, onSave]);

  return (
    <div className="w-full h-full relative">
      <ReactFlow
        nodes={nodesWithStatus}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onDrop={onDrop}
        onDragOver={onDragOver}
        nodeTypes={NODE_TYPES}
        fitView
        deleteKeyCode="Backspace"
      >
        <Background gap={16} color="#e5e7eb" />
        <Controls />
        <MiniMap nodeStrokeWidth={2} zoomable pannable />
      </ReactFlow>

      {/* Save button — positioned bottom-right inside the canvas */}
      <button
        onClick={handleSave}
        className="absolute bottom-4 right-4 px-3 py-1.5 text-sm bg-white border border-gray-300 rounded shadow hover:bg-gray-50 transition-colors z-10"
      >
        Save
      </button>
    </div>
  );
}

function _injectStatus(
  nodes: Node[],
  statuses: Map<string, NodeStatus>,
  onApprove: () => void,
  onReject: () => void
): Node[] {
  return nodes.map((n) => ({
    ...n,
    data: {
      ...n.data,
      status: statuses.get(n.id) ?? ("idle" as NodeStatus),
      onApprove: n.type === "hitl_approval_node" ? onApprove : undefined,
      onReject:  n.type === "hitl_approval_node" ? onReject  : undefined,
    },
  }));
}

function _defaultLabel(nodeType: string): string {
  const labels: Record<string, string> = {
    trigger_node:        "Trigger",
    agent_node:          "Agent",
    tool_node:           "Tool",
    condition_node:      "Condition",
    hitl_approval_node:  "Approval",
    channel_output_node: "Send",
  };
  return labels[nodeType] ?? nodeType;
}
```

**Build check:**

```bash
cd frontend && pnpm run build 2>&1 | grep -E "error TS|Error|✓" | tail -10
```

**Commit:**

```bash
git add frontend/src/components/canvas/workflow-canvas.tsx
git commit -m "feat(04-04): add WorkflowCanvas with drag-drop and status overlay"
```

---

## Task 5: NodePalette + RunControls

**Files:**
- Create: `frontend/src/components/canvas/node-palette.tsx`
- Create: `frontend/src/components/canvas/run-controls.tsx`

### NodePalette

`frontend/src/components/canvas/node-palette.tsx`:

```typescript
"use client";

import type { DragEvent } from "react";

interface PaletteItem {
  type: string;
  label: string;
  icon: string;
  color: string;
}

const PALETTE: PaletteItem[] = [
  { type: "trigger_node",        label: "Trigger",    icon: "⚡", color: "bg-orange-50 border-orange-200 hover:border-orange-400" },
  { type: "agent_node",          label: "Agent",      icon: "🤖", color: "bg-blue-50 border-blue-200 hover:border-blue-400" },
  { type: "tool_node",           label: "Tool",       icon: "🔧", color: "bg-gray-50 border-gray-200 hover:border-gray-400" },
  { type: "condition_node",      label: "Condition",  icon: "◈",  color: "bg-purple-50 border-purple-200 hover:border-purple-400" },
  { type: "hitl_approval_node",  label: "Approval",   icon: "✋", color: "bg-yellow-50 border-yellow-200 hover:border-yellow-400" },
  { type: "channel_output_node", label: "Send",       icon: "📤", color: "bg-green-50 border-green-200 hover:border-green-400" },
];

function onDragStart(e: DragEvent<HTMLDivElement>, nodeType: string) {
  e.dataTransfer.setData("application/reactflow", nodeType);
  e.dataTransfer.effectAllowed = "move";
}

export function NodePalette() {
  return (
    <div className="w-44 border-r border-gray-100 bg-white p-3 flex flex-col gap-2 overflow-y-auto shrink-0">
      <h3 className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1">
        Nodes
      </h3>
      {PALETTE.map((item) => (
        <div
          key={item.type}
          draggable
          onDragStart={(e) => onDragStart(e, item.type)}
          className={`flex items-center gap-2 px-2 py-2 rounded border cursor-grab active:cursor-grabbing select-none transition-colors ${item.color}`}
        >
          <span className="text-base">{item.icon}</span>
          <span className="text-xs font-medium text-gray-700">{item.label}</span>
        </div>
      ))}
    </div>
  );
}
```

### RunControls

`frontend/src/components/canvas/run-controls.tsx`:

```typescript
"use client";

interface RunControlsProps {
  isRunning: boolean;
  onRun: () => void;
}

export function RunControls({ isRunning, onRun }: RunControlsProps) {
  return (
    <button
      onClick={onRun}
      disabled={isRunning}
      className={`
        px-4 py-1.5 rounded text-sm font-medium transition-colors
        ${isRunning
          ? "bg-gray-200 text-gray-400 cursor-not-allowed"
          : "bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800"
        }
      `}
    >
      {isRunning ? (
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
          Running…
        </span>
      ) : (
        "▶ Run"
      )}
    </button>
  );
}
```

**Build check:**

```bash
cd frontend && pnpm run build 2>&1 | grep -E "error TS|Error|✓" | tail -10
```

**Commit:**

```bash
git add frontend/src/components/canvas/node-palette.tsx frontend/src/components/canvas/run-controls.tsx
git commit -m "feat(04-04): add NodePalette and RunControls components"
```

---

## Task 6: Wire Canvas Editor

**Files:**
- Modify: `frontend/src/app/workflows/[id]/canvas-editor.tsx`

Replace the placeholder shell created in 04-01 with the full implementation.

`frontend/src/app/workflows/[id]/canvas-editor.tsx`:

```typescript
"use client";

import { useCallback } from "react";
import type { Node, Edge } from "@xyflow/react";
import { WorkflowCanvas } from "@/components/canvas/workflow-canvas";
import { NodePalette }    from "@/components/canvas/node-palette";
import { RunControls }    from "@/components/canvas/run-controls";
import { useWorkflowRun } from "@/hooks/use-workflow-run";
import Link from "next/link";

interface WorkflowDefinition {
  schema_version: "1.0";
  nodes: unknown[];
  edges: unknown[];
}

interface Workflow {
  id: string;
  name: string;
  definition_json: WorkflowDefinition;
}

export function CanvasEditor({ workflow }: { workflow: Workflow }) {
  const {
    isRunning,
    nodeStatuses,
    pendingHitlNodeId,
    hitlMessage,
    error,
    startRun,
    approve,
    reject,
  } = useWorkflowRun(workflow.id);

  const handleSave = useCallback(
    async (nodes: Node[], edges: Edge[]) => {
      await fetch(`/api/workflows/${workflow.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          definition_json: {
            schema_version: "1.0",
            nodes,
            edges,
          },
        }),
      });
    },
    [workflow.id]
  );

  return (
    <div className="flex flex-col h-screen bg-white">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-100 shrink-0">
        <div className="flex items-center gap-3">
          <Link
            href="/workflows"
            className="text-gray-400 hover:text-gray-600 text-sm transition-colors"
          >
            ← Workflows
          </Link>
          <span className="text-gray-300">|</span>
          <h1 className="text-sm font-semibold text-gray-800">{workflow.name}</h1>
        </div>
        <RunControls isRunning={isRunning} onRun={startRun} />
      </div>

      {/* HITL banner */}
      {hitlMessage && (
        <div className="flex items-center gap-3 px-4 py-2 bg-yellow-50 border-b border-yellow-200 shrink-0">
          <span className="text-yellow-600 text-sm">⏸ {hitlMessage}</span>
          <button
            onClick={approve}
            className="px-3 py-1 text-xs font-medium bg-green-600 text-white rounded hover:bg-green-700"
          >
            Approve
          </button>
          <button
            onClick={reject}
            className="px-3 py-1 text-xs font-medium bg-red-500 text-white rounded hover:bg-red-600"
          >
            Reject
          </button>
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="px-4 py-2 bg-red-50 border-b border-red-200 shrink-0">
          <span className="text-red-600 text-sm">✗ {error}</span>
        </div>
      )}

      {/* Canvas area */}
      <div className="flex flex-1 overflow-hidden">
        <NodePalette />
        <div className="flex-1">
          <WorkflowCanvas
            initialNodes={workflow.definition_json.nodes as Node[]}
            initialEdges={workflow.definition_json.edges as Edge[]}
            nodeStatuses={nodeStatuses}
            onApprove={approve}
            onReject={reject}
            onSave={handleSave}
          />
        </div>
      </div>
    </div>
  );
}
```

**Build check:**

```bash
cd frontend && pnpm run build 2>&1 | grep -E "error TS|Error|✓" | tail -10
```
Expected: ✓ Compiled successfully

**Commit:**

```bash
git add frontend/src/app/workflows/[id]/canvas-editor.tsx
git commit -m "feat(04-04): wire canvas editor with hooks, palette, and run controls"
```

---

## Task 7: Pending-HITL Badge in Navigation

**Files:**
- Modify: `frontend/src/app/workflows/page.tsx`

Add a pending-HITL indicator on the workflow list page. The count is shown next to the "Workflows" heading so users know when approvals are waiting.

Add a `PendingBadge` client component to the top of the file and use it in the page:

`frontend/src/app/workflows/_pending-badge.tsx` (new file — Client Component):

```typescript
"use client";

import { usePendingHitl } from "@/hooks/use-pending-hitl";

export function PendingBadge() {
  const count = usePendingHitl();
  if (count === 0) return null;
  return (
    <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
      {count} pending
    </span>
  );
}
```

In `frontend/src/app/workflows/page.tsx`, import and use it:

```typescript
// Add this import at the top:
import { PendingBadge } from "./_pending-badge";

// Update the heading section from:
<h1 className="text-2xl font-bold">Workflows</h1>

// To:
<div className="flex items-center">
  <h1 className="text-2xl font-bold">Workflows</h1>
  <PendingBadge />
</div>
```

**Build check:**

```bash
cd frontend && pnpm run build 2>&1 | grep -E "error TS|Error|✓" | tail -10
```

**Commit:**

```bash
git add frontend/src/app/workflows/_pending-badge.tsx frontend/src/app/workflows/page.tsx
git commit -m "feat(04-04): add pending HITL badge to workflow list page"
```

---

## Task 8: Full Test Run + Build Verification

**Step 1: Run all backend tests**

```bash
cd backend && .venv/bin/pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: All tests pass, 0 failures.

**Step 2: Frontend production build**

```bash
cd frontend && pnpm run build
```
Expected: ✓ Compiled successfully, 0 TypeScript errors.

**Common issues and fixes:**

**`Module not found: @xyflow/react`**
```bash
cd frontend && pnpm add @xyflow/react
```

**`Type 'NodeProps' has no properties in common with type...`**
`@xyflow/react` v12 changed `NodeProps`. Use `data: NodeProps["data"]` or type the data field explicitly as done above.

**`Cannot use 'import.meta' outside a module`**
Not applicable here — Next.js 15 handles this transparently.

**`langgraph.checkpoint.postgres.aio` import error**
```bash
cd backend && uv add langgraph-checkpoint-postgres "psycopg[binary]"
```
If the import path changed in a newer LangGraph version, check with:
```bash
cd backend && .venv/bin/python -c "from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver; print('ok')"
```

**Step 3: Final commit**

```bash
git add -A
git status  # verify no unexpected files
git commit -m "fix(04-04): address any issues found in full test run"
```

---

**Plan 04-04 complete.** Delivers:
- `AsyncPostgresSaver` replacing `MemorySaver` — real HITL pause/resume across Celery worker restarts — 1 test
- `use-workflow-run` hook — SSE subscription + node status map + approve/reject
- `use-pending-hitl` hook — 30s polling for nav badge
- `node-status-ring` + 6 node renderers (trigger, agent, tool, condition, hitl-approval, channel-output)
- `WorkflowCanvas` — React Flow wrapper with drag-drop support
- `NodePalette` — drag source for all 6 node types
- `RunControls` — run button with spinner
- Full canvas editor wired (`canvas-editor.tsx`)
- Pending-HITL badge on workflow list page

**Next: Plan 04-05** — Pre-built templates (JSON fixtures + Alembic data migration + template gallery wiring).
