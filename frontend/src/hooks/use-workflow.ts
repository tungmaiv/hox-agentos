"use client";
/**
 * useWorkflow — CRUD hook for workflow management.
 *
 * Provides list, create, update, delete operations using the
 * /api/workflows proxy routes (which inject the server-side JWT).
 *
 * All state management is kept simple: fetch on mount, manual refresh.
 * More advanced caching/optimistic updates can be added in later plans.
 */
import { useState, useEffect, useCallback } from "react";

export interface WorkflowListItem {
  id: string;
  name: string;
  description: string | null;
  is_template: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkflowCreate {
  name: string;
  description?: string;
  definition_json: Record<string, unknown>;
}

export interface WorkflowUpdate {
  name?: string;
  description?: string;
  definition_json?: Record<string, unknown>;
}

interface UseWorkflowReturn {
  workflows: WorkflowListItem[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  createWorkflow: (data: WorkflowCreate) => Promise<WorkflowListItem | null>;
  updateWorkflow: (
    id: string,
    data: WorkflowUpdate
  ) => Promise<WorkflowListItem | null>;
  deleteWorkflow: (id: string) => Promise<boolean>;
}

export function useWorkflow(): UseWorkflowReturn {
  const [workflows, setWorkflows] = useState<WorkflowListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/workflows", { cache: "no-store" });
      if (!res.ok) throw new Error(`Failed to fetch workflows: ${res.status}`);
      const data = (await res.json()) as WorkflowListItem[];
      setWorkflows(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const createWorkflow = useCallback(
    async (data: WorkflowCreate): Promise<WorkflowListItem | null> => {
      try {
        const res = await fetch("/api/workflows", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        });
        if (!res.ok) return null;
        const created = (await res.json()) as WorkflowListItem;
        setWorkflows((prev) => [created, ...prev]);
        return created;
      } catch {
        return null;
      }
    },
    []
  );

  const updateWorkflow = useCallback(
    async (
      id: string,
      data: WorkflowUpdate
    ): Promise<WorkflowListItem | null> => {
      try {
        const res = await fetch(`/api/workflows/${id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        });
        if (!res.ok) return null;
        const updated = (await res.json()) as WorkflowListItem;
        setWorkflows((prev) =>
          prev.map((w) => (w.id === id ? updated : w))
        );
        return updated;
      } catch {
        return null;
      }
    },
    []
  );

  const deleteWorkflow = useCallback(async (id: string): Promise<boolean> => {
    try {
      const res = await fetch(`/api/workflows/${id}`, { method: "DELETE" });
      if (!res.ok && res.status !== 204) return false;
      setWorkflows((prev) => prev.filter((w) => w.id !== id));
      return true;
    } catch {
      return false;
    }
  }, []);

  return {
    workflows,
    loading,
    error,
    refresh,
    createWorkflow,
    updateWorkflow,
    deleteWorkflow,
  };
}
