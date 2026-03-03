# Phase 14: Ecosystem Capabilities - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Agents and users can introspect what the platform can do, any OpenAPI-described service can be wired in as an MCP server in minutes, and external skill repositories can be browsed, imported, and exported in a standard format. Four modules: capabilities tool (ECO-01), OpenAPI bridge (ECO-02), skill repositories (ECO-03/04/05), skill export (ECO-06). No Docker container generation for MCP servers, no per-user OAuth, no repository authentication, no chat-based API-to-MCP interaction.

</domain>

<decisions>
## Implementation Decisions

### Capabilities chat presentation (ECO-01)
- A2UI interactive card — custom `CapabilitiesCard` component, not plain markdown
- Collapsed sections with count badges — four sections (Agents, Tools, Skills, MCP Servers) collapsed by default, count badge on each, user expands to see list
- Dual output — agent returns A2UI card for web chat AND markdown fallback for channel delivery (Telegram, Teams); `format_for_channel()` renders the fallback automatically
- Static list — names + one-line descriptions per item, no clickable/expandable items; users ask the agent for details on specific items

### OpenAPI Connect flow (ECO-02)
- Multi-step wizard — Step 1: paste URL + fetch spec; Step 2: select endpoints; Step 3: name server + configure auth. Consistent with Phase 12 wizard pattern
- Wizard lives under MCP Servers tab — "Connect OpenAPI" button at top of existing MCP Servers page. No separate tab.
- Endpoints grouped by OpenAPI tags — collapsible tag groups with checkboxes at group and endpoint level. Method badges (GET=green, POST=blue, PUT=orange, DELETE=red) + path + summary
- Auth type selector — dropdown: Bearer token, API key in custom header, Basic auth (user:pass), or No auth. Covers most API patterns.

### Skill Store placement & browse (ECO-03/04/05)
- Tab in /admin — new "Skill Store" tab in admin layout. Keeps /admin as the single operations hub (Phase 12 principle)
- Sub-tabs within the tab — "Repositories" sub-tab (admin-only, requires `registry:manage`) and "Browse" sub-tab (all users, requires `chat`). Non-admins only see Browse.
- Card grid with metadata — skill name, one-line description, version badge, repository source, author, license. 3 cards per row. Search bar at top filters by name/description.
- Import dialog with details — click "Import" opens modal showing: skill name, security scan score, recommendation (approve/review/reject), and confirmation button. Admin approves later from Skills tab.

### Skill export (ECO-06)
- Per-row action in Skills tab — small download/export icon button on each skill row in the admin Skills table
- Direct download, no preview — click Export triggers immediate browser download of the .zip file
- Filename: `name-version.zip` — e.g., `morning-digest-1.0.zip`; includes version for side-by-side exports
- Export available for any skill status — works for active, pending_review, and disabled skills (useful for review/sharing before approval)

### Claude's Discretion
- A2UI CapabilitiesCard component styling and animation
- Exact color codes for method badges in endpoint picker
- Wizard step validation UX (inline vs on-next-step)
- Security scan score display format in import dialog
- Card grid responsive breakpoints for different screen sizes

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `gateway/tool_registry.py`: `list_tools()`, `get_tool()` — use for capabilities tool to enumerate all tools
- `security/rbac.py`: `batch_check_artifact_permissions()` — filter capabilities response per user's allowed artifacts
- `skills/importer.py`: `SkillImporter.import_from_url()` — reuse directly for repo import flow
- `skills/security_scanner.py`: `SecurityScanner.scan()` — run on every repo-imported skill
- `mcp/registry.py`: `MCPToolRegistry.refresh()` — hot-register after OpenAPI endpoints are created
- `security/credentials.py`: `encrypt_token()`/`decrypt_token()` — AES-256 for OpenAPI API keys
- A2UI pattern in `frontend/src/components/a2ui/` — follow existing card component patterns for CapabilitiesCard
- Phase 12 creation wizard at `/admin/create` — reuse multi-step form patterns for OpenAPI wizard
- Catch-all admin proxy at `frontend/src/app/api/admin/[...path]/route.ts` — automatically covers new backend routes; needs binary response fix for zip export

### Established Patterns
- DB-backed registries with `status` field (active/disabled/deprecated) — follow same pattern for `skill_repositories`
- Admin endpoints require `registry:manage` RBAC; user endpoints require `chat` — same split for skill repos
- Import quarantine: imported artifacts enter `pending_review`; admin approves via existing review endpoint
- `tool_definitions.handler_type` currently: `backend | mcp | sandbox` — add `openapi_proxy` value
- Sub-tab pattern not yet established — Phase 14 introduces this for Skill Store (Repositories + Browse)

### Integration Points
- `mcp_servers` table: add `openapi_spec_url` column (migration 019)
- `_LEGACY_REGISTRY` in `tool_registry.py`: seed `system.capabilities` tool definition
- `_pre_route` keyword routing in `master_agent.py`: add `capabilities`/`what can you do` keywords
- Admin layout tabs array in `frontend/src/app/admin/layout.tsx`: add "Skill Store" entry
- MCP Servers page: add "Connect OpenAPI" button

</code_context>

<specifics>
## Specific Ideas

- Design doc at `docs/plans/2026-03-04-phase14-ecosystem-capabilities-design.md` covers full architecture — module structure, DB schema, API endpoints, plan breakdown. Planner should read it as primary reference.
- Skill platform proposal at `docs/design/skill-tool-platform-proposal.md` has detailed gap analysis, Agent Skills standard mapping, and security invariants.
- OpenAPI endpoint selector should feel like a developer tool — method badges with color coding, path shown prominently, grouped by tags for large APIs.
- Import dialog should make the security scan visible — users should see WHY a skill is flagged as safe or risky before confirming import.
- Capabilities card in chat should be informative but not overwhelming — collapsed sections prevent cognitive overload for users with many registered artifacts.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 14-ecosystem-capabilities*
*Context gathered: 2026-03-04*
