# Phase 13 Plan 02: Frontend Local Auth (Login + Admin UI)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Users can sign in with local username/password from the login page, and admins can manage local users and groups from a new "Users" tab in the /admin dashboard.

**Architecture:** NextAuth v5 gains a `Credentials` provider that calls the backend `POST /auth/local/token`. The login page shows both a Keycloak SSO button and a local credentials form. The `/admin` layout adds a "Users" tab linking to `/admin/users`, which contains local user and group management tables with CRUD dialogs. All API calls go through the existing `/api/admin/[...path]` catch-all proxy — no new proxy routes needed.

**Tech Stack:** Next.js 15 (App Router), NextAuth v5, React, TypeScript (strict), Tailwind CSS

**Design doc:** `docs/plans/2026-03-03-phase13-local-auth-design.md`
**Depends on:** Plan 13-01 (backend must be deployed first)

---

### Task 1: Add NextAuth Credentials Provider

**Files:**
- Modify: `frontend/src/auth.ts`

**Step 1: Add Credentials provider import and configuration**

In `frontend/src/auth.ts`, add the Credentials provider alongside the existing Keycloak provider.

Add import:

```ts
import Credentials from "next-auth/providers/credentials";
```

Add helper to decode JWT payload (no verification — NextAuth authorize runs server-side after backend already verified):

```ts
function decodeJwtPayload(token: string): Record<string, unknown> {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("Invalid JWT");
  const payload = Buffer.from(parts[1], "base64url").toString("utf-8");
  return JSON.parse(payload);
}
```

Add to the `providers` array (after Keycloak):

```ts
Credentials({
  credentials: {
    username: { label: "Username", type: "text" },
    password: { label: "Password", type: "password" },
  },
  async authorize(credentials) {
    if (!credentials?.username || !credentials?.password) return null;

    const backendUrl =
      process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const res = await fetch(`${backendUrl}/auth/local/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: credentials.username,
        password: credentials.password,
      }),
    });

    if (!res.ok) return null;

    const { access_token } = (await res.json()) as {
      access_token: string;
    };
    const payload = decodeJwtPayload(access_token);

    return {
      id: payload.sub as string,
      name: payload.preferred_username as string,
      email: payload.email as string,
      // Store the backend JWT so it can be forwarded in the session
      accessToken: access_token,
    } as Record<string, unknown>;
  },
}),
```

**Step 2: Update the jwt() callback to handle both providers**

Replace the existing `jwt()` callback body with logic that handles both Keycloak (via `account`) and Credentials (via `user.accessToken`):

```ts
async jwt({ token, account, user }) {
  // ── Credentials provider (local auth) ──
  // The authorize() callback returns a user object with accessToken.
  // No account object is present for Credentials.
  if (user && "accessToken" in user) {
    return {
      ...token,
      accessToken: (user as Record<string, unknown>).accessToken as string,
      // No refresh token for local auth — user re-authenticates after expiry
      authProvider: "local",
    };
  }

  // ── Keycloak provider (existing path) ──
  if (account) {
    return {
      ...token,
      accessToken: account.access_token,
      idToken: account.id_token,
      refreshToken: account.refresh_token,
      expiresAt: account.expires_at,
      authProvider: "keycloak",
    };
  }

  // Subsequent requests — check token refresh (Keycloak only)
  if (token.authProvider === "keycloak") {
    if (Date.now() < (token.expiresAt as number) * 1000 - 30_000) {
      return token;
    }
    if (!token.refreshToken) {
      return token;
    }
    return refreshAccessToken(token);
  }

  // Local auth: no refresh needed, return as-is
  return token;
},
```

The `session()` callback stays unchanged — it already exposes `accessToken` server-side.

**Step 3: Verify TypeScript compiles**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
```

Expected: 0 errors

**Step 4: Commit**

```bash
git add frontend/src/auth.ts
git commit -m "feat(13-02): add NextAuth Credentials provider for local auth"
```

---

### Task 2: Redesign Login Page

**Files:**
- Rewrite: `frontend/src/app/login/page.tsx`

**Step 1: Replace the auto-redirect login page with a choice screen**

Rewrite `frontend/src/app/login/page.tsx`:

```tsx
"use client";
/**
 * Login page — dual auth: Keycloak SSO button + local credentials form.
 */
import { signIn } from "next-auth/react";
import { FormEvent, useState } from "react";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLocalLogin(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const result = await signIn("credentials", {
      username,
      password,
      redirect: false,
    });

    setLoading(false);

    if (result?.error) {
      setError("Invalid username or password");
    } else {
      window.location.href = "/chat";
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm space-y-6 rounded-lg bg-white p-8 shadow-md">
        <div className="text-center">
          <h1 className="text-2xl font-semibold text-gray-900">
            Blitz AgentOS
          </h1>
          <p className="mt-1 text-sm text-gray-500">Sign in to continue</p>
        </div>

        {/* Keycloak SSO */}
        <button
          onClick={() => signIn("keycloak", { callbackUrl: "/chat" })}
          className="flex w-full items-center justify-center gap-2 rounded-md border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 transition-colors"
        >
          Sign in with Keycloak SSO
        </button>

        {/* Divider */}
        <div className="flex items-center gap-4">
          <div className="h-px flex-1 bg-gray-200" />
          <span className="text-xs text-gray-400">or</span>
          <div className="h-px flex-1 bg-gray-200" />
        </div>

        {/* Local credentials form */}
        <form onSubmit={handleLocalLogin} className="space-y-4">
          <div>
            <label
              htmlFor="username"
              className="block text-sm font-medium text-gray-700"
            >
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-gray-700"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="flex w-full justify-center rounded-md bg-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
```

Expected: 0 errors

**Step 3: Verify build**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build
```

Expected: Build succeeds

**Step 4: Commit**

```bash
git add frontend/src/app/login/page.tsx
git commit -m "feat(13-02): redesign login page with Keycloak SSO + local credentials form"
```

---

### Task 3: Add "Users" Tab to Admin Layout

**Files:**
- Modify: `frontend/src/app/admin/layout.tsx:11-20` (ADMIN_TABS array)

**Step 1: Add the Users tab**

In `frontend/src/app/admin/layout.tsx`, add to the `ADMIN_TABS` array:

```ts
const ADMIN_TABS = [
  { label: "Agents",      href: "/admin/agents" },
  { label: "Tools",       href: "/admin/tools" },
  { label: "Skills",      href: "/admin/skills" },
  { label: "MCP Servers", href: "/admin/mcp-servers" },
  { label: "Permissions", href: "/admin/permissions" },
  { label: "Config",      href: "/admin/config" },
  { label: "Credentials", href: "/admin/credentials" },
  { label: "Users",       href: "/admin/users" },
  { label: "AI Builder",  href: "/admin/create" },
] as const;
```

**Step 2: Commit**

```bash
git add frontend/src/app/admin/layout.tsx
git commit -m "feat(13-02): add Users tab to admin dashboard layout"
```

---

### Task 4: Create Admin Users Page

**Files:**
- Create: `frontend/src/app/admin/users/page.tsx`

**Step 1: Create the Users management page**

Create `frontend/src/app/admin/users/page.tsx`:

```tsx
"use client";
/**
 * Admin Users page — manage local users and groups.
 *
 * Two sections:
 * 1. Local Users table with create/edit/delete
 * 2. Groups table with create/edit/delete
 *
 * All API calls go through /api/admin/local/* (catch-all proxy handles JWT).
 */
import { useCallback, useEffect, useState } from "react";

// ── Types ────────────────────────────────────────────────────

interface LocalGroup {
  id: string;
  name: string;
  description: string;
  roles: string[];
  member_count: number;
  created_at: string;
}

interface LocalUser {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  groups: { id: string; name: string }[];
  roles: string[];
  created_at: string;
  updated_at: string;
}

const KNOWN_ROLES = [
  "employee",
  "manager",
  "team-lead",
  "it-admin",
  "developer",
  "executive",
];

// ── API helpers ──────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  opts?: RequestInit
): Promise<T> {
  const res = await fetch(`/api/admin/local${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ?? `API error ${res.status}`
    );
  }
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

// ── Component ────────────────────────────────────────────────

export default function AdminUsersPage() {
  const [users, setUsers] = useState<LocalUser[]>([]);
  const [groups, setGroups] = useState<LocalGroup[]>([]);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"users" | "groups">("users");

  // ── Create User dialog state
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [newUser, setNewUser] = useState({
    username: "",
    email: "",
    password: "",
    group_ids: [] as string[],
    direct_roles: [] as string[],
  });

  // ── Create Group dialog state
  const [showCreateGroup, setShowCreateGroup] = useState(false);
  const [newGroup, setNewGroup] = useState({
    name: "",
    description: "",
    roles: [] as string[],
  });

  const loadUsers = useCallback(async () => {
    try {
      setUsers(await apiFetch<LocalUser[]>("/users"));
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  const loadGroups = useCallback(async () => {
    try {
      setGroups(await apiFetch<LocalGroup[]>("/groups"));
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void loadUsers();
    void loadGroups();
  }, [loadUsers, loadGroups]);

  // ── User CRUD handlers
  async function handleCreateUser() {
    try {
      setError("");
      await apiFetch("/users", {
        method: "POST",
        body: JSON.stringify(newUser),
      });
      setShowCreateUser(false);
      setNewUser({ username: "", email: "", password: "", group_ids: [], direct_roles: [] });
      await loadUsers();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleDeleteUser(id: string) {
    if (!confirm("Delete this user? This cannot be undone.")) return;
    try {
      await apiFetch(`/users/${id}`, { method: "DELETE" });
      await loadUsers();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleToggleActive(user: LocalUser) {
    try {
      await apiFetch(`/users/${user.id}`, {
        method: "PUT",
        body: JSON.stringify({ is_active: !user.is_active }),
      });
      await loadUsers();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  // ── Group CRUD handlers
  async function handleCreateGroup() {
    try {
      setError("");
      await apiFetch("/groups", {
        method: "POST",
        body: JSON.stringify(newGroup),
      });
      setShowCreateGroup(false);
      setNewGroup({ name: "", description: "", roles: [] });
      await loadGroups();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleDeleteGroup(id: string) {
    if (!confirm("Delete this group? This cannot be undone.")) return;
    try {
      await apiFetch(`/groups/${id}`, { method: "DELETE" });
      await loadGroups();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function toggleRole(list: string[], role: string): string[] {
    return list.includes(role)
      ? list.filter((r) => r !== role)
      : [...list, role];
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">
          Local User Management
        </h2>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          {error}
          <button
            onClick={() => setError("")}
            className="ml-2 text-red-500 hover:text-red-700"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Sub-tabs */}
      <div className="flex gap-4 border-b border-gray-200">
        <button
          onClick={() => setTab("users")}
          className={`pb-2 text-sm font-medium ${
            tab === "users"
              ? "border-b-2 border-blue-600 text-blue-600"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Users ({users.length})
        </button>
        <button
          onClick={() => setTab("groups")}
          className={`pb-2 text-sm font-medium ${
            tab === "groups"
              ? "border-b-2 border-blue-600 text-blue-600"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Groups ({groups.length})
        </button>
      </div>

      {/* ── Users Tab ──────────────────────────────── */}
      {tab === "users" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={() => setShowCreateUser(true)}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
            >
              Create User
            </button>
          </div>

          {/* Create User Dialog */}
          {showCreateUser && (
            <div className="rounded-lg border border-gray-200 bg-white p-6 space-y-4">
              <h3 className="font-medium text-gray-900">Create Local User</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-600">Username</label>
                  <input
                    value={newUser.username}
                    onChange={(e) =>
                      setNewUser({ ...newUser, username: e.target.value })
                    }
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-600">Email</label>
                  <input
                    type="email"
                    value={newUser.email}
                    onChange={(e) =>
                      setNewUser({ ...newUser, email: e.target.value })
                    }
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-600">Password</label>
                  <input
                    type="password"
                    value={newUser.password}
                    onChange={(e) =>
                      setNewUser({ ...newUser, password: e.target.value })
                    }
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-600">Groups</label>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {groups.map((g) => (
                      <label key={g.id} className="flex items-center gap-1 text-sm">
                        <input
                          type="checkbox"
                          checked={newUser.group_ids.includes(g.id)}
                          onChange={() =>
                            setNewUser({
                              ...newUser,
                              group_ids: newUser.group_ids.includes(g.id)
                                ? newUser.group_ids.filter((id) => id !== g.id)
                                : [...newUser.group_ids, g.id],
                            })
                          }
                        />
                        {g.name}
                      </label>
                    ))}
                  </div>
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-600">Direct Roles</label>
                <div className="mt-1 flex flex-wrap gap-2">
                  {KNOWN_ROLES.map((role) => (
                    <label key={role} className="flex items-center gap-1 text-sm">
                      <input
                        type="checkbox"
                        checked={newUser.direct_roles.includes(role)}
                        onChange={() =>
                          setNewUser({
                            ...newUser,
                            direct_roles: toggleRole(newUser.direct_roles, role),
                          })
                        }
                      />
                      {role}
                    </label>
                  ))}
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleCreateUser}
                  className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
                >
                  Create
                </button>
                <button
                  onClick={() => setShowCreateUser(false)}
                  className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Users Table */}
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Username</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Email</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Groups</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Roles</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {users.map((user) => (
                  <tr key={user.id}>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{user.username}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{user.email}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {user.groups.map((g) => g.name).join(", ") || "—"}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <div className="flex flex-wrap gap-1">
                        {user.roles.map((r) => (
                          <span key={r} className="inline-block rounded bg-blue-100 px-2 py-0.5 text-xs text-blue-700">
                            {r}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <button
                        onClick={() => handleToggleActive(user)}
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          user.is_active
                            ? "bg-green-100 text-green-700"
                            : "bg-red-100 text-red-700"
                        }`}
                      >
                        {user.is_active ? "Active" : "Inactive"}
                      </button>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <button
                        onClick={() => handleDeleteUser(user.id)}
                        className="text-red-600 hover:text-red-800 text-xs"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-sm text-gray-400">
                      No local users yet. Create one to get started.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Groups Tab ─────────────────────────────── */}
      {tab === "groups" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={() => setShowCreateGroup(true)}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
            >
              Create Group
            </button>
          </div>

          {/* Create Group Dialog */}
          {showCreateGroup && (
            <div className="rounded-lg border border-gray-200 bg-white p-6 space-y-4">
              <h3 className="font-medium text-gray-900">Create Local Group</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-600">Name</label>
                  <input
                    value={newGroup.name}
                    onChange={(e) =>
                      setNewGroup({ ...newGroup, name: e.target.value })
                    }
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-600">Description</label>
                  <input
                    value={newGroup.description}
                    onChange={(e) =>
                      setNewGroup({ ...newGroup, description: e.target.value })
                    }
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-600">Roles</label>
                <div className="mt-1 flex flex-wrap gap-2">
                  {KNOWN_ROLES.map((role) => (
                    <label key={role} className="flex items-center gap-1 text-sm">
                      <input
                        type="checkbox"
                        checked={newGroup.roles.includes(role)}
                        onChange={() =>
                          setNewGroup({
                            ...newGroup,
                            roles: toggleRole(newGroup.roles, role),
                          })
                        }
                      />
                      {role}
                    </label>
                  ))}
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleCreateGroup}
                  className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
                >
                  Create
                </button>
                <button
                  onClick={() => setShowCreateGroup(false)}
                  className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Groups Table */}
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Name</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Description</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Roles</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Members</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {groups.map((group) => (
                  <tr key={group.id}>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{group.name}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{group.description || "—"}</td>
                    <td className="px-4 py-3 text-sm">
                      <div className="flex flex-wrap gap-1">
                        {group.roles.map((r) => (
                          <span key={r} className="inline-block rounded bg-purple-100 px-2 py-0.5 text-xs text-purple-700">
                            {r}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{group.member_count}</td>
                    <td className="px-4 py-3 text-sm">
                      <button
                        onClick={() => handleDeleteGroup(group.id)}
                        className="text-red-600 hover:text-red-800 text-xs"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
                {groups.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-400">
                      No groups yet. Create one to organize users.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
```

Expected: 0 errors

**Step 3: Verify full build**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build
```

Expected: Build succeeds

**Step 4: Commit**

```bash
git add frontend/src/app/admin/users/page.tsx
git commit -m "feat(13-02): add admin Users page with local user and group management"
```

---

### Task 5: Final Verification

**Step 1: Full frontend build**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build
```

Expected: Build succeeds with 0 TypeScript errors.

**Step 2: Full backend test suite**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: All tests pass.

**Step 3: Verify commit log**

```bash
git log --oneline -5
```

Expected: 4 commits with `feat(13-02)` prefix.
