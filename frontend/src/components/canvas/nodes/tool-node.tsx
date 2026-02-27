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
        Tool
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
