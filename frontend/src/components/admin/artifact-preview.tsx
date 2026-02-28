"use client";
/**
 * ArtifactPreview — live preview of the artifact being built.
 *
 * Shows:
 * - Type badge
 * - Key-value field view
 * - Collapsible raw JSON
 * - Validation errors (if any)
 */
import { useState } from "react";

interface ArtifactPreviewProps {
  artifactType: string | null;
  draft: Record<string, unknown> | null;
  validationErrors: string[];
  isComplete: boolean;
}

const TYPE_COLORS: Record<string, string> = {
  agent: "bg-purple-100 text-purple-700",
  tool: "bg-blue-100 text-blue-700",
  skill: "bg-green-100 text-green-700",
  mcp_server: "bg-orange-100 text-orange-700",
};

const TYPE_LABELS: Record<string, string> = {
  agent: "Agent",
  tool: "Tool",
  skill: "Skill",
  mcp_server: "MCP Server",
};

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return "\u2014";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  if (Array.isArray(value)) {
    if (value.length === 0) return "[]";
    return value.map(String).join(", ");
  }
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

export function ArtifactPreview({
  artifactType,
  draft,
  validationErrors,
  isComplete,
}: ArtifactPreviewProps) {
  const [showJson, setShowJson] = useState(false);

  if (!artifactType && !draft) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <div className="text-center">
          <p className="text-sm">No artifact yet</p>
          <p className="text-xs mt-1">
            Start chatting to build an artifact definition
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Type badge + completion status */}
      <div className="flex items-center gap-2">
        {artifactType && (
          <span
            className={`px-2 py-0.5 rounded-full text-xs font-medium ${TYPE_COLORS[artifactType] ?? "bg-gray-100 text-gray-700"}`}
          >
            {TYPE_LABELS[artifactType] ?? artifactType}
          </span>
        )}
        {isComplete && validationErrors.length === 0 && (
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
            Ready to save
          </span>
        )}
        {validationErrors.length > 0 && (
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
            {validationErrors.length} issue
            {validationErrors.length > 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Field view */}
      {draft && Object.keys(draft).length > 0 && (
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <tbody>
              {Object.entries(draft).map(([key, value]) => (
                <tr
                  key={key}
                  className="border-b border-gray-100 last:border-0"
                >
                  <td className="px-3 py-2 text-gray-500 font-mono text-xs w-1/3 bg-gray-50">
                    {key}
                  </td>
                  <td className="px-3 py-2 text-gray-900 text-xs">
                    {renderValue(value)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Validation errors */}
      {validationErrors.length > 0 && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-md">
          <h4 className="text-xs font-semibold text-red-800 mb-1">
            Validation Issues
          </h4>
          <ul className="list-disc list-inside text-xs text-red-700 space-y-0.5">
            {validationErrors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Raw JSON toggle */}
      {draft && Object.keys(draft).length > 0 && (
        <div>
          <button
            onClick={() => setShowJson(!showJson)}
            className="text-xs text-blue-600 hover:text-blue-800 font-medium"
          >
            {showJson ? "Hide" : "Show"} raw JSON
          </button>
          {showJson && (
            <pre className="mt-2 p-3 bg-gray-900 text-gray-100 rounded-md text-xs overflow-auto max-h-64 font-mono">
              {JSON.stringify(draft, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
