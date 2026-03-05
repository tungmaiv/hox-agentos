"use client";

/**
 * Admin Memory Management page.
 *
 * Provides a reindex button that calls the Next.js proxy at
 * /api/admin/memory/reindex (which injects the JWT and forwards to backend).
 * Shows a destructive-action confirmation dialog before firing the request.
 *
 * Lives at /admin/memory (part of the unified admin dashboard).
 */

import { useState } from "react";
import { z } from "zod";

// --- Zod schema for the reindex API response ---
const ReindexResponseSchema = z.object({
  job_id: z.string(),
  message: z.string(),
});

type ReindexState =
  | { phase: "idle" }
  | { phase: "confirming" }
  | { phase: "submitting" }
  | { phase: "in_progress"; jobId: string; message: string }
  | { phase: "error"; message: string };

export default function AdminMemoryPage() {
  const [state, setState] = useState<ReindexState>({ phase: "idle" });

  async function handleConfirm() {
    setState({ phase: "submitting" });

    try {
      // Call the Next.js proxy — it injects the JWT server-side
      const res = await fetch("/api/admin/memory/reindex", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: true }),
      });

      if (res.status === 403) {
        setState({ phase: "error", message: "Admin access required." });
        return;
      }

      if (!res.ok) {
        const text = await res.text();
        setState({
          phase: "error",
          message: `Reindex failed (HTTP ${res.status}): ${text}`,
        });
        return;
      }

      const raw: unknown = await res.json();
      const parsed = ReindexResponseSchema.safeParse(raw);
      if (!parsed.success) {
        setState({ phase: "error", message: "Unexpected response from server." });
        return;
      }

      setState({
        phase: "in_progress",
        jobId: parsed.data.job_id,
        message: parsed.data.message,
      });
    } catch (err) {
      setState({
        phase: "error",
        message: err instanceof Error ? err.message : "Network error",
      });
    }
  }

  function handleCancel() {
    setState({ phase: "idle" });
  }

  return (
    <div>
      <h2 className="text-lg font-semibold mb-6">Memory Management</h2>

      {/* In-progress banner */}
      {state.phase === "in_progress" && (
        <div className="mb-6 rounded-lg border border-blue-200 bg-blue-50 p-4">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 h-4 w-4 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
            <div>
              <p className="font-medium text-blue-800">Reindex in progress</p>
              <p className="text-sm text-blue-700 mt-1">{state.message}</p>
              <p className="text-xs text-blue-600 mt-1">
                Job ID: <code className="font-mono">{state.jobId}</code>
              </p>
              <p className="text-xs text-blue-600 mt-1">
                This may take 5–15 minutes depending on memory volume. You can
                safely navigate away — the job will continue in the background.
              </p>
            </div>
          </div>
          <button
            onClick={() => setState({ phase: "idle" })}
            className="mt-4 text-sm text-blue-700 underline hover:no-underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Error banner */}
      {state.phase === "error" && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="font-medium text-red-800">Reindex failed</p>
          <p className="text-sm text-red-700 mt-1">{state.message}</p>
          <button
            onClick={() => setState({ phase: "idle" })}
            className="mt-3 text-sm text-red-700 underline hover:no-underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Danger zone card */}
      <section className="rounded-lg border border-red-200 bg-white p-6">
        <h3 className="text-base font-semibold text-red-700 mb-1">
          Danger Zone
        </h3>
        <p className="text-sm text-gray-500 mb-4">
          Actions here are irreversible. Proceed with caution.
        </p>

        <div className="flex items-start justify-between gap-6 border-t border-gray-100 pt-4">
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-900">
              Reindex All Memory
            </p>
            <p className="text-sm text-gray-500 mt-1">
              Deletes all embedding vectors and re-embeds every memory fact and
              episode from source text. Use this when the embedding model
              changes or vectors are corrupted. The operation runs
              asynchronously — the platform remains available during reindex.
            </p>
          </div>

          {/* Idle state: show trigger button */}
          {(state.phase === "idle" ||
            state.phase === "in_progress" ||
            state.phase === "error") && (
            <button
              onClick={() => setState({ phase: "confirming" })}
              disabled={state.phase === "in_progress"}
              className={[
                "shrink-0 rounded-md px-4 py-2 text-sm font-medium text-white transition-colors",
                state.phase === "in_progress"
                  ? "bg-red-300 cursor-not-allowed"
                  : "bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2",
              ].join(" ")}
            >
              Reindex Memory
            </button>
          )}

          {/* Confirming state: show inline confirmation */}
          {state.phase === "confirming" && (
            <div className="shrink-0 rounded-lg border border-red-300 bg-red-50 p-4 max-w-sm">
              <p className="text-sm font-semibold text-red-800 mb-1">
                Are you sure?
              </p>
              <p className="text-xs text-red-700 mb-3">
                This will delete <strong>all embedding vectors</strong> and
                re-embed from source text. This cannot be undone. The operation
                may take 5–15 minutes.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={handleCancel}
                  className="flex-1 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => void handleConfirm()}
                  className="flex-1 rounded-md bg-red-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-red-700 transition-colors focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1"
                >
                  Yes, Reindex
                </button>
              </div>
            </div>
          )}

          {/* Submitting state: spinner */}
          {state.phase === "submitting" && (
            <div className="shrink-0 flex items-center gap-2 text-sm text-gray-500">
              <div className="h-4 w-4 rounded-full border-2 border-gray-400 border-t-transparent animate-spin" />
              Submitting…
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
