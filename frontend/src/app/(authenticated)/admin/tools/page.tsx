"use client";
/**
 * Admin Tools page — CRUD management for tool definitions.
 *
 * Same pattern as agents page, with additional columns for
 * handler_type and sandbox_required.
 * Name search (300ms debounce) + handler_type dropdown filter.
 */
import { useState, useEffect } from "react";
import { useAdminArtifacts } from "@/hooks/use-admin-artifacts";
import type { ToolDefinition, ToolDefinitionCreate } from "@/lib/admin-types";
import { ArtifactTable } from "@/components/admin/artifact-table";
import { ArtifactCardGrid } from "@/components/admin/artifact-card-grid";
import { ViewToggle, useViewMode } from "@/components/admin/view-toggle";

export default function AdminToolsPage() {
  const { items, loading, error, create, patchStatus, activateVersion } =
    useAdminArtifacts<ToolDefinition>("tools");
  const [viewMode, setViewMode] = useViewMode();
  const [showCreate, setShowCreate] = useState(false);
  const [formData, setFormData] = useState<ToolDefinitionCreate>({
    name: "",
  });

  // Filter state
  const [toolSearch, setToolSearch] = useState("");
  const [debouncedToolSearch, setDebouncedToolSearch] = useState("");
  const [filterHandlerType, setFilterHandlerType] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setDebouncedToolSearch(toolSearch), 300);
    return () => clearTimeout(t);
  }, [toolSearch]);

  const handleCreate = async () => {
    const result = await create(formData as unknown as Record<string, unknown>);
    if (result) {
      setShowCreate(false);
      setFormData({ name: "" });
    }
  };

  const extraColumns = [
    {
      key: "handlerType",
      label: "Handler",
      render: (item: ToolDefinition) => (
        <span className="text-xs text-gray-600 bg-gray-100 px-1.5 py-0.5 rounded">
          {item.handlerType}
        </span>
      ),
    },
    {
      key: "sandboxRequired",
      label: "Sandbox",
      render: (item: ToolDefinition) =>
        item.sandboxRequired ? (
          <span className="text-xs text-orange-600">Required</span>
        ) : (
          <span className="text-xs text-gray-400">No</span>
        ),
    },
  ];

  const filteredTools = items.filter((item) => {
    const s = debouncedToolSearch.toLowerCase();
    const matchesName = !s || item.name.toLowerCase().includes(s);
    const matchesType = !filterHandlerType || item.handlerType === filterHandlerType;
    return matchesName && matchesType;
  });

  if (loading) {
    return <div className="text-gray-500 py-8">Loading tools...</div>;
  }

  return (
    <div>
      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <input
          type="text"
          value={toolSearch}
          onChange={(e) => setToolSearch(e.target.value)}
          placeholder="Search by name..."
          className="flex-1 min-w-40 text-sm border border-gray-300 rounded px-2 py-1.5 text-gray-900 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <select
          value={filterHandlerType}
          onChange={(e) => setFilterHandlerType(e.target.value)}
          className="text-sm border border-gray-300 rounded px-2 py-1.5 text-gray-700 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">All types</option>
          <option value="backend">Backend</option>
          <option value="mcp">MCP</option>
          <option value="sandbox">Sandbox</option>
        </select>
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Tool Definitions</h2>
        <div className="flex items-center gap-3">
          <ViewToggle value={viewMode} onChange={setViewMode} />
          <button
            onClick={() => setShowCreate(true)}
            className="px-3 py-1.5 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors"
          >
            Create Tool
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
          <h3 className="text-sm font-semibold text-gray-900 mb-3">New Tool</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Name *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white"
                placeholder="email.fetch"
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
                placeholder="Fetch Emails"
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
                placeholder="Fetches recent emails from user mailbox"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Handler Type</label>
              <select
                value={formData.handler_type ?? "backend"}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    handler_type: e.target.value as "backend" | "mcp" | "sandbox",
                  })
                }
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-700 bg-white"
              >
                <option value="backend">Backend</option>
                <option value="mcp">MCP</option>
                <option value="sandbox">Sandbox</option>
              </select>
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
            <div className="col-span-2 flex items-center gap-2">
              <input
                type="checkbox"
                id="sandbox_required"
                checked={formData.sandbox_required ?? false}
                onChange={(e) =>
                  setFormData({ ...formData, sandbox_required: e.target.checked })
                }
                className="w-4 h-4 text-blue-600 rounded border-gray-300"
              />
              <label htmlFor="sandbox_required" className="text-xs text-gray-600">
                Requires sandbox execution
              </label>
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

      {viewMode === "table" ? (
        <ArtifactTable
          items={filteredTools}
          columns={extraColumns}
          onPatchStatus={patchStatus}
          onActivateVersion={activateVersion}
        />
      ) : (
        <ArtifactCardGrid
          items={filteredTools}
          renderExtra={(item) => (
            <div className="flex items-center gap-2">
              <span className="bg-gray-100 px-1.5 py-0.5 rounded">
                {item.handlerType}
              </span>
              {item.sandboxRequired && (
                <span className="bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded">
                  Sandbox
                </span>
              )}
            </div>
          )}
          onPatchStatus={patchStatus}
          onActivateVersion={activateVersion}
        />
      )}
    </div>
  );
}
