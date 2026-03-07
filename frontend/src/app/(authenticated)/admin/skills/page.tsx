"use client";
/**
 * Admin Skills page — CRUD management for skill definitions.
 *
 * Additional columns for skill_type, slash_command, security_score.
 * Includes "Pending Review" filter shortcut and review actions.
 * Shows agentskills.io standard metadata fields (read-only) in detail panel.
 * FTS search + category + author + sort filter bar (client-side filtering).
 */
import { useState, useEffect } from "react";
import { useAdminArtifacts } from "@/hooks/use-admin-artifacts";
import type { SkillDefinition, SkillDefinitionCreate } from "@/lib/admin-types";
import { ArtifactTable } from "@/components/admin/artifact-table";
import { ArtifactCardGrid } from "@/components/admin/artifact-card-grid";
import { ViewToggle, useViewMode } from "@/components/admin/view-toggle";

/** Read-only metadata section shown when a skill has any of the 7 new fields. */
function SkillMetadataPanel({ skill }: { skill: SkillDefinition }) {
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

export default function AdminSkillsPage() {
  const { items, loading, error, create, patchStatus, activateVersion, refetch } =
    useAdminArtifacts<SkillDefinition>("skills");
  const [viewMode, setViewMode] = useViewMode();
  const [showCreate, setShowCreate] = useState(false);
  const [showPendingOnly, setShowPendingOnly] = useState(false);
  const [formData, setFormData] = useState<SkillDefinitionCreate>({
    name: "",
    skill_type: "instructional",
  });

  // Filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [filterAuthor, setFilterAuthor] = useState("");
  const [sortMode, setSortMode] = useState("newest");

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(searchQuery), 300);
    return () => clearTimeout(t);
  }, [searchQuery]);

  const handleCreate = async () => {
    const result = await create(formData as unknown as Record<string, unknown>);
    if (result) {
      setShowCreate(false);
      setFormData({ name: "", skill_type: "instructional" });
    }
  };

  const handleReview = async (
    skillId: string,
    decision: "approve" | "reject"
  ) => {
    try {
      await fetch(`/api/admin/skills/${skillId}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision }),
      });
      refetch();
    } catch {
      // Error handled by hook
    }
  };

  const handleExport = (skill: SkillDefinition) => {
    // Trigger browser download of the skill zip.
    // Use fetch + createObjectURL pattern to get the correct filename from
    // the Content-Disposition header and avoid opening in a new tab.
    fetch(`/api/admin/skills/${skill.id}/export`)
      .then((res) => {
        if (!res.ok) {
          return;
        }
        const disposition = res.headers.get("Content-Disposition") ?? "";
        const filenameMatch = disposition.match(/filename="?([^"]+)"?/);
        const filename =
          filenameMatch?.[1] ?? `${skill.name}-${skill.version}.zip`;
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
      .catch(() => {
        // Silent failure — export is a convenience feature
      });
  };

  const baseItems = showPendingOnly
    ? items.filter((s) => s.status === "pending_review")
    : items;

  const filteredItems = baseItems.filter((item) => {
    const s = debouncedSearch.toLowerCase();
    const matchesSearch =
      !s ||
      item.name.toLowerCase().includes(s) ||
      (item.description ?? "").toLowerCase().includes(s);
    const matchesCategory = !filterCategory || item.category === filterCategory;
    const matchesAuthor = !filterAuthor || item.createdBy === filterAuthor;
    return matchesSearch && matchesCategory && matchesAuthor;
  });

  const displayItems = [...filteredItems].sort((a, b) => {
    if (sortMode === "most_used") {
      return 0; // usageCount not in SkillDefinition — preserve order
    }
    if (sortMode === "oldest") {
      return new Date(a.createdAt ?? 0).getTime() - new Date(b.createdAt ?? 0).getTime();
    }
    // newest (default)
    return new Date(b.createdAt ?? 0).getTime() - new Date(a.createdAt ?? 0).getTime();
  });

  const extraColumns = [
    {
      key: "skillType",
      label: "Type",
      render: (item: SkillDefinition) => (
        <span
          className={`text-xs px-1.5 py-0.5 rounded ${
            item.skillType === "procedural"
              ? "bg-blue-100 text-blue-700"
              : "bg-purple-100 text-purple-700"
          }`}
        >
          {item.skillType}
        </span>
      ),
    },
    {
      key: "slashCommand",
      label: "Command",
      render: (item: SkillDefinition) =>
        item.slashCommand ? (
          <span className="text-xs font-mono text-gray-600">
            {item.slashCommand}
          </span>
        ) : (
          <span className="text-xs text-gray-400">-</span>
        ),
    },
    {
      key: "securityScore",
      label: "Security",
      render: (item: SkillDefinition) => {
        if (item.securityScore === null) {
          return <span className="text-xs text-gray-400">-</span>;
        }
        const color =
          item.securityScore >= 70
            ? "text-green-600"
            : item.securityScore >= 40
              ? "text-yellow-600"
              : "text-red-600";
        return (
          <span className={`text-xs font-medium ${color}`}>
            {item.securityScore}/100
          </span>
        );
      },
    },
  ];

  if (loading) {
    return <div className="text-gray-500 py-8">Loading skills...</div>;
  }

  return (
    <div>
      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search skills..."
          className="flex-1 min-w-40 text-sm border border-gray-300 rounded px-2 py-1.5 text-gray-900 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <input
          type="text"
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          placeholder="Category"
          className="w-32 text-sm border border-gray-300 rounded px-2 py-1.5 text-gray-900 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <input
          type="text"
          value={filterAuthor}
          onChange={(e) => setFilterAuthor(e.target.value)}
          placeholder="Author UUID"
          className="w-36 text-sm border border-gray-300 rounded px-2 py-1.5 text-gray-900 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <select
          value={sortMode}
          onChange={(e) => setSortMode(e.target.value)}
          className="text-sm border border-gray-300 rounded px-2 py-1.5 text-gray-700 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="newest">Newest</option>
          <option value="oldest">Oldest</option>
          <option value="most_used">Most Used</option>
        </select>
      </div>

      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-gray-900">
            Skill Definitions
          </h2>
          <button
            onClick={() => setShowPendingOnly(!showPendingOnly)}
            className={`text-xs px-2 py-1 rounded border transition-colors ${
              showPendingOnly
                ? "bg-yellow-100 border-yellow-300 text-yellow-700"
                : "bg-white border-gray-300 text-gray-600 hover:bg-gray-50"
            }`}
          >
            Pending Review
          </button>
        </div>
        <div className="flex items-center gap-3">
          <ViewToggle value={viewMode} onChange={setViewMode} />
          <button
            onClick={() => setShowCreate(true)}
            className="px-3 py-1.5 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors"
          >
            Create Skill
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-600">
          {error}
        </div>
      )}

      {showCreate && (
        <div className="mb-6 p-4 bg-white border border-gray-200 rounded-lg">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">New Skill</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Name *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white"
                placeholder="daily_standup"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">
                Skill Type *
              </label>
              <select
                value={formData.skill_type}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    skill_type: e.target.value as "instructional" | "procedural",
                  })
                }
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-700 bg-white"
              >
                <option value="instructional">Instructional</option>
                <option value="procedural">Procedural</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">
                Display Name
              </label>
              <input
                type="text"
                value={formData.display_name ?? ""}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    display_name: e.target.value || null,
                  })
                }
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white"
                placeholder="Daily Standup"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">
                Slash Command
              </label>
              <input
                type="text"
                value={formData.slash_command ?? ""}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    slash_command: e.target.value || null,
                  })
                }
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white"
                placeholder="/standup"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-600 mb-1">
                Description
              </label>
              <input
                type="text"
                value={formData.description ?? ""}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    description: e.target.value || null,
                  })
                }
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white"
                placeholder="Run daily standup summary"
              />
            </div>
            {formData.skill_type === "instructional" && (
              <div className="col-span-2">
                <label className="block text-xs text-gray-600 mb-1">
                  Instruction Markdown *
                </label>
                <textarea
                  value={formData.instruction_markdown ?? ""}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      instruction_markdown: e.target.value || null,
                    })
                  }
                  className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white min-h-[80px]"
                  placeholder="Instructions for the agent..."
                />
              </div>
            )}
          </div>
          <div className="flex items-center gap-2 mt-4">
            <button
              onClick={handleCreate}
              className="px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-700 transition-colors"
            >
              Create
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 text-xs font-medium rounded hover:bg-gray-200 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {viewMode === "table" ? (
        <ArtifactTable
          items={displayItems}
          columns={extraColumns}
          onPatchStatus={patchStatus}
          onActivateVersion={activateVersion}
          onExport={handleExport}
        />
      ) : (
        <ArtifactCardGrid
          items={displayItems}
          renderExtra={(item) => (
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className={`px-1.5 py-0.5 rounded ${
                    item.skillType === "procedural"
                      ? "bg-blue-100 text-blue-700"
                      : "bg-purple-100 text-purple-700"
                  }`}
                >
                  {item.skillType}
                </span>
                {item.slashCommand && (
                  <span className="font-mono text-gray-600">
                    {item.slashCommand}
                  </span>
                )}
                {item.securityScore !== null && (
                  <span
                    className={`font-medium ${
                      item.securityScore >= 70
                        ? "text-green-600"
                        : item.securityScore >= 40
                          ? "text-yellow-600"
                          : "text-red-600"
                    }`}
                  >
                    Score: {item.securityScore}
                  </span>
                )}
                {item.securityScore !== null && item.securityScore < 70 && (
                  <div className="flex gap-1 ml-auto">
                    <button
                      onClick={() => handleReview(item.id, "approve")}
                      className="px-1.5 py-0.5 bg-green-100 text-green-700 rounded hover:bg-green-200"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleReview(item.id, "reject")}
                      className="px-1.5 py-0.5 bg-red-100 text-red-700 rounded hover:bg-red-200"
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
              <SkillMetadataPanel skill={item as SkillDefinition} />
            </div>
          )}
          onPatchStatus={patchStatus}
          onActivateVersion={activateVersion}
          onExport={handleExport}
        />
      )}
    </div>
  );
}
