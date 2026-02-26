"use client";
// frontend/src/app/settings/integrations/page.tsx
/**
 * Settings → Integrations — live CRUD management of MCP servers.
 *
 * Client Component: needs useState for form state + fetch on mount.
 * Proxy routes inject the Bearer token server-side — auth tokens never touch browser.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { z } from "zod";

// ---------------------------------------------------------------------------
// Zod schema for API response validation
// ---------------------------------------------------------------------------
const McpServerSchema = z.object({
  id: z.string(),
  name: z.string(),
  url: z.string(),
  is_active: z.boolean(),
  status: z.string().optional(),
});

const McpServersResponseSchema = z.array(McpServerSchema);

type McpServer = z.infer<typeof McpServerSchema>;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function IntegrationsSettingsPage() {
  const [servers, setServers] = useState<McpServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formUrl, setFormUrl] = useState("");
  const [formToken, setFormToken] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchServers = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/mcp-servers", { cache: "no-store" });
      if (res.status === 403) {
        setError("Admin access required to manage MCP servers.");
        setLoading(false);
        return;
      }
      if (!res.ok) {
        setError(`Failed to fetch servers (${res.status})`);
        setLoading(false);
        return;
      }
      const raw = (await res.json()) as unknown;
      const parsed = McpServersResponseSchema.safeParse(raw);
      if (!parsed.success) {
        setError("Unexpected response format from server.");
        setLoading(false);
        return;
      }
      setServers(parsed.data);
    } catch {
      setError("Network error — could not reach backend.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchServers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim() || !formUrl.trim()) return;
    setSubmitting(true);
    try {
      const body: Record<string, string> = {
        name: formName.trim(),
        url: formUrl.trim(),
      };
      if (formToken.trim()) {
        body.auth_token = formToken.trim();
      }
      const res = await fetch("/api/admin/mcp-servers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = (await res.json()) as { detail?: string };
        setError(data.detail ?? `Failed to add server (${res.status})`);
        return;
      }
      setFormName("");
      setFormUrl("");
      setFormToken("");
      await fetchServers();
    } catch {
      setError("Network error — could not add server.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Remove this MCP server?")) return;
    try {
      const res = await fetch(`/api/admin/mcp-servers/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const data = (await res.json()) as { detail?: string };
        setError(data.detail ?? `Failed to delete server (${res.status})`);
        return;
      }
      await fetchServers();
    } catch {
      setError("Network error — could not delete server.");
    }
  };

  return (
    <main className="max-w-2xl mx-auto p-8">
      <div className="mb-6">
        <Link href="/settings" className="text-sm text-blue-600 hover:underline">
          &larr; Back to Settings
        </Link>
      </div>

      <h1 className="text-2xl font-semibold mb-2">Integrations</h1>
      <p className="text-sm text-gray-500 mb-8">
        Connect MCP servers to extend Blitz with external tools and data sources.
      </p>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Server list */}
      <section className="border border-gray-200 rounded-lg overflow-hidden mb-8">
        <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
          <h2 className="text-sm font-medium text-gray-700">Registered MCP Servers</h2>
        </div>

        {loading ? (
          <div className="px-4 py-6 text-sm text-gray-400 text-center">
            Loading...
          </div>
        ) : servers.length === 0 ? (
          <div className="px-4 py-6 text-sm text-gray-400 text-center">
            No MCP servers registered yet. Add one below.
          </div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {servers.map((server) => (
              <li
                key={server.id}
                className="flex items-center justify-between px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-gray-900">{server.name}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{server.url}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      server.is_active
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {server.is_active ? "active" : "inactive"}
                  </span>
                  <button
                    onClick={() => void handleDelete(server.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Remove
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Add server form */}
      <section className="border border-gray-200 rounded-lg overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
          <h2 className="text-sm font-medium text-gray-700">Add MCP Server</h2>
        </div>
        <form onSubmit={(e) => void handleAdd(e)} className="px-4 py-4 space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="e.g. crm"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              URL <span className="text-red-500">*</span>
            </label>
            <input
              type="url"
              value={formUrl}
              onChange={(e) => setFormUrl(e.target.value)}
              placeholder="e.g. http://mcp-crm:8001"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Auth Token <span className="text-gray-400">(optional)</span>
            </label>
            <input
              type="password"
              value={formToken}
              onChange={(e) => setFormToken(e.target.value)}
              placeholder="Bearer token if the server requires auth"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? "Adding..." : "Add Server"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
