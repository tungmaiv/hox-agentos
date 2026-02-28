"use client";
/**
 * Admin MCP Servers page — displays registered MCP servers with connectivity dots.
 *
 * Uses the existing MCP server admin API (evolved in 06-04).
 * Shows McpStatusDot per server (colored dot based on last_seen_at).
 */
import { useState, useEffect, useCallback } from "react";
import type { McpServerEntry } from "@/lib/admin-types";
import { mapArraySnakeToCamel } from "@/lib/admin-types";
import { McpStatusDot } from "@/components/admin/mcp-status-dot";
import { ViewToggle, useViewMode } from "@/components/admin/view-toggle";

export default function AdminMcpServersPage() {
  const [servers, setServers] = useState<McpServerEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useViewMode();

  const fetchServers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/mcp-servers", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as unknown[];
      setServers(mapArraySnakeToCamel<McpServerEntry>(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load servers");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchServers();
  }, [fetchServers]);

  const handleStatusToggle = async (
    id: string,
    newStatus: "active" | "disabled"
  ) => {
    try {
      const res = await fetch(`/api/admin/mcp-servers/${id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      void fetchServers();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to update status"
      );
    }
  };

  const handleHealthCheck = async (id: string) => {
    try {
      const res = await fetch(`/api/admin/mcp-servers/${id}/health`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as { healthy: boolean; latency_ms: number };
      alert(
        data.healthy
          ? `Server is healthy (${data.latency_ms}ms latency)`
          : "Server is unreachable"
      );
      void fetchServers();
    } catch {
      alert("Health check failed — server may be unreachable");
    }
  };

  if (loading) {
    return <div className="text-gray-500 py-8">Loading MCP servers...</div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">MCP Servers</h2>
        <ViewToggle value={viewMode} onChange={setViewMode} />
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-600">
          {error}
        </div>
      )}

      {viewMode === "table" ? (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  URL
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Version
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Enabled
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
                    <McpStatusDot lastSeenAt={server.lastSeenAt} />
                  </td>
                  <td className="px-4 py-2.5">
                    <div>
                      <span className="text-sm font-medium text-gray-900">
                        {server.displayName ?? server.name}
                      </span>
                      {server.displayName && (
                        <span className="text-xs text-gray-400 ml-1">
                          ({server.name})
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="text-xs font-mono text-gray-600">
                      {server.url}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="text-xs text-gray-600">
                      {server.version ?? "-"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    {server.isActive ? (
                      <span className="text-green-600 text-sm">&#10003;</span>
                    ) : (
                      <span className="text-gray-300 text-sm">-</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="inline-flex items-center gap-1">
                      <button
                        onClick={() => handleHealthCheck(server.id)}
                        className="text-xs px-2 py-1 text-blue-600 hover:bg-blue-50 rounded transition-colors"
                      >
                        Health Check
                      </button>
                      {server.status === "active" ? (
                        <button
                          onClick={() =>
                            handleStatusToggle(server.id, "disabled")
                          }
                          className="text-xs px-2 py-1 text-orange-600 hover:bg-orange-50 rounded transition-colors"
                        >
                          Disable
                        </button>
                      ) : (
                        <button
                          onClick={() =>
                            handleStatusToggle(server.id, "active")
                          }
                          className="text-xs px-2 py-1 text-green-600 hover:bg-green-50 rounded transition-colors"
                        >
                          Enable
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {servers.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-sm text-gray-400"
                  >
                    No MCP servers registered
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {servers.map((server) => (
            <div
              key={server.id}
              className="bg-white border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:shadow-sm transition-all"
            >
              <div className="flex items-center gap-2 mb-2">
                <McpStatusDot lastSeenAt={server.lastSeenAt} />
                <h3 className="text-sm font-medium text-gray-900">
                  {server.displayName ?? server.name}
                </h3>
              </div>
              <div className="text-xs font-mono text-gray-500 mb-2 truncate">
                {server.url}
              </div>
              <div className="flex items-center gap-2 text-xs text-gray-400 mb-3">
                {server.version && <span>v{server.version}</span>}
                <span>
                  {server.isActive ? "Enabled" : "Disabled"}
                </span>
              </div>
              <div className="flex items-center gap-1 border-t border-gray-100 pt-2">
                <button
                  onClick={() => handleHealthCheck(server.id)}
                  className="text-xs px-2 py-1 text-blue-600 hover:bg-blue-50 rounded transition-colors"
                >
                  Health Check
                </button>
                {server.status === "active" ? (
                  <button
                    onClick={() => handleStatusToggle(server.id, "disabled")}
                    className="text-xs px-2 py-1 text-orange-600 hover:bg-orange-50 rounded transition-colors"
                  >
                    Disable
                  </button>
                ) : (
                  <button
                    onClick={() => handleStatusToggle(server.id, "active")}
                    className="text-xs px-2 py-1 text-green-600 hover:bg-green-50 rounded transition-colors"
                  >
                    Enable
                  </button>
                )}
              </div>
            </div>
          ))}
          {servers.length === 0 && (
            <div className="col-span-3 text-center py-12 text-sm text-gray-400">
              No MCP servers registered
            </div>
          )}
        </div>
      )}
    </div>
  );
}
