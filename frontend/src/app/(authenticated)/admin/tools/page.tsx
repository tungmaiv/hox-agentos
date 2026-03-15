"use client";
/**
 * Admin Tools page — list + card view, search, handler/status filters, pagination.
 */
import { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import type { RegistryEntry, RegistryEntryCreate } from "@/lib/admin-types";
import { mapArraySnakeToCamel } from "@/lib/admin-types";
import { DualPagination } from "@/components/admin/dual-pagination";

type ViewMode = "list" | "card";
const PAGE_SIZE_OPTIONS = [10, 25, 50];

export default function AdminToolsPage() {
  const router = useRouter();
  const [items, setItems] = useState<RegistryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  // Toolbar state
  const [search, setSearch] = useState("");
  const [filterHandler, setFilterHandler] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("list");

  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const [formData, setFormData] = useState<RegistryEntryCreate>({
    type: "tool",
    name: "",
    displayName: null,
    description: null,
    config: { handler_type: "backend" },
    status: "draft",
  });

  const fetchTools = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/registry?type=tool", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as unknown[];
      setItems(mapArraySnakeToCamel<RegistryEntry>(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tools");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetchTools(); }, [fetchTools]);
  useEffect(() => { setPage(1); }, [search, filterHandler, filterStatus, pageSize]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((item) => {
      const matchSearch = !q || item.name.toLowerCase().includes(q) || (item.displayName ?? "").toLowerCase().includes(q);
      const matchHandler = !filterHandler || (item.config.handler_type as string) === filterHandler;
      const matchStatus = !filterStatus || item.status === filterStatus;
      return matchSearch && matchHandler && matchStatus;
    });
  }, [items, search, filterHandler, filterStatus]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize);

  const handleCreate = async () => {
    try {
      const payload = {
        type: formData.type,
        name: formData.name,
        display_name: formData.displayName || null,
        description: formData.description || null,
        config: formData.config ?? { handler_type: "backend" },
        status: formData.status ?? "draft",
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
      setFormData({ type: "tool", name: "", displayName: null, description: null, config: { handler_type: "backend" }, status: "draft" });
      void fetchTools();
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
      void fetchTools();
    } catch { setError("Status update failed"); }
  };

  const handleDelete = async (id: string) => {
    try {
      await fetch(`/api/registry/${id}`, { method: "DELETE" });
      void fetchTools();
    } catch { setError("Delete failed"); }
  };

  const StatusBadge = ({ status }: { status: string }) => (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
      status === "active" ? "bg-green-100 text-green-700"
      : status === "archived" ? "bg-gray-100 text-gray-500"
      : "bg-yellow-100 text-yellow-700"
    }`}>{status}</span>
  );

  const RowActions = ({ item }: { item: RegistryEntry }) => (
    <div className="flex gap-2">
      {item.status !== "active" && (
        <button onClick={() => void handleStatusChange(item.id, "active")} className="text-xs text-green-600 hover:text-green-800">Activate</button>
      )}
      {item.status === "active" && (
        <button onClick={() => void handleStatusChange(item.id, "archived")} className="text-xs text-red-600 hover:text-red-800">Archive</button>
      )}
      <button onClick={() => void handleDelete(item.id)} className="text-xs text-gray-400 hover:text-gray-600">Delete</button>
    </div>
  );

  if (loading) return <div className="text-gray-500 py-8">Loading tools...</div>;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Tool Definitions</h2>
        <button onClick={() => setShowCreate(true)} className="px-3 py-1.5 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors">
          Create Tool
        </button>
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <input
          type="search" value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Search tools..."
          className="flex-1 min-w-[180px] text-sm border border-gray-300 rounded-md px-3 py-1.5 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <select value={filterHandler} onChange={(e) => setFilterHandler(e.target.value)}
          className="text-sm border border-gray-300 rounded-md px-2 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">All handlers</option>
          <option value="backend">Backend</option>
          <option value="mcp">MCP</option>
          <option value="openapi_proxy">OpenAPI proxy</option>
          <option value="sandbox">Sandbox</option>
        </select>
        <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}
          className="text-sm border border-gray-300 rounded-md px-2 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="draft">Draft</option>
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
          <h3 className="text-sm font-semibold text-gray-900 mb-3">New Tool</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Name *</label>
              <input type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white" placeholder="email.fetch" />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Display Name</label>
              <input type="text" value={formData.displayName ?? ""} onChange={(e) => setFormData({ ...formData, displayName: e.target.value || null })}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white" placeholder="Fetch Emails" />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-600 mb-1">Description</label>
              <input type="text" value={formData.description ?? ""} onChange={(e) => setFormData({ ...formData, description: e.target.value || null })}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white" placeholder="Fetches recent emails from user mailbox" />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Handler Type</label>
              <select value={(formData.config?.handler_type as string) ?? "backend"}
                onChange={(e) => setFormData({ ...formData, config: { ...formData.config, handler_type: e.target.value } })}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-700 bg-white">
                <option value="backend">Backend</option>
                <option value="mcp">MCP</option>
                <option value="openapi_proxy">OpenAPI proxy</option>
                <option value="sandbox">Sandbox</option>
              </select>
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button onClick={handleCreate} className="px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-700 transition-colors">Create</button>
            <button onClick={() => setShowCreate(false)} className="px-3 py-1.5 bg-gray-100 text-gray-700 text-xs font-medium rounded hover:bg-gray-200 transition-colors">Cancel</button>
          </div>
        </div>
      )}

      {/* Top pagination */}
      <DualPagination page={page} pageSize={pageSize} total={filtered.length} onPageChange={setPage} onPageSizeChange={setPageSize} />

      {/* Content */}
      {filtered.length === 0 ? (
        <div className="text-gray-400 text-sm py-6 text-center">
          {search || filterHandler || filterStatus ? "No tools match the current filters." : "No tools found."}
        </div>
      ) : viewMode === "list" ? (
        <table className="w-full text-sm text-left">
          <thead>
            <tr className="border-b border-gray-200 text-xs text-gray-500 uppercase">
              <th className="py-2 pr-4">Name</th>
              <th className="py-2 pr-4">Handler</th>
              <th className="py-2 pr-4">Status</th>
              <th className="py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {paginated.map((item) => (
              <tr key={item.id} onClick={() => router.push(`/admin/tools/${item.id}`)} className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer">
                <td className="py-2 pr-4 font-mono text-gray-900">{item.name}</td>
                <td className="py-2 pr-4">
                  <span className="text-xs text-gray-600 bg-gray-100 px-1.5 py-0.5 rounded">{(item.config.handler_type as string) ?? "backend"}</span>
                </td>
                <td className="py-2 pr-4"><StatusBadge status={item.status} /></td>
                <td className="py-2" onClick={(e) => e.stopPropagation()}><RowActions item={item} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {paginated.map((item) => (
            <div key={item.id} onClick={() => router.push(`/admin/tools/${item.id}`)} className="bg-white border border-gray-200 rounded-lg p-4 flex flex-col gap-3 hover:shadow-sm transition-shadow cursor-pointer">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-mono text-sm font-medium text-gray-900 truncate">{item.name}</p>
                  {item.displayName && <p className="text-xs text-gray-500 mt-0.5">{item.displayName}</p>}
                </div>
                <StatusBadge status={item.status} />
              </div>
              {item.description && <p className="text-xs text-gray-500 line-clamp-2">{item.description}</p>}
              <div className="flex items-center justify-between mt-auto pt-2 border-t border-gray-100" onClick={(e) => e.stopPropagation()}>
                <span className="text-xs text-gray-600 bg-gray-100 px-1.5 py-0.5 rounded">{(item.config.handler_type as string) ?? "backend"}</span>
                <RowActions item={item} />
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
