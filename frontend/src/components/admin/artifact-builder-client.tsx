"use client";
/**
 * ArtifactBuilderClient — CopilotKit co-agent for artifact creation.
 *
 * Split-panel layout:
 * - Left (45%): CopilotChat for conversational AI
 * - Right (55%): Live preview of the artifact being built + similar skill discovery
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import { useCoAgentStateRender } from "@copilotkit/react-core";
import "@copilotkit/react-ui/styles.css";

import { ArtifactPreview } from "./artifact-preview";
import {
  SecurityReportCard,
  type SecurityReportData,
} from "./security-report-card";

/** Map artifact_type to admin API path segment */
const TYPE_TO_PATH: Record<string, string> = {
  agent: "agents",
  tool: "tools",
  skill: "skills",
  mcp_server: "mcp-servers",
};

/** A similar skill result from the search-similar API */
interface SimilarSkill {
  name: string;
  description: string | null;
  repository_name: string;
  source_url: string | null;
  category: string | null;
  tags: string[] | null;
}

/** Co-agent state shape matching ArtifactBuilderState on backend */
interface BuilderState {
  artifact_type: string | null;
  artifact_draft: Record<string, unknown> | null;
  validation_errors: string[];
  is_complete: boolean;
  similar_skills: SimilarSkill[] | null;
  fork_source: string | null;
  handler_code: string | null;
  security_report: Record<string, unknown> | null;
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
    similar_skills: null,
    fork_source: null,
    handler_code: null,
    security_report: null,
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [securityReport, setSecurityReport] =
    useState<SecurityReportData | null>(null);
  const [savedSkillId, setSavedSkillId] = useState<string | null>(null);

  // Similar skills discovery state
  const [similarSkills, setSimilarSkills] = useState<SimilarSkill[] | null>(null);
  const [findingSimilar, setFindingSimilar] = useState(false);
  const [similarError, setSimilarError] = useState<string | null>(null);

  // Edit JSON toggle state
  const [showJsonEditor, setShowJsonEditor] = useState(false);
  const [jsonEditValue, setJsonEditValue] = useState<string>("");
  const [jsonParseError, setJsonParseError] = useState<string | null>(null);

  // Ref to buffer co-agent state updates — avoids setState during render phase
  const pendingStateRef = useRef<BuilderState | null>(null);
  // When user manually edits draft via JSON editor, lock it so co-agent polling
  // doesn't overwrite their edits before they click Save.
  const manualDraftRef = useRef<Record<string, unknown> | null>(null);

  // Subscribe to co-agent state updates for live preview.
  // The render callback runs during React's render phase, so we buffer
  // state into a ref and apply it via useEffect to avoid the
  // "Cannot update a component while rendering a different component" error.
  useCoAgentStateRender<BuilderState>({
    name: "artifact_builder",
    render: ({ state }) => {
      if (state) {
        pendingStateRef.current = {
          artifact_type: state.artifact_type ?? null,
          artifact_draft: state.artifact_draft ?? null,
          validation_errors: state.validation_errors ?? [],
          is_complete: state.is_complete ?? false,
          similar_skills: state.similar_skills ?? null,
          fork_source: state.fork_source ?? null,
          handler_code: state.handler_code ?? null,
          security_report: state.security_report ?? null,
        };
      }
      return null;
    },
  });

  // Apply buffered state outside the render phase.
  // If the user has manually edited the draft via the JSON editor, preserve
  // their version and don't let co-agent polling overwrite it.
  useEffect(() => {
    const id = setInterval(() => {
      if (pendingStateRef.current) {
        const pending = pendingStateRef.current;
        pendingStateRef.current = null;
        setBuilderState((prev) => ({
          ...pending,
          artifact_draft: manualDraftRef.current ?? pending.artifact_draft ?? prev.artifact_draft,
        }));
      }
    }, 100);
    return () => clearInterval(id);
  }, []);

  // Navigation guard: warn on unsaved draft.
  // - beforeunload: browser close / refresh / external URL
  // - click capture on <a>: in-app SPA navigation (Next.js <Link>)
  useEffect(() => {
    if (!builderState.artifact_draft || saveSuccess) return;

    // Browser close / refresh
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", handleBeforeUnload);

    // In-app navigation: intercept link clicks in capture phase
    // (before Next.js router processes them)
    const handleClick = (e: MouseEvent) => {
      const anchor = (e.target as HTMLElement).closest("a");
      if (!anchor) return;
      const href = anchor.getAttribute("href");
      if (!href || href.startsWith("#") || href === window.location.pathname) return;

      if (!window.confirm("Changes you made may not be saved. Leave anyway?")) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    document.addEventListener("click", handleClick, true);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      document.removeEventListener("click", handleClick, true);
    };
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
      if (builderState.artifact_type === "skill") {
        // Skills go through builder-save for the security gate
        const res = await fetch("/api/admin/skills/builder-save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            skill_data: builderState.artifact_draft,
            skill_id: savedSkillId,
          }),
        });

        if (!res.ok) {
          const errBody = (await res.json().catch(() => ({}))) as Record<
            string,
            unknown
          >;
          let errorMsg = `HTTP ${res.status}`;
          if (typeof errBody.detail === "string") {
            errorMsg = errBody.detail;
          }
          throw new Error(errorMsg);
        }

        const data = (await res.json()) as {
          skill_id: string;
          status: string;
          security_report: SecurityReportData;
        };

        setSecurityReport(data.security_report);
        setSavedSkillId(data.skill_id);

        if (data.status === "active") {
          manualDraftRef.current = null;
          setSaveSuccess(true);
        }
        // If pending_review: stay in builder, SecurityReportCard renders
      } else {
        // Non-skill artifact types: use existing generic save
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
          // FastAPI returns Pydantic validation errors as:
          //   {"detail": [{"loc": [...], "msg": "...", "type": "..."}]}
          // Handle both string and array-of-objects formats.
          let errorMsg = `HTTP ${res.status}`;
          if (typeof body.detail === "string") {
            errorMsg = body.detail;
          } else if (Array.isArray(body.detail)) {
            errorMsg = (body.detail as Array<Record<string, unknown>>)
              .map((e) => {
                const loc = Array.isArray(e.loc)
                  ? (e.loc as string[]).join(" > ")
                  : "";
                return loc ? `${loc}: ${e.msg}` : String(e.msg ?? e);
              })
              .join("; ");
          }
          throw new Error(errorMsg);
        }

        setSaveSuccess(true);
      }
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }, [builderState.artifact_type, builderState.artifact_draft, savedSkillId]);

  /** POST to search-similar endpoint and update similar skills list */
  const handleFindSimilar = useCallback(async () => {
    const name = builderState.artifact_draft?.name;
    const description = builderState.artifact_draft?.description;
    if (!name || !description) return;
    if (typeof name !== "string" || typeof description !== "string") return;

    setFindingSimilar(true);
    setSimilarError(null);

    try {
      const res = await fetch("/api/admin/skill-repos/search-similar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description }),
      });

      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as Record<string, unknown>;
        const msg =
          typeof body.detail === "string"
            ? body.detail
            : `HTTP ${res.status}`;
        throw new Error(msg);
      }

      const data = (await res.json()) as { results: SimilarSkill[] };
      setSimilarSkills(data.results);
    } catch (err) {
      setSimilarError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setFindingSimilar(false);
    }
  }, [builderState.artifact_draft]);

  /** Fork a similar skill: copy its fields into the builder draft and set fork_source */
  const handleFork = useCallback((skill: SimilarSkill) => {
    const forkSource = `${skill.name}@${skill.source_url ?? ""}`;
    setBuilderState((prev) => ({
      ...prev,
      artifact_draft: {
        ...(prev.artifact_draft ?? {}),
        name: skill.name,
        description: skill.description ?? prev.artifact_draft?.description ?? null,
      },
      fork_source: forkSource,
    }));
    // Collapse the similar skills panel after forking
    setSimilarSkills(null);
  }, []);

  /** Parse the JSON editor textarea value and update draft state */
  const handleJsonParse = useCallback(() => {
    setJsonParseError(null);
    try {
      const parsed = JSON.parse(jsonEditValue) as Record<string, unknown>;
      // Lock the draft so co-agent polling doesn't overwrite the user's edits
      manualDraftRef.current = parsed;
      setBuilderState((prev) => ({ ...prev, artifact_draft: parsed }));
      setShowJsonEditor(false);
    } catch (err) {
      setJsonParseError(err instanceof Error ? err.message : "Invalid JSON");
    }
  }, [jsonEditValue]);

  // When toggling the JSON editor ON, pre-fill with current draft
  const handleToggleJsonEditor = useCallback(() => {
    setShowJsonEditor((prev) => {
      if (!prev && builderState.artifact_draft !== null) {
        setJsonEditValue(JSON.stringify(builderState.artifact_draft, null, 2));
        setJsonParseError(null);
      }
      return !prev;
    });
  }, [builderState.artifact_draft]);

  const hasDraftNameAndDescription =
    typeof builderState.artifact_draft?.name === "string" &&
    builderState.artifact_draft.name.length > 0 &&
    typeof builderState.artifact_draft?.description === "string" &&
    builderState.artifact_draft.description.length > 0;

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

      {/* Right panel: Preview + similar skills + JSON editor */}
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

        <div className="flex-1 overflow-auto p-4 space-y-4">
          {/* Security report (post-save pending_review path) */}
          {securityReport && !saveSuccess && savedSkillId ? (
            <SecurityReportCard
              skillId={savedSkillId}
              report={securityReport}
              onApproved={() => setSaveSuccess(true)}
            />
          ) : showJsonEditor ? (
            /* JSON editor mode */
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-gray-700">
                  Edit JSON
                </span>
                <button
                  onClick={handleToggleJsonEditor}
                  className="text-xs text-gray-500 hover:text-gray-700"
                >
                  Cancel
                </button>
              </div>
              <textarea
                value={jsonEditValue}
                onChange={(e) => setJsonEditValue(e.target.value)}
                rows={20}
                className="w-full font-mono text-xs border border-gray-300 rounded-md p-2 resize-y focus:outline-none focus:ring-1 focus:ring-blue-500"
                spellCheck={false}
              />
              {jsonParseError && (
                <p className="text-xs text-red-600">{jsonParseError}</p>
              )}
              <button
                onClick={handleJsonParse}
                className="px-3 py-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-xs font-medium"
              >
                Parse
              </button>
            </div>
          ) : (
            /* Normal artifact preview */
            <ArtifactPreview
              artifactType={builderState.artifact_type}
              draft={builderState.artifact_draft}
              validationErrors={builderState.validation_errors}
              isComplete={builderState.is_complete}
            />
          )}

          {/* Edit JSON toggle — only when artifact is complete and not in JSON editor mode */}
          {builderState.is_complete && !showJsonEditor && !securityReport && (
            <button
              onClick={handleToggleJsonEditor}
              className="text-xs text-blue-600 hover:text-blue-800 underline"
            >
              Edit JSON
            </button>
          )}

          {/* Find Similar button — visible when draft has name + description */}
          {hasDraftNameAndDescription && !securityReport && (
            <div className="border-t border-gray-100 pt-3">
              <button
                onClick={handleFindSimilar}
                disabled={findingSimilar}
                className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 text-xs font-medium disabled:opacity-50 border border-gray-200"
              >
                {findingSimilar ? "Searching..." : "Find Similar"}
              </button>

              {similarError && (
                <p className="mt-2 text-xs text-red-600">{similarError}</p>
              )}

              {/* Similar skills results */}
              {similarSkills !== null && (
                <div className="mt-3 space-y-2">
                  <h3 className="text-xs font-semibold text-gray-700">
                    Similar Skills
                  </h3>
                  {similarSkills.length === 0 ? (
                    <p className="text-xs text-gray-500">
                      No similar skills found.
                    </p>
                  ) : (
                    similarSkills.map((skill, idx) => (
                      <div
                        key={idx}
                        className="border border-gray-200 rounded-md p-3 bg-gray-50"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-semibold text-gray-900 truncate">
                              {skill.name}
                            </p>
                            {skill.description && (
                              <p className="text-xs text-gray-600 mt-0.5 line-clamp-2">
                                {skill.description}
                              </p>
                            )}
                            <p className="text-xs text-gray-400 mt-1">
                              {skill.repository_name}
                            </p>
                          </div>
                          <button
                            onClick={() => handleFork(skill)}
                            className="flex-shrink-0 px-2 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700"
                          >
                            Fork
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          )}

          {/* Fork attribution badge */}
          {builderState.fork_source && (
            <div className="text-xs text-gray-500 bg-blue-50 border border-blue-100 rounded px-2 py-1">
              Forked from:{" "}
              <span className="font-medium">{builderState.fork_source}</span>
            </div>
          )}

          {saveError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
              {saveError}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
