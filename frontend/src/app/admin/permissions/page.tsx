"use client";
/**
 * Admin Permissions page — global permission management.
 *
 * Shows role-permission table editor, artifact permission matrix,
 * and per-user overrides. "Apply All Pending" activates staged changes.
 */
import { useState, useEffect, useCallback } from "react";
import { useAdminPermissions } from "@/hooks/use-admin-permissions";
import { useAdminArtifacts } from "@/hooks/use-admin-artifacts";
import type { AgentDefinition, ToolDefinition, SkillDefinition } from "@/lib/admin-types";
import {
  PermissionMatrix,
  UserOverridesSection,
} from "@/components/admin/permission-matrix";

const KNOWN_ROLES = [
  "it-admin",
  "team-lead",
  "manager",
  "employee",
  "executive",
];

const KNOWN_PERMISSIONS = [
  "chat",
  "tool:email",
  "tool:calendar",
  "tool:project",
  "crm:read",
  "crm:write",
  "tool:reports",
  "tool:admin",
  "registry:manage",
  "sandbox:execute",
  "workflow:create",
  "workflow:approve",
];

export default function AdminPermissionsPage() {
  const {
    rolePermissions,
    loadingRoles,
    error,
    fetchRolePermissions,
    setRolePermissions,
  } = useAdminPermissions();

  const { items: agents, loading: loadingAgents } =
    useAdminArtifacts<AgentDefinition>("agents");
  const { items: tools, loading: loadingTools } =
    useAdminArtifacts<ToolDefinition>("tools");
  const { items: skills, loading: loadingSkills } =
    useAdminArtifacts<SkillDefinition>("skills");

  const [editingRole, setEditingRole] = useState<string | null>(null);
  const [editPerms, setEditPerms] = useState<string[]>([]);

  useEffect(() => {
    void fetchRolePermissions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleEditRole = (role: string) => {
    setEditingRole(role);
    setEditPerms(rolePermissions[role] ?? []);
  };

  const handleSaveRole = async () => {
    if (!editingRole) return;
    await setRolePermissions(editingRole, editPerms);
    setEditingRole(null);
  };

  const togglePerm = (perm: string) => {
    setEditPerms((prev) =>
      prev.includes(perm)
        ? prev.filter((p) => p !== perm)
        : [...prev, perm]
    );
  };

  // Combine all artifacts for the permission matrix
  const allArtifacts = useCallback(() => {
    return [
      ...agents.map((a) => ({
        id: a.id,
        name: a.name,
        displayName: a.displayName,
        type: "agent" as const,
      })),
      ...tools.map((t) => ({
        id: t.id,
        name: t.name,
        displayName: t.displayName,
        type: "tool" as const,
      })),
      ...skills.map((s) => ({
        id: s.id,
        name: s.name,
        displayName: s.displayName,
        type: "skill" as const,
      })),
    ];
  }, [agents, tools, skills]);

  const isLoading = loadingRoles || loadingAgents || loadingTools || loadingSkills;

  if (isLoading) {
    return <div className="text-gray-500 py-8">Loading permissions...</div>;
  }

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">
        Permission Management
      </h2>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Section 1: Role Permissions */}
      <section className="mb-8">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">
          Role Permissions
        </h3>
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Role
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Permissions
                </th>
                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {KNOWN_ROLES.map((role) => (
                <tr key={role} className="hover:bg-gray-50">
                  <td className="px-4 py-2.5 text-sm font-medium text-gray-900">
                    {role}
                  </td>
                  <td className="px-4 py-2.5">
                    {editingRole === role ? (
                      <div className="flex flex-wrap gap-1.5">
                        {KNOWN_PERMISSIONS.map((perm) => (
                          <label
                            key={perm}
                            className="flex items-center gap-1 text-xs"
                          >
                            <input
                              type="checkbox"
                              checked={editPerms.includes(perm)}
                              onChange={() => togglePerm(perm)}
                              className="w-3 h-3 text-blue-600 rounded border-gray-300"
                            />
                            <span className="text-gray-600">{perm}</span>
                          </label>
                        ))}
                      </div>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {(rolePermissions[role] ?? []).map((perm) => (
                          <span
                            key={perm}
                            className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded"
                          >
                            {perm}
                          </span>
                        ))}
                        {!(rolePermissions[role]?.length) && (
                          <span className="text-xs text-gray-400">
                            No permissions
                          </span>
                        )}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {editingRole === role ? (
                      <div className="inline-flex gap-1">
                        <button
                          onClick={handleSaveRole}
                          className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditingRole(null)}
                          className="text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => handleEditRole(role)}
                        className="text-xs px-2 py-1 text-blue-600 hover:bg-blue-50 rounded transition-colors"
                      >
                        Edit
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Section 2: Artifact Permission Matrix */}
      <section className="mb-8">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">
          Artifact Permission Matrix
        </h3>
        <p className="text-xs text-gray-500 mb-3">
          Manage per-artifact, per-role permissions. Changes are staged as
          &quot;pending&quot; until you click &quot;Apply Pending&quot;.
        </p>
        <PermissionMatrix artifacts={allArtifacts()} roles={KNOWN_ROLES} />
      </section>

      {/* Section 3: Per-User Overrides */}
      <section>
        <UserOverridesSection artifacts={allArtifacts()} />
      </section>
    </div>
  );
}
