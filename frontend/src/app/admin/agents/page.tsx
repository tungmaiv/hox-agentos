"use client";
/**
 * Admin Agents page — CRUD management for agent definitions.
 *
 * Uses useAdminArtifacts<AgentDefinition>("agents") for data.
 * Supports table/card view toggle and create dialog.
 */
import { useState } from "react";
import { useAdminArtifacts } from "@/hooks/use-admin-artifacts";
import type { AgentDefinition, AgentDefinitionCreate } from "@/lib/admin-types";
import { ArtifactTable } from "@/components/admin/artifact-table";
import { ArtifactCardGrid } from "@/components/admin/artifact-card-grid";
import { ViewToggle, useViewMode } from "@/components/admin/view-toggle";

export default function AdminAgentsPage() {
  const { items, loading, error, create, patchStatus, activateVersion } =
    useAdminArtifacts<AgentDefinition>("agents");
  const [viewMode, setViewMode] = useViewMode();
  const [showCreate, setShowCreate] = useState(false);
  const [formData, setFormData] = useState<AgentDefinitionCreate>({
    name: "",
  });

  const handleCreate = async () => {
    const result = await create(formData as unknown as Record<string, unknown>);
    if (result) {
      setShowCreate(false);
      setFormData({ name: "" });
    }
  };

  if (loading) {
    return <div className="text-gray-500 py-8">Loading agents...</div>;
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Agent Definitions</h2>
        <div className="flex items-center gap-3">
          <ViewToggle value={viewMode} onChange={setViewMode} />
          <button
            onClick={() => setShowCreate(true)}
            className="px-3 py-1.5 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors"
          >
            Create Agent
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Create dialog */}
      {showCreate && (
        <div className="mb-6 p-4 bg-white border border-gray-200 rounded-lg">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">New Agent</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Name *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white"
                placeholder="email_agent"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Display Name</label>
              <input
                type="text"
                value={formData.display_name ?? ""}
                onChange={(e) =>
                  setFormData({ ...formData, display_name: e.target.value || null })
                }
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white"
                placeholder="Email Agent"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-600 mb-1">Description</label>
              <input
                type="text"
                value={formData.description ?? ""}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value || null })
                }
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white"
                placeholder="Handles email-related tasks"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Handler Module</label>
              <input
                type="text"
                value={formData.handler_module ?? ""}
                onChange={(e) =>
                  setFormData({ ...formData, handler_module: e.target.value || null })
                }
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white"
                placeholder="agents.subagents.email_agent"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Handler Function</label>
              <input
                type="text"
                value={formData.handler_function ?? ""}
                onChange={(e) =>
                  setFormData({ ...formData, handler_function: e.target.value || null })
                }
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white"
                placeholder="handle_email"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Version</label>
              <input
                type="text"
                value={formData.version ?? "1.0.0"}
                onChange={(e) => setFormData({ ...formData, version: e.target.value })}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white"
                placeholder="1.0.0"
              />
            </div>
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

      {/* Views */}
      {viewMode === "table" ? (
        <ArtifactTable
          items={items}
          onPatchStatus={patchStatus}
          onActivateVersion={activateVersion}
        />
      ) : (
        <ArtifactCardGrid
          items={items}
          onPatchStatus={patchStatus}
          onActivateVersion={activateVersion}
        />
      )}
    </div>
  );
}
