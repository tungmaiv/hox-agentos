"use client";
/**
 * Admin Storage Settings page — /admin/storage
 *
 * Allows admins to configure:
 *   - Maximum file upload size (MB)
 *   - Allowed MIME types (comma-separated list)
 *
 * Reads from GET /api/admin/storage/settings
 * Saves via PUT /api/admin/storage/settings
 */
import { useState, useEffect, useCallback } from "react";

interface StorageSettings {
  max_file_size_mb: number;
  allowed_mime_types: string[];
}

export default function AdminStoragePage() {
  const [settings, setSettings] = useState<StorageSettings | null>(null);
  const [maxFileSize, setMaxFileSize] = useState<number>(100);
  const [mimeTypesText, setMimeTypesText] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const showToast = (type: "success" | "error", message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 4000);
  };

  const fetchSettings = useCallback(async () => {
    try {
      const res = await fetch(`/api/admin/storage/settings`, {
        credentials: "include",
        cache: "no-store",
      });
      if (!res.ok) {
        showToast("error", `Failed to load settings (${res.status})`);
        return;
      }
      const data = (await res.json()) as StorageSettings;
      setSettings(data);
      setMaxFileSize(data.max_file_size_mb);
      setMimeTypesText(data.allowed_mime_types.join(", "));
    } catch {
      showToast("error", "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchSettings();
  }, [fetchSettings]);

  const handleSave = async () => {
    setSaving(true);
    try {
      // Parse MIME types from comma-separated text
      const allowedMimeTypes = mimeTypesText
        .split(",")
        .map((s) => s.trim())
        .filter((s) => s.length > 0);

      const res = await fetch(`/api/admin/storage/settings`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_file_size_mb: maxFileSize,
          allowed_mime_types: allowedMimeTypes,
        }),
      });

      if (!res.ok) {
        const errorData = (await res.json().catch(() => ({}))) as { detail?: string };
        showToast("error", errorData.detail ?? `Save failed (${res.status})`);
        return;
      }

      const updated = (await res.json()) as StorageSettings;
      setSettings(updated);
      setMaxFileSize(updated.max_file_size_mb);
      setMimeTypesText(updated.allowed_mime_types.join(", "));
      showToast("success", "Storage settings saved");
    } catch {
      showToast("error", "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-gray-500 text-sm">Loading storage settings...</div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      {/* Toast notification */}
      {toast && (
        <div
          className={`mb-4 px-4 py-3 rounded-lg text-sm font-medium ${
            toast.type === "success"
              ? "bg-green-50 text-green-800 border border-green-200"
              : "bg-red-50 text-red-800 border border-red-200"
          }`}
        >
          {toast.message}
        </div>
      )}

      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900">Storage Settings</h2>
        <p className="text-sm text-gray-500 mt-1">
          Configure file upload limits and allowed file types for the storage service.
        </p>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-6">
        {/* Max file size */}
        <div>
          <label
            htmlFor="max-file-size"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Max file size (MB)
          </label>
          <input
            id="max-file-size"
            type="number"
            min={1}
            max={500}
            value={maxFileSize}
            onChange={(e) => setMaxFileSize(Number(e.target.value))}
            className="w-32 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <p className="mt-1 text-xs text-gray-400">
            Minimum: 1 MB &middot; Maximum: 500 MB &middot; Current backend default:{" "}
            {settings?.max_file_size_mb ?? 100} MB
          </p>
        </div>

        {/* Allowed MIME types */}
        <div>
          <label
            htmlFor="allowed-mime-types"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Allowed file types
          </label>
          <textarea
            id="allowed-mime-types"
            rows={6}
            value={mimeTypesText}
            onChange={(e) => setMimeTypesText(e.target.value)}
            placeholder="application/pdf, text/plain, image/jpeg, ..."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
          />
          <p className="mt-1 text-xs text-gray-400">
            Comma-separated MIME type strings. Example:{" "}
            <code className="bg-gray-100 px-1 rounded">application/pdf, image/jpeg</code>
          </p>
        </div>

        {/* Save button */}
        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={() => void handleSave()}
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {saving ? "Saving..." : "Save"}
          </button>
          <button
            onClick={() => {
              if (settings) {
                setMaxFileSize(settings.max_file_size_mb);
                setMimeTypesText(settings.allowed_mime_types.join(", "));
              }
            }}
            disabled={saving}
            className="px-4 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-200 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}
