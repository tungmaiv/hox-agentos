"use client";

import { useEffect, useState } from "react";

/**
 * Polls /api/workflows/runs/pending-hitl every `intervalMs` milliseconds.
 * Returns the count of workflow runs currently waiting for human approval.
 * Used to show a badge in the navigation.
 */
export function usePendingHitl(intervalMs = 30_000): number {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const res = await fetch("/api/workflows/runs/pending-hitl");
        if (res.ok && !cancelled) {
          const data = (await res.json()) as { count: number };
          setCount(data.count);
        }
      } catch {
        // Network error — keep previous count
      }
    };

    void poll();
    const id = setInterval(() => void poll(), intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [intervalMs]);

  return count;
}
