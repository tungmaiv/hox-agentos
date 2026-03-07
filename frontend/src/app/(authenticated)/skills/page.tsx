"use client";
/**
 * User Skills catalog page — browse all active skills.
 *
 * Uses ArtifactCardGrid + SkillMetadataPanel (same layout as admin view).
 * Admin-only actions are hidden by omitting all action props.
 * Supports FTS search (server-side via /api/skills?q=), category filter,
 * skill_type filter, and sort — all with 300ms debounce on search.
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

      const mapped: SkillItem[] = (items as Record<string, unknown>[]).map((item) => ({
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
      }));

      setSkills(mapped);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load skills");
    } finally {
      setLoading(false);
    }
  }, [debouncedQuery, category, skillType, sort]);

  useEffect(() => {
    void fetchSkills();
  }, [fetchSkills]);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Skills</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Browse available skills you can use with the agent.
        </p>
      </div>

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

      {/* Skill grid — read-only (no admin action props) */}
      {!loading && skills.length > 0 && (
        <ArtifactCardGrid
          items={skills}
          renderExtra={(skill) => (
            <div>
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
          // No onEdit, onPatchStatus, onActivateVersion, onExport, artifactType
          // Omitting all action props suppresses all admin buttons
        />
      )}
    </div>
  );
}
