"use client";
/**
 * SkillStoreRepositories — admin UI for managing external skill repositories.
 *
 * Features:
 * - Table of registered repositories: name, URL, skill count, last synced, status
 * - "Add Repository" dialog with URL input
 * - "Sync" button per row — re-fetches index
 * - "Remove" button per row — with confirm prompt
 */
import { useCallback, useEffect, useState } from "react";

interface RepoInfo {
  id: string;
  name: string;
  url: string;
  description: string | null;
  is_active: boolean;
  last_synced_at: string | null;
  skill_count: number;
}

export function SkillStoreRepositories() {
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [addUrl, setAddUrl] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);

  const fetchRepos = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/admin/skill-repos");
      if (!response.ok) {
        const data = (await response.json().catch(() => ({}))) as {
          detail?: string;
        };
        setError(data.detail ?? `Error ${response.status}`);
        return;
      }
      const data = (await response.json()) as RepoInfo[];
      setRepos(data);
    } catch {
      setError("Failed to connect to backend");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchRepos();
  }, [fetchRepos]);

  const handleAdd = async () => {
    if (!addUrl.trim()) return;
    setAdding(true);
    setAddError(null);
    try {
      const response = await fetch("/api/admin/skill-repos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: addUrl.trim() }),
      });
      if (!response.ok) {
        const data = (await response.json().catch(() => ({}))) as {
          detail?: string;
        };
        setAddError(data.detail ?? `Error ${response.status}`);
        return;
      }
      setShowAddDialog(false);
      setAddUrl("");
      await fetchRepos();
    } catch {
      setAddError("Failed to connect to backend");
    } finally {
      setAdding(false);
    }
  };

  const handleSync = async (repoId: string) => {
    setSyncingId(repoId);
    try {
      await fetch(`/api/admin/skill-repos/${repoId}/sync`, { method: "POST" });
      await fetchRepos();
    } catch {
      // Silent failure — user can retry
    } finally {
      setSyncingId(null);
    }
  };

  const handleRemove = async (repo: RepoInfo) => {
    const confirmed = window.confirm(
      `Remove repository "${repo.name}"?\n\nSkills imported from this repository will remain in the system.`
    );
    if (!confirmed) return;

    setRemovingId(repo.id);
    try {
      await fetch(`/api/admin/skill-repos/${repo.id}`, { method: "DELETE" });
      await fetchRepos();
    } catch {
      // Silent failure — user can retry
    } finally {
      setRemovingId(null);
    }
  };

  const formatDate = (iso: string | null): string => {
    if (!iso) return "Never";
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-500 text-sm">
        Loading repositories...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">
            Skill Repositories
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            External repositories that provide skills to browse and import.
          </p>
        </div>
        <button
          onClick={() => {
            setShowAddDialog(true);
            setAddError(null);
            setAddUrl("");
          }}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors"
        >
          Add Repository
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Empty state */}
      {!error && repos.length === 0 && (
        <div className="text-center py-12 text-gray-500 text-sm">
          No repositories registered yet. Add one to get started.
        </div>
      )}

      {/* Repositories table */}
      {repos.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">
                  Name
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">
                  URL
                </th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">
                  Skills
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">
                  Last Synced
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">
                  Status
                </th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {repos.map((repo) => (
                <tr key={repo.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    <div>{repo.name}</div>
                    {repo.description && (
                      <div className="text-xs text-gray-500 mt-0.5">
                        {repo.description}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600 max-w-xs">
                    <a
                      href={repo.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline truncate block"
                    >
                      {repo.url}
                    </a>
                  </td>
                  <td className="px-4 py-3 text-right text-gray-700">
                    {repo.skill_count}
                  </td>
                  <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                    {formatDate(repo.last_synced_at)}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        repo.is_active
                          ? "bg-green-100 text-green-800"
                          : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {repo.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                    <button
                      onClick={() => void handleSync(repo.id)}
                      disabled={syncingId === repo.id}
                      className="text-xs px-3 py-1 rounded border border-gray-300 text-gray-600 hover:border-blue-400 hover:text-blue-600 disabled:opacity-50 transition-colors"
                    >
                      {syncingId === repo.id ? "Syncing..." : "Sync"}
                    </button>
                    <button
                      onClick={() => void handleRemove(repo)}
                      disabled={removingId === repo.id}
                      className="text-xs px-3 py-1 rounded border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50 transition-colors"
                    >
                      {removingId === repo.id ? "Removing..." : "Remove"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Repository Dialog */}
      {showAddDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Add Skill Repository
            </h3>

            <div className="space-y-3">
              <label className="block text-sm font-medium text-gray-700">
                Repository Base URL
              </label>
              <input
                type="url"
                placeholder="https://skills.example.com"
                value={addUrl}
                onChange={(e) => setAddUrl(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void handleAdd();
                }}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                autoFocus
              />
              <p className="text-xs text-gray-500">
                The URL must serve an{" "}
                <code className="bg-gray-100 px-1 rounded">
                  agentskills-index.json
                </code>{" "}
                file at its root.
              </p>

              {addError && (
                <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
                  {addError}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => setShowAddDialog(false)}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => void handleAdd()}
                disabled={adding || !addUrl.trim()}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {adding ? "Adding..." : "Add Repository"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
