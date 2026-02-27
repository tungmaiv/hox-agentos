"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { NodeStatusRing } from "./node-status-ring";
import type { NodeStatus } from "@/hooks/use-workflow-run";

const CHANNEL_LABEL: Record<string, string> = {
  telegram: "Telegram",
  teams:    "MS Teams",
  web:      "Web",
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
        Output
      </p>
      <p className="text-sm font-medium text-gray-800">{d.label ?? "Send"}</p>
      <p className="text-xs text-gray-400 mt-1">
        {CHANNEL_LABEL[channel] ?? channel}
      </p>
    </NodeStatusRing>
  );
}
