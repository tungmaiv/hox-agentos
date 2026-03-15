"use client";
/**
 * Hook for SSO health data with auto-refresh, threshold configuration,
 * and circuit breaker reset.
 *
 * Fetches GET /api/admin/sso/health (proxied via Next.js API route).
 * Auto-refreshes every 30s by default.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import {
  SSOHealthStatusSchema,
  type SSOHealthStatus,
  type CircuitBreakerThresholds,
} from "@/lib/api-types";

interface UseSSOHealthOptions {
  autoRefresh?: boolean;
  intervalMs?: number;
}

interface UseSSOHealthReturn {
  health: SSOHealthStatus | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  updateThresholds: (thresholds: CircuitBreakerThresholds) => Promise<boolean>;
  resetCircuitBreaker: () => Promise<boolean>;
}

export function useSSOHealth(
  options: UseSSOHealthOptions = {}
): UseSSOHealthReturn {
  const { autoRefresh = true, intervalMs = 30_000 } = options;

  const [health, setHealth] = useState<SSOHealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/sso/health");
      if (!res.ok) {
        setError(`Failed to fetch health: ${res.status}`);
        return;
      }
      const data: unknown = await res.json();
      const parsed = SSOHealthStatusSchema.parse(data);
      setHealth(parsed);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch + auto-refresh
  useEffect(() => {
    void fetchHealth();

    if (autoRefresh) {
      intervalRef.current = setInterval(() => void fetchHealth(), intervalMs);
      return () => {
        if (intervalRef.current) clearInterval(intervalRef.current);
      };
    }
  }, [fetchHealth, autoRefresh, intervalMs]);

  const refresh = useCallback(async () => {
    setLoading(true);
    await fetchHealth();
  }, [fetchHealth]);

  const updateThresholds = useCallback(
    async (thresholds: CircuitBreakerThresholds): Promise<boolean> => {
      try {
        const res = await fetch("/api/admin/sso/circuit-breaker/config", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(thresholds),
        });
        if (res.ok) {
          await fetchHealth();
          return true;
        }
        return false;
      } catch {
        return false;
      }
    },
    [fetchHealth]
  );

  const resetCircuitBreaker = useCallback(async (): Promise<boolean> => {
    try {
      const res = await fetch("/api/admin/sso/circuit-breaker/reset", {
        method: "POST",
      });
      if (res.ok) {
        await fetchHealth();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }, [fetchHealth]);

  return { health, loading, error, refresh, updateThresholds, resetCircuitBreaker };
}
