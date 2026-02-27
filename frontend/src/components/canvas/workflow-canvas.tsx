"use client";
/**
 * WorkflowCanvas — React Flow canvas shell.
 *
 * This is the canvas editor shell for Phase 4. Execution wiring and full
 * drag-and-drop node editing comes in plans 04-03 and 04-04.
 *
 * For now: renders an empty ReactFlow canvas with the workflow name in the
 * toolbar, ready for nodes/edges to be populated in subsequent plans.
 */
import { ReactFlow, Background, Controls, MiniMap } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

interface WorkflowDefinition {
  schema_version: "1.0";
  nodes: unknown[];
  edges: unknown[];
}

interface Workflow {
  id: string;
  name: string;
  description: string | null;
  definition_json: WorkflowDefinition;
}

interface WorkflowCanvasProps {
  workflow: Workflow;
}

export function WorkflowCanvas({ workflow }: WorkflowCanvasProps) {
  const nodeCount = workflow.definition_json.nodes.length;
  const edgeCount = workflow.definition_json.edges.length;

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b bg-white shadow-sm">
        <div>
          <h1 className="font-semibold text-gray-900">{workflow.name}</h1>
          {workflow.description && (
            <p className="text-xs text-gray-500">{workflow.description}</p>
          )}
        </div>
        <span className="text-xs text-gray-400">
          {nodeCount} nodes &middot; {edgeCount} edges &middot; Canvas wiring in 04-03
        </span>
      </div>

      {/* Canvas */}
      <div className="flex-1">
        <ReactFlow
          nodes={[]}
          edges={[]}
          fitView
        >
          <Background />
          <Controls />
          <MiniMap />
        </ReactFlow>
      </div>
    </div>
  );
}
