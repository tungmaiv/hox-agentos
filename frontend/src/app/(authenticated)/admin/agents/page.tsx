"use client";
/**
 * Admin Agents page — CRUD management for agent definitions.
 *
 * Phase 24: migrated from /api/admin/agents to /api/registry?type=agent.
 */
import { useState, useEffect, useCallback } from "react";
import type { RegistryEntry, RegistryEntryCreate } from "@/lib/admin-types";
import { mapArraySnakeToCamel } from "@/lib/admin-types";

export default function AdminAgentsPage() {
  const [items, setItems] = useState<RegistryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
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
      const res = await fetch("/api/registry?type=agent", {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as unknown[];
      setItems(mapArraySnakeToCamel<RegistryEntry>(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load agents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchAgents();
  }, [fetchAgents]);

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
      setFormData({
        type: "agent",
        name: "",
        displayName: null,
        description: null,
        config: {},
        status: "draft",
      });
      void fetchAgents();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  };

  const handleDisable = async (id: string) => {
    try {
      const res = await fetch(`/api/registry/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "archived" }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      void fetchAgents();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Status update failed");
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
        <button
          onClick={() => setShowCreate(true)}
          className="px-3 py-1.5 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors"
        >
          Create Agent
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
                value={formData.displayName ?? ""}
                onChange={(e) =>
                  setFormData({ ...formData, displayName: e.target.value || null })
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

      {/* Table */}
      {items.length === 0 ? (
        <div className="text-gray-400 text-sm py-6 text-center">No agents found.</div>
      ) : (
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
            {items.map((item) => (
              <tr key={item.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-2 pr-4 font-mono text-gray-900">{item.name}</td>
                <td className="py-2 pr-4 text-gray-600">{item.displayName ?? "-"}</td>
                <td className="py-2 pr-4">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      item.status === "active"
                        ? "bg-green-100 text-green-700"
                        : item.status === "archived"
                        ? "bg-gray-100 text-gray-500"
                        : "bg-yellow-100 text-yellow-700"
                    }`}
                  >
                    {item.status}
                  </span>
                </td>
                <td className="py-2">
                  {item.status === "active" && (
                    <button
                      onClick={() => void handleDisable(item.id)}
                      className="text-xs text-red-600 hover:text-red-800"
                    >
                      Archive
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
