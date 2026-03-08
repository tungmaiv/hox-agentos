"use client";
/**
 * useAdminArtifacts — generic CRUD hook for admin artifact management.
 *
 * Parameterized by ArtifactType ("agents" | "tools" | "skills" | "mcp-servers").
 * All calls go through the /api/admin/* Next.js proxy which injects the JWT.
 *
 * Returns: { items, loading, error, create, update, patchStatus, bulkStatus,
 *            activateVersion, refetch }
 */
import { useState, useEffect, useCallback } from "react";
import type { ArtifactType } from "@/lib/admin-types";
import { mapArraySnakeToCamel } from "@/lib/admin-types";

interface UseAdminArtifactsResult<T> {
  items: T[];
  loading: boolean;
  error: string | null;
  create: (data: object) => Promise<T | null>;
  update: (id: string, data: Record<string, unknown>) => Promise<T | null>;
  patchStatus: (
    id: string,
    status: "active" | "disabled" | "deprecated"
  ) => Promise<boolean>;
  bulkStatus: (
    ids: string[],
    status: "active" | "disabled" | "deprecated"
  ) => Promise<boolean>;
  activateVersion: (id: string) => Promise<T | null>;
  refetch: () => void;
}

export function useAdminArtifacts<T>(
  type: ArtifactType,
  params?: Record<string, string>
): UseAdminArtifactsResult<T> {
  const [items, setItems] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const basePath = `/api/admin/${type}`;
  // Serialize params for stable dependency tracking
  const paramsStr = params ? new URLSearchParams(params).toString() : "";

  const refetch = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const fetchUrl = paramsStr ? `${basePath}?${paramsStr}` : basePath;
    fetch(fetchUrl, { cache: "no-store" })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: unknown) => {
        if (!cancelled && Array.isArray(data)) {
          setItems(mapArraySnakeToCamel<T>(data));
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load artifacts"
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [basePath, paramsStr, refreshKey]);

  const create = useCallback(
    async (data: object): Promise<T | null> => {
      try {
        const res = await fetch(basePath, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        });
        if (!res.ok) {
          const body = (await res.json().catch(() => ({}))) as Record<
            string,
            unknown
          >;
          const detail = body.detail;
          let message: string;
          if (Array.isArray(detail) && detail.length > 0) {
            const first = detail[0] as Record<string, unknown>;
            message =
              typeof first.msg === "string" ? first.msg : `HTTP ${res.status}`;
          } else if (typeof detail === "string") {
            message = detail;
          } else {
            message = `HTTP ${res.status}`;
          }
          throw new Error(message);
        }
        const created = (await res.json()) as Record<string, unknown>;
        refetch();
        return mapArraySnakeToCamel<T>([created])[0] ?? null;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Create failed");
        return null;
      }
    },
    [basePath, refetch]
  );

  const update = useCallback(
    async (id: string, data: Record<string, unknown>): Promise<T | null> => {
      try {
        const res = await fetch(`${basePath}/${id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const updated = (await res.json()) as Record<string, unknown>;
        refetch();
        return mapArraySnakeToCamel<T>([updated])[0] ?? null;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Update failed");
        return null;
      }
    },
    [basePath, refetch]
  );

  const patchStatus = useCallback(
    async (
      id: string,
      status: "active" | "disabled" | "deprecated"
    ): Promise<boolean> => {
      try {
        const res = await fetch(`${basePath}/${id}/status`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        refetch();
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Status update failed");
        return false;
      }
    },
    [basePath, refetch]
  );

  const bulkStatus = useCallback(
    async (
      ids: string[],
      status: "active" | "disabled" | "deprecated"
    ): Promise<boolean> => {
      try {
        const res = await fetch(`${basePath}/bulk-status`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids, status }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        refetch();
        return true;
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Bulk status update failed"
        );
        return false;
      }
    },
    [basePath, refetch]
  );

  const activateVersion = useCallback(
    async (id: string): Promise<T | null> => {
      try {
        const res = await fetch(`${basePath}/${id}/activate`, {
          method: "PATCH",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const activated = (await res.json()) as Record<string, unknown>;
        refetch();
        return mapArraySnakeToCamel<T>([activated])[0] ?? null;
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Version activation failed"
        );
        return null;
      }
    },
    [basePath, refetch]
  );

  return {
    items,
    loading,
    error,
    create,
    update,
    patchStatus,
    bulkStatus,
    activateVersion,
    refetch,
  };
}
