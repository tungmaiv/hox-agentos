"use client";
/**
 * Admin MCP Servers page — displays registered MCP servers.
 *
 * Phase 24: migrated from /api/admin/mcp-servers to /api/registry?type=mcp_server.
 */
import { useState, useEffect, useCallback } from "react";
import type { RegistryEntry, RegistryEntryCreate } from "@/lib/admin-types";
import { mapArraySnakeToCamel } from "@/lib/admin-types";

export default function AdminMcpServersPage() {
  const [servers, setServers] = useState<RegistryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [formData, setFormData] = useState<RegistryEntryCreate>({
    type: "mcp_server",
    name: "",
    displayName: null,
    description: null,
    config: { url: "", transport: "http_sse" },
    status: "active",
  });

  const fetchServers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/registry?type=mcp_server", {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as unknown[];
      setServers(mapArraySnakeToCamel<RegistryEntry>(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load servers");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchServers();
  }, [fetchServers]);

  const handleCreate = async () => {
    try {
      const payload = {
        type: formData.type,
        name: formData.name,
        display_name: formData.displayName || null,
        description: formData.description || null,
        config: formData.config ?? { url: "", transport: "http_sse" },
        status: formData.status ?? "active",
      };
      const res = await fetch("/api/registry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(body.detail ?? `HTTP ${res.status}`);
      }
      setShowCreate(false);
      setFormData({
        type: "mcp_server",
        name: "",
        displayName: null,
        description: null,
        config: { url: "", transport: "http_sse" },
        status: "active",
      });
      void fetchServers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  };

  const handleStatusChange = async (id: string, status: string) => {
    try {
      const res = await fetch(`/api/registry/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      void fetchServers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Status update failed");
    }
  };

  if (loading) {
    return <div className="text-gray-500 py-8">Loading MCP servers...</div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">MCP Servers</h2>
        <button
          onClick={() => setShowCreate(true)}
          className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors"
        >
          + Register Server
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Create dialog */}
      {showCreate && (
        <div className="mb-6 p-4 bg-white border border-gray-200 rounded-lg">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Register MCP Server</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Name *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white"
                placeholder="crm-server"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">URL *</label>
              <input
                type="text"
                value={(formData.config?.url as string) ?? ""}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    config: { ...formData.config, url: e.target.value },
                  })
                }
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white"
                placeholder="http://mcp-crm:9000"
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
                placeholder="CRM MCP server"
              />
            </div>
          </div>
          <div className="flex items-center gap-2 mt-4">
            <button
              onClick={handleCreate}
              className="px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-700 transition-colors"
            >
              Register
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

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Name
              </th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                URL
              </th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {servers.map((server) => (
              <tr key={server.id} className="hover:bg-gray-50">
                <td className="px-4 py-2.5">
                  <span className="text-sm font-medium text-gray-900">
                    {server.displayName ?? server.name}
                  </span>
                  {server.displayName && (
                    <span className="text-xs text-gray-400 ml-1">
                      ({server.name})
                    </span>
                  )}
                </td>
                <td className="px-4 py-2.5">
                  <span className="text-xs font-mono text-gray-600">
                    {(server.config.url as string) ?? "-"}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      server.status === "active"
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {server.status}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-right">
                  {server.status === "active" ? (
                    <button
                      onClick={() => void handleStatusChange(server.id, "archived")}
                      className="text-xs px-2 py-1 text-orange-600 hover:bg-orange-50 rounded transition-colors"
                    >
                      Disable
                    </button>
                  ) : (
                    <button
                      onClick={() => void handleStatusChange(server.id, "active")}
                      className="text-xs px-2 py-1 text-green-600 hover:bg-green-50 rounded transition-colors"
                    >
                      Enable
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {servers.length === 0 && (
              <tr>
                <td
                  colSpan={4}
                  className="px-4 py-8 text-center text-sm text-gray-400"
                >
                  No MCP servers registered
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
