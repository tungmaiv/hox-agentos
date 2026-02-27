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
        Trigger
      </p>
      <p className="text-sm font-medium text-gray-800">{d.label ?? "Trigger"}</p>
      <p className="text-xs text-gray-400 mt-1">
        {config.trigger_type === "cron"
          ? `Cron: ${config.cron_expression ?? "schedule"}`
          : "Webhook"}
      </p>
      <Handle type="source" position={Position.Bottom} />
    </NodeStatusRing>
  );
}
