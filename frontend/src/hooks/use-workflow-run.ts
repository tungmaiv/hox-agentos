"use client";

import { useState, useCallback, useRef, useEffect } from "react";

export type NodeStatus =
  | "idle"
  | "running"
  | "completed"
  | "failed"
  | "awaiting_approval";

export interface WorkflowRunState {
  runId: string | null;
  isRunning: boolean;
  nodeStatuses: Map<string, NodeStatus>;
  pendingHitlNodeId: string | null;
  hitlMessage: string | null;
  error: string | null;
}

export interface WorkflowRunActions {
  startRun: () => Promise<void>;
  approve: () => Promise<void>;
  reject: () => Promise<void>;
  reset: () => void;
}

const INITIAL_STATE: WorkflowRunState = {
  runId: null,
  isRunning: false,
  nodeStatuses: new Map(),
  pendingHitlNodeId: null,
  hitlMessage: null,
  error: null,
};

export function useWorkflowRun(
  workflowId: string
): WorkflowRunState & WorkflowRunActions {
  const [state, setState] = useState<WorkflowRunState>(INITIAL_STATE);
  const esRef = useRef<EventSource | null>(null);

  // Clean up EventSource on unmount
  useEffect(() => {
    return () => {
      esRef.current?.close();
    };
  }, []);

  const _subscribeToRun = useCallback((runId: string) => {
    esRef.current?.close();
    const es = new EventSource(`/api/workflows/runs/${runId}/events`);
    esRef.current = es;

    es.onmessage = (e: MessageEvent<string>) => {
      let event: Record<string, unknown>;
      try {
        event = JSON.parse(e.data) as Record<string, unknown>;
      } catch {
        return;
      }

      const eventType = event.event as string;
      const nodeId = event.node_id as string | undefined;

      setState((prev) => {
        const next: WorkflowRunState = {
          ...prev,
          nodeStatuses: new Map(prev.nodeStatuses),
        };

        switch (eventType) {
          case "node_started":
            if (nodeId) next.nodeStatuses.set(nodeId, "running");
            break;

          case "node_completed":
            if (nodeId) next.nodeStatuses.set(nodeId, "completed");
            break;

          case "node_failed":
            if (nodeId) next.nodeStatuses.set(nodeId, "failed");
            break;

          case "hitl_paused":
            if (nodeId) next.nodeStatuses.set(nodeId, "awaiting_approval");
            next.pendingHitlNodeId = nodeId ?? null;
            next.hitlMessage = (event.message as string) ?? "Approval required";
            next.isRunning = false;
            break;

          case "workflow_completed":
            next.isRunning = false;
            es.close();
            break;

          case "workflow_failed":
            next.isRunning = false;
            next.error = (event.error as string) ?? "Workflow failed";
            es.close();
            break;

          case "workflow_rejected":
            next.isRunning = false;
            es.close();
            break;
        }

        return next;
      });
    };

    es.onerror = () => {
      setState((prev) => ({ ...prev, isRunning: false }));
      es.close();
    };
  }, []);

  const startRun = useCallback(async () => {
    setState({
      ...INITIAL_STATE,
      isRunning: true,
    });

    const res = await fetch(`/api/workflows/${workflowId}/run`, {
      method: "POST",
    });

    if (!res.ok) {
      setState((prev) => ({
        ...prev,
        isRunning: false,
        error: `Failed to start run: ${res.status}`,
      }));
      return;
    }

    const data = (await res.json()) as { id: string };
    setState((prev) => ({ ...prev, runId: data.id }));
    _subscribeToRun(data.id);
  }, [workflowId, _subscribeToRun]);

  const approve = useCallback(async () => {
    if (!state.runId) return;
    setState((prev) => ({
      ...prev,
      isRunning: true,
      pendingHitlNodeId: null,
      hitlMessage: null,
    }));
    await fetch(`/api/workflows/runs/${state.runId}/approve`, { method: "POST" });
    _subscribeToRun(state.runId);
  }, [state.runId, _subscribeToRun]);

  const reject = useCallback(async () => {
    if (!state.runId) return;
    await fetch(`/api/workflows/runs/${state.runId}/reject`, { method: "POST" });
    setState((prev) => ({
      ...prev,
      isRunning: false,
      pendingHitlNodeId: null,
      hitlMessage: null,
    }));
  }, [state.runId]);

  const reset = useCallback(() => {
    esRef.current?.close();
    setState(INITIAL_STATE);
  }, []);

  return { ...state, startRun, approve, reject, reset };
}
