"use client";
/**
 * SkillStoreBrowse — card grid for browsing and importing skills from external repositories.
 *
 * Features:
 * - Search bar filters by name/description (debounced)
 * - Paginated 3-column card grid (20 per page, cursor-based Load More)
 * - Detail drawer: clicking a card opens full metadata before import
 * - Import dialog with 2-step flow: confirm → show security scan results
 */
import { useCallback, useEffect, useState } from "react";

interface SkillBrowseItem {
  name: string;
  description: string | null;
  version: string | null;
  repository_name: string;
  repository_id: string;
  metadata: Record<string, unknown> | null;
  category: string | null;
  tags: string[] | null;
  license: string | null;
  author: string | null;
  source_url: string | null;
}

interface ImportResponse {
  skill_id: string;
  name: string;
  status: string;
  security_score: number;
  security_recommendation: string;
}

type ImportDialogState =
  | { phase: "confirm"; skill: SkillBrowseItem }
  | { phase: "importing"; skill: SkillBrowseItem }
  | {
      phase: "result";
      skill: SkillBrowseItem;
      result: ImportResponse;
    }
  | { phase: "error"; skill: SkillBrowseItem; error: string };

export function SkillStoreBrowse() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [skills, setSkills] = useState<SkillBrowseItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dialogState, setDialogState] = useState<ImportDialogState | null>(
    null
  );
  // Detail drawer state — opens before the import confirm dialog
  const [drawerSkill, setDrawerSkill] = useState<SkillBrowseItem | null>(null);

  // Debounce search query by 300ms
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(timer);
  }, [query]);

  const fetchSkills = useCallback(
    async (q: string, append = false, currentCursor = 0) => {
      if (!append) setLoading(true);
      else setLoadingMore(true);
      setError(null);
      try {
        const params = new URLSearchParams({
          limit: "20",
          cursor: String(currentCursor),
        });
        if (q.trim()) params.set("q", encodeURIComponent(q.trim()));
        const response = await fetch(
          `/api/skill-repos/browse?${params.toString()}`
        );
        if (!response.ok) {
          const data = (await response.json().catch(() => ({}))) as {
            detail?: string;
          };
          setError(data.detail ?? `Error ${response.status}`);
          return;
        }
        const data: unknown = await response.json();
        if (!Array.isArray(data)) {
          setError("Unexpected response from server");
          return;
        }
        const items = data as SkillBrowseItem[];
        if (append) {
          setSkills((prev) => [...prev, ...items]);
        } else {
          setSkills(items);
        }
        setHasMore(items.length === 20);
      } catch {
        setError("Failed to connect to backend");
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    []
  );

  // Reset and refetch when query changes
  useEffect(() => {
    void fetchSkills(debouncedQuery, false, 0);
  }, [fetchSkills, debouncedQuery]);

  const handleLoadMore = useCallback(() => {
    const nextCursor = skills.length;
    void fetchSkills(debouncedQuery, true, nextCursor);
  }, [fetchSkills, debouncedQuery, skills.length]);

  const handleImportConfirm = async () => {
    if (!dialogState || dialogState.phase !== "confirm") return;
    const { skill } = dialogState;

    setDialogState({ phase: "importing", skill });

    try {
      const response = await fetch("/api/skill-repos/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repository_id: skill.repository_id,
          skill_name: skill.name,
        }),
      });

      if (!response.ok) {
        const data = (await response.json().catch(() => ({}))) as {
          detail?: string;
        };
        setDialogState({
          phase: "error",
          skill,
          error: data.detail ?? `Import failed (${response.status})`,
        });
        return;
      }

      const result = (await response.json()) as ImportResponse;
      setDialogState({ phase: "result", skill, result });
    } catch {
      setDialogState({
        phase: "error",
        skill,
        error: "Failed to connect to backend",
      });
    }
  };

  const scoreColor = (score: number): string => {
    if (score >= 80) return "text-green-700";
    if (score >= 60) return "text-yellow-700";
    return "text-red-700";
  };

  const scoreBackground = (score: number): string => {
    if (score >= 80) return "bg-green-50 border-green-200";
    if (score >= 60) return "bg-yellow-50 border-yellow-200";
    return "bg-red-50 border-red-200";
  };

  const recommendationLabel = (rec: string): string => {
    switch (rec) {
      case "approve":
        return "Looks Good";
      case "review":
        return "Needs Review";
      case "reject":
        return "High Risk";
      default:
        return rec;
    }
  };

  return (
    <div className="space-y-6">
      {/* Search bar */}
      <div className="relative">
        <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none">
          <svg
            className="h-4 w-4 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>
        <input
          type="text"
          placeholder="Search skills by name or description..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
        />
        {loading && (
          <div className="absolute inset-y-0 right-3 flex items-center">
            <div className="h-4 w-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && skills.length === 0 && (
        <div className="text-center py-16 text-gray-500 text-sm">
          {debouncedQuery
            ? `No skills found matching "${debouncedQuery}"`
            : "No skills available. Add a repository to get started."}
        </div>
      )}

      {/* Skill card grid */}
      {skills.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {skills.map((skill) => (
            <div
              key={`${skill.repository_id}:${skill.name}`}
              className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow flex flex-col cursor-pointer"
              onClick={() => setDrawerSkill(skill)}
            >
              {/* Skill header */}
              <div className="flex items-start justify-between gap-2 mb-2">
                <h3 className="font-semibold text-gray-900 text-sm leading-tight">
                  {skill.name}
                </h3>
                {skill.version && (
                  <span className="shrink-0 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-mono">
                    v{skill.version}
                  </span>
                )}
              </div>

              {/* Description */}
              {skill.description && (
                <p className="text-xs text-gray-600 leading-relaxed mb-3 flex-1">
                  {skill.description}
                </p>
              )}

              {/* Metadata */}
              <div className="space-y-1 mb-4">
                <div className="flex items-center gap-1.5 text-xs text-gray-500">
                  <svg
                    className="h-3.5 w-3.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                    />
                  </svg>
                  <span className="truncate">{skill.repository_name}</span>
                </div>

                {skill.author && (
                  <div className="flex items-center gap-1.5 text-xs text-gray-500">
                    <svg
                      className="h-3.5 w-3.5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                      />
                    </svg>
                    <span>{skill.author}</span>
                  </div>
                )}

                {skill.license && (
                  <div className="flex items-center gap-1.5 text-xs text-gray-500">
                    <svg
                      className="h-3.5 w-3.5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                      />
                    </svg>
                    <span>{skill.license}</span>
                  </div>
                )}
              </div>

              {/* View Details hint */}
              <div className="w-full py-2 text-sm font-medium text-blue-600 border border-blue-200 rounded-md text-center hover:bg-blue-50 transition-colors">
                View Details
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Load More button */}
      {hasMore && (
        <div className="mt-6 flex justify-center">
          <button
            onClick={handleLoadMore}
            disabled={loadingMore}
            className="px-4 py-2 text-sm font-medium text-blue-600 border border-blue-300 rounded-md hover:bg-blue-50 disabled:opacity-50 transition-colors"
          >
            {loadingMore ? "Loading..." : "Load More"}
          </button>
        </div>
      )}

      {/* Detail Drawer — shows full metadata before import */}
      {drawerSkill && (
        <div className="fixed inset-0 z-50 flex justify-end">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/30"
            onClick={() => setDrawerSkill(null)}
          />
          {/* Drawer panel */}
          <aside className="relative z-10 w-full max-w-md bg-white shadow-xl flex flex-col h-full overflow-y-auto">
            <div className="flex items-center justify-between p-4 border-b">
              <h2 className="font-semibold text-gray-900 text-lg">
                {drawerSkill.name}
              </h2>
              <button
                onClick={() => setDrawerSkill(null)}
                className="text-gray-400 hover:text-gray-600 text-xl leading-none"
              >
                &times;
              </button>
            </div>
            <div className="p-4 flex-1 space-y-4">
              {drawerSkill.description && (
                <p className="text-sm text-gray-700">{drawerSkill.description}</p>
              )}
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                {drawerSkill.version && (
                  <>
                    <dt className="text-gray-500">Version</dt>
                    <dd className="text-gray-900">{drawerSkill.version}</dd>
                  </>
                )}
                {drawerSkill.category && (
                  <>
                    <dt className="text-gray-500">Category</dt>
                    <dd className="text-gray-900">{drawerSkill.category}</dd>
                  </>
                )}
                {drawerSkill.license && (
                  <>
                    <dt className="text-gray-500">License</dt>
                    <dd className="text-gray-900">{drawerSkill.license}</dd>
                  </>
                )}
                {drawerSkill.author && (
                  <>
                    <dt className="text-gray-500">Author</dt>
                    <dd className="text-gray-900">{drawerSkill.author}</dd>
                  </>
                )}
                {drawerSkill.source_url && (
                  <>
                    <dt className="text-gray-500">Source</dt>
                    <dd className="truncate">
                      <a
                        href={drawerSkill.source_url}
                        className="text-blue-600 hover:underline text-xs"
                        target="_blank"
                        rel="noreferrer"
                      >
                        {drawerSkill.source_url}
                      </a>
                    </dd>
                  </>
                )}
                <dt className="text-gray-500">Repository</dt>
                <dd className="text-gray-900">{drawerSkill.repository_name}</dd>
              </dl>
              {drawerSkill.tags && drawerSkill.tags.length > 0 && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">Tags</p>
                  <div className="flex flex-wrap gap-1">
                    {drawerSkill.tags.map((tag) => (
                      <span
                        key={tag}
                        className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div className="p-4 border-t">
              <button
                onClick={() => {
                  setDialogState({ phase: "confirm", skill: drawerSkill });
                  setDrawerSkill(null);
                }}
                className="w-full px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors"
              >
                Import Skill
              </button>
            </div>
          </aside>
        </div>
      )}

      {/* Import Dialog */}
      {dialogState && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
            {/* Step 1: Confirm */}
            {dialogState.phase === "confirm" && (
              <>
                <h3 className="text-lg font-semibold text-gray-900 mb-1">
                  Import Skill
                </h3>
                <p className="text-sm text-gray-500 mb-4">
                  {dialogState.skill.name}
                </p>

                <div className="bg-gray-50 border border-gray-200 rounded-md px-4 py-3 text-sm text-gray-700 mb-4">
                  <div className="font-medium mb-1">
                    {dialogState.skill.description}
                  </div>
                  <div className="text-xs text-gray-500">
                    From: {dialogState.skill.repository_name}
                  </div>
                </div>

                <p className="text-sm text-gray-600 mb-6">
                  Importing will run a security scan. The skill will enter
                  pending review status and must be approved by an admin before
                  it becomes active.
                </p>

                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => setDialogState(null)}
                    className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => void handleImportConfirm()}
                    className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors"
                  >
                    Import &amp; Scan
                  </button>
                </div>
              </>
            )}

            {/* Loading */}
            {dialogState.phase === "importing" && (
              <>
                <div className="flex flex-col items-center justify-center py-8 gap-4">
                  <div className="h-8 w-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin" />
                  <p className="text-sm text-gray-600">
                    Importing and scanning{" "}
                    <strong>{dialogState.skill.name}</strong>...
                  </p>
                </div>
              </>
            )}

            {/* Step 2: Result */}
            {dialogState.phase === "result" && (
              <>
                <h3 className="text-lg font-semibold text-gray-900 mb-1">
                  Import Complete
                </h3>
                <p className="text-sm text-gray-500 mb-4">
                  {dialogState.result.name}
                </p>

                <div
                  className={`rounded-md border px-4 py-4 mb-4 ${scoreBackground(dialogState.result.security_score)}`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-700">
                      Security Score
                    </span>
                    <span
                      className={`text-2xl font-bold ${scoreColor(dialogState.result.security_score)}`}
                    >
                      {dialogState.result.security_score}/100
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-600">
                      Recommendation:
                    </span>
                    <span
                      className={`text-sm font-medium ${scoreColor(dialogState.result.security_score)}`}
                    >
                      {recommendationLabel(
                        dialogState.result.security_recommendation
                      )}
                    </span>
                  </div>
                </div>

                <div className="bg-blue-50 border border-blue-200 rounded-md px-4 py-3 text-sm text-blue-700 mb-6">
                  Skill imported — pending admin review before it becomes
                  active.
                </div>

                <div className="flex justify-end">
                  <button
                    onClick={() => setDialogState(null)}
                    className="px-4 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-200 transition-colors"
                  >
                    Close
                  </button>
                </div>
              </>
            )}

            {/* Error */}
            {dialogState.phase === "error" && (
              <>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                  Import Failed
                </h3>

                <div className="bg-red-50 border border-red-200 rounded-md px-4 py-3 text-sm text-red-700 mb-6">
                  {dialogState.error}
                </div>

                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => setDialogState(null)}
                    className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() =>
                      setDialogState({
                        phase: "confirm",
                        skill: dialogState.skill,
                      })
                    }
                    className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors"
                  >
                    Try Again
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
