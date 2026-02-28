"use client";
/**
 * PermissionMatrix — role x artifact permission matrix with staged apply.
 *
 * Displays a table where rows are artifacts and columns are roles.
 * Each cell is a checkbox (allowed/denied). Pending changes are shown
 * with a yellow highlight. "Apply Pending" button activates staged changes.
 *
 * Also includes a per-user overrides section below the matrix.
 */
import { useState, useEffect, useCallback } from "react";
import { useAdminPermissions } from "@/hooks/use-admin-permissions";
import type { ArtifactBase, ArtifactPermission } from "@/lib/admin-types";

interface ArtifactEntry {
  id: string;
  name: string;
  displayName: string | null;
  type: string;
}

interface PermissionMatrixProps {
  /** All artifacts across all types for the matrix view. */
  artifacts: ArtifactEntry[];
  /** Available roles in the system. */
  roles: string[];
}

interface PermissionCell {
  artifactId: string;
  artifactType: string;
  role: string;
  allowed: boolean;
  status: string;
  permissionId: string | null;
}

export function PermissionMatrix({ artifacts, roles }: PermissionMatrixProps) {
  const {
    error,
    getArtifactPermissions,
    setArtifactPermissions,
    applyPending,
  } = useAdminPermissions();

  const [cells, setCells] = useState<Map<string, PermissionCell>>(new Map());
  const [pendingIds, setPendingIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);

  const cellKey = (artifactId: string, role: string) =>
    `${artifactId}:${role}`;

  // Load permissions for all artifacts
  const loadPermissions = useCallback(async () => {
    setLoading(true);
    const newCells = new Map<string, PermissionCell>();
    const newPendingIds: string[] = [];

    for (const artifact of artifacts) {
      const perms = await getArtifactPermissions(artifact.type, artifact.id);
      for (const perm of perms) {
        const key = cellKey(perm.artifactId, perm.role);
        newCells.set(key, {
          artifactId: perm.artifactId,
          artifactType: artifact.type,
          role: perm.role,
          allowed: perm.allowed,
          status: perm.status,
          permissionId: perm.id,
        });
        if (perm.status === "pending") {
          newPendingIds.push(perm.id);
        }
      }
    }

    setCells(newCells);
    setPendingIds(newPendingIds);
    setLoading(false);
  }, [artifacts, getArtifactPermissions]);

  useEffect(() => {
    if (artifacts.length > 0) {
      void loadPermissions();
    } else {
      setLoading(false);
    }
    // Only reload when artifacts array reference changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [artifacts]);

  const handleToggle = async (artifact: ArtifactEntry, role: string) => {
    const key = cellKey(artifact.id, role);
    const current = cells.get(key);
    const newAllowed = !(current?.allowed ?? false);

    // Set permission (staged as pending)
    const result = await setArtifactPermissions(artifact.type, artifact.id, [
      { role, allowed: newAllowed },
    ]);

    // Update local state
    const updatedCells = new Map(cells);
    for (const perm of result) {
      const k = cellKey(perm.artifactId, perm.role);
      updatedCells.set(k, {
        artifactId: perm.artifactId,
        artifactType: artifact.type,
        role: perm.role,
        allowed: perm.allowed,
        status: perm.status,
        permissionId: perm.id,
      });
    }
    setCells(updatedCells);

    // Update pending IDs
    const newPending = Array.from(updatedCells.values())
      .filter((c) => c.status === "pending" && c.permissionId)
      .map((c) => c.permissionId as string);
    setPendingIds(newPending);
  };

  const handleApplyAll = async () => {
    if (pendingIds.length === 0) return;
    setApplying(true);
    await applyPending(pendingIds);
    // Reload to get updated statuses
    await loadPermissions();
    setApplying(false);
  };

  if (loading) {
    return <div className="text-sm text-gray-500 py-4">Loading permissions...</div>;
  }

  return (
    <div>
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Apply pending button */}
      {pendingIds.length > 0 && (
        <div className="mb-4 flex items-center gap-3 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
          <span className="text-sm text-yellow-800">
            {pendingIds.length} pending permission
            {pendingIds.length !== 1 ? "s" : ""} to apply
          </span>
          <button
            onClick={handleApplyAll}
            disabled={applying}
            className="px-3 py-1.5 bg-yellow-600 hover:bg-yellow-700 text-white text-xs font-medium rounded-md transition-colors disabled:opacity-50"
          >
            {applying ? "Applying..." : "Apply Pending"}
          </button>
        </div>
      )}

      {/* Matrix table */}
      {artifacts.length === 0 ? (
        <div className="text-sm text-gray-400 py-8 text-center">
          No artifacts available for permission management
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Artifact
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Type
                </th>
                {roles.map((role) => (
                  <th
                    key={role}
                    className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
                  >
                    {role}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {artifacts.map((artifact) => (
                <tr key={artifact.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 text-sm text-gray-900">
                    {artifact.displayName ?? artifact.name}
                  </td>
                  <td className="px-4 py-2">
                    <span className="text-xs text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
                      {artifact.type}
                    </span>
                  </td>
                  {roles.map((role) => {
                    const key = cellKey(artifact.id, role);
                    const cell = cells.get(key);
                    const isPending = cell?.status === "pending";
                    return (
                      <td
                        key={role}
                        className={`px-3 py-2 text-center ${
                          isPending ? "bg-yellow-50" : ""
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={cell?.allowed ?? false}
                          onChange={() => handleToggle(artifact, role)}
                          className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                          title={
                            isPending
                              ? "Pending - click Apply to activate"
                              : cell?.allowed
                                ? "Allowed"
                                : "Denied"
                          }
                        />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Per-user overrides section
// ---------------------------------------------------------------------------

interface UserOverridesSectionProps {
  artifacts: ArtifactEntry[];
}

interface UserOverride {
  artifactId: string;
  artifactName: string;
  artifactType: string;
  userId: string;
  allowed: boolean;
  status: string;
  permissionId: string;
}

export function UserOverridesSection({ artifacts }: UserOverridesSectionProps) {
  const { getUserPermissions, setUserPermissions, applyPending, error } =
    useAdminPermissions();

  const [overrides, setOverrides] = useState<UserOverride[]>([]);
  const [loading, setLoading] = useState(true);
  const [newUserId, setNewUserId] = useState("");
  const [newArtifactId, setNewArtifactId] = useState("");
  const [newAllowed, setNewAllowed] = useState(true);

  const loadOverrides = useCallback(async () => {
    setLoading(true);
    const all: UserOverride[] = [];
    for (const artifact of artifacts) {
      const perms = await getUserPermissions(artifact.type, artifact.id);
      for (const perm of perms) {
        all.push({
          artifactId: perm.artifactId,
          artifactName: artifact.displayName ?? artifact.name,
          artifactType: artifact.type,
          userId: perm.userId,
          allowed: perm.allowed,
          status: perm.status,
          permissionId: perm.id,
        });
      }
    }
    setOverrides(all);
    setLoading(false);
  }, [artifacts, getUserPermissions]);

  useEffect(() => {
    if (artifacts.length > 0) {
      void loadOverrides();
    } else {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [artifacts]);

  const handleAdd = async () => {
    if (!newUserId.trim() || !newArtifactId) return;
    const artifact = artifacts.find((a) => a.id === newArtifactId);
    if (!artifact) return;

    await setUserPermissions(artifact.type, artifact.id, [
      { artifact_type: artifact.type, user_id: newUserId, allowed: newAllowed },
    ]);
    setNewUserId("");
    await loadOverrides();
  };

  const handleApplyAll = async () => {
    const pendingIds = overrides
      .filter((o) => o.status === "pending")
      .map((o) => o.permissionId);
    if (pendingIds.length === 0) return;
    await applyPending(pendingIds);
    await loadOverrides();
  };

  if (loading) {
    return <div className="text-sm text-gray-500 py-4">Loading overrides...</div>;
  }

  const pendingCount = overrides.filter((o) => o.status === "pending").length;

  return (
    <div className="mt-8">
      <h3 className="text-sm font-semibold text-gray-900 mb-3">
        Per-User Permission Overrides
      </h3>

      {error && (
        <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-600">
          {error}
        </div>
      )}

      {/* Add override form */}
      <div className="flex items-center gap-2 mb-4 p-3 bg-gray-50 rounded-md">
        <select
          value={newArtifactId}
          onChange={(e) => setNewArtifactId(e.target.value)}
          className="text-xs border border-gray-300 rounded px-2 py-1 bg-white text-gray-700"
        >
          <option value="">Select artifact...</option>
          {artifacts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.displayName ?? a.name} ({a.type})
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="User ID (UUID)"
          value={newUserId}
          onChange={(e) => setNewUserId(e.target.value)}
          className="text-xs border border-gray-300 rounded px-2 py-1 bg-white text-gray-700 w-64"
        />
        <select
          value={newAllowed ? "allow" : "deny"}
          onChange={(e) => setNewAllowed(e.target.value === "allow")}
          className="text-xs border border-gray-300 rounded px-2 py-1 bg-white text-gray-700"
        >
          <option value="allow">Allow</option>
          <option value="deny">Deny</option>
        </select>
        <button
          onClick={handleAdd}
          className="text-xs px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
        >
          Add Override
        </button>
      </div>

      {/* Apply pending */}
      {pendingCount > 0 && (
        <div className="mb-3 flex items-center gap-2">
          <span className="text-xs text-yellow-700">
            {pendingCount} pending override{pendingCount !== 1 ? "s" : ""}
          </span>
          <button
            onClick={handleApplyAll}
            className="text-xs px-2 py-1 bg-yellow-600 text-white rounded hover:bg-yellow-700 transition-colors"
          >
            Apply Pending
          </button>
        </div>
      )}

      {/* Overrides list */}
      {overrides.length === 0 ? (
        <p className="text-xs text-gray-400">No per-user overrides configured.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                  Artifact
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                  Type
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                  User ID
                </th>
                <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase">
                  Access
                </th>
                <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {overrides.map((o) => (
                <tr
                  key={`${o.artifactId}-${o.userId}`}
                  className={`hover:bg-gray-50 ${o.status === "pending" ? "bg-yellow-50" : ""}`}
                >
                  <td className="px-3 py-2 text-xs text-gray-900">
                    {o.artifactName}
                  </td>
                  <td className="px-3 py-2">
                    <span className="text-xs text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
                      {o.artifactType}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs text-gray-600 font-mono">
                    {o.userId}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {o.allowed ? (
                      <span className="text-green-600 text-xs font-medium">
                        Allow
                      </span>
                    ) : (
                      <span className="text-red-600 text-xs font-medium">
                        Deny
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <span
                      className={`text-xs px-1.5 py-0.5 rounded ${
                        o.status === "pending"
                          ? "bg-yellow-100 text-yellow-700"
                          : "bg-green-100 text-green-700"
                      }`}
                    >
                      {o.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
