/**
 * Shared types for the workflow canvas and execution engine.
 *
 * NodeStatus drives the visual status ring on each canvas node.
 * RunEvent is the shape of SSE messages from /api/workflows/runs/{id}/events.
 */

export type NodeStatus =
  | "idle"
  | "running"
  | "completed"
  | "failed"
  | "awaiting_approval";

export interface WorkflowNodeData {
  label: string;
  nodeType: string;
  config: Record<string, unknown>;
  status?: NodeStatus;
}

export type WorkflowEdgeData = Record<string, unknown>;

export interface RunEvent {
  event: string;
  node_id?: string;
  output?: unknown;
  message?: string;
  error?: string;
}
