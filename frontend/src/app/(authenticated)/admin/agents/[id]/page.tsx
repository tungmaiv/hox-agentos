"use client";
/**
 * Agent detail page — view and edit agent registry entry.
 *
 * Tabs: Overview (read-only fields + editable display name / description),
 * Config (system prompt, model alias, routing keywords, handler info),
 * Permissions (placeholder).
 */
import { useState, useEffect, useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import type { RegistryEntry } from "@/lib/admin-types";
import { mapSnakeToCamel } from "@/lib/admin-types";
import { RegistryDetailLayout } from "@/components/admin/registry-detail-layout";
import {
  agentFormSchema,
  validateField,
  type AgentFormValues,
} from "@/lib/registry-schemas";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "config", label: "Config" },
  { id: "permissions", label: "Permissions" },
];

const MODEL_ALIAS_OPTIONS = [
  "blitz/master",
  "blitz/fast",
  "blitz/coder",
  "blitz/summarizer",
] as const;

interface AgentFormData {
  displayName: string;
  description: string;
  status: string;
  systemPrompt: string;
  modelAlias: string;
  routingKeywords: string;
  handlerModule: string;
  handlerFunction: string;
  advancedJson: string;
}

function buildFormData(entry: RegistryEntry): AgentFormData {
  const cfg = entry.config ?? {};
  // Collect "known" config keys to compute advanced/remaining
  const knownKeys = new Set([
    "system_prompt",
    "model_alias",
    "routing_keywords",
    "handler_module",
    "handler_function",
  ]);
  const remaining: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(cfg)) {
    if (!knownKeys.has(k)) remaining[k] = v;
  }

  return {
    displayName: entry.displayName ?? "",
    description: entry.description ?? "",
    status: entry.status,
    systemPrompt: (cfg.system_prompt as string) ?? "",
    modelAlias: (cfg.model_alias as string) ?? "",
    routingKeywords: Array.isArray(cfg.routing_keywords)
      ? (cfg.routing_keywords as string[]).join(", ")
      : "",
    handlerModule: (cfg.handler_module as string) ?? "",
    handlerFunction: (cfg.handler_function as string) ?? "",
    advancedJson:
      Object.keys(remaining).length > 0
        ? JSON.stringify(remaining, null, 2)
        : "",
  };
}

function formToPayload(
  form: AgentFormData,
  originalConfig: Record<string, unknown>,
) {
  // Parse advanced JSON, falling back to empty object
  let advanced: Record<string, unknown> = {};
  if (form.advancedJson.trim()) {
    try {
      advanced = JSON.parse(form.advancedJson) as Record<string, unknown>;
    } catch {
      // Invalid JSON — will be caught by validation
    }
  }

  const keywords = form.routingKeywords
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  return {
    display_name: form.displayName || null,
    description: form.description || null,
    status: form.status,
    config: {
      ...originalConfig,
      ...advanced,
      system_prompt: form.systemPrompt || null,
      model_alias: form.modelAlias || null,
      routing_keywords: keywords.length > 0 ? keywords : null,
      handler_module: form.handlerModule || null,
      handler_function: form.handlerFunction || null,
    },
  };
}

export default function AgentDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [entry, setEntry] = useState<RegistryEntry | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // Form state
  const [formData, setFormData] = useState<AgentFormData | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Original form data for change detection
  const [originalFormData, setOriginalFormData] =
    useState<AgentFormData | null>(null);

  const fetchEntry = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/registry/${id}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as Record<string, unknown>;
      const mapped = mapSnakeToCamel<RegistryEntry>(data);
      setEntry(mapped);
      const fd = buildFormData(mapped);
      setFormData(fd);
      setOriginalFormData(fd);
      setFieldErrors({});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load entry");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void fetchEntry();
  }, [fetchEntry]);

  // Clear save message after 3 seconds
  useEffect(() => {
    if (!saveMessage) return;
    const t = setTimeout(() => setSaveMessage(null), 3000);
    return () => clearTimeout(t);
  }, [saveMessage]);

  const hasChanges = useMemo(() => {
    if (!formData || !originalFormData) return false;
    return JSON.stringify(formData) !== JSON.stringify(originalFormData);
  }, [formData, originalFormData]);

  const handleFieldChange = (field: keyof AgentFormData, value: string) => {
    if (!formData) return;
    setFormData({ ...formData, [field]: value });
  };

  const handleFieldBlur = (field: string, value: unknown) => {
    // Map form field names to schema field names
    const schemaField =
      field === "routingKeywords"
        ? "routingKeywords"
        : field === "systemPrompt"
          ? "systemPrompt"
          : field === "modelAlias"
            ? "modelAlias"
            : field;

    // For routingKeywords, validate as array
    let validateValue = value;
    if (field === "routingKeywords" && typeof value === "string") {
      validateValue = value
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    }

    const err = validateField(agentFormSchema, schemaField, validateValue);
    setFieldErrors((prev) => {
      const next = { ...prev };
      if (err) next[field] = err;
      else delete next[field];
      return next;
    });
  };

  const handleSave = async () => {
    if (!formData || !entry) return;

    // Run full validation
    const zodValues: AgentFormValues = {
      displayName: formData.displayName || null,
      description: formData.description || null,
      systemPrompt: formData.systemPrompt || null,
      modelAlias:
        (formData.modelAlias as AgentFormValues["modelAlias"]) || null,
      routingKeywords: formData.routingKeywords
        ? formData.routingKeywords
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : null,
      status: formData.status as AgentFormValues["status"],
    };

    const result = agentFormSchema.safeParse(zodValues);
    if (!result.success) {
      const errors: Record<string, string> = {};
      for (const issue of result.error.issues) {
        const key = issue.path[0];
        if (typeof key === "string") errors[key] = issue.message;
      }
      setFieldErrors(errors);
      setSaveMessage({ type: "error", text: "Validation failed. Fix errors before saving." });
      return;
    }

    setSaving(true);
    setSaveMessage(null);
    try {
      const payload = formToPayload(formData, entry.config);
      const res = await fetch(`/api/registry/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(body || `HTTP ${res.status}`);
      }
      const data = (await res.json()) as Record<string, unknown>;
      const updated = mapSnakeToCamel<RegistryEntry>(data);
      setEntry(updated);
      const fd = buildFormData(updated);
      setFormData(fd);
      setOriginalFormData(fd);
      setFieldErrors({});
      setSaveMessage({ type: "success", text: "Changes saved successfully." });
    } catch (err) {
      setSaveMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Save failed",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDiscard = () => {
    if (originalFormData) {
      setFormData({ ...originalFormData });
      setFieldErrors({});
      setSaveMessage(null);
    }
  };

  // ---------- Render ----------

  if (loading) {
    return (
      <div className="text-gray-500 py-8 text-center">
        Loading agent details...
      </div>
    );
  }

  if (error || !entry || !formData) {
    return (
      <div className="py-8">
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-600">
          {error ?? "Entry not found"}
        </div>
        <a
          href="/admin/agents"
          className="text-sm text-blue-600 hover:underline"
        >
          Back to Agents
        </a>
      </div>
    );
  }

  return (
    <RegistryDetailLayout
      entry={entry}
      backHref="/admin/agents"
      backLabel="Agents"
      tabs={TABS}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      hasChanges={hasChanges}
      saving={saving}
      onSave={() => void handleSave()}
      onDiscard={handleDiscard}
    >
      {/* Save/error message */}
      {saveMessage && (
        <div
          className={`mb-4 p-3 rounded-md text-sm ${
            saveMessage.type === "success"
              ? "bg-green-50 border border-green-200 text-green-700"
              : "bg-red-50 border border-red-200 text-red-600"
          }`}
        >
          {saveMessage.text}
        </div>
      )}

      {/* Overview tab */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Read-only fields */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-3">
              Entry Details
            </h3>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <div>
                <dt className="text-gray-500 text-xs">ID</dt>
                <dd className="font-mono text-gray-900">{entry.id}</dd>
              </div>
              <div>
                <dt className="text-gray-500 text-xs">Name</dt>
                <dd className="font-mono text-gray-900">{entry.name}</dd>
              </div>
              <div>
                <dt className="text-gray-500 text-xs">Status</dt>
                <dd className="text-gray-900">{entry.status}</dd>
              </div>
              <div>
                <dt className="text-gray-500 text-xs">Owner ID</dt>
                <dd className="font-mono text-gray-900 truncate">
                  {entry.ownerId}
                </dd>
              </div>
              <div>
                <dt className="text-gray-500 text-xs">Created</dt>
                <dd className="text-gray-900">
                  {new Date(entry.createdAt).toLocaleString()}
                </dd>
              </div>
              <div>
                <dt className="text-gray-500 text-xs">Updated</dt>
                <dd className="text-gray-900">
                  {new Date(entry.updatedAt).toLocaleString()}
                </dd>
              </div>
            </dl>
          </div>

          {/* Editable fields */}
          <div className="border-t border-gray-200 pt-4 space-y-4">
            <h3 className="text-sm font-semibold text-gray-700">
              Editable Fields
            </h3>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Display Name
              </label>
              <input
                type="text"
                value={formData.displayName}
                onChange={(e) =>
                  handleFieldChange("displayName", e.target.value)
                }
                onBlur={(e) =>
                  handleFieldBlur("displayName", e.target.value || null)
                }
                placeholder="Human-friendly name"
                className="w-full text-sm border border-gray-300 rounded-md px-3 py-1.5 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              {fieldErrors.displayName && (
                <p className="text-xs text-red-600 mt-1">
                  {fieldErrors.displayName}
                </p>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) =>
                  handleFieldChange("description", e.target.value)
                }
                onBlur={(e) =>
                  handleFieldBlur("description", e.target.value || null)
                }
                rows={3}
                placeholder="What does this agent do?"
                className="w-full text-sm border border-gray-300 rounded-md px-3 py-1.5 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y"
              />
              {fieldErrors.description && (
                <p className="text-xs text-red-600 mt-1">
                  {fieldErrors.description}
                </p>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Status
              </label>
              <select
                value={formData.status}
                onChange={(e) => handleFieldChange("status", e.target.value)}
                className="text-sm border border-gray-300 rounded-md px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="active">active</option>
                <option value="disabled">disabled</option>
                <option value="deprecated">deprecated</option>
                <option value="draft">draft</option>
                <option value="archived">archived</option>
                <option value="pending_review">pending_review</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Config tab */}
      {activeTab === "config" && (
        <div className="space-y-5">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              System Prompt
            </label>
            <textarea
              value={formData.systemPrompt}
              onChange={(e) =>
                handleFieldChange("systemPrompt", e.target.value)
              }
              onBlur={(e) =>
                handleFieldBlur("systemPrompt", e.target.value || null)
              }
              rows={6}
              placeholder="System prompt for this agent..."
              className="w-full text-sm border border-gray-300 rounded-md px-3 py-2 bg-white text-gray-900 placeholder-gray-400 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y"
            />
            {fieldErrors.systemPrompt && (
              <p className="text-xs text-red-600 mt-1">
                {fieldErrors.systemPrompt}
              </p>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Model Alias
            </label>
            <select
              value={formData.modelAlias}
              onChange={(e) => handleFieldChange("modelAlias", e.target.value)}
              onBlur={(e) =>
                handleFieldBlur("modelAlias", e.target.value || null)
              }
              className="text-sm border border-gray-300 rounded-md px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">-- Select model --</option>
              {MODEL_ALIAS_OPTIONS.map((alias) => (
                <option key={alias} value={alias}>
                  {alias}
                </option>
              ))}
            </select>
            {fieldErrors.modelAlias && (
              <p className="text-xs text-red-600 mt-1">
                {fieldErrors.modelAlias}
              </p>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Routing Keywords
              <span className="text-gray-400 font-normal ml-1">
                (comma-separated)
              </span>
            </label>
            <input
              type="text"
              value={formData.routingKeywords}
              onChange={(e) =>
                handleFieldChange("routingKeywords", e.target.value)
              }
              onBlur={(e) =>
                handleFieldBlur("routingKeywords", e.target.value)
              }
              placeholder="email, inbox, send mail"
              className="w-full text-sm border border-gray-300 rounded-md px-3 py-1.5 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            {fieldErrors.routingKeywords && (
              <p className="text-xs text-red-600 mt-1">
                {fieldErrors.routingKeywords}
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Handler Module
                <span className="text-gray-400 font-normal ml-1">
                  (read-only)
                </span>
              </label>
              <input
                type="text"
                value={formData.handlerModule}
                readOnly
                className="w-full text-sm border border-gray-200 rounded-md px-3 py-1.5 bg-gray-100 text-gray-600 font-mono cursor-not-allowed"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Handler Function
                <span className="text-gray-400 font-normal ml-1">
                  (read-only)
                </span>
              </label>
              <input
                type="text"
                value={formData.handlerFunction}
                readOnly
                className="w-full text-sm border border-gray-200 rounded-md px-3 py-1.5 bg-gray-100 text-gray-600 font-mono cursor-not-allowed"
              />
            </div>
          </div>

          {/* Advanced raw JSON */}
          <div className="border-t border-gray-200 pt-4">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-1 text-xs font-medium text-gray-500 hover:text-gray-700 transition-colors"
            >
              <svg
                className={`w-3 h-3 transition-transform ${showAdvanced ? "rotate-90" : ""}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
              Advanced (raw JSON)
            </button>
            {showAdvanced && (
              <div className="mt-2">
                <textarea
                  value={formData.advancedJson}
                  onChange={(e) =>
                    handleFieldChange("advancedJson", e.target.value)
                  }
                  rows={8}
                  placeholder="{}"
                  className="w-full text-sm border border-gray-300 rounded-md px-3 py-2 bg-white text-gray-900 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Additional config keys not covered by the fields above. Must
                  be valid JSON.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Permissions tab */}
      {activeTab === "permissions" && (
        <div className="py-8 text-center">
          <div className="text-gray-400 text-sm">
            Permission management coming soon.
          </div>
          <p className="text-xs text-gray-300 mt-2">
            Role-based and user-level permissions will be configurable here in a
            future update.
          </p>
        </div>
      )}
    </RegistryDetailLayout>
  );
}
