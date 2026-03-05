# Phase 16: Navigation & User Experience — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a persistent navigation rail to all authenticated pages, create a profile page with account info and LLM preferences, and restructure the frontend route hierarchy.

**Architecture:** Next.js `(authenticated)` route group wraps all auth'd pages with a shared layout containing `NavRail` (desktop) + `MobileTabBar` (mobile). Backend extends existing `/api/user/preferences` endpoint with new `user_preferences` table to store `thinking_mode`, `response_style`, and `rendering_mode`. Agent reads preferences at conversation start.

**Tech Stack:** Next.js 15 App Router, Tailwind CSS v4, lucide-react (new dep), FastAPI, SQLAlchemy async, Alembic, Pydantic v2

**Design doc:** `docs/plans/2026-03-05-navigation-ux-design.md`

---

## Task 1: Backend — UserPreference model + Alembic migration

**Files:**
- Create: `backend/core/models/user_preference.py`
- Modify: `backend/core/models/__init__.py`
- Create: `backend/alembic/versions/020_user_preferences.py`

**Step 1: Create the ORM model**

Create `backend/core/models/user_preference.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, index=True
    )
    rendering_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="markdown"
    )
    thinking_mode: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    response_style: Mapped[str] = mapped_column(
        String(20), nullable=False, default="concise"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
```

**Step 2: Register the model in `__init__.py`**

Add to `backend/core/models/__init__.py` after the `user_instructions` import:

```python
from core.models.user_preference import UserPreference  # noqa: F401
```

**Step 3: Create Alembic migration**

Create `backend/alembic/versions/020_user_preferences.py`:

```python
"""user_preferences table

Revision ID: 020
Revises: 019
Create Date: 2026-03-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rendering_mode", sa.String(20), nullable=False, server_default="markdown"),
        sa.Column("thinking_mode", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("response_style", sa.String(20), nullable=False, server_default="concise"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_user_preferences_user_id")
    op.drop_table("user_preferences")
```

**Step 4: Verify migration file is valid**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && .venv/bin/alembic heads`
Expected: `020 (head)`

**Step 5: Commit**

```bash
git add backend/core/models/user_preference.py backend/core/models/__init__.py backend/alembic/versions/020_user_preferences.py
git commit -m "feat(16-01): add UserPreference model and migration 020"
```

---

## Task 2: Backend — Update preferences endpoint + tests

Extends the existing `GET/PUT /api/user/preferences` endpoint in `memory_settings.py` to use the new `user_preferences` table (replacing `system_config` storage) and add `thinking_mode` + `response_style` fields. Also exports a `get_user_preferences()` helper for the agent.

**Files:**
- Modify: `backend/api/routes/memory_settings.py` (lines 166-225)
- Create: `backend/tests/api/test_user_preferences.py`

**Step 1: Write the failing tests**

Create `backend/tests/api/test_user_preferences.py`:

```python
"""Tests for GET/PUT /api/user/preferences — user preferences endpoint."""
import asyncio
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from core.db import Base, get_db
from core.models.user import UserContext
from core.models.user_preference import UserPreference  # noqa: F401 — DDL
from main import app
from security.deps import get_current_user

_USER_ID = uuid4()


def _make_user() -> UserContext:
    return UserContext(
        user_id=_USER_ID,
        email="test@blitz.local",
        username="testuser",
        roles=["employee"],
        groups=[],
    )


@pytest.fixture()
def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_setup())

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_current_user] = _make_user
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)
    loop.run_until_complete(engine.dispose())
    loop.close()


def test_get_preferences_returns_defaults(client: TestClient) -> None:
    """GET returns default values when no preferences exist."""
    resp = client.get("/api/user/preferences")
    assert resp.status_code == 200
    data = resp.json()
    assert data["rendering_mode"] == "markdown"
    assert data["thinking_mode"] is False
    assert data["response_style"] == "concise"


def test_put_preferences_creates_row(client: TestClient) -> None:
    """PUT creates preferences when none exist (upsert)."""
    resp = client.put(
        "/api/user/preferences",
        json={"thinking_mode": True, "response_style": "detailed"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["thinking_mode"] is True
    assert data["response_style"] == "detailed"
    assert data["rendering_mode"] == "markdown"  # default preserved


def test_put_preferences_updates_existing(client: TestClient) -> None:
    """PUT updates only provided fields (partial update)."""
    # Create initial preferences
    client.put(
        "/api/user/preferences",
        json={"thinking_mode": True, "response_style": "detailed"},
    )
    # Update only rendering_mode
    resp = client.put(
        "/api/user/preferences",
        json={"rendering_mode": "card_wrapped"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rendering_mode"] == "card_wrapped"
    assert data["thinking_mode"] is True  # preserved from first PUT
    assert data["response_style"] == "detailed"  # preserved from first PUT


def test_put_preferences_validates_response_style(client: TestClient) -> None:
    """PUT rejects invalid response_style values."""
    resp = client.put(
        "/api/user/preferences",
        json={"response_style": "invalid_value"},
    )
    assert resp.status_code == 422


def test_get_preferences_after_put(client: TestClient) -> None:
    """GET reflects previously saved preferences."""
    client.put(
        "/api/user/preferences",
        json={"thinking_mode": True, "response_style": "conversational", "rendering_mode": "inline_chips"},
    )
    resp = client.get("/api/user/preferences")
    assert resp.status_code == 200
    data = resp.json()
    assert data["thinking_mode"] is True
    assert data["response_style"] == "conversational"
    assert data["rendering_mode"] == "inline_chips"
```

**Step 2: Run the tests — verify they fail**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/api/test_user_preferences.py -v`
Expected: FAIL — the endpoint still returns the old `ChatPreferences` schema (no `thinking_mode`/`response_style` fields)

**Step 3: Update the preferences endpoint in `memory_settings.py`**

Replace lines 166-225 of `backend/api/routes/memory_settings.py` (the entire "Chat Preferences" section) with:

```python
# ---------------------------------------------------------------------------
# User Preferences — stored in user_preferences table
# ---------------------------------------------------------------------------

from typing import Literal

from core.models.user_preference import UserPreference


class UserPreferencesResponse(BaseModel):
    rendering_mode: str
    thinking_mode: bool
    response_style: str

    model_config = {"from_attributes": True}


class UserPreferencesUpdate(BaseModel):
    rendering_mode: Literal["markdown", "card_wrapped", "inline_chips"] | None = None
    thinking_mode: bool | None = None
    response_style: Literal["concise", "detailed", "conversational"] | None = None


async def get_user_preferences(
    user_id: UUID,
    session: AsyncSession,
) -> UserPreferencesResponse:
    """
    Get preferences for a user_id (internal helper for agents).

    Returns defaults if no preferences row exists.
    """
    result = await session.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return UserPreferencesResponse(
            rendering_mode="markdown",
            thinking_mode=False,
            response_style="concise",
        )
    return UserPreferencesResponse.model_validate(row)


@router.get("/preferences")
async def get_preferences(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> UserPreferencesResponse:
    """
    Get all user preferences (rendering, thinking, response style).
    Returns defaults if no preferences stored yet.
    """
    return await get_user_preferences(user["user_id"], session)


@router.put("/preferences")
async def update_preferences(
    body: UserPreferencesUpdate,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> UserPreferencesResponse:
    """
    Update user preferences (partial update — only provided fields change).
    Uses upsert: creates row if missing, updates if present.
    """
    result = await session.execute(
        select(UserPreference).where(UserPreference.user_id == user["user_id"])
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = UserPreference(user_id=user["user_id"])
        if body.rendering_mode is not None:
            row.rendering_mode = body.rendering_mode
        if body.thinking_mode is not None:
            row.thinking_mode = body.thinking_mode
        if body.response_style is not None:
            row.response_style = body.response_style
        session.add(row)
    else:
        if body.rendering_mode is not None:
            row.rendering_mode = body.rendering_mode
        if body.thinking_mode is not None:
            row.thinking_mode = body.thinking_mode
        if body.response_style is not None:
            row.response_style = body.response_style

    await session.commit()
    await session.refresh(row)
    logger.info(
        "preferences_updated",
        user_id=str(user["user_id"]),
        rendering_mode=row.rendering_mode,
        thinking_mode=row.thinking_mode,
        response_style=row.response_style,
    )
    return UserPreferencesResponse.model_validate(row)
```

Remove the old `ChatPreferences` class, old imports (`from core.models.system_config import SystemConfig`), and the old endpoint implementations that used `system_config`.

**Step 4: Run the tests — verify they pass**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/api/test_user_preferences.py -v`
Expected: All 5 tests PASS

**Step 5: Run the full test suite to verify no regressions**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q`
Expected: All tests pass (any failures in pre-existing tests are not from this change)

**Step 6: Commit**

```bash
git add backend/api/routes/memory_settings.py backend/tests/api/test_user_preferences.py
git commit -m "feat(16-02): extend preferences endpoint with thinking_mode and response_style"
```

---

## Task 3: Backend — Self-service password change endpoint + tests

Adds `PUT /api/auth/local/change-password` so local-auth users can change their own password from the profile page. SSO users don't use this (password managed by Keycloak).

**Files:**
- Modify: `backend/api/routes/auth_local.py`
- Create: `backend/tests/api/test_password_change.py`

**Step 1: Write the failing test**

Create `backend/tests/api/test_password_change.py`:

```python
"""Tests for PUT /api/auth/local/change-password — user self-service password change."""
import asyncio
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from core.db import Base, get_db
from core.models.local_auth import LocalUser  # noqa: F401 — DDL
from core.models.user import UserContext
from main import app
from security.deps import get_current_user
from security.local_auth import hash_password

_USER_ID = uuid4()


def _make_user() -> UserContext:
    return UserContext(
        user_id=_USER_ID,
        email="local@blitz.local",
        username="localuser",
        roles=["employee"],
        groups=[],
    )


@pytest.fixture()
def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # Seed a local user
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            user = LocalUser(
                id=_USER_ID,
                username="localuser",
                email="local@blitz.local",
                password_hash=hash_password("OldPass123!"),
                is_active=True,
            )
            session.add(user)
            await session.commit()

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_setup())

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_current_user] = _make_user
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)
    loop.run_until_complete(engine.dispose())
    loop.close()


def test_change_password_success(client: TestClient) -> None:
    resp = client.put(
        "/api/auth/local/change-password",
        json={"current_password": "OldPass123!", "new_password": "NewPass456!"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_change_password_wrong_current(client: TestClient) -> None:
    resp = client.put(
        "/api/auth/local/change-password",
        json={"current_password": "WrongPassword", "new_password": "NewPass456!"},
    )
    assert resp.status_code == 401


def test_change_password_no_local_user(client: TestClient) -> None:
    """SSO user (no LocalUser row) gets 404."""
    sso_id = uuid4()

    def _make_sso_user() -> UserContext:
        return UserContext(
            user_id=sso_id,
            email="sso@blitz.local",
            username="ssouser",
            roles=["employee"],
            groups=[],
        )

    app.dependency_overrides[get_current_user] = _make_sso_user
    resp = client.put(
        "/api/auth/local/change-password",
        json={"current_password": "any", "new_password": "NewPass456!"},
    )
    assert resp.status_code == 404
```

**Step 2: Run tests — verify they fail**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/api/test_password_change.py -v`
Expected: FAIL — endpoint doesn't exist yet (404 for all)

**Step 3: Add the password change endpoint to `auth_local.py`**

Add to `backend/api/routes/auth_local.py` after the `local_login` function:

```python
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


@router.put("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Change password for the authenticated local user.

    Verifies current password before updating. Returns 404 for SSO users
    (no LocalUser row). Returns 401 if current password is wrong.
    """
    result = await session.execute(
        select(LocalUser).where(LocalUser.id == user["user_id"])
    )
    local_user = result.scalar_one_or_none()
    if local_user is None:
        raise HTTPException(status_code=404, detail="No local account found")

    if not verify_password(body.current_password, local_user.password_hash):
        logger.info("password_change_failed", user_id=str(user["user_id"]), reason="wrong_current")
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    local_user.password_hash = hash_password(body.new_password)
    await session.commit()
    logger.info("password_changed", user_id=str(user["user_id"]))
    return {"status": "ok"}
```

Add these imports at the top of `auth_local.py` (some already exist):

```python
from pydantic import BaseModel, Field
from core.models.user import UserContext
from security.deps import get_current_user
from security.local_auth import hash_password  # add hash_password to existing import
```

**Step 4: Run tests — verify they pass**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/api/test_password_change.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add backend/api/routes/auth_local.py backend/tests/api/test_password_change.py
git commit -m "feat(16-03): add self-service password change endpoint for local auth users"
```

---

## Task 4: Backend — Agent preferences integration

Modifies `_master_node()` in `master_agent.py` to load user preferences and inject response style/thinking directives into the system prompt.

**Files:**
- Modify: `backend/agents/master_agent.py`

**Step 1: Add preference import**

Add to imports in `backend/agents/master_agent.py` (near line 40, alongside the `user_instructions` import):

```python
from api.routes.memory_settings import get_user_preferences
```

**Step 2: Load preferences and inject into system prompt**

In `_master_node()`, after the `custom_instructions` loading block (around line 218, inside the `try` block that already has `async with async_session() as session`), add:

```python
                # Load user preferences for response style/thinking
                prefs = await get_user_preferences(user["user_id"], session)
```

Then after the custom instructions append (around line 253, after the `if custom_instructions:` block), add:

```python
    # Inject preference directives
    if prefs is not None:
        if prefs.thinking_mode:
            system_content += "\n\nThink step-by-step: show your reasoning process before giving the final answer."
        match prefs.response_style:
            case "detailed":
                system_content += "\n\nProvide thorough, detailed responses with examples and explanations."
            case "conversational":
                system_content += "\n\nRespond in a casual, conversational tone. Keep it friendly and natural."
            # "concise" is default — no extra directive
```

Initialize `prefs` to `None` alongside `custom_instructions = ""` (around line 211):

```python
    custom_instructions = ""
    prefs = None
    user_context_str = ""
```

**Step 3: Run the full test suite**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q`
Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/agents/master_agent.py
git commit -m "feat(16-04): inject user preferences (thinking mode, response style) into agent system prompt"
```

---

## Task 5: Frontend — Install lucide-react + create NavRail + MobileTabBar

**Files:**
- Create: `frontend/src/components/nav/nav-rail.tsx`
- Create: `frontend/src/components/nav/mobile-tab-bar.tsx`

**Step 1: Install lucide-react**

Run: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm add lucide-react`

**Step 2: Create the NavRail component**

Create `frontend/src/components/nav/nav-rail.tsx`:

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import {
  MessageSquare,
  GitBranch,
  Zap,
  Shield,
  Settings,
  User,
} from "lucide-react";

const ADMIN_ROLES = ["admin", "developer", "it-admin"];

interface NavItem {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  adminOnly?: boolean;
}

const TOP_ITEMS: NavItem[] = [
  { href: "/chat", icon: MessageSquare, label: "Chat" },
  { href: "/workflows", icon: GitBranch, label: "Workflows" },
  { href: "/skills", icon: Zap, label: "Skills" },
];

const BOTTOM_ITEMS: NavItem[] = [
  { href: "/admin", icon: Shield, label: "Admin", adminOnly: true },
  { href: "/settings", icon: Settings, label: "Settings" },
  { href: "/profile", icon: User, label: "Profile" },
];

function NavIcon({
  item,
  isActive,
}: {
  item: NavItem;
  isActive: boolean;
}) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      title={item.label}
      className={`relative flex items-center justify-center w-12 h-12 rounded-lg transition-colors group
        ${isActive ? "text-blue-600 bg-blue-50" : "text-gray-500 hover:text-gray-900 hover:bg-gray-100"}`}
    >
      {isActive && (
        <span className="absolute left-0 top-2 bottom-2 w-0.5 rounded-r bg-blue-600" />
      )}
      <Icon className="w-5 h-5" />
      {/* Tooltip */}
      <span className="absolute left-full ml-2 px-2 py-1 text-xs font-medium text-white bg-gray-900 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
        {item.label}
      </span>
    </Link>
  );
}

export function NavRail({ className }: { className?: string }) {
  const pathname = usePathname();
  const { data: session } = useSession();
  const roles = (session as unknown as Record<string, unknown>)?.realmRoles as string[] ?? [];
  const isAdmin = roles.some((r) => ADMIN_ROLES.includes(r));

  function isActive(href: string): boolean {
    if (href === "/chat") return pathname === "/chat" || pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <nav
      className={`flex flex-col items-center w-16 bg-white border-r border-gray-200 py-4 ${className ?? ""}`}
    >
      {/* Logo */}
      <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-blue-600 text-white font-bold text-lg mb-6">
        B
      </div>

      {/* Top group */}
      <div className="flex flex-col items-center gap-1">
        {TOP_ITEMS.map((item) => (
          <NavIcon key={item.href} item={item} isActive={isActive(item.href)} />
        ))}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Bottom group */}
      <div className="flex flex-col items-center gap-1">
        {BOTTOM_ITEMS.filter((item) => !item.adminOnly || isAdmin).map((item) => (
          <NavIcon key={item.href} item={item} isActive={isActive(item.href)} />
        ))}
      </div>
    </nav>
  );
}
```

**Step 3: Create the MobileTabBar component**

Create `frontend/src/components/nav/mobile-tab-bar.tsx`:

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  MessageSquare,
  GitBranch,
  Zap,
  Settings,
  User,
} from "lucide-react";

interface TabItem {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}

const TABS: TabItem[] = [
  { href: "/chat", icon: MessageSquare, label: "Chat" },
  { href: "/workflows", icon: GitBranch, label: "Workflows" },
  { href: "/skills", icon: Zap, label: "Skills" },
  { href: "/settings", icon: Settings, label: "Settings" },
  { href: "/profile", icon: User, label: "Profile" },
];

export function MobileTabBar({ className }: { className?: string }) {
  const pathname = usePathname();

  function isActive(href: string): boolean {
    if (href === "/chat") return pathname === "/chat" || pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <nav
      className={`fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-40 ${className ?? ""}`}
    >
      <div className="flex items-center justify-around h-14">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const active = isActive(tab.href);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`flex flex-col items-center justify-center gap-0.5 flex-1 h-full transition-colors
                ${active ? "text-blue-600" : "text-gray-400"}`}
            >
              <Icon className="w-5 h-5" />
              <span className="text-[10px] font-medium">{tab.label}</span>
              {active && (
                <span className="absolute bottom-0 w-8 h-0.5 rounded-t bg-blue-600" />
              )}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
```

**Step 4: Commit**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/src/components/nav/
git commit -m "feat(16-05): add NavRail and MobileTabBar components with lucide-react icons"
```

---

## Task 6: Frontend — Route group restructure + authenticated layout

Moves all authenticated pages into `(authenticated)/` route group and creates the shared layout with NavRail + MobileTabBar.

**Files:**
- Create: `frontend/src/app/(authenticated)/layout.tsx`
- Move: `app/chat/` → `app/(authenticated)/chat/`
- Move: `app/workflows/` → `app/(authenticated)/workflows/`
- Move: `app/settings/` → `app/(authenticated)/settings/`
- Move: `app/admin/` → `app/(authenticated)/admin/`
- Create: `frontend/src/app/(authenticated)/skills/page.tsx`
- Create: `frontend/src/app/(authenticated)/profile/page.tsx` (placeholder)

**Step 1: Create the directory structure**

Run:
```bash
cd /home/tungmv/Projects/hox-agentos/frontend/src/app
mkdir -p "(authenticated)"
```

**Step 2: Create the authenticated layout**

Create `frontend/src/app/(authenticated)/layout.tsx`:

```tsx
"use client";

import { NavRail } from "@/components/nav/nav-rail";
import { MobileTabBar } from "@/components/nav/mobile-tab-bar";

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen bg-gray-50">
      {/* Desktop nav rail */}
      <NavRail className="hidden md:flex" />

      {/* Page content */}
      <div className="flex-1 min-w-0 flex flex-col">
        <main className="flex-1 min-h-0">{children}</main>
      </div>

      {/* Mobile bottom tab bar */}
      <MobileTabBar className="md:hidden" />
    </div>
  );
}
```

**Step 3: Move page directories into the route group**

Run:
```bash
cd /home/tungmv/Projects/hox-agentos/frontend/src/app
mv chat "(authenticated)/chat"
mv workflows "(authenticated)/workflows"
mv settings "(authenticated)/settings"
mv admin "(authenticated)/admin"
```

**Step 4: Create user-facing skills page**

Create `frontend/src/app/(authenticated)/skills/page.tsx`:

```tsx
"use client";

import Link from "next/link";
import { useSkills } from "@/hooks/use-skills";

export default function SkillsPage() {
  const { skills, loading } = useSkills();

  return (
    <div className="p-6 max-w-4xl mx-auto overflow-y-auto h-full">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Skills</h1>

      {loading ? (
        <div className="text-sm text-gray-500">Loading skills...</div>
      ) : skills.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p className="text-lg font-medium">No skills available</p>
          <p className="text-sm mt-1">
            Ask your admin to enable skills for your role.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {skills.map((skill) => (
            <div
              key={skill.id}
              className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:bg-blue-50 transition-colors"
            >
              <h3 className="font-medium text-gray-900">
                {skill.displayName ?? skill.name}
              </h3>
              {skill.description && (
                <p className="text-sm text-gray-500 mt-1 line-clamp-2">
                  {skill.description}
                </p>
              )}
              {skill.slashCommand && (
                <p className="text-xs text-blue-600 mt-2 font-mono">
                  /{skill.slashCommand}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

**Step 5: Create profile page placeholder**

Create `frontend/src/app/(authenticated)/profile/page.tsx`:

```tsx
export default function ProfilePage() {
  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900">Profile</h1>
      <p className="text-gray-500 mt-2">Coming in Task 7...</p>
    </div>
  );
}
```

**Step 6: Fix the chat page layout**

The chat page's `ChatLayout` uses `flex h-screen` which works inside the authenticated layout's `flex-1 min-h-0` container. However, `h-screen` (100vh) inside a flex child may cause overflow. Update `ChatLayout` to use `h-full` instead:

In `frontend/src/components/chat/chat-layout.tsx`, change:
```tsx
// Before:
<div className="flex h-screen bg-gray-50 overflow-hidden">
// After:
<div className="flex h-full bg-gray-50 overflow-hidden">
```

**Step 7: Fix non-chat pages for mobile bottom bar padding**

The MobileTabBar is `fixed bottom-0`, so on mobile, page content at the bottom gets hidden behind it. Add bottom padding to scrollable pages.

In the authenticated layout, update main to add mobile bottom padding:

```tsx
<main className="flex-1 min-h-0 pb-14 md:pb-0">{children}</main>
```

**Step 8: Verify the build compiles**

Run: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm run build`
Expected: Build succeeds (may have pre-existing warnings from other pages — those are not from this change)

Note: If build fails on SWR-in-Server-Component issues (pre-existing tech debt from STATE.md), that's expected and unrelated to this change. The key test is that no NEW TypeScript errors appear.

**Step 9: Commit**

```bash
cd /home/tungmv/Projects/hox-agentos
git add frontend/src/app/\(authenticated\)/ frontend/src/components/chat/chat-layout.tsx
git add -u  # pick up file moves (git detects renames)
git commit -m "feat(16-06): restructure routes into (authenticated) group with nav rail layout"
```

---

## Task 7: Frontend — Profile page

Creates the full profile page with account info, custom instructions, LLM preferences, password change, and sign out.

**Files:**
- Rewrite: `frontend/src/app/(authenticated)/profile/page.tsx`
- Create: `frontend/src/app/api/auth/local/change-password/route.ts`

**Step 1: Create the password change proxy route**

Create `frontend/src/app/api/auth/local/change-password/route.ts`:

```ts
/**
 * Server-side proxy for PUT /api/auth/local/change-password.
 * Injects Bearer token server-side — credentials never touch browser.
 */
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const API_URL =
  process.env.BACKEND_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

async function getAccessToken(): Promise<string | undefined> {
  const session = await auth();
  return (session as unknown as Record<string, unknown>)?.accessToken as
    | string
    | undefined;
}

export async function PUT(request: NextRequest): Promise<NextResponse> {
  const accessToken = await getAccessToken();
  if (!accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body: unknown = await request.json();
    const res = await fetch(`${API_URL}/api/auth/local/change-password`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(body),
    });
    const data: unknown = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { error: "Failed to change password" },
      { status: 500 }
    );
  }
}
```

**Step 2: Create the full profile page**

Rewrite `frontend/src/app/(authenticated)/profile/page.tsx`:

```tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import { SignOutButton } from "@/components/sign-out-button";

type ResponseStyle = "concise" | "detailed" | "conversational";
type RenderingMode = "markdown" | "card_wrapped" | "inline_chips";

interface Preferences {
  thinking_mode: boolean;
  response_style: ResponseStyle;
  rendering_mode: RenderingMode;
}

const RESPONSE_STYLES: { value: ResponseStyle; label: string; desc: string }[] = [
  { value: "concise", label: "Concise", desc: "Short, direct answers" },
  { value: "detailed", label: "Detailed", desc: "Thorough responses with examples" },
  { value: "conversational", label: "Conversational", desc: "Casual, friendly tone" },
];

const RENDERING_MODES: { value: RenderingMode; label: string }[] = [
  { value: "markdown", label: "Markdown" },
  { value: "card_wrapped", label: "Card Wrapped" },
  { value: "inline_chips", label: "Inline Chips" },
];

export default function ProfilePage() {
  const { data: session } = useSession();

  // Account info
  const email = session?.user?.email ?? "";
  const sessionData = session as unknown as Record<string, unknown>;
  const roles = (sessionData?.realmRoles as string[]) ?? [];
  const authProvider = (sessionData?.authProvider as string) ?? "unknown";
  const isLocal = authProvider === "credentials";

  // Custom instructions
  const [instructions, setInstructions] = useState("");
  const [instructionsSaved, setInstructionsSaved] = useState(false);
  const [instructionsLoading, setInstructionsLoading] = useState(true);

  // Preferences
  const [prefs, setPrefs] = useState<Preferences>({
    thinking_mode: false,
    response_style: "concise",
    rendering_mode: "markdown",
  });
  const [prefsLoading, setPrefsLoading] = useState(true);

  // Password change
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordMsg, setPasswordMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [passwordLoading, setPasswordLoading] = useState(false);

  // Load instructions
  useEffect(() => {
    fetch("/api/user/instructions/")
      .then((r) => r.json())
      .then((data: unknown) => {
        const d = data as Record<string, unknown>;
        setInstructions((d.instructions as string) ?? "");
      })
      .catch(() => {})
      .finally(() => setInstructionsLoading(false));
  }, []);

  // Load preferences
  useEffect(() => {
    fetch("/api/settings/preferences")
      .then((r) => r.json())
      .then((data: unknown) => {
        const d = data as Preferences;
        setPrefs({
          thinking_mode: d.thinking_mode ?? false,
          response_style: d.response_style ?? "concise",
          rendering_mode: d.rendering_mode ?? "markdown",
        });
      })
      .catch(() => {})
      .finally(() => setPrefsLoading(false));
  }, []);

  // Save instructions
  const saveInstructions = useCallback(async () => {
    try {
      await fetch("/api/user/instructions/", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instructions }),
      });
      setInstructionsSaved(true);
      setTimeout(() => setInstructionsSaved(false), 2000);
    } catch {
      // ignore
    }
  }, [instructions]);

  // Update preference (auto-save)
  const updatePref = useCallback(
    async (update: Partial<Preferences>) => {
      const next = { ...prefs, ...update };
      setPrefs(next);
      try {
        await fetch("/api/settings/preferences", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(update),
        });
      } catch {
        // revert on error
        setPrefs(prefs);
      }
    },
    [prefs]
  );

  // Change password
  const handleChangePassword = useCallback(async () => {
    if (newPassword !== confirmPassword) {
      setPasswordMsg({ type: "err", text: "Passwords do not match" });
      return;
    }
    if (newPassword.length < 8) {
      setPasswordMsg({ type: "err", text: "Password must be at least 8 characters" });
      return;
    }
    setPasswordLoading(true);
    setPasswordMsg(null);
    try {
      const res = await fetch("/api/auth/local/change-password", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      if (res.ok) {
        setPasswordMsg({ type: "ok", text: "Password changed successfully" });
        setCurrentPassword("");
        setNewPassword("");
        setConfirmPassword("");
      } else {
        const data = (await res.json()) as Record<string, unknown>;
        setPasswordMsg({
          type: "err",
          text: (data.detail as string) ?? "Failed to change password",
        });
      }
    } catch {
      setPasswordMsg({ type: "err", text: "Network error" });
    } finally {
      setPasswordLoading(false);
    }
  }, [currentPassword, newPassword, confirmPassword]);

  return (
    <div className="p-6 max-w-2xl mx-auto overflow-y-auto h-full space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Profile</h1>

      {/* Account Information */}
      <section className="bg-white rounded-lg border border-gray-200 p-6 space-y-3">
        <h2 className="text-lg font-semibold text-gray-900">
          Account Information
        </h2>
        <div className="grid grid-cols-[120px_1fr] gap-y-2 text-sm">
          <span className="text-gray-500">Email</span>
          <span className="text-gray-900">{email}</span>
          <span className="text-gray-500">Auth Provider</span>
          <span className="text-gray-900">
            {isLocal ? "Local" : "SSO (Keycloak)"}
          </span>
          <span className="text-gray-500">Roles</span>
          <span className="text-gray-900">
            {roles.length > 0 ? roles.join(", ") : "—"}
          </span>
        </div>
      </section>

      {/* Password Change (local users only) */}
      {isLocal && (
        <section className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Change Password
          </h2>
          <div className="space-y-3 max-w-sm">
            <input
              type="password"
              placeholder="Current password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <input
              type="password"
              placeholder="New password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <input
              type="password"
              placeholder="Confirm new password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={() => void handleChangePassword()}
              disabled={passwordLoading || !currentPassword || !newPassword || !confirmPassword}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {passwordLoading ? "Changing..." : "Change Password"}
            </button>
            {passwordMsg && (
              <p
                className={`text-sm ${passwordMsg.type === "ok" ? "text-green-600" : "text-red-600"}`}
              >
                {passwordMsg.text}
              </p>
            )}
          </div>
        </section>
      )}

      {/* Custom Instructions */}
      <section className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">
          Custom Instructions
        </h2>
        <p className="text-sm text-gray-500">
          These instructions are appended to every conversation with Blitz.
        </p>
        {instructionsLoading ? (
          <div className="text-sm text-gray-400">Loading...</div>
        ) : (
          <>
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              maxLength={4000}
              rows={5}
              placeholder="e.g., Always respond in Vietnamese. Prefer bullet points."
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm resize-y focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <div className="flex items-center gap-3">
              <button
                onClick={() => void saveInstructions()}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700"
              >
                Save
              </button>
              {instructionsSaved && (
                <span className="text-sm text-green-600">Saved</span>
              )}
              <span className="text-xs text-gray-400 ml-auto">
                {instructions.length}/4000
              </span>
            </div>
          </>
        )}
      </section>

      {/* LLM Preferences */}
      <section className="bg-white rounded-lg border border-gray-200 p-6 space-y-6">
        <h2 className="text-lg font-semibold text-gray-900">
          LLM Preferences
        </h2>

        {prefsLoading ? (
          <div className="text-sm text-gray-400">Loading...</div>
        ) : (
          <>
            {/* Thinking Mode */}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-900">
                  Thinking Mode
                </p>
                <p className="text-xs text-gray-500">
                  Show step-by-step reasoning before answering
                </p>
              </div>
              <button
                onClick={() =>
                  void updatePref({ thinking_mode: !prefs.thinking_mode })
                }
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  prefs.thinking_mode ? "bg-blue-600" : "bg-gray-300"
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    prefs.thinking_mode ? "translate-x-5" : ""
                  }`}
                />
              </button>
            </div>

            {/* Response Style */}
            <fieldset>
              <legend className="text-sm font-medium text-gray-900 mb-2">
                Response Style
              </legend>
              <div className="space-y-2">
                {RESPONSE_STYLES.map((style) => (
                  <label
                    key={style.value}
                    className="flex items-start gap-3 cursor-pointer"
                  >
                    <input
                      type="radio"
                      name="response_style"
                      value={style.value}
                      checked={prefs.response_style === style.value}
                      onChange={() =>
                        void updatePref({ response_style: style.value })
                      }
                      className="mt-0.5 accent-blue-600"
                    />
                    <div>
                      <p className="text-sm text-gray-900">{style.label}</p>
                      <p className="text-xs text-gray-500">{style.desc}</p>
                    </div>
                  </label>
                ))}
              </div>
            </fieldset>

            {/* Chat Display */}
            <fieldset>
              <legend className="text-sm font-medium text-gray-900 mb-2">
                Chat Display
              </legend>
              <div className="space-y-2">
                {RENDERING_MODES.map((mode) => (
                  <label
                    key={mode.value}
                    className="flex items-center gap-3 cursor-pointer"
                  >
                    <input
                      type="radio"
                      name="rendering_mode"
                      value={mode.value}
                      checked={prefs.rendering_mode === mode.value}
                      onChange={() =>
                        void updatePref({ rendering_mode: mode.value })
                      }
                      className="accent-blue-600"
                    />
                    <span className="text-sm text-gray-900">{mode.label}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          </>
        )}
      </section>

      {/* Sign Out */}
      <section className="bg-white rounded-lg border border-gray-200 p-6">
        <SignOutButton />
      </section>
    </div>
  );
}
```

**Step 3: Verify the build compiles**

Run: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm exec tsc --noEmit`
Expected: No new errors

**Step 4: Commit**

```bash
git add frontend/src/app/\(authenticated\)/profile/page.tsx frontend/src/app/api/auth/local/change-password/
git commit -m "feat(16-07): create profile page with account info, preferences, and password change"
```

---

## Task 8: Frontend — Settings page slim-down + cleanup

Removes custom instructions and chat-preferences from the settings page since they've moved to profile. Removes the standalone `/settings/chat-preferences` page.

**Files:**
- Modify: `frontend/src/app/(authenticated)/settings/page.tsx`
- Delete or redirect: `frontend/src/app/(authenticated)/settings/chat-preferences/page.tsx`

**Step 1: Update the settings hub page**

Rewrite `frontend/src/app/(authenticated)/settings/page.tsx` to remove the custom instructions form and the chat-preferences card. Keep only: channels, memory, integrations.

The page should look like:

```tsx
"use client";

import Link from "next/link";

const SETTINGS_LINKS = [
  {
    href: "/settings/channels",
    title: "Channel Linking",
    description: "Connect Telegram, WhatsApp, Teams",
  },
  {
    href: "/settings/memory",
    title: "Memory",
    description: "View and manage stored facts and episodes",
  },
];

export default function SettingsPage() {
  return (
    <div className="p-6 max-w-2xl mx-auto overflow-y-auto h-full">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {SETTINGS_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="flex items-center p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors"
          >
            <div>
              <h3 className="font-medium text-gray-900">{link.title}</h3>
              <p className="text-sm text-gray-500">{link.description}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
```

**Step 2: Remove or redirect the chat-preferences page**

If `frontend/src/app/(authenticated)/settings/chat-preferences/page.tsx` exists after the move, replace its contents with a redirect:

```tsx
import { redirect } from "next/navigation";

export default function ChatPreferencesRedirect() {
  redirect("/profile");
}
```

**Step 3: Update back links in settings sub-pages**

In `frontend/src/app/(authenticated)/settings/memory/page.tsx` and `frontend/src/app/(authenticated)/settings/channels/page.tsx`, verify back links point to `/settings` (they should already since they use `href="/settings"`).

**Step 4: Verify the build**

Run: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm exec tsc --noEmit`
Expected: No new errors

**Step 5: Commit**

```bash
git add frontend/src/app/\(authenticated\)/settings/
git commit -m "feat(16-08): slim down settings page — custom instructions and chat prefs moved to profile"
```

---

## Verification Checklist

After all 8 tasks, verify these success criteria:

| # | Criterion | How to verify |
|---|-----------|---------------|
| 1 | Nav rail visible on all authenticated pages | Visit `/chat`, `/workflows`, `/skills`, `/settings`, `/admin`, `/profile` — nav rail present on all |
| 2 | Admin item role-gated | Log in as `employee` role — Admin icon hidden. Log in as `admin` — Admin icon visible |
| 3 | Profile page shows account info + password change for local users | Visit `/profile` — see email, roles, auth provider. Log in as local user — password change form visible. Log in as SSO — form hidden |
| 4 | LLM preferences reflected in agent | Set thinking mode ON and response style to "detailed" in profile. Start new conversation — agent should reason step-by-step and give detailed responses |
| 5 | Login page has no nav rail | Visit `/login` — no nav rail, no bottom tab bar |

Backend tests: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/api/test_user_preferences.py tests/api/test_password_change.py -v`

Full test suite: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/ -q`

Frontend build: `cd frontend && pnpm run build`
