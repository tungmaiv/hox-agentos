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
        Agent
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
