"use client";
/**
 * User Skills catalog page — browse all active skills.
 *
 * Uses ArtifactCardGrid + SkillMetadataPanel (same layout as admin view).
 * Admin-only actions are hidden by omitting all action props.
 * Supports FTS search (server-side via /api/skills?q=), category filter,
 * skill_type filter, and sort — all with 300ms debounce on search.
 *
 * Phase 22: Promoted section above main grid, Shared badge in main grid,
 * Export button per card.
 */
import { useState, useEffect, useCallback } from "react";
import { ArtifactCardGrid } from "@/components/admin/artifact-card-grid";
import type { ArtifactStatus } from "@/lib/admin-types";

interface SkillItem {
  // ArtifactBase required fields
  id: string;
  name: string;
  displayName: string | null;
  description: string | null;
  version: string;
  isActive: boolean;
  status: ArtifactStatus;
  lastSeenAt: string | null;
  createdAt: string;
  // Skill-specific fields
  skillType: string;
  category: string | null;
  tags: string[] | null;
  license: string | null;
  sourceUrl: string | null;
  allowedTools: string[] | null;
  compatibility: string | null;
  usageCount: number;
  // Phase 22 fields
  isPromoted: boolean;
  isShared: boolean;
}

/** Map a raw API item to SkillItem — used by fetchSkills and fetchPromotedSkills. */
function mapSkillItem(item: Record<string, unknown>): SkillItem {
  return {
    id: String(item.id ?? ""),
    name: String(item.name ?? ""),
    displayName: (item.display_name ?? item.displayName ?? null) as string | null,
    description: (item.description ?? null) as string | null,
    version: String(item.version ?? "1.0.0"),
    isActive: Boolean(item.is_active ?? item.isActive ?? true),
    status: ((item.status ?? "active") as ArtifactStatus),
    lastSeenAt: (item.last_seen_at ?? item.lastSeenAt ?? null) as string | null,
    createdAt: String(item.created_at ?? item.createdAt ?? new Date().toISOString()),
    skillType: String(item.skill_type ?? item.skillType ?? "instructional"),
    category: (item.category ?? null) as string | null,
    tags: (item.tags ?? null) as string[] | null,
    license: (item.license ?? null) as string | null,
    sourceUrl: (item.source_url ?? item.sourceUrl ?? null) as string | null,
    allowedTools: (item.allowed_tools ?? item.allowedTools ?? null) as string[] | null,
    compatibility: (item.compatibility ?? null) as string | null,
    usageCount: Number(item.usage_count ?? item.usageCount ?? 0),
    isPromoted: Boolean(item.is_promoted ?? item.isPromoted ?? false),
    isShared: Boolean(item.is_shared ?? item.isShared ?? false),
  };
}

/** Read-only metadata section shown when a skill has any metadata fields. */
function SkillMetadataPanel({ skill }: { skill: SkillItem }) {
  const hasMetadata =
    skill.license ||
    skill.compatibility ||
    skill.category ||
    skill.sourceUrl ||
    (skill.allowedTools && skill.allowedTools.length > 0) ||
    (skill.tags && skill.tags.length > 0);

  if (!hasMetadata) return null;

  return (
    <div className="mt-3 pt-3 border-t border-gray-100">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
        Metadata
      </p>
      <dl className="space-y-1">
        {skill.license && (
          <div className="flex gap-2 text-xs">
            <dt className="text-gray-500 w-24 shrink-0">License</dt>
            <dd className="text-gray-800 font-mono">{skill.license}</dd>
          </div>
        )}
        {skill.category && (
          <div className="flex gap-2 text-xs">
            <dt className="text-gray-500 w-24 shrink-0">Category</dt>
            <dd className="text-gray-800">{skill.category}</dd>
          </div>
        )}
        {skill.tags && skill.tags.length > 0 && (
          <div className="flex gap-2 text-xs">
            <dt className="text-gray-500 w-24 shrink-0">Tags</dt>
            <dd className="flex flex-wrap gap-1">
              {skill.tags.map((tag) => (
                <span
                  key={tag}
                  className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-xs"
                >
                  {tag}
                </span>
              ))}
            </dd>
          </div>
        )}
        {skill.allowedTools && skill.allowedTools.length > 0 && (
          <div className="flex gap-2 text-xs">
            <dt className="text-gray-500 w-24 shrink-0">Allowed Tools</dt>
            <dd className="flex flex-wrap gap-1">
              {skill.allowedTools.map((tool) => (
                <span
                  key={tool}
                  className="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded text-xs font-mono"
                >
                  {tool}
                </span>
              ))}
            </dd>
          </div>
        )}
        {skill.compatibility && (
          <div className="flex gap-2 text-xs">
            <dt className="text-gray-500 w-24 shrink-0">Compat.</dt>
            <dd className="text-gray-700">{skill.compatibility}</dd>
          </div>
        )}
        {skill.sourceUrl && (
          <div className="flex gap-2 text-xs">
            <dt className="text-gray-500 w-24 shrink-0">Source URL</dt>
            <dd className="text-blue-600 truncate max-w-xs">{skill.sourceUrl}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Promoted skills state
  const [promotedSkills, setPromotedSkills] = useState<SkillItem[]>([]);
  const [promotedLoading, setPromotedLoading] = useState(true);

  // Filter state
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [category, setCategory] = useState("");
  const [skillType, setSkillType] = useState("");
  const [sort, setSort] = useState("newest");

  // 300ms debounce on search query
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(timer);
  }, [query]);

  const fetchSkills = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (debouncedQuery) params.set("q", debouncedQuery);
      if (category) params.set("category", category);
      if (skillType) params.set("skill_type", skillType);
      if (sort) params.set("sort", sort);

      const url = `/api/skills${params.toString() ? `?${params.toString()}` : ""}`;
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`Failed to fetch skills: ${res.status}`);
      }
      const data: unknown = await res.json();
      const items = Array.isArray(data) ? data : (data as { items?: unknown[] }).items ?? [];

      setSkills((items as Record<string, unknown>[]).map(mapSkillItem));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load skills");
    } finally {
      setLoading(false);
    }
  }, [debouncedQuery, category, skillType, sort]);

  const fetchPromotedSkills = useCallback(async () => {
    setPromotedLoading(true);
    try {
      const res = await fetch("/api/skills?promoted=true");
      if (!res.ok) return;
      const data: unknown = await res.json();
      const items = Array.isArray(data) ? data : (data as { items?: unknown[] }).items ?? [];
      setPromotedSkills((items as Record<string, unknown>[]).map(mapSkillItem));
    } catch {
      // Non-fatal — promoted section simply won't show
    } finally {
      setPromotedLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchSkills();
  }, [fetchSkills]);

  useEffect(() => {
    void fetchPromotedSkills();
  }, [fetchPromotedSkills]);

  /** Trigger a ZIP download for the given skill via GET /api/skills/{id}/export. */
  const handleExport = (skill: SkillItem) => {
    fetch(`/api/skills/${skill.id}/export`)
      .then((res) => {
        if (!res.ok) return;
        const disposition = res.headers.get("Content-Disposition") ?? "";
        const filenameMatch = disposition.match(/filename="?([^"]+)"?/);
        const filename = filenameMatch?.[1] ?? `${skill.name}-${skill.version}.zip`;
        return res.blob().then((blob) => {
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = filename;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        });
      })
      .catch(() => {});
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Skills</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Browse available skills you can use with the agent.
        </p>
      </div>

      {/* Promoted / Featured Skills section — hidden when empty */}
      {!promotedLoading && promotedSkills.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-amber-500 text-base">★</span>
            <h2 className="text-base font-semibold text-gray-800">Featured Skills</h2>
            <span className="text-xs text-gray-400">Curated picks</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {promotedSkills.map((skill) => (
              <div key={skill.id} className="border border-amber-200 bg-amber-50 rounded-lg p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-gray-900">
                      {skill.displayName ?? skill.name}
                    </p>
                    {skill.description && (
                      <p className="text-xs text-gray-600 mt-1 line-clamp-2">
                        {skill.description}
                      </p>
                    )}
                  </div>
                  <span
                    className={`shrink-0 px-1.5 py-0.5 rounded text-xs ${
                      skill.skillType === "procedural"
                        ? "bg-blue-100 text-blue-700"
                        : "bg-purple-100 text-purple-700"
                    }`}
                  >
                    {skill.skillType}
                  </span>
                </div>
                {skill.usageCount > 0 && (
                  <p className="text-xs text-gray-400 mt-2">Used {skill.usageCount}x</p>
                )}
                <button
                  onClick={() => handleExport(skill)}
                  className="mt-2 text-xs text-gray-500 hover:text-gray-700 underline"
                >
                  Export
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2 mb-6">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search skills..."
          className="flex-1 min-w-48 text-sm border border-gray-300 rounded px-3 py-1.5 text-gray-900 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <input
          type="text"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          placeholder="Category"
          className="w-36 text-sm border border-gray-300 rounded px-3 py-1.5 text-gray-900 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <select
          value={skillType}
          onChange={(e) => setSkillType(e.target.value)}
          className="text-sm border border-gray-300 rounded px-3 py-1.5 text-gray-700 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">All types</option>
          <option value="instructional">Instructional</option>
          <option value="procedural">Procedural</option>
        </select>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          className="text-sm border border-gray-300 rounded px-3 py-1.5 text-gray-700 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="newest">Newest</option>
          <option value="oldest">Oldest</option>
          <option value="most_used">Most Used</option>
        </select>
      </div>

      {/* Error state */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="text-gray-500 py-8 text-sm">Loading skills...</div>
      )}

      {/* Empty state */}
      {!loading && !error && skills.length === 0 && (
        <div className="text-center py-12 text-sm text-gray-400">
          No skills found{debouncedQuery || category || skillType ? " matching your filters" : ""}.
        </div>
      )}

      {/* Skill grid — shows Shared badge per card, Export button via onExport */}
      {!loading && skills.length > 0 && (
        <ArtifactCardGrid
          items={skills}
          onExport={handleExport}
          renderExtra={(skill) => (
            <div>
              {/* Shared badge — only shown when skill was shared with this user */}
              {(skill as SkillItem).isShared && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-green-100 text-green-700 font-medium mb-1">
                  Shared
                </span>
              )}
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className={`px-1.5 py-0.5 rounded text-xs ${
                    skill.skillType === "procedural"
                      ? "bg-blue-100 text-blue-700"
                      : "bg-purple-100 text-purple-700"
                  }`}
                >
                  {skill.skillType}
                </span>
                {skill.usageCount > 0 && (
                  <span className="text-xs text-gray-400">
                    Used {skill.usageCount}x
                  </span>
                )}
              </div>
              <SkillMetadataPanel skill={skill} />
            </div>
          )}
          // No onEdit, onPatchStatus, onActivateVersion, artifactType
          // Omitting all action props (except onExport) suppresses all admin buttons
        />
      )}
    </div>
  );
}
