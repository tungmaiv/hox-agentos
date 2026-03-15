"use client";
/**
 * Admin MCP server detail page — /admin/mcp-servers/[id].
 *
 * Provides form-based editing with three tabs:
 * - Overview: read-only metadata + editable display name / description
 * - Connection: URL, auth token, status, Test Connection button
 * - Tools: read-only list of tools registered from this server
 *
 * Uses RegistryDetailLayout for consistent shell with save bar.
 */
import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useParams } from "next/navigation";
import { mapSnakeToCamel, mapArraySnakeToCamel } from "@/lib/admin-types";
import type { RegistryEntry } from "@/lib/admin-types";
import { RegistryDetailLayout } from "@/components/admin/registry-detail-layout";
import {
  mcpServerFormSchema,
  validateField,
} from "@/lib/registry-schemas";
import type { McpServerFormValues } from "@/lib/registry-schemas";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TestResult {
  success: boolean;
  latency_ms: number;
  tool_count: number | null;
  error: string | null;
  hint: string | null;
}

interface ToolEntry {
  id: string;
  name: string;
  displayName: string | null;
  description: string | null;
  config: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "connection", label: "Connection" },
  { id: "tools", label: "Tools" },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AdminMcpServerDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [entry, setEntry] = useState<RegistryEntry | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("overview");

  // Form state
  const [formData, setFormData] = useState<McpServerFormValues>({
    displayName: null,
    description: null,
    url: "",
    authToken: null,
    status: "active",
  });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | null>>(
    {}
  );
  const initialFormRef = useRef<McpServerFormValues | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // Connection test state
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  // Tools tab state
  const [tools, setTools] = useState<ToolEntry[]>([]);
  const [toolsLoading, setToolsLoading] = useState(false);
  const [expandedSchemas, setExpandedSchemas] = useState<Set<string>>(
    new Set()
  );

  // ---------------------------------------------------------------------------
  // Data loading
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    fetch(`/api/registry/${id}`, { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const raw = (await res.json()) as unknown;
        const mapped = mapSnakeToCamel<RegistryEntry>(
          raw as Record<string, unknown>
        );
        setEntry(mapped);

        // Initialize form from entry
        const cfg = mapped.config;
        const initial: McpServerFormValues = {
          displayName: mapped.displayName ?? null,
          description: mapped.description ?? null,
          url: (cfg.url as string) ?? "",
          authToken: null, // Never pre-fill encrypted token
          status: mapped.status as McpServerFormValues["status"],
        };
        setFormData(initial);
        initialFormRef.current = initial;
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Failed to load MCP server"
        );
      })
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!saveMessage) return;
    const t = setTimeout(() => setSaveMessage(null), 3000);
    return () => clearTimeout(t);
  }, [saveMessage]);

  // ---------------------------------------------------------------------------
  // Change tracking
  // ---------------------------------------------------------------------------

  const hasChanges = useMemo(() => {
    if (!initialFormRef.current) return false;
    const init = initialFormRef.current;
    return (
      formData.displayName !== init.displayName ||
      formData.description !== init.description ||
      formData.url !== init.url ||
      (formData.authToken != null && formData.authToken !== "") ||
      formData.status !== init.status
    );
  }, [formData]);

  // ---------------------------------------------------------------------------
  // Field update + validation
  // ---------------------------------------------------------------------------

  const updateField = useCallback(
    (field: keyof McpServerFormValues, value: unknown) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
      setSaveMessage(null);
    },
    []
  );

  const validateOnBlur = useCallback(
    (field: keyof McpServerFormValues, value: unknown) => {
      const err = validateField(mcpServerFormSchema, field, value);
      setFieldErrors((prev) => ({ ...prev, [field]: err }));
    },
    []
  );

  // ---------------------------------------------------------------------------
  // Save
  // ---------------------------------------------------------------------------

  const handleSave = useCallback(async () => {
    if (!entry) return;

    // Validate all fields
    const result = mcpServerFormSchema.safeParse(formData);
    if (!result.success) {
      const errs: Record<string, string | null> = {};
      for (const issue of result.error.issues) {
        const key = issue.path[0];
        if (typeof key === "string") {
          errs[key] = issue.message;
        }
      }
      setFieldErrors(errs);
      return;
    }

    setSaving(true);
    setSaveMessage(null);

    // Build config update — merge with existing config
    const configUpdate: Record<string, unknown> = {
      ...entry.config,
      url: formData.url,
    };
    // Only include auth_token if the user entered a new one
    if (formData.authToken && formData.authToken.trim() !== "") {
      configUpdate.auth_token = formData.authToken;
    }

    const payload = {
      display_name: formData.displayName,
      description: formData.description,
      config: configUpdate,
      status: formData.status,
    };

    try {
      const res = await fetch(`/api/registry/${entry.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as Record<
          string,
          unknown
        > | null;
        throw new Error(
          (body?.detail as string) ?? `Save failed (HTTP ${res.status})`
        );
      }
      const raw = (await res.json()) as unknown;
      const updated = mapSnakeToCamel<RegistryEntry>(
        raw as Record<string, unknown>
      );
      setEntry(updated);

      // Reset form with updated values
      const cfg = updated.config;
      const newInitial: McpServerFormValues = {
        displayName: updated.displayName ?? null,
        description: updated.description ?? null,
        url: (cfg.url as string) ?? "",
        authToken: null, // Clear token field after save
        status: updated.status as McpServerFormValues["status"],
      };
      setFormData(newInitial);
      initialFormRef.current = newInitial;
      setFieldErrors({});
      setSaveMessage({ type: "success", text: "Changes saved successfully." });
    } catch (err: unknown) {
      setSaveMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Save failed",
      });
    } finally {
      setSaving(false);
    }
  }, [entry, formData]);

  // ---------------------------------------------------------------------------
  // Discard
  // ---------------------------------------------------------------------------

  const handleDiscard = useCallback(() => {
    if (initialFormRef.current) {
      setFormData(initialFormRef.current);
      setFieldErrors({});
      setSaveMessage(null);
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Connection test
  // ---------------------------------------------------------------------------

  const handleTestConnection = useCallback(async () => {
    setTesting(true);
    setTestResult(null);

    try {
      const res = await fetch("/api/admin/mcp-servers/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: formData.url,
          auth_token:
            formData.authToken && formData.authToken.trim() !== ""
              ? formData.authToken
              : null,
        }),
      });
      const data = (await res.json()) as TestResult;
      setTestResult(data);
    } catch {
      setTestResult({
        success: false,
        latency_ms: 0,
        tool_count: null,
        error: "Network error — could not reach test endpoint",
        hint: "Check that the backend is running",
      });
    } finally {
      setTesting(false);
    }
  }, [formData.url, formData.authToken]);

  // ---------------------------------------------------------------------------
  // Tools loading
  // ---------------------------------------------------------------------------

  const loadTools = useCallback(async () => {
    if (!entry) return;
    setToolsLoading(true);
    try {
      const res = await fetch("/api/registry?type=tool", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const raw = (await res.json()) as unknown;
      const items = Array.isArray(raw)
        ? mapArraySnakeToCamel<ToolEntry>(raw)
        : mapArraySnakeToCamel<ToolEntry>(
            (raw as Record<string, unknown[]>).items ?? []
          );
      // Filter tools belonging to this MCP server
      const serverTools = items.filter(
        (t) =>
          (t.config.mcp_server_id as string) === entry.id ||
          (t.config.mcpServerId as string) === entry.id
      );
      setTools(serverTools);
    } catch {
      setTools([]);
    } finally {
      setToolsLoading(false);
    }
  }, [entry]);

  // Load tools when switching to tools tab
  useEffect(() => {
    if (activeTab === "tools" && entry) {
      loadTools();
    }
  }, [activeTab, entry, loadTools]);

  const toggleSchema = useCallback((toolId: string) => {
    setExpandedSchemas((prev) => {
      const next = new Set(prev);
      if (next.has(toolId)) {
        next.delete(toolId);
      } else {
        next.add(toolId);
      }
      return next;
    });
  }, []);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="text-gray-400 text-sm py-8">Loading MCP server...</div>
    );
  }

  if (error || !entry) {
    return (
      <div className="py-8">
        <p className="text-red-600 text-sm mb-4">
          {error ?? "MCP server not found"}
        </p>
        <a
          href="/admin/mcp-servers"
          className="text-sm text-blue-600 hover:underline"
        >
          &larr; Back to MCP Servers
        </a>
      </div>
    );
  }

  return (
    <RegistryDetailLayout
      entry={entry}
      backHref="/admin/mcp-servers"
      backLabel="MCP Servers"
      tabs={TABS}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      hasChanges={hasChanges}
      saving={saving}
      onSave={handleSave}
      onDiscard={handleDiscard}
    >
      {saveMessage && (
        <div
          className={`mb-4 p-3 rounded text-sm ${
            saveMessage.type === "success"
              ? "bg-green-50 border border-green-200 text-green-700"
              : "bg-red-50 border border-red-200 text-red-700"
          }`}
        >
          {saveMessage.text}
        </div>
      )}

      {/* Overview tab */}
      {activeTab === "overview" && (
        <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
          {/* Read-only fields */}
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-gray-500">ID</dt>
              <dd className="font-mono text-gray-900 text-xs mt-0.5">
                {entry.id}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Name</dt>
              <dd className="text-gray-900 mt-0.5">{entry.name}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Status</dt>
              <dd className="text-gray-900 mt-0.5">{entry.status}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Owner ID</dt>
              <dd className="font-mono text-gray-900 text-xs mt-0.5">
                {entry.ownerId ?? "\u2014"}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Created</dt>
              <dd className="text-gray-900 mt-0.5">
                {new Date(entry.createdAt).toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Updated</dt>
              <dd className="text-gray-900 mt-0.5">
                {new Date(entry.updatedAt).toLocaleString()}
              </dd>
            </div>
          </dl>

          <hr className="border-gray-100" />

          {/* Editable fields */}
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Display Name
              </label>
              <input
                type="text"
                value={formData.displayName ?? ""}
                onChange={(e) =>
                  updateField(
                    "displayName",
                    e.target.value || null
                  )
                }
                onBlur={(e) =>
                  validateOnBlur("displayName", e.target.value || null)
                }
                placeholder="Optional display name"
                className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              {fieldErrors.displayName && (
                <p className="text-xs text-red-600 mt-1">
                  {fieldErrors.displayName}
                </p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description
              </label>
              <textarea
                value={formData.description ?? ""}
                onChange={(e) =>
                  updateField(
                    "description",
                    e.target.value || null
                  )
                }
                onBlur={(e) =>
                  validateOnBlur("description", e.target.value || null)
                }
                placeholder="Optional description"
                rows={3}
                className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              {fieldErrors.description && (
                <p className="text-xs text-red-600 mt-1">
                  {fieldErrors.description}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Connection tab */}
      {activeTab === "connection" && (
        <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              URL <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.url}
              onChange={(e) => updateField("url", e.target.value)}
              onBlur={(e) => validateOnBlur("url", e.target.value)}
              placeholder="https://mcp-server.example.com/sse"
              className={`w-full border rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                fieldErrors.url ? "border-red-300" : "border-gray-300"
              }`}
            />
            {fieldErrors.url && (
              <p className="text-xs text-red-600 mt-1">{fieldErrors.url}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Auth Token
            </label>
            <input
              type="password"
              value={formData.authToken ?? ""}
              onChange={(e) =>
                updateField("authToken", e.target.value || null)
              }
              placeholder="Enter new token to update"
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <p className="text-xs text-gray-400 mt-1">
              Leave empty to keep the existing token. The stored token is
              encrypted and cannot be displayed.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Status
            </label>
            <select
              value={formData.status}
              onChange={(e) =>
                updateField(
                  "status",
                  e.target.value as McpServerFormValues["status"]
                )
              }
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="active">Active</option>
              <option value="disabled">Disabled</option>
              <option value="deprecated">Deprecated</option>
            </select>
          </div>

          {/* Test Connection */}
          <div className="pt-2 border-t border-gray-100">
            <button
              onClick={handleTestConnection}
              disabled={testing || !formData.url}
              className="px-4 py-1.5 text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              {testing && (
                <svg
                  className="animate-spin h-4 w-4 text-white"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
              )}
              {testing ? "Testing..." : "Test Connection"}
            </button>

            {/* Test result card */}
            {testResult && (
              <div
                className={`mt-3 p-3 rounded-md border ${
                  testResult.success
                    ? "border-green-300 bg-green-50"
                    : "border-red-300 bg-red-50"
                }`}
              >
                {testResult.success ? (
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-green-800">
                      Connected
                    </p>
                    <p className="text-xs text-green-700">
                      Latency: {testResult.latency_ms}ms
                      {testResult.tool_count != null &&
                        ` \u00b7 ${testResult.tool_count} tool${testResult.tool_count !== 1 ? "s" : ""} available`}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-red-800">
                      {testResult.error ?? "Connection failed"}
                    </p>
                    {testResult.hint && (
                      <p className="text-xs text-gray-500">
                        {testResult.hint}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tools tab */}
      {activeTab === "tools" && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-700">
              Registered Tools
            </h3>
            <button
              onClick={loadTools}
              disabled={toolsLoading}
              className="px-3 py-1 text-xs font-medium rounded-md border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              {toolsLoading ? "Loading..." : "Refresh"}
            </button>
          </div>

          {toolsLoading && tools.length === 0 ? (
            <p className="text-sm text-gray-400">Loading tools...</p>
          ) : tools.length === 0 ? (
            <p className="text-sm text-gray-500">
              No tools registered from this server
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 pr-4 font-medium text-gray-500">
                    Name
                  </th>
                  <th className="text-left py-2 pr-4 font-medium text-gray-500">
                    Description
                  </th>
                  <th className="text-left py-2 font-medium text-gray-500">
                    Input Schema
                  </th>
                </tr>
              </thead>
              <tbody>
                {tools.map((tool) => {
                  const inputSchema = tool.config.input_schema as
                    | Record<string, unknown>
                    | null
                    | undefined;
                  return (
                    <tr
                      key={tool.id}
                      className="border-b border-gray-100 last:border-0"
                    >
                      <td className="py-2 pr-4 font-mono text-xs text-gray-900">
                        {tool.name}
                      </td>
                      <td className="py-2 pr-4 text-gray-600">
                        {tool.displayName ?? tool.description ?? "\u2014"}
                      </td>
                      <td className="py-2">
                        {inputSchema ? (
                          <div>
                            <button
                              onClick={() => toggleSchema(tool.id)}
                              className="text-xs text-blue-600 hover:underline"
                            >
                              {expandedSchemas.has(tool.id)
                                ? "Hide"
                                : "Show"}
                            </button>
                            {expandedSchemas.has(tool.id) && (
                              <pre className="mt-1 p-2 bg-gray-50 rounded text-xs overflow-auto max-h-48 text-gray-700">
                                {JSON.stringify(inputSchema, null, 2)}
                              </pre>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400">
                            None
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </RegistryDetailLayout>
  );
}
