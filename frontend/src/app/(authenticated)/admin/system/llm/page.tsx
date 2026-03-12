"use client";
/**
 * Admin LLM model/provider configuration page — /admin/system/llm.
 *
 * Fetches models from LiteLLM proxy via backend API.
 * Shows disclaimer that changes require config.yaml update for persistence.
 */
import { useState, useEffect, useCallback } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ModelInfo {
  model_alias: string;
  provider_model: string | null;
  api_base: string | null;
}

interface LLMConfigResponse {
  models: ModelInfo[];
  litellm_available: boolean;
}

interface AddModelForm {
  model_alias: string;
  provider_model: string;
  api_base: string;
}

const EMPTY_FORM: AddModelForm = {
  model_alias: "",
  provider_model: "",
  api_base: "",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AdminLLMPage() {
  const [config, setConfig] = useState<LLMConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState<AddModelForm>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const fetchModels = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/llm/models", { cache: "no-store" });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        throw new Error(body.error ?? `HTTP ${res.status}`);
      }
      const data = (await res.json()) as LLMConfigResponse;
      setConfig(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load LLM config");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchModels();
  }, [fetchModels]);

  const handleAddModel = async () => {
    if (!form.model_alias.trim() || !form.provider_model.trim()) {
      setSaveError("Model alias and provider model are required.");
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const payload: Record<string, string | null> = {
        model_alias: form.model_alias.trim(),
        provider_model: form.provider_model.trim(),
        api_base: form.api_base.trim() || null,
      };
      const res = await fetch("/api/admin/llm/models", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(body.detail ?? `HTTP ${res.status}`);
      }
      setShowAddForm(false);
      setForm(EMPTY_FORM);
      void fetchModels();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to add model");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteModel = async (alias: string) => {
    try {
      const res = await fetch(
        `/api/admin/llm/models/${encodeURIComponent(alias)}`,
        { method: "DELETE" }
      );
      if (!res.ok && res.status !== 204) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(body.detail ?? `HTTP ${res.status}`);
      }
      void fetchModels();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete model");
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">LLM Model Configuration</h2>
        <button
          onClick={() => {
            setShowAddForm(true);
            setSaveError(null);
          }}
          className="px-3 py-1.5 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors"
        >
          Add Model
        </button>
      </div>

      {/* Persistence disclaimer — always visible */}
      <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-md text-sm text-amber-800">
        <strong>Note:</strong> Model changes apply immediately but require manual{" "}
        <code className="font-mono bg-amber-100 px-1 rounded">config.yaml</code> update for
        persistence across restarts. Edit{" "}
        <code className="font-mono bg-amber-100 px-1 rounded">infra/litellm/config.yaml</code>{" "}
        to make changes permanent.
      </div>

      {/* LiteLLM unavailable banner */}
      {config && !config.litellm_available && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
          LiteLLM proxy unavailable — model changes cannot be applied. Check that the LiteLLM
          service is running.
        </div>
      )}

      {/* General error */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Add model inline form */}
      {showAddForm && (
        <div className="mb-6 p-4 bg-white border border-gray-200 rounded-lg">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Add Model</h3>
          {saveError && (
            <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-600">
              {saveError}
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">
                Model Alias <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={form.model_alias}
                onChange={(e) => setForm({ ...form, model_alias: e.target.value })}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white"
                placeholder="blitz/custom"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">
                Provider Model <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={form.provider_model}
                onChange={(e) => setForm({ ...form, provider_model: e.target.value })}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white"
                placeholder="gpt-4o-mini"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-600 mb-1">API Base (optional)</label>
              <input
                type="text"
                value={form.api_base}
                onChange={(e) => setForm({ ...form, api_base: e.target.value })}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1 text-gray-900 bg-white"
                placeholder="e.g. http://host.docker.internal:11434"
              />
            </div>
          </div>
          <div className="flex items-center gap-2 mt-4">
            <button
              onClick={() => void handleAddModel()}
              disabled={saving}
              className="px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save"}
            </button>
            <button
              onClick={() => {
                setShowAddForm(false);
                setForm(EMPTY_FORM);
                setSaveError(null);
              }}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 text-xs font-medium rounded hover:bg-gray-200 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Model table */}
      {loading ? (
        <div className="text-gray-400 text-sm py-6">Loading models...</div>
      ) : config && config.models.length === 0 ? (
        <div className="text-gray-400 text-sm py-6 text-center">
          {config.litellm_available
            ? "No models configured. Use the Add Model button to add one."
            : "Cannot load models — LiteLLM proxy is offline."}
        </div>
      ) : (
        <table className="w-full text-sm text-left">
          <thead>
            <tr className="border-b border-gray-200 text-xs text-gray-500 uppercase">
              <th className="py-2 pr-4">Model Alias</th>
              <th className="py-2 pr-4">Provider Model</th>
              <th className="py-2 pr-4">API Base</th>
              <th className="py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {config?.models.map((model) => (
              <tr
                key={model.model_alias}
                className="border-b border-gray-100 hover:bg-gray-50"
              >
                <td className="py-2 pr-4 font-mono text-gray-900">{model.model_alias}</td>
                <td className="py-2 pr-4 text-gray-700">{model.provider_model ?? "—"}</td>
                <td className="py-2 pr-4 text-gray-500 font-mono text-xs">
                  {model.api_base ?? "—"}
                </td>
                <td className="py-2">
                  <button
                    onClick={() => void handleDeleteModel(model.model_alias)}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
