"use client";
/**
 * Admin Skills page — CRUD management for skill definitions.
 *
 * Additional columns for skill_type, slash_command, security_score.
 * Includes "Pending Review" filter shortcut and review actions.
 */
import { useState } from "react";
import { useAdminArtifacts } from "@/hooks/use-admin-artifacts";
import type { SkillDefinition, SkillDefinitionCreate } from "@/lib/admin-types";
import { ArtifactTable } from "@/components/admin/artifact-table";
import { ArtifactCardGrid } from "@/components/admin/artifact-card-grid";
import { ViewToggle, useViewMode } from "@/components/admin/view-toggle";

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

  const displayItems = showPendingOnly
    ? items.filter((s) => s.status === "pending_review")
    : items;

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
          )}
          onPatchStatus={patchStatus}
          onActivateVersion={activateVersion}
          onExport={handleExport}
        />
      )}
    </div>
  );
}
