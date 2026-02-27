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
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { TriggerNode }       from "./nodes/trigger-node";
import { AgentNode }         from "./nodes/agent-node";
import { ToolNode }          from "./nodes/tool-node";
import { ConditionNode }     from "./nodes/condition-node";
import { HitlApprovalNode }  from "./nodes/hitl-approval-node";
import { ChannelOutputNode } from "./nodes/channel-output-node";
import type { NodeStatus }   from "@/hooks/use-workflow-run";

const NODE_TYPES = {
  trigger_node:        TriggerNode,
  agent_node:          AgentNode,
  tool_node:           ToolNode,
  condition_node:      ConditionNode,
  hitl_approval_node:  HitlApprovalNode,
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
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync node statuses into node data whenever they change
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
        y: event.clientY - rect.top - 40,
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
