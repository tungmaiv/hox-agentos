"use client";
/**
 * useAdminPermissions — hook for permission management with staged apply.
 *
 * Manages role permissions, artifact-level permissions (staged model),
 * per-user permission overrides, and the "apply pending" flow.
 *
 * All calls go through /api/admin/permissions/* Next.js proxy with JWT injection.
 */
import { useState, useCallback } from "react";
import type {
  RolePermissions,
  ArtifactPermission,
  UserArtifactPermission,
  ArtifactPermissionSetEntry,
  UserPermissionSetEntry,
} from "@/lib/admin-types";
import { mapArraySnakeToCamel } from "@/lib/admin-types";

interface UseAdminPermissionsResult {
  /** All role-permission mappings grouped by role. */
  rolePermissions: RolePermissions;
  /** Loading state for role permissions fetch. */
  loadingRoles: boolean;
  /** General error message. */
  error: string | null;
  /** Fetch all role-permission mappings. */
  fetchRolePermissions: () => Promise<void>;
  /** Replace all permissions for a role. */
  setRolePermissions: (
    role: string,
    permissions: string[]
  ) => Promise<boolean>;
  /** Get artifact permissions for a specific artifact. */
  getArtifactPermissions: (
    artifactType: string,
    artifactId: string
  ) => Promise<ArtifactPermission[]>;
  /** Set artifact permissions (creates as pending). */
  setArtifactPermissions: (
    artifactType: string,
    artifactId: string,
    roles: ArtifactPermissionSetEntry[]
  ) => Promise<ArtifactPermission[]>;
  /** Get per-user permission overrides for an artifact. */
  getUserPermissions: (
    artifactType: string,
    artifactId: string
  ) => Promise<UserArtifactPermission[]>;
  /** Set per-user permission overrides (creates as pending). */
  setUserPermissions: (
    artifactType: string,
    artifactId: string,
    entries: UserPermissionSetEntry[]
  ) => Promise<UserArtifactPermission[]>;
  /** Apply pending permissions by their IDs. */
  applyPending: (ids: string[]) => Promise<number>;
}

export function useAdminPermissions(): UseAdminPermissionsResult {
  const [rolePermissions, setRolePermissionsState] = useState<RolePermissions>(
    {}
  );
  const [loadingRoles, setLoadingRoles] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const basePath = "/api/admin/permissions";

  const fetchRolePermissions = useCallback(async () => {
    setLoadingRoles(true);
    setError(null);
    try {
      const res = await fetch(`${basePath}/roles`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as RolePermissions;
      setRolePermissionsState(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch role permissions"
      );
    } finally {
      setLoadingRoles(false);
    }
  }, [basePath]);

  const setRolePermissionsApi = useCallback(
    async (role: string, permissions: string[]): Promise<boolean> => {
      try {
        const res = await fetch(`${basePath}/roles/${role}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ permissions }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        // Refresh role permissions after update
        void fetchRolePermissions();
        return true;
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to set role permissions"
        );
        return false;
      }
    },
    [basePath, fetchRolePermissions]
  );

  const getArtifactPermissions = useCallback(
    async (
      artifactType: string,
      artifactId: string
    ): Promise<ArtifactPermission[]> => {
      try {
        const res = await fetch(
          `${basePath}/artifacts/${artifactType}/${artifactId}`,
          { cache: "no-store" }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as unknown[];
        return mapArraySnakeToCamel<ArtifactPermission>(data);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to get artifact permissions"
        );
        return [];
      }
    },
    [basePath]
  );

  const setArtifactPermissions = useCallback(
    async (
      artifactType: string,
      artifactId: string,
      roles: ArtifactPermissionSetEntry[]
    ): Promise<ArtifactPermission[]> => {
      try {
        const res = await fetch(
          `${basePath}/artifacts/${artifactType}/${artifactId}`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ artifact_type: artifactType, roles }),
          }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as unknown[];
        return mapArraySnakeToCamel<ArtifactPermission>(data);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to set artifact permissions"
        );
        return [];
      }
    },
    [basePath]
  );

  const getUserPermissions = useCallback(
    async (
      artifactType: string,
      artifactId: string
    ): Promise<UserArtifactPermission[]> => {
      try {
        const res = await fetch(
          `${basePath}/users/${artifactType}/${artifactId}`,
          { cache: "no-store" }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as unknown[];
        return mapArraySnakeToCamel<UserArtifactPermission>(data);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to get user permissions"
        );
        return [];
      }
    },
    [basePath]
  );

  const setUserPermissions = useCallback(
    async (
      artifactType: string,
      artifactId: string,
      entries: UserPermissionSetEntry[]
    ): Promise<UserArtifactPermission[]> => {
      try {
        const res = await fetch(
          `${basePath}/users/${artifactType}/${artifactId}`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(entries),
          }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as unknown[];
        return mapArraySnakeToCamel<UserArtifactPermission>(data);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to set user permissions"
        );
        return [];
      }
    },
    [basePath]
  );

  const applyPending = useCallback(
    async (ids: string[]): Promise<number> => {
      try {
        const res = await fetch(`${basePath}/apply`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as { applied: number };
        return data.applied;
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to apply pending permissions"
        );
        return 0;
      }
    },
    [basePath]
  );

  return {
    rolePermissions,
    loadingRoles,
    error,
    fetchRolePermissions,
    setRolePermissions: setRolePermissionsApi,
    getArtifactPermissions,
    setArtifactPermissions,
    getUserPermissions,
    setUserPermissions,
    applyPending,
  };
}
