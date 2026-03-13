"use client";
/**
 * Admin Agents page — list + card view, search, status filter, pagination.
 */
import { useState, useEffect, useCallback, useMemo } from "react";
import type { RegistryEntry, RegistryEntryCreate } from "@/lib/admin-types";
import { mapArraySnakeToCamel } from "@/lib/admin-types";

type ViewMode = "list" | "card";
const PAGE_SIZE_OPTIONS = [10, 25, 50];

export default function AdminAgentsPage() {
  const [items, setItems] = useState<RegistryEntry[]>([]);
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
    type: "agent",
    name: "",
    displayName: null,
    description: null,
    config: {},
    status: "draft",
  });

  const fetchAgents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/registry?type=agent", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as unknown[];
      setItems(mapArraySnakeToCamel<RegistryEntry>(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load agents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetchAgents(); }, [fetchAgents]);
  useEffect(() => { setPage(1); }, [search, filterStatus, pageSize]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((item) => {
      const matchSearch = !q || item.name.toLowerCase().includes(q) || (item.displayName ?? "").toLowerCase().includes(q);
      const matchStatus = !filterStatus || item.status === filterStatus;
      return matchSearch && matchStatus;
    });
  }, [items, search, filterStatus]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize);

  const handleCreate = async () => {
    try {
      const payload = {
        type: formData.type,
        name: formData.name,
        display_name: formData.displayName || null,
        description: formData.description || null,
        config: formData.config ?? {},
        status: formData.status ?? "draft",
      };
      const res = await fetch("/api/registry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setShowCreate(false);
      setFormData({ type: "agent", name: "", displayName: null, description: null, config: {}, status: "draft" });
      void fetchAgents();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  };

  const handleDisable = async (id: string) => {
    try {
      await fetch(`/api/registry/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "archived" }),
      });
      void fetchAgents();
    } catch { setError("Status update failed"); }
  };

  const StatusBadge = ({ status }: { status: string }) => (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
      status === "active" ? "bg-green-100 text-green-700"
      : status === "archived" ? "bg-gray-100 text-gray-500"
      : "bg-yellow-100 text-yellow-700"
    }`}>{status}</span>
  );

  if (loading) return <div className="text-gray-500 py-8">Loading agents...</div>;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Agent Definitions</h2>
        <button onClick={() => setShowCreate(true)} className="px-3 py-1.5 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors">
          Create Agent
        </button>
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <input
          type="search" value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Search agents..."
          className="flex-1 min-w-[180px] text-sm border border-gray-300 rounded-md px-3 py-1.5 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
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
          <h3 className="text-sm font-semibold text-gray-900 mb-3">New Agent</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Name *</label>
              <input type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white" placeholder="email_agent" />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Display Name</label>
              <input type="text" value={formData.displayName ?? ""} onChange={(e) => setFormData({ ...formData, displayName: e.target.value || null })}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white" placeholder="Email Agent" />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-600 mb-1">Description</label>
              <input type="text" value={formData.description ?? ""} onChange={(e) => setFormData({ ...formData, description: e.target.value || null })}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white" placeholder="Handles email-related tasks" />
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button onClick={handleCreate} className="px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-700 transition-colors">Create</button>
            <button onClick={() => setShowCreate(false)} className="px-3 py-1.5 bg-gray-100 text-gray-700 text-xs font-medium rounded hover:bg-gray-200 transition-colors">Cancel</button>
          </div>
        </div>
      )}

      {/* Content */}
      {filtered.length === 0 ? (
        <div className="text-gray-400 text-sm py-6 text-center">
          {search || filterStatus ? "No agents match the current filters." : "No agents found."}
        </div>
      ) : viewMode === "list" ? (
        <table className="w-full text-sm text-left">
          <thead>
            <tr className="border-b border-gray-200 text-xs text-gray-500 uppercase">
              <th className="py-2 pr-4">Name</th>
              <th className="py-2 pr-4">Display Name</th>
              <th className="py-2 pr-4">Status</th>
              <th className="py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {paginated.map((item) => (
              <tr key={item.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-2 pr-4 font-mono text-gray-900">{item.name}</td>
                <td className="py-2 pr-4 text-gray-600">{item.displayName ?? "-"}</td>
                <td className="py-2 pr-4"><StatusBadge status={item.status} /></td>
                <td className="py-2">
                  {item.status === "active" && (
                    <button onClick={() => void handleDisable(item.id)} className="text-xs text-red-600 hover:text-red-800">Archive</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {paginated.map((item) => (
            <div key={item.id} className="bg-white border border-gray-200 rounded-lg p-4 flex flex-col gap-3 hover:shadow-sm transition-shadow">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-mono text-sm font-medium text-gray-900 truncate">{item.name}</p>
                  {item.displayName && <p className="text-xs text-gray-500 mt-0.5">{item.displayName}</p>}
                </div>
                <StatusBadge status={item.status} />
              </div>
              {item.description && <p className="text-xs text-gray-500 line-clamp-2">{item.description}</p>}
              <div className="flex items-center justify-end mt-auto pt-2 border-t border-gray-100">
                {item.status === "active" && (
                  <button onClick={() => void handleDisable(item.id)} className="text-xs text-red-600 hover:text-red-800">Archive</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {filtered.length > 0 && (
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-200">
          <span className="text-xs text-gray-500">
            Showing {Math.min((page - 1) * pageSize + 1, filtered.length)}–{Math.min(page * pageSize, filtered.length)} of {filtered.length}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Rows:</span>
            <select value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))}
              className="text-xs border border-gray-300 rounded px-1.5 py-1 bg-white text-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500">
              {PAGE_SIZE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
              className="px-2 py-1 text-xs border border-gray-300 rounded bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
              ‹ Prev
            </button>
            <span className="text-xs text-gray-600 min-w-[60px] text-center">{page} / {totalPages}</span>
            <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
              className="px-2 py-1 text-xs border border-gray-300 rounded bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
              Next ›
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
