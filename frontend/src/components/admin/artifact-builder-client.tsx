"use client";
/**
 * ArtifactBuilderClient — CopilotKit co-agent for artifact creation.
 *
 * Split-panel layout:
 * - Left (45%): CopilotChat for conversational AI
 * - Right (55%): Live preview of the artifact being built
 */
import { useState, useEffect, useCallback } from "react";
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import { useCoAgentStateRender } from "@copilotkit/react-core";
import "@copilotkit/react-ui/styles.css";

import { ArtifactPreview } from "./artifact-preview";

/** Map artifact_type to admin API path segment */
const TYPE_TO_PATH: Record<string, string> = {
  agent: "agents",
  tool: "tools",
  skill: "skills",
  mcp_server: "mcp-servers",
};

/** Co-agent state shape matching ArtifactBuilderState on backend */
interface BuilderState {
  artifact_type: string | null;
  artifact_draft: Record<string, unknown> | null;
  validation_errors: string[];
  is_complete: boolean;
}

export function ArtifactBuilderClient() {
  return (
    <CopilotKit runtimeUrl="/api/copilotkit" agent="artifact_builder">
      <BuilderInner />
    </CopilotKit>
  );
}

function BuilderInner() {
  const [builderState, setBuilderState] = useState<BuilderState>({
    artifact_type: null,
    artifact_draft: null,
    validation_errors: [],
    is_complete: false,
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Subscribe to co-agent state updates for live preview
  useCoAgentStateRender<BuilderState>({
    name: "artifact_builder",
    render: ({ state }) => {
      if (state) {
        setBuilderState({
          artifact_type: state.artifact_type ?? null,
          artifact_draft: state.artifact_draft ?? null,
          validation_errors: state.validation_errors ?? [],
          is_complete: state.is_complete ?? false,
        });
      }
      return null;
    },
  });

  // Navigation guard: warn on unsaved draft
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (builderState.artifact_draft && !saveSuccess) {
        e.preventDefault();
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [builderState.artifact_draft, saveSuccess]);

  const handleSave = useCallback(async () => {
    if (!builderState.artifact_type || !builderState.artifact_draft) return;

    setSaving(true);
    setSaveError(null);

    const path = TYPE_TO_PATH[builderState.artifact_type];
    if (!path) {
      setSaveError(`Unknown artifact type: ${builderState.artifact_type}`);
      setSaving(false);
      return;
    }

    try {
      const res = await fetch(`/api/admin/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(builderState.artifact_draft),
      });

      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as Record<
          string,
          unknown
        >;
        throw new Error(
          (body.detail as string | undefined) ?? `HTTP ${res.status}`
        );
      }

      setSaveSuccess(true);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }, [builderState.artifact_type, builderState.artifact_draft]);

  if (saveSuccess) {
    const listPath = TYPE_TO_PATH[builderState.artifact_type ?? ""] ?? "agents";

    return (
      <div className="flex items-center justify-center h-[calc(100vh-140px)]">
        <div className="text-center p-8">
          <div className="text-4xl mb-4">&#10003;</div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            {(builderState.artifact_type ?? "").replace("_", " ")} created
            successfully!
          </h2>
          <div className="flex gap-3 justify-center mt-4">
            <a
              href={`/admin/${listPath}`}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
            >
              View in Registry
            </a>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 text-sm"
            >
              Create Another
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-4 h-[calc(100vh-140px)]">
      {/* Left panel: Chat */}
      <div className="w-[45%] flex flex-col border border-gray-200 rounded-lg overflow-hidden bg-white">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
          <h2 className="text-sm font-semibold text-gray-900">
            AI Artifact Builder
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Describe what you need and I&apos;ll help create it
          </p>
        </div>
        <div className="flex-1 overflow-hidden">
          <CopilotChat
            className="h-full"
            labels={{
              initial:
                "What artifact would you like to create? (agent, tool, skill, or MCP server)",
            }}
          />
        </div>
      </div>

      {/* Right panel: Preview */}
      <div className="w-[55%] flex flex-col border border-gray-200 rounded-lg overflow-hidden bg-white">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900">
            Artifact Preview
          </h2>
          {builderState.is_complete &&
            builderState.validation_errors.length === 0 && (
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-3 py-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-xs font-medium disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save to Registry"}
              </button>
            )}
        </div>
        <div className="flex-1 overflow-auto p-4">
          <ArtifactPreview
            artifactType={builderState.artifact_type}
            draft={builderState.artifact_draft}
            validationErrors={builderState.validation_errors}
            isComplete={builderState.is_complete}
          />
          {saveError && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
              {saveError}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
