"use client";
/**
 * Admin MCP Servers page — list + card view, search, status filter, pagination.
 */
import { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import type { RegistryEntry, RegistryEntryCreate } from "@/lib/admin-types";
import { mapArraySnakeToCamel } from "@/lib/admin-types";
import { DualPagination } from "@/components/admin/dual-pagination";

type ViewMode = "list" | "card";
const PAGE_SIZE_OPTIONS = [10, 25, 50];

export default function AdminMcpServersPage() {
  const router = useRouter();
  const [servers, setServers] = useState<RegistryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  // Toolbar state
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("list");

  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

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
      const res = await fetch("/api/registry?type=mcp_server", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as unknown[];
      setServers(mapArraySnakeToCamel<RegistryEntry>(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load servers");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetchServers(); }, [fetchServers]);
  useEffect(() => { setPage(1); }, [search, filterStatus, pageSize]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return servers.filter((s) => {
      const matchSearch =
        !q ||
        s.name.toLowerCase().includes(q) ||
        (s.displayName ?? "").toLowerCase().includes(q) ||
        ((s.config.url as string) ?? "").toLowerCase().includes(q);
      const matchStatus = !filterStatus || s.status === filterStatus;
      return matchSearch && matchStatus;
    });
  }, [servers, search, filterStatus]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize);

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
      setFormData({ type: "mcp_server", name: "", displayName: null, description: null, config: { url: "", transport: "http_sse" }, status: "active" });
      void fetchServers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  };

  const handleStatusChange = async (id: string, status: string) => {
    try {
      await fetch(`/api/registry/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      void fetchServers();
    } catch { setError("Status update failed"); }
  };

  const StatusBadge = ({ status }: { status: string }) => (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
      status === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
    }`}>{status}</span>
  );

  if (loading) return <div className="text-gray-500 py-8">Loading MCP servers...</div>;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">MCP Servers</h2>
        <button onClick={() => setShowCreate(true)} className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors">
          + Register Server
        </button>
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <input
          type="search" value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Search servers or URL..."
          className="flex-1 min-w-[180px] text-sm border border-gray-300 rounded-md px-3 py-1.5 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}
          className="text-sm border border-gray-300 rounded-md px-2 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="archived">Archived</option>
        </select>
        <div className="flex border border-gray-300 rounded-md overflow-hidden">
          <button onClick={() => setViewMode("list")} title="List view"
            className={`px-2.5 py-1.5 transition-colors ${viewMode === "list" ? "bg-blue-600 text-white" : "bg-white text-gray-500 hover:bg-gray-50"}`}>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" /></svg>
          </button>
          <button onClick={() => setViewMode("card")} title="Card view"
            className={`px-2.5 py-1.5 transition-colors ${viewMode === "card" ? "bg-blue-600 text-white" : "bg-white text-gray-500 hover:bg-gray-50"}`}>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>
          </button>
        </div>
      </div>

      {error && <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-600">{error}</div>}

      {/* Create dialog */}
      {showCreate && (
        <div className="mb-6 p-4 bg-white border border-gray-200 rounded-lg">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Register MCP Server</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Name *</label>
              <input type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white" placeholder="crm-server" />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">URL *</label>
              <input type="text" value={(formData.config?.url as string) ?? ""}
                onChange={(e) => setFormData({ ...formData, config: { ...formData.config, url: e.target.value } })}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white" placeholder="http://mcp-crm:9000" />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-600 mb-1">Description</label>
              <input type="text" value={formData.description ?? ""} onChange={(e) => setFormData({ ...formData, description: e.target.value || null })}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white" placeholder="CRM MCP server" />
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button onClick={handleCreate} className="px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-700 transition-colors">Register</button>
            <button onClick={() => setShowCreate(false)} className="px-3 py-1.5 bg-gray-100 text-gray-700 text-xs font-medium rounded hover:bg-gray-200 transition-colors">Cancel</button>
          </div>
        </div>
      )}

      {/* Top pagination */}
      <DualPagination page={page} pageSize={pageSize} total={filtered.length} onPageChange={setPage} onPageSizeChange={setPageSize} />

      {/* Content */}
      {filtered.length === 0 ? (
        <div className="py-8 text-center text-sm text-gray-400">
          {search || filterStatus ? "No servers match the current filters." : "No MCP servers registered"}
        </div>
      ) : viewMode === "list" ? (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">URL</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {paginated.map((server) => (
                <tr key={server.id} onClick={() => router.push(`/admin/mcp-servers/${server.id}`)} className="hover:bg-gray-50 cursor-pointer">
                  <td className="px-4 py-2.5">
                    <span className="text-sm font-medium text-gray-900">{server.displayName ?? server.name}</span>
                    {server.displayName && <span className="text-xs text-gray-400 ml-1">({server.name})</span>}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="text-xs font-mono text-gray-600">{(server.config.url as string) ?? "-"}</span>
                  </td>
                  <td className="px-4 py-2.5"><StatusBadge status={server.status} /></td>
                  <td className="px-4 py-2.5 text-right" onClick={(e) => e.stopPropagation()}>
                    {server.status === "active" ? (
                      <button onClick={() => void handleStatusChange(server.id, "archived")} className="text-xs px-2 py-1 text-orange-600 hover:bg-orange-50 rounded transition-colors">Disable</button>
                    ) : (
                      <button onClick={() => void handleStatusChange(server.id, "active")} className="text-xs px-2 py-1 text-green-600 hover:bg-green-50 rounded transition-colors">Enable</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {paginated.map((server) => (
            <div key={server.id} onClick={() => router.push(`/admin/mcp-servers/${server.id}`)} className="bg-white border border-gray-200 rounded-lg p-4 flex flex-col gap-3 hover:shadow-sm transition-shadow cursor-pointer">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{server.displayName ?? server.name}</p>
                  {server.displayName && <p className="text-xs text-gray-400 font-mono mt-0.5">{server.name}</p>}
                </div>
                <StatusBadge status={server.status} />
              </div>
              {server.description && <p className="text-xs text-gray-500 line-clamp-2">{server.description}</p>}
              <div className="flex items-center justify-between mt-auto pt-2 border-t border-gray-100" onClick={(e) => e.stopPropagation()}>
                <span className="text-xs font-mono text-gray-500 truncate max-w-[60%]">{(server.config.url as string) ?? "-"}</span>
                {server.status === "active" ? (
                  <button onClick={() => void handleStatusChange(server.id, "archived")} className="text-xs text-orange-600 hover:text-orange-800">Disable</button>
                ) : (
                  <button onClick={() => void handleStatusChange(server.id, "active")} className="text-xs text-green-600 hover:text-green-800">Enable</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Bottom pagination */}
      <DualPagination page={page} pageSize={pageSize} total={filtered.length} onPageChange={setPage} onPageSizeChange={setPageSize} />
    </div>
  );
}
