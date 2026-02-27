"use client";

/**
 * TemplateCard — displays a workflow template with a "Use Template" button.
 *
 * On click, calls POST /api/workflows/templates/{id}/copy (via the Next.js
 * backend proxy which injects the user's JWT), then navigates to the newly
 * created workflow's canvas editor at /workflows/{newId}.
 *
 * This is a Client Component because it needs:
 * - useRouter (navigation after copy)
 * - useState (loading / error state)
 * - onClick handler
 */
import { useRouter } from "next/navigation";
import { useState } from "react";

export interface TemplateCardProps {
  template: {
    id: string;
    name: string;
    description: string | null;
  };
}

export function TemplateCard({ template }: TemplateCardProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUseTemplate() {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(
        `/api/workflows/templates/${template.id}/copy`,
        { method: "POST" }
      );

      if (!res.ok) {
        const text = await res.text().catch(() => "Unknown error");
        throw new Error(`Copy failed (${res.status}): ${text}`);
      }

      const data = (await res.json()) as { id: string };
      router.push(`/workflows/${data.id}`);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to copy template";
      setError(message);
      setLoading(false);
    }
  }

  return (
    <div className="border rounded-lg p-4 bg-gray-50">
      <h3 className="font-medium text-gray-900">{template.name}</h3>
      {template.description && (
        <p className="text-sm text-gray-500 mt-1">{template.description}</p>
      )}
      {error && (
        <p className="text-xs text-red-500 mt-2" role="alert">
          {error}
        </p>
      )}
      <button
        type="button"
        onClick={handleUseTemplate}
        disabled={loading}
        className="mt-3 text-sm px-3 py-1 bg-white border border-gray-300 rounded hover:bg-gray-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? "Copying…" : "Use template \u2192"}
      </button>
    </div>
  );
}
