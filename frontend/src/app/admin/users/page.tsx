"use client";
/**
 * Admin Users tab — local user and group management.
 *
 * Two sections stacked vertically:
 * 1. Local Users — table with search, Create/Edit/Delete dialogs
 * 2. Groups — table with search, Create/Edit/Delete dialogs
 *
 * All mutations POST to Next.js proxy routes which forward to backend
 * admin CRUD endpoints with the server-side Authorization header.
 */

import { useEffect, useState, useCallback } from "react";

// ---------------------------------------------------------------------------
// Types — mirror backend LocalUserResponse / LocalGroupResponse
// ---------------------------------------------------------------------------

interface GroupBrief {
  id: string;
  name: string;
}

interface LocalUser {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  groups: GroupBrief[];
  roles: string[];
  created_at: string;
  updated_at: string;
}

interface LocalGroup {
  id: string;
  name: string;
  description: string;
  roles: string[];
  member_count: number;
  created_at: string;
}

interface ApiErrorBody {
  detail?: string;
  error?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const KNOWN_ROLES = [
  "employee",
  "manager",
  "team-lead",
  "it-admin",
  "executive",
] as const;

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

function isApiErrorBody(val: unknown): val is ApiErrorBody {
  return typeof val === "object" && val !== null;
}

async function apiRequest<T>(
  url: string,
  options?: RequestInit
): Promise<{ data: T | null; error: string | null; status: number }> {
  try {
    const res = await fetch(url, options);
    if (res.status === 204) {
      return { data: null, error: null, status: 204 };
    }
    const json: unknown = await res.json();
    if (!res.ok) {
      const msg =
        isApiErrorBody(json)
          ? (json.detail ?? json.error ?? `HTTP ${res.status}`)
          : `HTTP ${res.status}`;
      return { data: null, error: String(msg), status: res.status };
    }
    return { data: json as T, error: null, status: res.status };
  } catch {
    return { data: null, error: "Network error", status: 0 };
  }
}

// ---------------------------------------------------------------------------
// Multi-select role checkbox component
// ---------------------------------------------------------------------------

function RoleCheckboxes({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (roles: string[]) => void;
}) {
  function toggle(role: string) {
    if (selected.includes(role)) {
      onChange(selected.filter((r) => r !== role));
    } else {
      onChange([...selected, role]);
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      {KNOWN_ROLES.map((role) => (
        <label
          key={role}
          className="flex items-center gap-1.5 cursor-pointer text-sm"
        >
          <input
            type="checkbox"
            checked={selected.includes(role)}
            onChange={() => toggle(role)}
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="text-gray-700">{role}</span>
        </label>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Multi-select group checkbox component
// ---------------------------------------------------------------------------

function GroupCheckboxes({
  groups,
  selected,
  onChange,
}: {
  groups: GroupBrief[];
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  function toggle(id: string) {
    if (selected.includes(id)) {
      onChange(selected.filter((g) => g !== id));
    } else {
      onChange([...selected, id]);
    }
  }

  if (groups.length === 0) {
    return (
      <p className="text-sm text-gray-400">
        No groups available. Create a group first.
      </p>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {groups.map((g) => (
        <label
          key={g.id}
          className="flex items-center gap-1.5 cursor-pointer text-sm"
        >
          <input
            type="checkbox"
            checked={selected.includes(g.id)}
            onChange={() => toggle(g.id)}
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="text-gray-700">{g.name}</span>
        </label>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Modal wrapper
// ---------------------------------------------------------------------------

function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <h2 className="text-base font-semibold text-gray-900">{title}</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>
        <div className="px-6 py-4">{children}</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Password toast — show once, gone forever
// ---------------------------------------------------------------------------

function PasswordToast({
  username,
  password,
  onDismiss,
}: {
  username: string;
  password: string;
  onDismiss: () => void;
}) {
  const [copied, setCopied] = useState(false);

  function handleCopy(): void {
    void navigator.clipboard.writeText(password).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 max-w-sm rounded-lg border border-green-200 bg-green-50 p-4 shadow-lg">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <p className="text-sm font-semibold text-green-800">
            User &quot;{username}&quot; created
          </p>
          <p className="mt-1 text-xs text-green-700">
            Initial password (shown once — copy now):
          </p>
          <div className="mt-2 flex items-center gap-2">
            <code className="flex-1 rounded bg-green-100 px-2 py-1 font-mono text-sm text-green-900 break-all">
              {password}
            </code>
            <button
              onClick={handleCopy}
              className="shrink-0 rounded bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700 transition-colors"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
          <p className="mt-2 text-xs text-green-600">
            This message will not appear again after dismissal.
          </p>
        </div>
        <button
          onClick={onDismiss}
          className="shrink-0 text-green-600 hover:text-green-800 transition-colors"
        >
          <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clipRule="evenodd"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Confirmation dialog
// ---------------------------------------------------------------------------

function ConfirmDialog({
  message,
  onConfirm,
  onCancel,
  loading,
}: {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
        <p className="text-sm text-gray-700">{message}</p>
        <div className="mt-4 flex justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={loading}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Form field component
// ---------------------------------------------------------------------------

function Field({
  label,
  id,
  children,
  hint,
}: {
  label: string;
  id: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <div>
      <label
        htmlFor={id}
        className="block text-sm font-medium text-gray-700 mb-1"
      >
        {label}
      </label>
      {children}
      {hint && <p className="mt-1 text-xs text-gray-400">{hint}</p>}
    </div>
  );
}

const inputClass =
  "mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500";

// ---------------------------------------------------------------------------
// Create/Edit User dialog
// ---------------------------------------------------------------------------

interface UserFormState {
  username: string;
  email: string;
  password: string;
  groupIds: string[];
  roleNames: string[];
}

function UserDialog({
  editUser,
  groups,
  onClose,
  onSuccess,
}: {
  editUser: LocalUser | null;
  groups: LocalGroup[];
  onClose: () => void;
  onSuccess: (user: LocalUser, password: string) => void;
}) {
  const isEdit = editUser !== null;
  const [form, setForm] = useState<UserFormState>({
    username: editUser?.username ?? "",
    email: editUser?.email ?? "",
    password: "",
    groupIds: editUser?.groups.map((g) => g.id) ?? [],
    roleNames: editUser?.roles ?? [],
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    setLoading(true);

    if (isEdit) {
      // PUT update
      const body: Record<string, unknown> = {};
      if (form.username !== editUser.username) body.username = form.username;
      if (form.email !== editUser.email) body.email = form.email;
      if (form.password) body.password = form.password;

      const { data, error: err } = await apiRequest<LocalUser>(
        `/api/admin/local/users/${editUser.id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      );
      if (err) {
        setError(err);
        setLoading(false);
        return;
      }
      onSuccess(data!, "");
    } else {
      // POST create
      const { data, error: err } = await apiRequest<LocalUser>(
        "/api/admin/local/users",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: form.username,
            email: form.email,
            password: form.password,
            group_ids: form.groupIds,
            role_names: form.roleNames,
          }),
        }
      );
      if (err) {
        setError(err);
        setLoading(false);
        return;
      }
      onSuccess(data!, form.password);
    }
    setLoading(false);
  }

  return (
    <Modal title={isEdit ? "Edit User" : "Create User"} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Username" id="username">
          <input
            id="username"
            type="text"
            required
            minLength={3}
            maxLength={64}
            value={form.username}
            onChange={(e) =>
              setForm((f) => ({ ...f, username: e.target.value }))
            }
            className={inputClass}
            placeholder="3-64 characters"
          />
        </Field>

        <Field label="Email" id="email">
          <input
            id="email"
            type="email"
            required
            value={form.email}
            onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
            className={inputClass}
            placeholder="user@example.com"
          />
        </Field>

        <Field
          label={isEdit ? "New Password (leave blank to keep current)" : "Password"}
          id="password"
          hint="Min 8 chars, must include uppercase, lowercase, and a digit"
        >
          <input
            id="password"
            type="password"
            required={!isEdit}
            minLength={isEdit ? 0 : 8}
            value={form.password}
            onChange={(e) =>
              setForm((f) => ({ ...f, password: e.target.value }))
            }
            className={inputClass}
            placeholder={isEdit ? "Leave blank to keep current" : "Min 8 chars"}
          />
        </Field>

        {!isEdit && (
          <>
            <Field label="Groups" id="groups">
              <div className="mt-1">
                <GroupCheckboxes
                  groups={groups.map((g) => ({ id: g.id, name: g.name }))}
                  selected={form.groupIds}
                  onChange={(ids) => setForm((f) => ({ ...f, groupIds: ids }))}
                />
              </div>
            </Field>

            <Field label="Direct Roles" id="roles">
              <div className="mt-1">
                <RoleCheckboxes
                  selected={form.roleNames}
                  onChange={(roles) =>
                    setForm((f) => ({ ...f, roleNames: roles }))
                  }
                />
              </div>
            </Field>
          </>
        )}

        {error && (
          <p className="text-sm text-red-600" role="alert">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Saving..." : isEdit ? "Save Changes" : "Create User"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Create/Edit Group dialog
// ---------------------------------------------------------------------------

interface GroupFormState {
  name: string;
  description: string;
  roles: string[];
}

function GroupDialog({
  editGroup,
  onClose,
  onSuccess,
}: {
  editGroup: LocalGroup | null;
  onClose: () => void;
  onSuccess: (group: LocalGroup) => void;
}) {
  const isEdit = editGroup !== null;
  const [form, setForm] = useState<GroupFormState>({
    name: editGroup?.name ?? "",
    description: editGroup?.description ?? "",
    roles: editGroup?.roles ?? [],
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    setLoading(true);

    if (isEdit) {
      const { data, error: err } = await apiRequest<LocalGroup>(
        `/api/admin/local/groups/${editGroup.id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: form.name,
            description: form.description,
            roles: form.roles,
          }),
        }
      );
      if (err) {
        setError(err);
        setLoading(false);
        return;
      }
      onSuccess(data!);
    } else {
      const { data, error: err } = await apiRequest<LocalGroup>(
        "/api/admin/local/groups",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: form.name,
            description: form.description,
            roles: form.roles,
          }),
        }
      );
      if (err) {
        setError(err);
        setLoading(false);
        return;
      }
      onSuccess(data!);
    }
    setLoading(false);
  }

  return (
    <Modal title={isEdit ? "Edit Group" : "Create Group"} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Group Name" id="groupName">
          <input
            id="groupName"
            type="text"
            required
            minLength={3}
            maxLength={64}
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            className={inputClass}
            placeholder="3-64 characters"
          />
        </Field>

        <Field label="Description" id="groupDesc">
          <input
            id="groupDesc"
            type="text"
            value={form.description}
            onChange={(e) =>
              setForm((f) => ({ ...f, description: e.target.value }))
            }
            className={inputClass}
            placeholder="Optional description"
          />
        </Field>

        <Field label="Roles" id="groupRoles">
          <div className="mt-1">
            <RoleCheckboxes
              selected={form.roles}
              onChange={(roles) => setForm((f) => ({ ...f, roles }))}
            />
          </div>
        </Field>

        {error && (
          <p className="text-sm text-red-600" role="alert">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading
              ? "Saving..."
              : isEdit
              ? "Save Changes"
              : "Create Group"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
        active
          ? "bg-green-100 text-green-800"
          : "bg-gray-100 text-gray-600"
      }`}
    >
      {active ? "Active" : "Inactive"}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

type DeleteTarget =
  | { type: "user"; id: string; name: string }
  | { type: "group"; id: string; name: string };

export default function AdminUsersPage() {
  const [users, setUsers] = useState<LocalUser[]>([]);
  const [groups, setGroups] = useState<LocalGroup[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [loadingGroups, setLoadingGroups] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Search
  const [userSearch, setUserSearch] = useState("");
  const [groupSearch, setGroupSearch] = useState("");

  // Dialogs
  const [userDialog, setUserDialog] = useState<{
    open: boolean;
    edit: LocalUser | null;
  }>({ open: false, edit: null });
  const [groupDialog, setGroupDialog] = useState<{
    open: boolean;
    edit: LocalGroup | null;
  }>({ open: false, edit: null });
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Password toast
  const [passwordToast, setPasswordToast] = useState<{
    username: string;
    password: string;
  } | null>(null);

  const fetchUsers = useCallback(async () => {
    setLoadingUsers(true);
    const { data, error } = await apiRequest<LocalUser[]>(
      "/api/admin/local/users"
    );
    if (error) {
      setLoadError(error);
    } else {
      setUsers(data ?? []);
    }
    setLoadingUsers(false);
  }, []);

  const fetchGroups = useCallback(async () => {
    setLoadingGroups(true);
    const { data, error } = await apiRequest<LocalGroup[]>(
      "/api/admin/local/groups"
    );
    if (error) {
      setLoadError(error);
    } else {
      setGroups(data ?? []);
    }
    setLoadingGroups(false);
  }, []);

  useEffect(() => {
    void fetchUsers();
    void fetchGroups();
  }, [fetchUsers, fetchGroups]);

  // ---- User mutations ----

  function handleUserSuccess(user: LocalUser, password: string): void {
    setUserDialog({ open: false, edit: null });
    void fetchUsers();
    if (password) {
      setPasswordToast({ username: user.username, password });
    }
  }

  async function handleDeleteConfirm(): Promise<void> {
    if (!deleteTarget) return;
    setDeleteLoading(true);

    if (deleteTarget.type === "user") {
      await apiRequest(`/api/admin/local/users/${deleteTarget.id}`, {
        method: "DELETE",
      });
      void fetchUsers();
    } else {
      await apiRequest(`/api/admin/local/groups/${deleteTarget.id}`, {
        method: "DELETE",
      });
      void fetchGroups();
    }

    setDeleteLoading(false);
    setDeleteTarget(null);
  }

  // ---- Group mutations ----

  function handleGroupSuccess(group: LocalGroup): void {
    setGroupDialog({ open: false, edit: null });
    void fetchGroups();
    // Re-fetch users too since role resolution may have changed
    void fetchUsers();
    void group; // used above via callback
  }

  // ---- Filtered data ----

  const filteredUsers = users.filter(
    (u) =>
      u.username.toLowerCase().includes(userSearch.toLowerCase()) ||
      u.email.toLowerCase().includes(userSearch.toLowerCase())
  );

  const filteredGroups = groups.filter(
    (g) =>
      g.name.toLowerCase().includes(groupSearch.toLowerCase()) ||
      g.description.toLowerCase().includes(groupSearch.toLowerCase())
  );

  return (
    <div className="space-y-8">
      {/* Global load error */}
      {loadError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          Failed to load data: {loadError}
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Local Users section */}
      {/* ------------------------------------------------------------------ */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Local Users
            </h2>
            <p className="mt-0.5 text-sm text-gray-500">
              Users who sign in with username and password (local auth)
            </p>
          </div>
          <button
            onClick={() => setUserDialog({ open: true, edit: null })}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            + Create User
          </button>
        </div>

        {/* Search */}
        <div className="mb-3">
          <input
            type="search"
            placeholder="Search by username or email..."
            value={userSearch}
            onChange={(e) => setUserSearch(e.target.value)}
            className="w-full max-w-sm rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Users table */}
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Username
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Email
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Groups
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Roles
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loadingUsers ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-sm text-gray-400"
                  >
                    Loading users...
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-sm text-gray-400"
                  >
                    {userSearch ? "No users match your search." : "No local users yet. Create one to get started."}
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => (
                  <tr key={u.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      {u.username}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {u.email}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {u.groups.length > 0
                        ? u.groups.map((g) => g.name).join(", ")
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {u.roles.length > 0 ? u.roles.join(", ") : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge active={u.is_active} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() =>
                            setUserDialog({ open: true, edit: u })
                          }
                          className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() =>
                            setDeleteTarget({
                              type: "user",
                              id: u.id,
                              name: u.username,
                            })
                          }
                          className="text-sm text-red-600 hover:text-red-800 transition-colors"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Groups section */}
      {/* ------------------------------------------------------------------ */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Groups</h2>
            <p className="mt-0.5 text-sm text-gray-500">
              Role collections — users inherit all roles from their groups
            </p>
          </div>
          <button
            onClick={() => setGroupDialog({ open: true, edit: null })}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            + Create Group
          </button>
        </div>

        {/* Search */}
        <div className="mb-3">
          <input
            type="search"
            placeholder="Search by name or description..."
            value={groupSearch}
            onChange={(e) => setGroupSearch(e.target.value)}
            className="w-full max-w-sm rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Groups table */}
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Description
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Roles
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Members
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loadingGroups ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-8 text-center text-sm text-gray-400"
                  >
                    Loading groups...
                  </td>
                </tr>
              ) : filteredGroups.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-8 text-center text-sm text-gray-400"
                  >
                    {groupSearch ? "No groups match your search." : "No groups yet. Create one to get started."}
                  </td>
                </tr>
              ) : (
                filteredGroups.map((g) => (
                  <tr key={g.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      {g.name}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {g.description || "—"}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {g.roles.length > 0 ? g.roles.join(", ") : "—"}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {g.member_count}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() =>
                            setGroupDialog({ open: true, edit: g })
                          }
                          className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() =>
                            setDeleteTarget({
                              type: "group",
                              id: g.id,
                              name: g.name,
                            })
                          }
                          className="text-sm text-red-600 hover:text-red-800 transition-colors"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Dialogs */}
      {/* ------------------------------------------------------------------ */}

      {userDialog.open && (
        <UserDialog
          editUser={userDialog.edit}
          groups={groups}
          onClose={() => setUserDialog({ open: false, edit: null })}
          onSuccess={handleUserSuccess}
        />
      )}

      {groupDialog.open && (
        <GroupDialog
          editGroup={groupDialog.edit}
          onClose={() => setGroupDialog({ open: false, edit: null })}
          onSuccess={handleGroupSuccess}
        />
      )}

      {deleteTarget && (
        <ConfirmDialog
          message={`Are you sure you want to delete ${deleteTarget.type} "${deleteTarget.name}"? This action cannot be undone.`}
          onConfirm={() => void handleDeleteConfirm()}
          onCancel={() => setDeleteTarget(null)}
          loading={deleteLoading}
        />
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Password toast */}
      {/* ------------------------------------------------------------------ */}

      {passwordToast && (
        <PasswordToast
          username={passwordToast.username}
          password={passwordToast.password}
          onDismiss={() => setPasswordToast(null)}
        />
      )}
    </div>
  );
}
