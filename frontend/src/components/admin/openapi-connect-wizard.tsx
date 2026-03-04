"use client";
/**
 * OpenAPIConnectWizard — 3-step admin wizard for connecting OpenAPI services as tools.
 *
 * Step 1 — Paste URL: admin provides an OpenAPI spec URL → fetch & parse
 * Step 2 — Select Endpoints: collapsible tag groups, method badges, individual selection
 * Step 3 — Configure Server: name + auth type (Bearer/API Key/Basic/None) → register
 *
 * On success: shows tools_created count toast, closes wizard, triggers refresh.
 *
 * Calls:
 *   POST /api/admin/openapi/parse  → ParseResponse
 *   POST /api/admin/openapi/register → RegisterResponse
 *
 * The catch-all admin proxy at /api/admin/[...path]/route.ts forwards
 * these automatically — no new proxy routes needed.
 */
import { useState, useCallback } from "react";

// ---------------------------------------------------------------------------
// Types matching the backend Pydantic schemas
// ---------------------------------------------------------------------------

interface ParameterInfo {
  name: string;
  location: string;
  required: boolean;
  schema_type: string;
  description: string | null;
}

interface EndpointInfo {
  operation_id: string | null;
  method: string;
  path: string;
  summary: string | null;
  description: string | null;
  tags: string[];
  parameters: ParameterInfo[];
  request_body_schema: Record<string, unknown> | null;
  deprecated: boolean;
}

interface ParseResponse {
  base_url: string;
  title: string | null;
  version: string | null;
  endpoints: EndpointInfo[];
  tag_groups: Record<string, number[]>;
}

interface RegisterResponse {
  server_id: string;
  tools_created: number;
}

// Auth type choices
type AuthType = "none" | "bearer" | "api_key" | "basic";

interface WizardState {
  step: 1 | 2 | 3;
  // Step 1
  specUrl: string;
  isParsing: boolean;
  parseError: string | null;
  // Step 2 state (populated after parse)
  parseResult: ParseResponse | null;
  selectedIndices: Set<number>;
  collapsedTags: Set<string>;
  // Step 3
  serverName: string;
  authType: AuthType;
  bearerToken: string;
  apiKey: string;
  apiKeyHeader: string;
  basicUsername: string;
  basicPassword: string;
  isRegistering: boolean;
  registerError: string | null;
}

const INITIAL_STATE: WizardState = {
  step: 1,
  specUrl: "",
  isParsing: false,
  parseError: null,
  parseResult: null,
  selectedIndices: new Set(),
  collapsedTags: new Set(),
  serverName: "",
  authType: "none",
  bearerToken: "",
  apiKey: "",
  apiKeyHeader: "X-API-Key",
  basicUsername: "",
  basicPassword: "",
  isRegistering: false,
  registerError: null,
};

// ---------------------------------------------------------------------------
// Method badge colors
// ---------------------------------------------------------------------------

const METHOD_BADGE_CLASSES: Record<string, string> = {
  GET: "bg-green-100 text-green-800",
  POST: "bg-blue-100 text-blue-800",
  PUT: "bg-orange-100 text-orange-800",
  PATCH: "bg-yellow-100 text-yellow-800",
  DELETE: "bg-red-100 text-red-800",
  HEAD: "bg-gray-100 text-gray-800",
  OPTIONS: "bg-purple-100 text-purple-800",
};

function MethodBadge({ method }: { method: string }) {
  const classes =
    METHOD_BADGE_CLASSES[method.toUpperCase()] ?? "bg-gray-100 text-gray-800";
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-mono font-semibold ${classes}`}
    >
      {method.toUpperCase()}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface OpenAPIConnectWizardProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

// ---------------------------------------------------------------------------
// Main wizard component
// ---------------------------------------------------------------------------

export function OpenAPIConnectWizard({
  open,
  onClose,
  onSuccess,
}: OpenAPIConnectWizardProps) {
  const [state, setState] = useState<WizardState>(INITIAL_STATE);

  const reset = useCallback(() => {
    setState(INITIAL_STATE);
  }, []);

  const handleClose = useCallback(() => {
    reset();
    onClose();
  }, [reset, onClose]);

  // ── Step 1: Fetch & parse ────────────────────────────────────────────────

  const handleParse = useCallback(async () => {
    if (!state.specUrl.trim()) return;

    setState((prev) => ({ ...prev, isParsing: true, parseError: null }));

    try {
      const res = await fetch("/api/admin/openapi/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: state.specUrl.trim() }),
      });

      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as Record<
          string,
          unknown
        >;
        const detail =
          typeof body.detail === "string" ? body.detail : `HTTP ${res.status}`;
        throw new Error(detail);
      }

      const parsed = (await res.json()) as ParseResponse;

      // Pre-select all endpoints and derive a default server name
      const allIndices = new Set(parsed.endpoints.map((_, i) => i));
      const defaultName = parsed.title
        ? parsed.title
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "_")
            .replace(/^_+|_+$/g, "")
        : "";

      setState((prev) => ({
        ...prev,
        isParsing: false,
        parseResult: parsed,
        selectedIndices: allIndices,
        collapsedTags: new Set(), // all expanded by default
        serverName: defaultName,
        step: 2,
      }));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        isParsing: false,
        parseError:
          err instanceof Error ? err.message : "Failed to parse spec",
      }));
    }
  }, [state.specUrl]);

  // ── Step 2: Endpoint selection ──────────────────────────────────────────

  const toggleTagCollapse = useCallback((tag: string) => {
    setState((prev) => {
      const next = new Set(prev.collapsedTags);
      if (next.has(tag)) {
        next.delete(tag);
      } else {
        next.add(tag);
      }
      return { ...prev, collapsedTags: next };
    });
  }, []);

  const toggleEndpoint = useCallback((idx: number) => {
    setState((prev) => {
      const next = new Set(prev.selectedIndices);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        next.add(idx);
      }
      return { ...prev, selectedIndices: next };
    });
  }, []);

  const toggleTagAll = useCallback(
    (tag: string, indices: number[], selectAll: boolean) => {
      setState((prev) => {
        const next = new Set(prev.selectedIndices);
        if (selectAll) {
          indices.forEach((i) => next.add(i));
        } else {
          indices.forEach((i) => next.delete(i));
        }
        return { ...prev, selectedIndices: next };
      });
    },
    []
  );

  const selectAll = useCallback(() => {
    if (!state.parseResult) return;
    setState((prev) => ({
      ...prev,
      selectedIndices: new Set(prev.parseResult!.endpoints.map((_, i) => i)),
    }));
  }, [state.parseResult]);

  const deselectAll = useCallback(() => {
    setState((prev) => ({ ...prev, selectedIndices: new Set() }));
  }, []);

  // ── Step 3: Register ─────────────────────────────────────────────────────

  const handleRegister = useCallback(async () => {
    if (!state.parseResult || !state.serverName.trim()) return;

    const selectedEndpoints = Array.from(state.selectedIndices).map(
      (i) => state.parseResult!.endpoints[i]
    );

    if (selectedEndpoints.length === 0) return;

    // Build auth_value from the auth inputs
    let authValue: string | null = null;
    if (state.authType === "bearer" && state.bearerToken) {
      authValue = state.bearerToken;
    } else if (state.authType === "api_key" && state.apiKey) {
      authValue = state.apiKey;
    } else if (state.authType === "basic") {
      authValue = `${state.basicUsername}:${state.basicPassword}`;
    }

    const authHeader =
      state.authType === "api_key" ? state.apiKeyHeader || "X-API-Key" : null;

    setState((prev) => ({
      ...prev,
      isRegistering: true,
      registerError: null,
    }));

    try {
      const res = await fetch("/api/admin/openapi/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          server_name: state.serverName.trim(),
          base_url: state.parseResult.base_url,
          spec_url: state.specUrl,
          selected_endpoints: selectedEndpoints,
          auth_type: state.authType,
          auth_value: authValue,
          auth_header: authHeader,
        }),
      });

      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as Record<
          string,
          unknown
        >;
        const detail =
          typeof body.detail === "string" ? body.detail : `HTTP ${res.status}`;
        throw new Error(detail);
      }

      const result = (await res.json()) as RegisterResponse;

      // Success — reset, close, notify parent
      reset();
      onClose();
      onSuccess();
      // Simple alert instead of a toast library dependency
      alert(
        `Registered "${state.serverName}" with ${result.tools_created} tool${result.tools_created !== 1 ? "s" : ""}. The MCP Servers list will refresh.`
      );
    } catch (err) {
      setState((prev) => ({
        ...prev,
        isRegistering: false,
        registerError:
          err instanceof Error ? err.message : "Registration failed",
      }));
    }
  }, [state, onClose, onSuccess, reset]);

  if (!open) return null;

  const parseResult = state.parseResult;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 flex-shrink-0">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Connect OpenAPI Service
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Step {state.step} of 3:{" "}
              {state.step === 1
                ? "Paste spec URL"
                : state.step === 2
                  ? "Select endpoints"
                  : "Configure server"}
            </p>
          </div>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600 transition-colors text-xl leading-none"
            aria-label="Close wizard"
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {/* ── Step 1 ── */}
          {state.step === 1 && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  OpenAPI Spec URL
                </label>
                <input
                  type="url"
                  value={state.specUrl}
                  onChange={(e) =>
                    setState((prev) => ({
                      ...prev,
                      specUrl: e.target.value,
                      parseError: null,
                    }))
                  }
                  placeholder="https://api.example.com/openapi.json"
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void handleParse();
                  }}
                />
                <p className="text-xs text-gray-400 mt-1">
                  Supports OpenAPI 3.0 and 3.1 in JSON or YAML format.
                </p>
              </div>

              {state.parseError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
                  {state.parseError}
                </div>
              )}
            </div>
          )}

          {/* ── Step 2 ── */}
          {state.step === 2 && parseResult && (
            <div className="space-y-3">
              {/* Metadata */}
              <div className="text-sm text-gray-500">
                <span className="font-medium text-gray-900">
                  {parseResult.title ?? "Untitled API"}
                </span>
                {parseResult.version && (
                  <span className="ml-1">v{parseResult.version}</span>
                )}
                <span className="ml-2 text-xs font-mono text-gray-400">
                  {parseResult.base_url}
                </span>
              </div>

              {/* Selection controls */}
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-500">
                  {state.selectedIndices.size} of {parseResult.endpoints.length}{" "}
                  selected
                </span>
                <button
                  onClick={selectAll}
                  className="text-xs text-blue-600 hover:underline"
                >
                  Select All
                </button>
                <button
                  onClick={deselectAll}
                  className="text-xs text-gray-500 hover:underline"
                >
                  Deselect All
                </button>
              </div>

              {/* Tag groups */}
              {Object.entries(parseResult.tag_groups).map(([tag, indices]) => {
                const isCollapsed = state.collapsedTags.has(tag);
                const tagIndices = indices as number[];
                const allTagSelected = tagIndices.every((i) =>
                  state.selectedIndices.has(i)
                );
                const someTagSelected = tagIndices.some((i) =>
                  state.selectedIndices.has(i)
                );

                return (
                  <div
                    key={tag}
                    className="border border-gray-200 rounded-lg overflow-hidden"
                  >
                    {/* Tag header */}
                    <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border-b border-gray-200">
                      <input
                        type="checkbox"
                        checked={allTagSelected}
                        ref={(el) => {
                          if (el) {
                            el.indeterminate =
                              someTagSelected && !allTagSelected;
                          }
                        }}
                        onChange={(e) =>
                          toggleTagAll(tag, tagIndices, e.target.checked)
                        }
                        className="rounded border-gray-300"
                        aria-label={`Select all in ${tag}`}
                      />
                      <button
                        onClick={() => toggleTagCollapse(tag)}
                        className="flex-1 text-left text-sm font-medium text-gray-800 hover:text-blue-600 transition-colors"
                      >
                        {isCollapsed ? "+" : "-"} {tag}
                        <span className="ml-1.5 text-xs text-gray-400 font-normal">
                          ({tagIndices.length} endpoint
                          {tagIndices.length !== 1 ? "s" : ""})
                        </span>
                      </button>
                    </div>

                    {/* Endpoints */}
                    {!isCollapsed && (
                      <div className="divide-y divide-gray-100">
                        {tagIndices.map((idx) => {
                          const ep = parseResult.endpoints[idx];
                          if (!ep) return null;
                          return (
                            <label
                              key={idx}
                              className="flex items-start gap-3 px-3 py-2.5 hover:bg-gray-50 cursor-pointer"
                            >
                              <input
                                type="checkbox"
                                checked={state.selectedIndices.has(idx)}
                                onChange={() => toggleEndpoint(idx)}
                                className="mt-0.5 rounded border-gray-300"
                              />
                              <MethodBadge method={ep.method} />
                              <div className="flex-1 min-w-0">
                                <span className="text-xs font-mono text-gray-700 break-all">
                                  {ep.path}
                                </span>
                                {ep.summary && (
                                  <p className="text-xs text-gray-500 mt-0.5 truncate">
                                    {ep.summary}
                                  </p>
                                )}
                              </div>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* ── Step 3 ── */}
          {state.step === 3 && (
            <div className="space-y-4">
              {/* Server name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Server Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={state.serverName}
                  onChange={(e) =>
                    setState((prev) => ({
                      ...prev,
                      serverName: e.target.value,
                      registerError: null,
                    }))
                  }
                  placeholder="my_api"
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Used as the tool name prefix: {state.serverName || "api"}.
                  tool_name
                </p>
              </div>

              {/* Auth type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Authentication
                </label>
                <select
                  value={state.authType}
                  onChange={(e) =>
                    setState((prev) => ({
                      ...prev,
                      authType: e.target.value as AuthType,
                    }))
                  }
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="none">No Authentication</option>
                  <option value="bearer">Bearer Token</option>
                  <option value="api_key">API Key</option>
                  <option value="basic">Basic Auth</option>
                </select>
              </div>

              {/* Conditional auth inputs */}
              {state.authType === "bearer" && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Bearer Token
                  </label>
                  <input
                    type="password"
                    value={state.bearerToken}
                    onChange={(e) =>
                      setState((prev) => ({
                        ...prev,
                        bearerToken: e.target.value,
                      }))
                    }
                    placeholder="eyJhbGci..."
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              )}

              {state.authType === "api_key" && (
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      API Key
                    </label>
                    <input
                      type="password"
                      value={state.apiKey}
                      onChange={(e) =>
                        setState((prev) => ({
                          ...prev,
                          apiKey: e.target.value,
                        }))
                      }
                      placeholder="sk-..."
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Header Name
                    </label>
                    <input
                      type="text"
                      value={state.apiKeyHeader}
                      onChange={(e) =>
                        setState((prev) => ({
                          ...prev,
                          apiKeyHeader: e.target.value,
                        }))
                      }
                      placeholder="X-API-Key"
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>
              )}

              {state.authType === "basic" && (
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Username
                    </label>
                    <input
                      type="text"
                      value={state.basicUsername}
                      onChange={(e) =>
                        setState((prev) => ({
                          ...prev,
                          basicUsername: e.target.value,
                        }))
                      }
                      placeholder="username"
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Password
                    </label>
                    <input
                      type="password"
                      value={state.basicPassword}
                      onChange={(e) =>
                        setState((prev) => ({
                          ...prev,
                          basicPassword: e.target.value,
                        }))
                      }
                      placeholder="password"
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>
              )}

              {/* Summary */}
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-md text-sm text-blue-800">
                {state.selectedIndices.size} endpoint
                {state.selectedIndices.size !== 1 ? "s" : ""} will be
                registered as tools under the server{" "}
                <code className="font-mono">{state.serverName || "..."}</code>.
              </div>

              {state.registerError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
                  {state.registerError}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 flex-shrink-0 bg-gray-50">
          <div className="flex items-center gap-2">
            {state.step > 1 && (
              <button
                onClick={() =>
                  setState((prev) => ({
                    ...prev,
                    step: (prev.step - 1) as 1 | 2 | 3,
                  }))
                }
                className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-200 rounded-md transition-colors"
              >
                Back
              </button>
            )}
            <button
              onClick={handleClose}
              className="px-4 py-2 text-sm text-gray-500 hover:bg-gray-200 rounded-md transition-colors"
            >
              Cancel
            </button>
          </div>

          <div>
            {state.step === 1 && (
              <button
                onClick={() => void handleParse()}
                disabled={!state.specUrl.trim() || state.isParsing}
                className="px-5 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {state.isParsing ? "Fetching..." : "Fetch & Parse"}
              </button>
            )}

            {state.step === 2 && (
              <button
                onClick={() =>
                  setState((prev) => ({ ...prev, step: 3 }))
                }
                disabled={state.selectedIndices.size === 0}
                className="px-5 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next: Configure ({state.selectedIndices.size} endpoint
                {state.selectedIndices.size !== 1 ? "s" : ""})
              </button>
            )}

            {state.step === 3 && (
              <button
                onClick={() => void handleRegister()}
                disabled={
                  !state.serverName.trim() ||
                  state.selectedIndices.size === 0 ||
                  state.isRegistering
                }
                className="px-5 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {state.isRegistering
                  ? "Registering..."
                  : `Register ${state.selectedIndices.size} Tool${state.selectedIndices.size !== 1 ? "s" : ""}`}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
