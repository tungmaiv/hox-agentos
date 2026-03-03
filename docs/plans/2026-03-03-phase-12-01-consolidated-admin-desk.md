# Phase 12-01: Consolidated Admin Desk Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move all admin-only controls out of `/settings` and into `/admin`, adding a Config tab (agent toggles) and a Credentials tab (admin view/revoke of all users' OAuth connections).

**Architecture:** New backend route `admin_credentials.py` exposes `GET /api/admin/credentials` and `DELETE /api/admin/credentials/{user_id}/{provider}` gated by `registry:manage`. Frontend adds two new admin tab pages. The existing catch-all proxy at `frontend/src/app/api/admin/[...path]/route.ts` already handles all `/api/admin/*` routes — no new proxy files needed. `/settings/agents` and `/settings/integrations` are deleted; `/settings/page.tsx` is updated to remove its Admin section.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, Next.js 15 App Router, TypeScript strict

---

## Canonical Commands

```bash
# Backend tests (always use this exact form — uv run times out)
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q

# TypeScript check
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
```

## Pre-flight Check

Before starting, verify baseline passes:

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
# Expected: 586 passed (or higher), 0 failed
```

---

## Task 1: Backend — `admin_credentials.py` route

**Files:**
- Create: `backend/api/routes/admin_credentials.py`

**Context:** The `user_credentials` table (model at `backend/core/models/credentials.py`) stores per-user OAuth tokens encrypted with AES-256. It has columns: `id`, `user_id` (UUID), `provider` (str), `ciphertext`, `iv`, `created_at`, `updated_at`. The admin endpoint lists all rows across all users (no decryption — never expose token values) and can delete rows.

**Step 1: Write the file**

```python
"""
Admin credential management API — read-only view + force-revoke.

GET    /api/admin/credentials                     — list all users' connected providers
DELETE /api/admin/credentials/{user_id}/{provider} — admin force-revoke a credential

Security: registry:manage permission (Gate 2 RBAC).
Credentials (token values) are NEVER returned in responses.
"""
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.credentials import UserCredential
from core.models.user import UserContext
from security.deps import get_current_user
from security.rbac import has_permission

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin/credentials", tags=["admin-credentials"])


class AdminCredentialView(BaseModel):
    """A connected OAuth provider row — token values are NEVER included."""
    user_id: str
    provider: str
    connected_at: str  # ISO timestamp


async def _require_registry_manager(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    if not await has_permission(user, "registry:manage", session):
        raise HTTPException(status_code=403, detail="Registry manage permission required")
    return user


@router.get("", response_model=list[AdminCredentialView])
async def list_all_credentials(
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> list[AdminCredentialView]:
    """
    List all users' connected OAuth providers.

    Returns user_id, provider name, and timestamp — never token values.
    Admin access required (registry:manage).
    """
    async with session.begin():
        result = await session.execute(
            select(UserCredential).order_by(UserCredential.user_id, UserCredential.created_at)
        )
        rows = result.scalars().all()

    logger.info(
        "admin_credentials_listed",
        user_id=str(user["user_id"]),
        count=len(rows),
    )
    return [
        AdminCredentialView(
            user_id=str(row.user_id),
            provider=row.provider,
            connected_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


@router.delete("/{target_user_id}/{provider}", status_code=204)
async def admin_revoke_credential(
    target_user_id: UUID,
    provider: str,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> None:
    """
    Admin force-revoke an OAuth credential for any user.

    Returns 204 on success. Returns 404 if not found.
    """
    async with session.begin():
        result = await session.execute(
            select(UserCredential).where(
                UserCredential.user_id == target_user_id,
                UserCredential.provider == provider,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Credential not found for user {target_user_id}, provider '{provider}'",
            )
        await session.execute(
            delete(UserCredential).where(
                UserCredential.user_id == target_user_id,
                UserCredential.provider == provider,
            )
        )

    logger.info(
        "admin_credential_revoked",
        admin_id=str(user["user_id"]),
        target_user_id=str(target_user_id),
        provider=provider,
    )
```

**Step 2: Commit**

```bash
git add backend/api/routes/admin_credentials.py
git commit -m "feat(12-01): add admin_credentials route (list + force-revoke)"
```

---

## Task 2: Register route in `main.py`

**Files:**
- Modify: `backend/main.py`

**Step 1: Add import**

Find the existing imports block (around line 15). Add to the `from api.routes import (...)` block:

```python
    admin_credentials,
```

**Step 2: Register router**

After the `app.include_router(admin_permissions.router)` line (around line 156), add:

```python
    # Admin credential management — /api/admin/credentials (registry:manage)
    app.include_router(admin_credentials.router)
```

**Step 3: Verify import compiles**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. python -c "from main import app; print('OK')"
# Expected: OK (no errors)
```

**Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat(12-01): register admin_credentials router in main.py"
```

---

## Task 3: Tests for admin credentials endpoint

**Files:**
- Create: `backend/tests/api/test_admin_credentials.py`

**Step 1: Write the test file**

Model this exactly after `backend/tests/api/test_admin_agents.py`. Key patterns:
- `make_admin_ctx()` for it-admin (has `registry:manage`)
- `make_employee_ctx()` for employee (lacks `registry:manage`)
- `sqlite_db` fixture with in-memory SQLite
- `client` fixture that overrides `get_db` and `get_current_user`

```python
"""
Tests for admin credential management API — /api/admin/credentials.

Covers:
  - 401 without auth
  - 403 with employee role (no registry:manage)
  - GET /api/admin/credentials — lists all users' credentials (no token values)
  - DELETE /api/admin/credentials/{user_id}/{provider} — 204 on success, 404 if not found
"""
import asyncio
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.db import Base, get_db
from core.models.credentials import UserCredential  # noqa: F401
from core.models.role_permission import RolePermission  # noqa: F401
from core.models.user import UserContext
from main import app
from security.deps import get_current_user


def make_admin_ctx() -> UserContext:
    return UserContext(
        user_id=uuid4(),
        email="admin@blitz.local",
        username="admin_user",
        roles=["it-admin"],
        groups=["/it"],
    )


def make_employee_ctx() -> UserContext:
    return UserContext(
        user_id=uuid4(),
        email="emp@blitz.local",
        username="emp_user",
        roles=["employee"],
        groups=["/tech"],
    )


@pytest.fixture
def sqlite_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_setup())

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    yield session_factory
    app.dependency_overrides.pop(get_db, None)
    loop.run_until_complete(engine.dispose())
    loop.close()


@pytest.fixture
def admin_client(sqlite_db):
    admin = make_admin_ctx()
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app, raise_server_exceptions=True)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def employee_client(sqlite_db):
    emp = make_employee_ctx()
    app.dependency_overrides[get_current_user] = lambda: emp
    client = TestClient(app, raise_server_exceptions=True)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


def _seed_credential(session_factory, user_id, provider: str = "google") -> None:
    """Insert a test credential row."""
    import asyncio
    from datetime import datetime, timezone

    async def _insert():
        async with session_factory() as session:
            async with session.begin():
                cred = UserCredential(
                    user_id=user_id,
                    provider=provider,
                    ciphertext=b"fake_ciphertext",
                    iv=b"fake_iv_12345678",
                )
                session.add(cred)

    asyncio.get_event_loop().run_until_complete(_insert())


# ---------------------------------------------------------------------------
# 401 without auth
# ---------------------------------------------------------------------------


def test_list_credentials_no_auth():
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get("/api/admin/credentials")
    assert resp.status_code == 401


def test_revoke_credential_no_auth():
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.delete(f"/api/admin/credentials/{uuid4()}/google")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 403 for employee (no registry:manage)
# ---------------------------------------------------------------------------


def test_list_credentials_forbidden(employee_client):
    resp = employee_client.get("/api/admin/credentials")
    assert resp.status_code == 403


def test_revoke_credential_forbidden(employee_client):
    resp = employee_client.delete(f"/api/admin/credentials/{uuid4()}/google")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET — lists credentials
# ---------------------------------------------------------------------------


def test_list_credentials_empty(admin_client):
    resp = admin_client.get("/api/admin/credentials")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_credentials_returns_rows(admin_client, sqlite_db):
    user_id = uuid4()
    _seed_credential(sqlite_db, user_id, "google")
    _seed_credential(sqlite_db, user_id, "microsoft")

    resp = admin_client.get("/api/admin/credentials")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    providers = {row["provider"] for row in data}
    assert providers == {"google", "microsoft"}
    # Token values must never appear
    for row in data:
        assert "ciphertext" not in row
        assert "iv" not in row
        assert "token" not in row


# ---------------------------------------------------------------------------
# DELETE — revoke credential
# ---------------------------------------------------------------------------


def test_revoke_credential_success(admin_client, sqlite_db):
    user_id = uuid4()
    _seed_credential(sqlite_db, user_id, "google")

    resp = admin_client.delete(f"/api/admin/credentials/{user_id}/google")
    assert resp.status_code == 204

    # Verify gone
    resp2 = admin_client.get("/api/admin/credentials")
    assert resp2.status_code == 200
    assert resp2.json() == []


def test_revoke_credential_not_found(admin_client, sqlite_db):
    resp = admin_client.delete(f"/api/admin/credentials/{uuid4()}/google")
    assert resp.status_code == 404
```

**Step 2: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/api/test_admin_credentials.py -v
# Expected: all pass
```

**Step 3: Run full suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
# Expected: 586+ passed, 0 failed
```

**Step 4: Commit**

```bash
git add backend/tests/api/test_admin_credentials.py
git commit -m "test(12-01): add admin credentials endpoint tests"
```

---

## Task 4: Frontend — `/admin/config/page.tsx`

**Files:**
- Create: `frontend/src/app/admin/config/page.tsx`

**Context:** This is the agent toggle UI from `/settings/agents/page.tsx`. It uses `GET /api/admin/config` and `PUT /api/admin/config/{key}`. The proxy routes already exist at `frontend/src/app/api/admin/config/route.ts` and `frontend/src/app/api/admin/config/[key]/route.ts`. Copy the toggle logic from `/settings/agents/page.tsx` but remove the back-link nav and adapt for the admin page layout.

**Step 1: Write the file**

```typescript
"use client";
/**
 * Admin Config page — system-wide agent enable/disable toggles.
 * Uses /api/admin/config (GET) and /api/admin/config/{key} (PUT).
 * Data and behavior identical to the removed /settings/agents page.
 */
import { useEffect, useState } from "react";
import { z } from "zod";

const AgentConfigSchema = z
  .object({
    "agent.email.enabled": z.boolean().optional(),
    "agent.calendar.enabled": z.boolean().optional(),
    "agent.project.enabled": z.boolean().optional(),
  })
  .passthrough();

type AgentConfig = z.infer<typeof AgentConfigSchema>;

interface AgentToggle {
  key: keyof Pick<
    AgentConfig,
    "agent.email.enabled" | "agent.calendar.enabled" | "agent.project.enabled"
  >;
  label: string;
  description: string;
}

const AGENT_TOGGLES: AgentToggle[] = [
  {
    key: "agent.email.enabled",
    label: "Email Agent",
    description: "Enables email fetching, summarization, and drafting tools.",
  },
  {
    key: "agent.calendar.enabled",
    label: "Calendar Agent",
    description: "Enables calendar lookup and event management tools.",
  },
  {
    key: "agent.project.enabled",
    label: "Project Agent",
    description: "Enables project status and task management tools.",
  },
];

type LoadState = "loading" | "error" | "ready";

export default function AdminConfigPage() {
  const [config, setConfig] = useState<AgentConfig>({});
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/config", { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) { setLoadState("error"); return; }
        const raw: unknown = await res.json();
        const parsed = AgentConfigSchema.safeParse(raw);
        if (parsed.success) setConfig(parsed.data);
        setLoadState("ready");
      })
      .catch(() => setLoadState("error"));
  }, []);

  async function handleToggle(key: AgentToggle["key"], newValue: boolean) {
    setSaving(key);
    try {
      const res = await fetch(`/api/admin/config/${encodeURIComponent(key)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: newValue }),
      });
      if (res.ok) setConfig((prev) => ({ ...prev, [key]: newValue }));
    } finally {
      setSaving(null);
    }
  }

  if (loadState === "loading") {
    return <div className="py-8 text-gray-500">Loading configuration...</div>;
  }

  if (loadState === "error") {
    return (
      <div className="py-8 text-red-600 text-sm">
        Failed to load configuration. Please try again.
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900">System Configuration</h2>
        <p className="text-sm text-gray-500 mt-1">
          Enable or disable AI agents system-wide. Changes take effect immediately.
        </p>
      </div>

      <section className="max-w-2xl">
        <h3 className="text-sm font-medium text-gray-700 uppercase tracking-wider mb-4">
          Agent Enable / Disable
        </h3>
        <div className="space-y-4">
          {AGENT_TOGGLES.map(({ key, label, description }) => {
            const isEnabled = config[key] ?? true;
            const isSaving = saving === key;
            return (
              <div
                key={key}
                className="flex items-start justify-between p-4 border border-gray-200 rounded-lg bg-white"
              >
                <div className="flex-1 mr-4">
                  <h4 className="text-base font-medium text-gray-900">{label}</h4>
                  <p className="text-sm text-gray-500 mt-1">{description}</p>
                </div>
                <button
                  role="switch"
                  aria-checked={isEnabled}
                  aria-label={`Toggle ${label}`}
                  disabled={isSaving}
                  onClick={() => void handleToggle(key, !isEnabled)}
                  className={[
                    "relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent",
                    "transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2",
                    isSaving ? "opacity-50 cursor-not-allowed" : "",
                    isEnabled ? "bg-blue-600" : "bg-gray-200",
                  ].filter(Boolean).join(" ")}
                >
                  <span
                    aria-hidden="true"
                    className={[
                      "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0",
                      "transition duration-200 ease-in-out",
                      isEnabled ? "translate-x-5" : "translate-x-0",
                    ].join(" ")}
                  />
                </button>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
```

**Step 2: TypeScript check**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
# Expected: 0 errors
```

**Step 3: Commit**

```bash
git add frontend/src/app/admin/config/page.tsx
git commit -m "feat(12-01): add /admin/config page (agent toggles)"
```

---

## Task 5: Frontend — `/admin/credentials/page.tsx`

**Files:**
- Create: `frontend/src/app/admin/credentials/page.tsx`

**Context:** The catch-all proxy at `frontend/src/app/api/admin/[...path]/route.ts` already handles `GET /api/admin/credentials` and `DELETE /api/admin/credentials/{userId}/{provider}` — no new proxy files needed. The page fetches credentials and shows them in a table with a Revoke button per row.

**Step 1: Write the file**

```typescript
"use client";
/**
 * Admin Credentials page — view and revoke all users' OAuth connections.
 *
 * Uses GET /api/admin/credentials (list) and
 * DELETE /api/admin/credentials/{userId}/{provider} (revoke).
 * Token values are NEVER shown — only provider name, user ID, and timestamp.
 */
import { useEffect, useState } from "react";
import { z } from "zod";

const CredentialRowSchema = z.object({
  user_id: z.string(),
  provider: z.string(),
  connected_at: z.string(),
});
const CredentialsListSchema = z.array(CredentialRowSchema);
type CredentialRow = z.infer<typeof CredentialRowSchema>;

export default function AdminCredentialsPage() {
  const [rows, setRows] = useState<CredentialRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<string | null>(null);

  const fetchCredentials = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/credentials", { cache: "no-store" });
      if (!res.ok) {
        setError(`Failed to load credentials (${res.status})`);
        return;
      }
      const raw: unknown = await res.json();
      const parsed = CredentialsListSchema.safeParse(raw);
      if (!parsed.success) { setError("Unexpected response format."); return; }
      setRows(parsed.data);
    } catch {
      setError("Network error — could not reach backend.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void fetchCredentials(); }, []);

  const handleRevoke = async (userId: string, provider: string) => {
    if (!confirm(`Revoke ${provider} credential for user ${userId}?`)) return;
    const key = `${userId}/${provider}`;
    setRevoking(key);
    try {
      const res = await fetch(`/api/admin/credentials/${userId}/${provider}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const data = (await res.json()) as { detail?: string };
        setError(data.detail ?? `Failed to revoke (${res.status})`);
        return;
      }
      await fetchCredentials();
    } catch {
      setError("Network error — could not revoke credential.");
    } finally {
      setRevoking(null);
    }
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900">OAuth Credentials</h2>
        <p className="text-sm text-gray-500 mt-1">
          All users&apos; connected OAuth providers. Token values are never displayed.
        </p>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                User ID
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Provider
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Connected At
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-100">
            {loading ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-sm text-gray-400">
                  Loading...
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-sm text-gray-400">
                  No OAuth credentials found.
                </td>
              </tr>
            ) : (
              rows.map((row) => {
                const key = `${row.user_id}/${row.provider}`;
                const isRevoking = revoking === key;
                return (
                  <tr key={key}>
                    <td className="px-4 py-3 text-sm font-mono text-gray-600 truncate max-w-xs">
                      {row.user_id}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 capitalize">
                      {row.provider}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {new Date(row.connected_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => void handleRevoke(row.user_id, row.provider)}
                        disabled={isRevoking}
                        className="text-xs text-red-600 hover:underline disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isRevoking ? "Revoking..." : "Revoke"}
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

**Step 2: TypeScript check**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
# Expected: 0 errors
```

**Step 3: Commit**

```bash
git add frontend/src/app/admin/credentials/page.tsx
git commit -m "feat(12-01): add /admin/credentials page (admin OAuth view + revoke)"
```

---

## Task 6: Update `admin/layout.tsx` — add Config and Credentials tabs

**Files:**
- Modify: `frontend/src/app/admin/layout.tsx`

**Step 1: Replace `ADMIN_TABS`**

Find the `ADMIN_TABS` constant (around line 11). Replace it with:

```typescript
const ADMIN_TABS = [
  { label: "Agents",      href: "/admin/agents" },
  { label: "Tools",       href: "/admin/tools" },
  { label: "Skills",      href: "/admin/skills" },
  { label: "MCP Servers", href: "/admin/mcp-servers" },
  { label: "Permissions", href: "/admin/permissions" },
  { label: "Config",      href: "/admin/config" },
  { label: "Credentials", href: "/admin/credentials" },
  { label: "AI Builder",  href: "/admin/create" },
] as const;
```

**Step 2: TypeScript check**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
# Expected: 0 errors
```

**Step 3: Commit**

```bash
git add frontend/src/app/admin/layout.tsx
git commit -m "feat(12-01): add Config and Credentials tabs to admin nav"
```

---

## Task 7: Delete orphaned settings pages

**Files:**
- Delete: `frontend/src/app/settings/agents/page.tsx`
- Delete: `frontend/src/app/settings/integrations/page.tsx`

**Step 1: Delete the files**

```bash
rm frontend/src/app/settings/agents/page.tsx
rm frontend/src/app/settings/integrations/page.tsx
```

**Step 2: TypeScript check (should still pass since no one imports these)**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
# Expected: 0 errors
```

**Step 3: Commit**

```bash
git add -u frontend/src/app/settings/agents/page.tsx frontend/src/app/settings/integrations/page.tsx
git commit -m "feat(12-01): delete /settings/agents and /settings/integrations (moved to /admin)"
```

---

## Task 8: Update `/settings/page.tsx` — remove Admin section

**Files:**
- Modify: `frontend/src/app/settings/page.tsx`

**Step 1: Remove the Admin grid section**

Find the `<h2>Admin</h2>` block and the `<div className="grid grid-cols-2 gap-3">` below it containing the Agents and Integrations links. Delete those elements (roughly lines 97–123 in the current file). Keep the Personal grid and the Custom Instructions section.

The resulting page should only have:
- Back to chat link
- "Settings" h1
- Personal nav section (Memory, Chat Preferences, Channel Linking)
- Custom Instructions section

**Step 2: TypeScript check**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
# Expected: 0 errors
```

**Step 3: Commit**

```bash
git add frontend/src/app/settings/page.tsx
git commit -m "feat(12-01): remove Admin section from /settings page"
```

---

## Task 9: Final verification

**Step 1: Run full backend test suite**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
# Expected: 586+ passed (new tests add to the count), 0 failed
```

**Step 2: TypeScript full build**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build
# Expected: 0 TypeScript errors, build succeeds
```

**Step 3: Commit if anything was adjusted**

If any fixes were needed, commit them with `fix(12-01): ...`.

---

## Success Criteria Checklist

- [ ] `GET /api/admin/credentials` returns `[{user_id, provider, connected_at}]` for admin; 403 for employee
- [ ] `DELETE /api/admin/credentials/{user_id}/{provider}` returns 204 for admin; 404 if not found
- [ ] `/admin/config` tab shows agent enable/disable toggles — toggles save to backend
- [ ] `/admin/credentials` tab shows all users' OAuth connections with Revoke button
- [ ] `/settings/agents` and `/settings/integrations` are 404
- [ ] `/settings` page has no Admin section (only Personal + Custom Instructions)
- [ ] 586+ backend tests pass, TypeScript strict 0 errors
