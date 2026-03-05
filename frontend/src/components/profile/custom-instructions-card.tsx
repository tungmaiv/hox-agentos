"use client";
/**
 * CustomInstructionsCard — textarea for per-user custom instructions with manual Save.
 *
 * Moved from the settings page to the profile page (Plan 16-03).
 * Fetches from GET /api/user/instructions/ on mount.
 * Saves via PUT /api/user/instructions/ on Save click.
 * Shows character count and "Saved ✓" indicator on success.
 */
import { useEffect, useState } from "react";

interface UserInstructionsResponse {
  instructions: string;
  updated_at: string;
}

export function CustomInstructionsCard() {
  const [instructions, setInstructions] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/user/instructions/", { cache: "no-store" })
      .then((r) => r.json())
      .then((data: UserInstructionsResponse) => {
        setInstructions(data.instructions ?? "");
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  async function handleSave() {
    setError(null);
    setSaving(true);
    try {
      const res = await fetch("/api/user/instructions/", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instructions }),
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      } else {
        setError("Failed to save instructions");
      }
    } catch {
      setError("Network error — please try again");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
      <h2 className="text-base font-semibold text-gray-900 mb-1">
        Custom Instructions
      </h2>
      <p className="text-sm text-gray-500 mb-4">
        These instructions are appended to every conversation with Blitz.
        Example: &quot;Always respond in Vietnamese&quot; or &quot;I am a
        backend engineer.&quot;
      </p>

      {error && (
        <p className="mb-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
          {error}
        </p>
      )}

      <textarea
        className="w-full min-h-[140px] p-3 border border-gray-300 rounded-md font-mono text-sm text-gray-900 bg-white resize-y focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
        value={instructions}
        onChange={(e) => setInstructions(e.target.value)}
        placeholder={
          loading
            ? "Loading..."
            : "Add custom instructions that Blitz will follow in every conversation..."
        }
        maxLength={4000}
        disabled={loading}
      />

      <div className="flex items-center justify-between mt-3">
        <span className="text-xs text-gray-400">
          {instructions.length}/4000 characters
        </span>
        <button
          onClick={() => void handleSave()}
          disabled={loading || saving}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-md text-sm font-medium transition-colors"
        >
          {saved ? "Saved \u2713" : saving ? "Saving..." : "Save Instructions"}
        </button>
      </div>
    </div>
  );
}
