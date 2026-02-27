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
        Condition
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
