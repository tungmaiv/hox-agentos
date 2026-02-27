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
        Approval
      </p>
      <p className="text-sm font-medium text-gray-800">
        {d.label ?? "Approval Required"}
      </p>
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
