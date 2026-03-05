# Phase 16: Navigation & User Experience — Design

**Date:** 2026-03-05
**Phase:** 16 of v1.3 Production Readiness & Skill Platform
**Depends on:** Phase 15 (Session & Auth Hardening) — completed 2026-03-05
**Goal:** Users can navigate the entire application from a persistent navigation rail and manage their profile and preferences from a dedicated page

---

## Success Criteria

1. A vertical navigation rail with icons for Chat, Workflows, Skills, Settings, Admin, and Profile is visible on every authenticated page — clicking any icon navigates to that section
2. The Admin nav item is visible only to users with `admin`, `developer`, or `it-admin` roles — other users do not see it
3. User can view their profile at `/profile` showing name, email, auth provider (SSO or Local), roles, and current session expiry — local users can change their password from this page
4. User can set LLM thinking mode (on/off) and response style (concise/detailed/conversational) from the profile page — preferences are reflected in the next agent conversation
5. The `/login` page and API routes are excluded from the navigation rail layout

---

## 1. Route Group Structure

All authenticated pages move into an `(authenticated)` route group. The login page stays outside. Route groups are a Next.js App Router convention — parenthesized names don't appear in URLs.

```
src/app/
├── layout.tsx                           # Root: SessionProvider + AuthErrorToasts (unchanged)
├── login/page.tsx                       # Login page — NO nav rail
├── (authenticated)/
│   ├── layout.tsx                       # NEW: NavRail + MobileTabBar wrapper
│   ├── chat/page.tsx                    # moved from app/chat/
│   ├── workflows/page.tsx              # moved from app/workflows/
│   ├── workflows/new/page.tsx          # moved
│   ├── workflows/[id]/page.tsx         # moved
│   ├── skills/page.tsx                 # existing user-facing skills
│   ├── profile/page.tsx                # NEW: account info + preferences
│   ├── settings/                       # slimmed down
│   │   ├── page.tsx                    # hub: channels + memory + integrations links
│   │   ├── channels/page.tsx           # existing channel pairing
│   │   ├── memory/page.tsx             # existing memory management
│   │   └── integrations/page.tsx       # redirect to /admin/mcp-servers
│   └── admin/                          # existing admin area (keeps its own layout.tsx)
│       ├── layout.tsx                  # existing admin tab bar
│       └── ... (all admin sub-pages unchanged)
```

**Key decision:** Custom instructions and chat-preferences move from `/settings` to `/profile`. Settings becomes slim (channels, memory, integrations only).

---

## 2. NavRail Component (Desktop)

**Width:** 64px fixed
**Position:** Left edge, full height
**Style:** Icon-only with tooltip on hover
**Active indicator:** 2px blue left border + icon color change

### Items (top to bottom)

| Position | Icon (Lucide) | Label | Route | Visibility |
|----------|---------------|-------|-------|------------|
| Top | Logo/monogram | — | — | Always |
| Group 1 | `MessageSquare` | Chat | `/chat` | Always |
| Group 1 | `GitBranch` | Workflows | `/workflows` | Always |
| Group 1 | `Zap` | Skills | `/skills` | Always |
| Spacer | — | — | — | — |
| Group 2 | `Shield` | Admin | `/admin` | Role-gated |
| Group 2 | `Settings` | Settings | `/settings` | Always |
| Group 2 | `User` | Profile | `/profile` | Always |

### Role gating (Admin item)

```tsx
const { data: session } = useSession();
const roles = session?.realmRoles ?? [];
const isAdmin = roles.some(r => ["admin", "developer", "it-admin"].includes(r));
```

### Chat page layout

Nav rail sits to the left of the existing `ConversationSidebar`. The conversation sidebar keeps its Settings link and Sign Out button in the footer (no change to sidebar).

```
Desktop (>= 768px):
┌──────┬────────────────┬──────────────────────────┐
│ Nav  │ Conversation   │     Chat Panel           │
│ Rail │ Sidebar (w-72) │                          │
│ 64px │                │                          │
└──────┴────────────────┴──────────────────────────┘

Other pages:
┌──────┬──────────────────────────────────────────┐
│ Nav  │           Page Content                   │
│ Rail │                                          │
│ 64px │                                          │
└──────┴──────────────────────────────────────────┘
```

---

## 3. MobileTabBar Component (< 768px)

**Position:** Fixed bottom, full width
**Style:** Horizontal icon row with active indicator (bottom border)
**Items:** Chat, Workflows, Skills, Settings, Profile (5 items — Admin accessible from Settings)

The vertical nav rail is hidden on mobile (`hidden md:flex`). The mobile tab bar is hidden on desktop (`md:hidden`).

---

## 4. Profile Page (`/profile`)

### Sections

**4.1 Account Information**
- Name: from `GET /api/auth/me`
- Email: from session
- Auth provider: badge showing "Local" or "SSO (Keycloak)"
- Roles: comma-separated list from `session.realmRoles`
- Session expiry: countdown computed from token `exp` claim
- Password change button: visible only for local auth users, calls `PUT /api/auth/change-password`

**4.2 Custom Instructions**
- Textarea (4000 char limit), moved from `/settings`
- Calls `GET/PUT /api/users/me/instructions` (existing endpoints, no backend change)

**4.3 LLM Preferences**
- Thinking mode: toggle switch (on/off), default off
- Response style: radio group (concise/detailed/conversational), default concise
- Chat display mode: radio group (markdown/card_wrapped/inline_chips), default markdown — moved from `/settings/chat-preferences`
- Auto-saves on change via `PUT /api/users/me/preferences`

**4.4 Sign Out**
- Red "Sign Out" button at the bottom
- Same behavior as existing `SignOutButton` component

---

## 5. Backend Changes

### 5.1 New table: `user_preferences`

```sql
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE,  -- no FK (users in Keycloak)
    thinking_mode BOOLEAN NOT NULL DEFAULT false,
    response_style VARCHAR(20) NOT NULL DEFAULT 'concise'
        CHECK (response_style IN ('concise', 'detailed', 'conversational')),
    chat_display_mode VARCHAR(20) NOT NULL DEFAULT 'markdown'
        CHECK (chat_display_mode IN ('markdown', 'card_wrapped', 'inline_chips')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 5.2 New API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/users/me/preferences` | Get preferences (upsert defaults if none exist) |
| `PUT` | `/api/users/me/preferences` | Partial update preferences |

### 5.3 ORM model

```python
class UserPreference(Base):
    __tablename__ = "user_preferences"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(unique=True, nullable=False)
    thinking_mode: Mapped[bool] = mapped_column(default=False)
    response_style: Mapped[str] = mapped_column(String(20), default="concise")
    chat_display_mode: Mapped[str] = mapped_column(String(20), default="markdown")
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
```

### 5.4 Pydantic schemas

```python
class UserPreferencesRead(BaseModel):
    thinking_mode: bool
    response_style: str  # concise | detailed | conversational
    chat_display_mode: str  # markdown | card_wrapped | inline_chips

class UserPreferencesUpdate(BaseModel):
    thinking_mode: bool | None = None
    response_style: str | None = None
    chat_display_mode: str | None = None
```

### 5.5 Agent integration

In `master_agent.py`, extend `_pre_route` or `_load_memory_node` to load user preferences and append directives to the system prompt:

```python
prefs = await get_user_preferences(user_id)
if prefs.thinking_mode:
    system_prompt += "\nShow your reasoning step-by-step before answering."
match prefs.response_style:
    case "detailed":
        system_prompt += "\nProvide thorough, detailed responses with examples."
    case "conversational":
        system_prompt += "\nRespond in a casual, conversational tone."
    # "concise" is the default — no extra prompt needed
```

### 5.6 Migration

Alembic migration 020: `CREATE TABLE user_preferences`.

---

## 6. Settings Page Slim-Down

### Remove from `/settings`:
- Custom instructions textarea → moved to `/profile`
- Chat preferences link → moved to `/profile`

### Keep in `/settings`:
- Channel connections (Telegram, WhatsApp, Teams)
- Memory management
- Integrations (redirect to admin)

---

## 7. Testing Strategy

### Frontend
- NavRail renders correct items based on role (admin vs non-admin)
- Active state highlights current route
- Mobile tab bar visible on small screens, nav rail hidden
- Profile page displays account info correctly
- Preference changes call the API and update UI
- Password change form visible only for local auth users

### Backend
- `GET /api/users/me/preferences` returns defaults for new user
- `PUT /api/users/me/preferences` updates only provided fields
- Agent system prompt includes preference directives
- Migration 020 applies cleanly

---

## 8. Files Changed (Estimated)

### New files
- `frontend/src/app/(authenticated)/layout.tsx` — nav shell
- `frontend/src/components/nav/nav-rail.tsx` — desktop nav rail
- `frontend/src/components/nav/mobile-tab-bar.tsx` — mobile bottom tabs
- `frontend/src/app/(authenticated)/profile/page.tsx` — profile page
- `backend/core/models/user_preference.py` — ORM model
- `backend/core/schemas/user_preference.py` — Pydantic schemas
- `backend/api/routes/user_preferences.py` — API routes
- `backend/alembic/versions/020_*.py` — migration
- `tests/api/test_user_preferences.py` — backend tests

### Modified files
- `frontend/src/app/(authenticated)/settings/page.tsx` — remove custom instructions + chat prefs
- `backend/agents/master_agent.py` — load preferences into system prompt
- `backend/main.py` — register preferences router
- Move ~10 page directories into `(authenticated)/`

### Removed/redirected
- `frontend/src/app/settings/chat-preferences/page.tsx` → functionality moved to profile
