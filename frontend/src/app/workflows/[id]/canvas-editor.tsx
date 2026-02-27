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
            Workflows
          </Link>
          <span className="text-gray-300">|</span>
          <h1 className="text-sm font-semibold text-gray-800">{workflow.name}</h1>
        </div>
        <RunControls isRunning={isRunning} onRun={startRun} />
      </div>

      {/* HITL banner */}
      {hitlMessage && (
        <div className="flex items-center gap-3 px-4 py-2 bg-yellow-50 border-b border-yellow-200 shrink-0">
          <span className="text-yellow-600 text-sm">Paused: {hitlMessage}</span>
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
          <span className="text-red-600 text-sm">Error: {error}</span>
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
