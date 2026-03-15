# Phase 27: Admin Registry Edit UI - Context

**Gathered:** 2026-03-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Admins can edit any registered artifact (agent, tool, MCP server, skill) through structured forms instead of raw JSON. Each registry type gets a detail page with consistent layout and type-specific tabs. MCP servers include connection testing. All list pages get dual pagination. Form validation uses Zod with inline errors.

Creating new registry types, new artifact capabilities, or builder enhancements are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Detail page layout
- Shared reusable layout component with common header (back link, name, status badge, timestamps) and type-specific tab content below
- Type-specific tabs:
  - **Agent:** Overview, Config, Permissions
  - **Tool:** Overview, Config, Permissions
  - **MCP Server:** Overview, Connection, Tools
  - **Skill:** Overview, Config, Scan Results (keep existing 3-tab structure)
- Detail pages are full-page routes at `/admin/{type}/[id]` (not slide-over or modal)
- Skills already have `/admin/skills/[id]` — extend pattern to agents, tools, mcp-servers
- List pages link to detail via clickable row; actions (delete, toggle status) stay in actions dropdown at row end

### Form field design
- Always-editable forms — fields are always interactive, no view/edit toggle
- Sticky save bar appears at bottom when changes are detected ("Unsaved changes [Discard] [Save]")
- Known JSONB config fields extracted as proper form inputs (e.g., agent system_prompt → textarea, model_alias → dropdown); unknown/extra config keys shown in collapsible "Advanced (raw JSON)" editor at bottom
- Markdown fields (instruction_markdown, system_prompt) use plain textarea with a Preview toggle that renders markdown
- `name` field is read-only after creation (identifier used in tool ACL, agent routing — changing breaks references)

### MCP connection testing
- "Test Connection" button on MCP Server's Connection tab
- Test uses current (possibly unsaved) form values — admin can tweak URL, test, then save once it works
- Backend endpoint: `POST /api/admin/mcp-servers/test` with `{ url, auth_config }` body
- Test verifies: SSE handshake + tools/list call (confirms reachability and MCP protocol compliance)
- Result displayed as inline card below button: success shows latency + tool count; failure shows error + hint
- MCP Tools tab shows read-only list of tools from the server (name, description, input schema) with Refresh button

### Validation & save UX
- Zod validation on field blur + full form validation on save
- Inline errors appear under each field immediately on blur
- Browser `beforeunload` + Next.js router guard for unsaved changes warning ("You have unsaved changes. Leave anyway?")
- Pessimistic save: Save button shows spinner, fields disabled during request; success → toast + timestamp refresh; error → toast with message, fields stay editable
- Dual pagination (top + bottom) on all list pages: same pagination component at top and bottom, showing page selector, page size dropdown, total count, both in sync

### Claude's Discretion
- Exact shared layout component API and prop structure
- Which existing admin page components to reuse vs create new
- Pagination component styling and page size options
- Toast notification implementation (existing or new)
- Exact Zod schema structure per registry type
- How to handle concurrent edit conflicts (optimistic locking optional)

</decisions>

<specifics>
## Specific Ideas

- Extend the existing skill detail page pattern (`/admin/skills/[id]`) as the template for other types
- MCP connection test should feel responsive — inline result card, not a modal or page reload
- "Advanced (raw JSON)" section should be collapsed by default so it doesn't intimidate non-technical admins

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/app/(authenticated)/admin/skills/[id]/page.tsx`: Existing skill detail page with 3-tab layout (Overview, Config, Scan Results) — extend as template
- `frontend/src/lib/admin-types.ts`: `RegistryEntry`, `RegistryEntryUpdate`, `RegistryEntryCreate` interfaces already defined
- `backend/api/routes/registry.py`: `PUT /api/registry/{id}` endpoint already exists for updates
- `backend/core/schemas/registry.py`: `RegistryEntryUpdate` Pydantic schema with type-specific update schemas (AgentDefinitionUpdate, ToolDefinitionUpdate, etc.)
- `backend/api/routes/mcp_servers.py`: `GET /api/admin/mcp-servers/{id}/health` — basic MCP health check exists

### Established Patterns
- List pages use `fetch("/api/registry?type=X")` with client-side filtering, search, pagination
- Snake-to-camel mapping via `mapSnakeToCamel()` / `mapArraySnakeToCamel()` from `admin-types.ts`
- All admin pages are `"use client"` components under `(authenticated)/admin/`
- Registry entries use unified `registry_entries` table with JSONB `config` for type-specific fields

### Integration Points
- New detail page routes: `/admin/agents/[id]`, `/admin/tools/[id]`, `/admin/mcp-servers/[id]`
- Existing list pages (agents, tools, mcp-servers, skills) need row click → navigate to detail
- New backend endpoint needed: `POST /api/admin/mcp-servers/test` for connection testing with unsaved values
- Dual pagination needs to be added to all 4 list pages

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 27-admin-registry-edit-ui*
*Context gathered: 2026-03-15*
