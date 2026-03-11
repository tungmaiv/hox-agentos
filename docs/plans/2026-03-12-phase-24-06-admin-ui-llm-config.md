# Phase 24-06: Admin UI & LLM Config Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate the admin dashboard from 13 scattered tabs into 4 grouped tabs (Registry / Access / System / Build); add LLM provider management UI with full add/remove/key-rotation and alias remapping; providers hot-reload into LiteLLM proxy without container restart.

**Architecture:** Admin layout.tsx is restructured with 4 top-level tabs, each with sub-navigation. Registry tab uses `ArtifactCardGrid` backed by `/api/registry`. New `LlmProviderPanel` component manages provider CRUD. Backend `platform_config` table stores encrypted provider configs; new `/api/admin/llm-providers` routes call LiteLLM proxy admin API on save.

**Tech Stack:** Next.js 15 App Router, TypeScript strict, Tailwind, SWR for client-side fetching in `"use client"` components. Backend: FastAPI, SQLAlchemy async, AES-256 encryption (same as credentials).

**Depends on:** Phase 24-02 (registry CRUD routes must exist).

---

## Task 1: Restructure Admin Layout to 4 Tabs

**Files:**
- Modify: `frontend/src/app/(authenticated)/admin/layout.tsx`

**Step 1: Rewrite `ADMIN_TABS` to 4 groups**

The current layout has 13 flat tabs. Replace with 4 top-level tabs. Each tab is a URL prefix; sub-pages under it handle specific entity types.

```tsx
// Replace ADMIN_TABS in layout.tsx:
const ADMIN_TABS = [
  { label: "Registry",  href: "/admin/registry" },
  { label: "Access",    href: "/admin/access" },
  { label: "System",    href: "/admin/system" },
  { label: "Build",     href: "/admin/build" },
] as const;
```

Keep the existing tab rendering logic (the `<Link>` map) unchanged — just the data changes.

**Step 2: Create redirect pages for old URLs**

Old admin URLs must redirect to new locations so existing bookmarks don't 404:

```
/admin/agents       → /admin/registry?type=agent
/admin/skills       → /admin/registry?type=skill
/admin/tools        → /admin/registry?type=tool
/admin/mcp-servers  → /admin/registry?type=mcp_server
/admin/permissions  → /admin/access
/admin/identity     → /admin/system
/admin/config       → /admin/system
/admin/memory       → /admin/system
/admin/credentials  → /admin/access
/admin/users        → /admin/access
/admin/skill-store  → /admin/build
/admin/create       → /admin/build
/admin/builder      → /admin/build
```

For each old page file that exists, replace its content with a redirect:

```tsx
// Example: frontend/src/app/(authenticated)/admin/agents/page.tsx
import { redirect } from "next/navigation";
export default function AgentsPage() {
  redirect("/admin/registry?type=agent");
}
```

**Step 3: Verify TypeScript compiles**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
```

**Step 4: Commit**

```bash
git commit -m "feat(24-06): restructure admin to 4-tab layout with redirects"
```

---

## Task 2: Registry Tab Page

**Files:**
- Create: `frontend/src/app/(authenticated)/admin/registry/page.tsx`

**Step 1: Create the page**

```tsx
// frontend/src/app/(authenticated)/admin/registry/page.tsx
"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";

const ENTITY_TYPES = [
  { value: "agent",      label: "Agents" },
  { value: "skill",      label: "Skills" },
  { value: "tool",       label: "Tools" },
  { value: "mcp_server", label: "MCP Servers" },
  { value: "policy",     label: "Policies" },
];

async function fetcher(url: string) {
  const resp = await fetch(url, { credentials: "include" });
  if (!resp.ok) throw new Error("Failed to fetch");
  return resp.json();
}

export default function RegistryPage() {
  const searchParams = useSearchParams();
  const initialType = searchParams.get("type") ?? "skill";
  const [selectedType, setSelectedType] = useState(initialType);

  const { data, isLoading, mutate } = useSWR(
    `/api/backend/registry?type=${selectedType}`,
    fetcher
  );

  const items: unknown[] = data?.items ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Registry</h2>
        <button
          className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700"
          onClick={() => {/* TODO: open create modal */}}
        >
          + New Entry
        </button>
      </div>

      {/* Type filter tabs */}
      <div className="flex gap-2 mb-4 border-b border-gray-200">
        {ENTITY_TYPES.map((t) => (
          <button
            key={t.value}
            onClick={() => setSelectedType(t.value)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              selectedType === t.value
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Entry list */}
      {isLoading ? (
        <p className="text-gray-400 text-sm">Loading...</p>
      ) : (
        <div className="grid gap-3">
          {(items as Array<{id: string; name: string; status: string; description?: string}>).map((entry) => (
            <div
              key={entry.id}
              className="bg-white border border-gray-200 rounded-lg p-4 flex items-center justify-between"
            >
              <div>
                <p className="font-medium text-gray-900">{entry.name}</p>
                {entry.description && (
                  <p className="text-sm text-gray-500 mt-0.5">{entry.description}</p>
                )}
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${
                    entry.status === "active"
                      ? "bg-green-100 text-green-700"
                      : entry.status === "pending_review"
                      ? "bg-yellow-100 text-yellow-700"
                      : "bg-gray-100 text-gray-500"
                  }`}
                >
                  {entry.status}
                </span>
                <button
                  className="text-sm text-red-500 hover:text-red-700"
                  onClick={async () => {
                    await fetch(`/api/backend/registry/${entry.id}`, {
                      method: "DELETE",
                      credentials: "include",
                    });
                    mutate();
                  }}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
          {items.length === 0 && (
            <p className="text-gray-400 text-sm text-center py-8">
              No {selectedType} entries found.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
```

**Step 2: Add a Next.js API proxy for registry**

The frontend needs to proxy `/api/backend/registry` to `http://backend:8000/api/registry`.

Create: `frontend/src/app/api/backend/registry/route.ts`

```ts
// frontend/src/app/api/backend/registry/route.ts
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://backend:8000";

async function handler(req: NextRequest) {
  const session = await auth();
  const token = (session as unknown as Record<string, unknown>)?.accessToken as string | undefined;
  if (!token) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const url = `${BACKEND_URL}/api/registry${req.nextUrl.search}`;
  const resp = await fetch(url, {
    method: req.method,
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: req.method !== "GET" && req.method !== "DELETE"
      ? await req.text()
      : undefined,
  });

  const body = await resp.text();
  return new NextResponse(body, {
    status: resp.status,
    headers: { "Content-Type": resp.headers.get("Content-Type") ?? "application/json" },
  });
}

export { handler as GET, handler as POST };
```

Also create the `[id]` route:

```ts
// frontend/src/app/api/backend/registry/[id]/route.ts
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://backend:8000";

async function handler(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const session = await auth();
  const token = (session as unknown as Record<string, unknown>)?.accessToken as string | undefined;
  if (!token) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const resp = await fetch(`${BACKEND_URL}/api/registry/${id}`, {
    method: req.method,
    headers: { "Authorization": `Bearer ${token}` },
  });

  if (resp.status === 204) return new NextResponse(null, { status: 204 });
  const body = await resp.text();
  return new NextResponse(body, { status: resp.status });
}

export { handler as GET, handler as PUT, handler as DELETE };
```

**Step 3: Type check**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
```

**Step 4: Commit**

```bash
git commit -m "feat(24-06): add Registry tab page with unified entity CRUD"
```

---

## Task 3: Backend LLM Provider Routes

**Files:**
- Create: `backend/api/routes/admin_llm_providers.py`
- Modify: `backend/main.py`

**Step 1: Write failing tests first**

```python
# backend/tests/api/test_admin_llm_providers.py
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_providers_requires_admin(async_client: AsyncClient):
    resp = await async_client.get("/api/admin/llm-providers")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_provider(async_client: AsyncClient, admin_token: str):
    payload = {
        "name": "test-anthropic",
        "provider_type": "anthropic",
        "base_url": "https://api.anthropic.com",
        "api_key": "sk-test-key",
    }
    resp = await async_client.post(
        "/api/admin/llm-providers",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-anthropic"
    assert "api_key" not in data  # key never returned
    assert data["has_key"] is True


@pytest.mark.asyncio
async def test_delete_provider(async_client: AsyncClient, admin_token: str):
    # Create first
    create_resp = await async_client.post(
        "/api/admin/llm-providers",
        json={"name": "to-delete", "provider_type": "openai"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    pid = create_resp.json()["id"]
    del_resp = await async_client.delete(
        f"/api/admin/llm-providers/{pid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert del_resp.status_code == 204
```

**Step 2: Run tests to confirm they fail**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/api/test_admin_llm_providers.py -v 2>&1 | tail -10
```

**Step 3: Implement the routes**

```python
# backend/api/routes/admin_llm_providers.py
"""
LLM Provider management routes.

Stores provider configs (name, type, base_url, encrypted_api_key) in
platform_config table. On save/delete, calls LiteLLM proxy admin API
to hot-reload routing config without container restart.
"""
import uuid
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.db import get_session
from core.models.platform_config import PlatformConfig
from security.deps import require_permission
from security.acl import encrypt_value, decrypt_value  # AES-256 helpers

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/admin/llm-providers", tags=["admin-llm"])

LITELLM_URL = "http://litellm:4000"
_PROVIDER_KEY_PREFIX = "llm_provider:"
_ALIAS_KEY_PREFIX = "llm_alias:"


class LlmProviderCreate(BaseModel):
    name: str
    provider_type: str  # anthropic | openai | ollama | openrouter | custom
    base_url: str | None = None
    api_key: str | None = None


class LlmProviderOut(BaseModel):
    id: str
    name: str
    provider_type: str
    base_url: str | None
    has_key: bool
    is_reachable: bool = False


class AliasUpdate(BaseModel):
    alias: str    # blitz/master | blitz/fast | blitz/coder | blitz/summarizer
    provider_name: str
    model_name: str


@router.get("")
async def list_providers(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:admin")),
) -> list[LlmProviderOut]:
    result = await session.execute(
        select(PlatformConfig).where(
            PlatformConfig.key.like(f"{_PROVIDER_KEY_PREFIX}%")
        )
    )
    rows = result.scalars().all()
    return [_row_to_out(r) for r in rows]


@router.post("", status_code=201)
async def create_provider(
    body: LlmProviderCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:admin")),
) -> LlmProviderOut:
    config_value: dict[str, Any] = {
        "provider_type": body.provider_type,
        "base_url": body.base_url,
    }
    if body.api_key:
        config_value["encrypted_key"] = encrypt_value(body.api_key)

    key = f"{_PROVIDER_KEY_PREFIX}{body.name}"
    # Upsert in platform_config
    existing = await session.execute(
        select(PlatformConfig).where(PlatformConfig.key == key)
    )
    row = existing.scalar_one_or_none()
    if row:
        row.value = str(config_value)
    else:
        row = PlatformConfig(key=key, value=str(config_value))
        session.add(row)

    await session.commit()
    await session.refresh(row)
    await _reload_litellm(session)
    return _row_to_out(row)


@router.delete("/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: str,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:admin")),
) -> None:
    # provider_id is the provider name here (used as the config key suffix)
    key = f"{_PROVIDER_KEY_PREFIX}{provider_id}"
    result = await session.execute(
        select(PlatformConfig).where(PlatformConfig.key == key)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Provider not found")
    await session.delete(row)
    await session.commit()
    await _reload_litellm(session)


@router.put("/aliases")
async def update_alias(
    body: AliasUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:admin")),
) -> dict:
    """Remap a blitz/* model alias to a different provider+model."""
    key = f"{_ALIAS_KEY_PREFIX}{body.alias}"
    value = f"{body.provider_name}/{body.model_name}"

    existing = await session.execute(
        select(PlatformConfig).where(PlatformConfig.key == key)
    )
    row = existing.scalar_one_or_none()
    if row:
        row.value = value
    else:
        row = PlatformConfig(key=key, value=value)
        session.add(row)
    await session.commit()
    await _reload_litellm(session)
    return {"alias": body.alias, "mapped_to": value}


@router.post("/{provider_name}/test")
async def test_provider(
    provider_name: str,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("system:admin")),
) -> dict:
    """Test connectivity to a provider via LiteLLM."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{LITELLM_URL}/health")
            if resp.status_code == 200:
                return {"ok": True, "message": "LiteLLM proxy reachable"}
            return {"ok": False, "message": f"LiteLLM returned {resp.status_code}"}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}


async def _reload_litellm(session: AsyncSession) -> None:
    """Trigger LiteLLM hot-reload via its admin API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{LITELLM_URL}/config/update",
                headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
                json={},
            )
        logger.info("litellm_config_reloaded")
    except Exception as exc:
        logger.warning("litellm_reload_failed", error=str(exc))


def _row_to_out(row: PlatformConfig) -> LlmProviderOut:
    import ast
    try:
        config = ast.literal_eval(row.value)
    except Exception:
        config = {}
    name = row.key.removeprefix(_PROVIDER_KEY_PREFIX)
    return LlmProviderOut(
        id=name,
        name=name,
        provider_type=config.get("provider_type", "custom"),
        base_url=config.get("base_url"),
        has_key="encrypted_key" in config,
    )
```

**Step 4: Register router in `main.py`**

```python
from api.routes.admin_llm_providers import router as admin_llm_providers_router
app.include_router(admin_llm_providers_router)
```

Also add `system:admin` to RBAC in `backend/security/rbac.py`.

**Step 5: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/api/test_admin_llm_providers.py -v
```

**Step 6: Commit**

```bash
git add backend/api/routes/admin_llm_providers.py backend/main.py backend/security/rbac.py \
        backend/tests/api/test_admin_llm_providers.py
git commit -m "feat(24-06): add LLM provider management API routes"
```

---

## Task 4: LLM Providers UI (System Tab)

**Files:**
- Create: `frontend/src/app/(authenticated)/admin/system/page.tsx`
- Create: `frontend/src/app/api/backend/llm-providers/route.ts`

**Step 1: Create the system page**

```tsx
// frontend/src/app/(authenticated)/admin/system/page.tsx
"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";

const SUB_TABS = ["LLM Providers", "Identity", "Config", "Memory"] as const;
type SubTab = (typeof SUB_TABS)[number];

async function fetcher(url: string) {
  const resp = await fetch(url, { credentials: "include" });
  if (!resp.ok) throw new Error("Failed");
  return resp.json();
}

function LlmProvidersPanel() {
  const { data, isLoading } = useSWR("/api/backend/llm-providers", fetcher);
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState("anthropic");
  const [newKey, setNewKey] = useState("");
  const [adding, setAdding] = useState(false);

  const providers: Array<{id: string; name: string; provider_type: string; has_key: boolean}> = data ?? [];

  async function addProvider() {
    setAdding(true);
    await fetch("/api/backend/llm-providers", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName, provider_type: newType, api_key: newKey || undefined }),
    });
    setNewName(""); setNewKey(""); setAdding(false);
    mutate("/api/backend/llm-providers");
  }

  async function deleteProvider(id: string) {
    await fetch(`/api/backend/llm-providers/${id}`, { method: "DELETE", credentials: "include" });
    mutate("/api/backend/llm-providers");
  }

  return (
    <div>
      <h3 className="font-medium text-gray-900 mb-4">LLM Providers</h3>

      {/* Existing providers */}
      <div className="space-y-2 mb-6">
        {isLoading && <p className="text-sm text-gray-400">Loading...</p>}
        {providers.map((p) => (
          <div key={p.id} className="flex items-center justify-between bg-white border border-gray-200 rounded-lg p-3">
            <div>
              <span className="font-medium text-sm">{p.name}</span>
              <span className="ml-2 text-xs text-gray-500">{p.provider_type}</span>
              {p.has_key && <span className="ml-2 text-xs text-green-600">● key set</span>}
            </div>
            <button
              onClick={() => deleteProvider(p.id)}
              className="text-xs text-red-500 hover:text-red-700"
            >
              Remove
            </button>
          </div>
        ))}
      </div>

      {/* Add provider form */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <h4 className="text-sm font-medium text-gray-700 mb-3">Add Provider</h4>
        <div className="grid grid-cols-3 gap-2 mb-2">
          <input
            placeholder="Provider name (e.g. my-anthropic)"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="col-span-1 text-sm border border-gray-300 rounded px-2 py-1.5"
          />
          <select
            value={newType}
            onChange={(e) => setNewType(e.target.value)}
            className="col-span-1 text-sm border border-gray-300 rounded px-2 py-1.5"
          >
            <option value="anthropic">Anthropic</option>
            <option value="openai">OpenAI</option>
            <option value="ollama">Ollama</option>
            <option value="openrouter">OpenRouter</option>
            <option value="custom">Custom</option>
          </select>
          <input
            type="password"
            placeholder="API key (optional)"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            className="col-span-1 text-sm border border-gray-300 rounded px-2 py-1.5"
          />
        </div>
        <button
          onClick={addProvider}
          disabled={!newName || adding}
          className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {adding ? "Adding..." : "Add Provider"}
        </button>
      </div>
    </div>
  );
}

export default function SystemPage() {
  const [activeTab, setActiveTab] = useState<SubTab>("LLM Providers");

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">System</h2>

      {/* Sub-tabs */}
      <div className="flex gap-2 border-b border-gray-200 mb-6">
        {SUB_TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === "LLM Providers" && <LlmProvidersPanel />}
      {activeTab === "Identity" && <p className="text-sm text-gray-400">Identity config (from /admin/identity)</p>}
      {activeTab === "Config" && <p className="text-sm text-gray-400">System config (from /admin/config)</p>}
      {activeTab === "Memory" && <p className="text-sm text-gray-400">Memory settings (from /admin/memory)</p>}
    </div>
  );
}
```

**Step 2: Create LLM providers proxy route**

```ts
// frontend/src/app/api/backend/llm-providers/route.ts
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://backend:8000";

async function handler(req: NextRequest) {
  const session = await auth();
  const token = (session as unknown as Record<string, unknown>)?.accessToken as string | undefined;
  if (!token) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const resp = await fetch(`${BACKEND_URL}/api/admin/llm-providers`, {
    method: req.method,
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: req.method === "POST" ? await req.text() : undefined,
  });

  const body = await resp.text();
  return new NextResponse(body, { status: resp.status });
}

export { handler as GET, handler as POST };
```

Also create: `frontend/src/app/api/backend/llm-providers/[id]/route.ts`

```ts
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://backend:8000";

async function handler(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const session = await auth();
  const token = (session as unknown as Record<string, unknown>)?.accessToken as string | undefined;
  if (!token) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const resp = await fetch(`${BACKEND_URL}/api/admin/llm-providers/${id}`, {
    method: req.method,
    headers: { "Authorization": `Bearer ${token}` },
  });

  if (resp.status === 204) return new NextResponse(null, { status: 204 });
  return new NextResponse(await resp.text(), { status: resp.status });
}

export { handler as DELETE };
```

**Step 3: Verify TypeScript**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
```

**Step 4: Commit**

```bash
git add frontend/src/app/\(authenticated\)/admin/system/ \
        frontend/src/app/api/backend/llm-providers/
git commit -m "feat(24-06): add System tab with LLM provider management UI"
```

---

## Task 5: Create Access and Build Tab Stubs

**Files:**
- Create: `frontend/src/app/(authenticated)/admin/access/page.tsx`
- Create: `frontend/src/app/(authenticated)/admin/build/page.tsx`

**Step 1: Access page — links to sub-sections**

```tsx
// frontend/src/app/(authenticated)/admin/access/page.tsx
import Link from "next/link";

const ACCESS_LINKS = [
  { label: "Users",       href: "/admin/users",       desc: "Manage local users and roles" },
  { label: "Permissions", href: "/admin/permissions",  desc: "Tool ACL and role permissions" },
  { label: "Credentials", href: "/admin/credentials",  desc: "OAuth and API credentials" },
];

export default function AccessPage() {
  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Access</h2>
      <div className="grid gap-3 max-w-lg">
        {ACCESS_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="block bg-white border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:shadow-sm transition-all"
          >
            <p className="font-medium text-gray-900">{link.label}</p>
            <p className="text-sm text-gray-500 mt-0.5">{link.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
```

**Step 2: Build page**

```tsx
// frontend/src/app/(authenticated)/admin/build/page.tsx
import Link from "next/link";

const BUILD_LINKS = [
  { label: "AI Builder",   href: "/admin/create",      desc: "Create skills with AI assistance" },
  { label: "Builder+",     href: "/admin/builder",      desc: "Advanced skill builder with security gate" },
  { label: "Skill Store",  href: "/admin/skill-store",  desc: "Browse and import external skills" },
];

export default function BuildPage() {
  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Build</h2>
      <div className="grid gap-3 max-w-lg">
        {BUILD_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="block bg-white border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:shadow-sm transition-all"
          >
            <p className="font-medium text-gray-900">{link.label}</p>
            <p className="text-sm text-gray-500 mt-0.5">{link.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
```

**Step 3: Verify TypeScript**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
```

**Step 4: Commit**

```bash
git add frontend/src/app/\(authenticated\)/admin/access/ \
        frontend/src/app/\(authenticated\)/admin/build/
git commit -m "feat(24-06): add Access and Build tab stub pages"
```

---

## Completion Check

```bash
# Backend tests pass
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q

# Frontend TypeScript clean
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit

# Admin layout renders at /admin (spot-check in browser or curl)
curl -s http://localhost:3000/admin | grep -i "registry\|access\|system\|build"
```
