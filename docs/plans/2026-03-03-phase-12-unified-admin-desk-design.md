# Phase 12 Design: Unified Admin Desk

*Date: 2026-03-03*
*Status: Approved*

## Goal

All artifact management is consolidated at `/admin`. `/settings` becomes personal-only. Every artifact type can be created through a guided hybrid wizard (structured form + AI chat assistant with bidirectional state sync) that validates input, prevents name conflicts, and starts from templates or existing clones.

## Context

Phase 11 shipped prompt externalization, Cloudflare Tunnel, and dead code removal. Phase 12 is the frontend-heavy DX phase that closes the admin UX gap.

**What exists today:**
- `/admin` — 6 tabs: Agents, Tools, Skills, MCP Servers, Permissions, AI Builder (CopilotKit chat-only)
- `/settings` — Personal section (Memory, Chat Prefs, Channels) + Admin section (agent toggles, MCP integrations)
- `/settings/agents` — enable/disable Email, Calendar, Project agents (uses `/api/admin/config`)
- `/settings/integrations` — add/remove MCP servers (duplicates `/admin/mcp-servers`)

## Plan Structure: 2 Plans

### Plan 12-01: Consolidated Admin Desk
- Config tab, Credentials tab, settings migration, settings cleanup
- Mostly frontend; 1 new backend endpoint

### Plan 12-02: Hybrid Form Wizard
- Replace `/admin/create` with form wizard + AI chat assistant
- Bidirectional state sync via co-agent `fill_form` tool
- Templates, name conflict check, permission dropdown, clone support

---

## Plan 12-01: Consolidated Admin Desk

### Changes

#### 1. New Admin Tab: Config (`/admin/config`)

A new tab in the admin nav showing agent enable/disable toggles. Reuses the existing `GET /api/admin/config` + `PUT /api/admin/config/{key}` endpoints — no backend changes needed.

```
/admin/config
┌─────────────────────────────────┐
│ System Configuration            │
│                                 │
│ Agent Enable/Disable            │
│ ┌───────────────────────────┐   │
│ │ Email Agent        [●]    │   │
│ │ Calendar Agent     [●]    │   │
│ │ Project Agent      [○]    │   │
│ └───────────────────────────┘   │
└─────────────────────────────────┘
```

**Files:**
- CREATE `frontend/src/app/admin/config/page.tsx` — copy toggle logic from `/settings/agents`
- UPDATE `frontend/src/app/admin/layout.tsx` — add Config to `ADMIN_TABS`

#### 2. New Admin Tab: Credentials (`/admin/credentials`)

Admin-only view of all users' OAuth connected providers. Includes admin force-revoke.

**New backend endpoint:** `GET /api/admin/credentials`
- Required permission: `registry:manage`
- Returns: `[{user_id: uuid, email: str, provider: str, connected_at: datetime | null}]`
- Joins `oauth_credentials` table with `user_id` to derive email from Keycloak (or just show user_id if email unavailable)

**New backend endpoint:** `DELETE /api/admin/credentials/{user_id}/{provider}`
- Required permission: `registry:manage`
- Deletes the credential row for the given user_id + provider

**New file:** `backend/api/routes/admin_credentials.py`

```python
router = APIRouter(prefix="/api/admin/credentials", tags=["admin-credentials"])

@router.get("/", response_model=list[AdminCredentialView])
async def list_all_credentials(...)

@router.delete("/{user_id}/{provider}", status_code=204)
async def admin_revoke_credential(...)
```

**Frontend:**
- CREATE `frontend/src/app/admin/credentials/page.tsx` — table of user_id/email, provider, connected_at, Revoke button
- UPDATE `frontend/src/app/admin/layout.tsx` — add Credentials to `ADMIN_TABS`
- CREATE `frontend/src/app/api/admin/credentials/route.ts` — Next.js proxy route
- CREATE `frontend/src/app/api/admin/credentials/[userId]/[provider]/route.ts` — Next.js proxy for DELETE

#### 3. Settings Cleanup

- DELETE `frontend/src/app/settings/agents/page.tsx`
- DELETE `frontend/src/app/settings/integrations/page.tsx`
- UPDATE `frontend/src/app/settings/page.tsx` — remove the "Admin" grid section (the 2-column grid with Agents + Integrations links); keep Personal grid + Custom Instructions section

#### 4. Admin Tab Order (final)

```typescript
const ADMIN_TABS = [
  { label: "Agents",      href: "/admin/agents" },
  { label: "Tools",       href: "/admin/tools" },
  { label: "Skills",      href: "/admin/skills" },
  { label: "MCP Servers", href: "/admin/mcp-servers" },
  { label: "Permissions", href: "/admin/permissions" },
  { label: "Config",      href: "/admin/config" },        // NEW
  { label: "Credentials", href: "/admin/credentials" },   // NEW
  { label: "AI Builder",  href: "/admin/create" },
];
```

### Success Criteria for 12-01

- [ ] `/admin` shows Config and Credentials tabs
- [ ] Config tab shows agent toggles that save via `/api/admin/config/{key}` — same behavior as old `/settings/agents`
- [ ] Credentials tab shows a table of all users' OAuth connections; Revoke button calls DELETE endpoint
- [ ] `/settings` page no longer has an Admin section
- [ ] `/settings/agents` and `/settings/integrations` return 404
- [ ] 586+ tests still pass

---

## Plan 12-02: Hybrid Form Wizard

### Overview

Replaces the chat-only AI builder at `/admin/create` with a split-panel hybrid:
- **Left panel (45%):** Multi-section structured form (type selector → template picker → fields → JSON preview)
- **Right panel (55%):** CopilotKit chat assistant that can push values into form fields via the `fill_form` tool

The AI assistant populates fields **directly** — when it suggests permissions or a name, it calls `fill_form(name="...", permissions=[...])` and the form fields update live. The form is always the source of truth.

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Admin Dashboard [tabs]                                      │
├───────────────────────────┬─────────────────────────────────┤
│  FORM (45%)               │  AI ASSISTANT (55%)             │
│                           │                                 │
│  Create Artifact          │  [CopilotChat]                  │
│  ─────────────────────    │                                 │
│  Type                     │  "Tell me what you want to     │
│  ○ Agent  ○ Tool          │   build and I'll fill out the  │
│  ○ Skill  ○ MCP Server    │   form for you."               │
│                           │                                 │
│  Template                 │  User: "Create a daily email   │
│  [Blank ▼] [Clone...]     │   digest agent that sends to  │
│  [email-digest] [project] │   Telegram"                    │
│                           │                                 │
│  Name                     │  AI: *calls fill_form()*       │
│  [my-email-agent] ✓ OK    │  → form fields update live     │
│                           │                                 │
│  Description              │                                 │
│  [________________]       │                                 │
│                           │                                 │
│  Permissions              │                                 │
│  ☑ tool:email             │                                 │
│  ☑ tool:calendar          │                                 │
│  ☐ crm:read               │                                 │
│  ... (checklist)          │                                 │
│                           │                                 │
│  JSON Preview             │                                 │
│  { "name": "...", ... }   │                                 │
│                           │                                 │
│  [Cancel]    [Submit →]   │                                 │
└───────────────────────────┴─────────────────────────────────┘
```

### Form Sections

The form is a single scrollable page (not a step wizard with Next buttons). Sections appear in order but the user can fill them in any order.

**Section 1: Artifact Type**
4 buttons (radio group): Agent, Tool, Skill, MCP Server. Selecting one updates what templates and field schema appear below.

**Section 2: Template / Clone**
- `[Start Blank]` button — clears all fields
- `[Clone Existing]` button — opens a searchable modal listing all existing artifacts of the selected type; selecting one pre-fills all fields with a `_copy` suffix on the name
- Template cards (1-2 per type, hardcoded):

| Type | Templates |
|------|-----------|
| Agent | `email-digest-agent`, `project-status-agent` |
| Tool | `rest-api-tool`, `python-script-tool` |
| Skill | `summarizer-skill`, `data-extractor-skill` |
| MCP Server | `openapi-mcp-server` |

Clicking a template card pre-fills name + description + relevant fields.

**Section 3: Common Fields (all types)**
- `Name` — text input; debounced name-check (300ms) calls `GET /api/admin/{type}/check-name?name=xxx`; shows ✓ or ✗ badge inline
- `Description` — textarea
- `Version` — text input, defaults to `"1.0.0"`

**Section 3: Type-specific Fields**

*Agent:*
- `system_prompt` — textarea (for inline agents; hidden for router agents)
- `model_alias` — dropdown: `blitz/master`, `blitz/fast`, `blitz/coder`, `blitz/summarizer`

*Tool:*
- `required_permissions` — multi-select checklist from permission strings
- `sandbox_required` — checkbox
- `handler_module` — text input

*Skill:*
- `required_permissions` — multi-select checklist
- `entry_point` — text input
- `sandbox_required` — checkbox

*MCP Server:*
- `url` — URL input
- `auth_token` — password input (optional)

**Section 4: JSON Preview**
Read-only code block showing the current form values as the JSON that will be submitted. Updates live as fields change.

**Section 5: Actions**
- `[Cancel]` — clears form, resets to blank state
- `[Submit]` — calls `POST /api/admin/{type}`, shows success toast with link to the new artifact's row in the admin table; no page reload

### Bidirectional AI ↔ Form Sync

The backend `artifact_builder` co-agent gets a new tool: `fill_form`.

```python
@tool
def fill_form(
    name: str | None = None,
    description: str | None = None,
    artifact_type: str | None = None,
    required_permissions: list[str] | None = None,
    model_alias: str | None = None,
    system_prompt: str | None = None,
    url: str | None = None,
    **extra_fields: str,
) -> str:
    """Fill one or more form fields. Only provide the fields you want to change."""
    ...
```

When the agent calls `fill_form`, the frontend receives the tool call result via `useCoAgentStateRender`, extracts the field updates, and merges them into form state. The user sees fields fill in as the AI streams.

The form also feeds its current state into the agent context so the AI knows what's already filled.

### Name Conflict Check Endpoints

Add to each existing admin route file:

```python
@router.get("/check-name")
async def check_name(name: str = Query(...)) -> dict[str, bool]:
    """Returns {"available": true/false} for the given artifact name."""
    exists = await session.scalar(
        select(func.count()).where(
            func.lower(Model.name) == name.lower(),
            Model.is_active == True,
        )
    )
    return {"available": exists == 0}
```

Files to add `check-name` to:
- `backend/api/routes/admin_agents.py`
- `backend/api/routes/admin_tools.py`
- `backend/api/routes/admin_skills.py`
- `backend/api/routes/admin_mcp_servers.py` (or equivalent)

### Clone Entry Points

Each artifact row in the admin tables gets a "Clone" action. This navigates to:
```
/admin/create?clone_type=agent&clone_id={uuid}
```

The wizard reads these query params on mount, fetches the artifact's current values via `GET /api/admin/{type}/{id}`, and pre-fills the form with a `_copy` suffix on the name field.

### Backend: artifact_builder agent updates

The existing `artifact_builder` agent in `backend/agents/` gets:
- New `fill_form` tool definition (see above)
- Updated system prompt to use `fill_form` instead of just describing values in text
- Updated `ArtifactBuilderState` to include all form field values (so state renders sync to frontend)

### Frontend Files for 12-02

| File | Action |
|------|--------|
| `frontend/src/app/admin/create/page.tsx` | Replace with form wizard |
| `frontend/src/components/admin/artifact-wizard.tsx` | NEW — main wizard component |
| `frontend/src/components/admin/artifact-wizard-form.tsx` | NEW — form fields per type |
| `frontend/src/components/admin/artifact-wizard-templates.tsx` | NEW — template cards |
| `frontend/src/components/admin/artifact-wizard-name-check.tsx` | NEW — debounced name check |
| `frontend/src/components/admin/clone-artifact-modal.tsx` | NEW — searchable clone picker |
| `frontend/src/components/admin/artifact-table.tsx` | UPDATE — add Clone button |
| `frontend/src/components/admin/artifact-card-grid.tsx` | UPDATE — add Clone button |
| `frontend/src/app/api/admin/[type]/check-name/route.ts` | NEW — proxy for name check |

### Success Criteria for 12-02

- [ ] `/admin/create` shows form panel (left) + AI chat panel (right)
- [ ] Selecting an artifact type updates the form fields shown below
- [ ] Selecting a template pre-fills name, description, and type-specific fields
- [ ] Typing a name shows ✓ or ✗ within 500ms (debounced network call)
- [ ] Permissions field is a checklist (no free-text); all known permissions listed
- [ ] AI chat response that includes form field suggestions automatically fills those fields in the form
- [ ] Clone button on agent/tool/skill/MCP row opens wizard pre-filled with that artifact's values
- [ ] Submitting creates the artifact and it appears in the relevant admin tab without page reload
- [ ] 586+ tests still pass; TypeScript strict 0 errors

---

## Backend API Summary

### New Endpoints (Plan 12-01)

| Method | Path | Purpose | Permission |
|--------|------|---------|------------|
| GET | `/api/admin/credentials` | List all users' OAuth connections | `registry:manage` |
| DELETE | `/api/admin/credentials/{user_id}/{provider}` | Admin revoke credential | `registry:manage` |

### New Endpoints (Plan 12-02)

| Method | Path | Purpose | Permission |
|--------|------|---------|------------|
| GET | `/api/admin/agents/check-name` | Name availability check | `registry:manage` |
| GET | `/api/admin/tools/check-name` | Name availability check | `registry:manage` |
| GET | `/api/admin/skills/check-name` | Name availability check | `registry:manage` |
| GET | `/api/admin/mcp-servers/check-name` | Name availability check | `registry:manage` |

---

## Phase 12 Success Criteria (from roadmap)

| # | Criterion | Plan |
|---|-----------|------|
| 1 | Admin can reach all admin functions from `/admin`; `/settings` has no admin controls | 12-01 |
| 2 | Wizard: select type → fill form with inline validation → preview JSON → submit → artifact appears | 12-02 |
| 3 | At least one starter template per artifact type | 12-02 |
| 4 | Live "name available" / "name taken" indicator while typing | 12-02 |
| 5 | Permissions selected from dropdown (not free-text) | 12-02 |
| 6 | Clone: wizard opens pre-filled from source artifact | 12-02 |

---

## Migration Notes

- No database migrations needed for Phase 12 — all changes are frontend + API layer
- Alembic migration count stays at 017 after Phase 12
- The `oauth_credentials` table (existing) is the data source for the admin credentials endpoint
- `/settings/channels` (personal OAuth link/unlink) is unchanged — users still manage their own creds there
