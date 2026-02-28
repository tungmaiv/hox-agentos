# Phase 6: Extensibility Registries - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Admins and developers can manage the platform's agents, tools, skills, and MCP servers as runtime artifacts through database-backed registries with granular permissions. This phase replaces the existing in-memory `tool_registry.py` dict and `tool_acl` table with a unified database-backed registry system. CRUD APIs, per-artifact per-role permissions (with per-user overrides), and a frontend admin UI are in scope. Adding new artifact types, marketplace features, or plugin sandboxing are NOT in scope.

</domain>

<decisions>
## Implementation Decisions

### Registry data model
- Separate tables per artifact type: `agent_registry`, `tool_registry`, `skill_registry`, `mcp_server_registry` — each with type-specific columns (e.g. `sandbox_required` on tools, `sse_url` on MCP servers)
- Each table carries: name, description, version (semver string), status (enabled/disabled), required_permissions, created_at, updated_at, plus a JSONB `config` column for arbitrary type-specific settings (timeouts, retry policies, custom params)
- Status tracking: enabled/disabled toggle plus `last_seen_at` timestamp updated on each successful call — frontend shows stale indicators based on this
- Support multiple versions of the same artifact with an active flag — allows rollback
- Existing `tool_registry.py` in-memory dict is replaced entirely — becomes a thin cache wrapper that reads from DB
- Existing `tool_acl` table is replaced by the new `artifact_permissions` table — migration script moves existing rows

### CRUD API design
- Per-type REST endpoints: `/api/registry/tools`, `/api/registry/agents`, `/api/registry/skills`, `/api/registry/mcp-servers`
- Standard CRUD operations: GET list, GET by ID, POST create, PUT update, DELETE
- Hot registration via DB insert + cache invalidation — no backend restart needed. Runtime cache has short TTL; DB changes propagate within TTL window
- Bulk disable/enable supported via PATCH endpoint accepting list of IDs + new status — useful for maintenance windows
- Role-based write access: admin and developer can create/register new artifacts; only admin can disable, re-enable, or delete

### Permission model
- Per-role permissions as the default, with per-user overrides for exceptions
- New `artifact_permissions` table maps (artifact_type, artifact_id, role) to allowed/denied — replaces `tool_acl` entirely
- Per-user override table for individual grants/revocations beyond role defaults
- Default permissions on new artifact registration: admin and developer roles can use immediately; employee and viewer roles need explicit permission grants
- Permission changes are staged as "pending" until admin confirms/applies — prevents accidental changes
- Gate 3 (ACL check in `agui_middleware.py`) reads from new `artifact_permissions` table instead of `tool_acl`
- Changes take effect only after admin applies — staged model

### Runtime integration
- In-memory cache with TTL (e.g., 60s) loaded on startup — fast lookups, minimal DB queries during agent execution
- Full reload on TTL expiry — at ~100 users with dozens of artifacts, this is simple and fast
- When an artifact is disabled mid-workflow: current run completes gracefully, future invocations in new runs are blocked
- Cache invalidation on DB changes ensures new registrations propagate within TTL

### Frontend UI
- Dedicated `/admin` route, visible only to admin and developer roles — separate from user-facing `/settings`
- Tabs for Tools, Agents, Skills, MCP Servers
- Supports both table view and card grid view — admin/developer can toggle between them
- Table view columns: name, type, version, status (badge), last_seen
- Table row actions: edit, disable/enable, delete
- Filters by type and status
- Permission management available in two places:
  - Per-artifact permission panel: when editing an artifact, a "Permissions" section shows role matrix (checkboxes per role) + per-user overrides list. Changes staged until Apply
  - Global permissions page: full matrix of all artifacts x all roles for batch editing
- MCP server connectivity: colored dot based on `last_seen_at` — green (< 5 min), yellow (< 30 min), red (> 30 min or never). No active polling

### Claude's Discretion
- Cache TTL duration (suggested ~60s, Claude can adjust)
- Exact DB schema column types and index strategy
- Migration script implementation for tool_acl to artifact_permissions
- UI component library choices and layout details
- Exact Alembic migration numbering and structure
- Error handling and validation patterns for CRUD endpoints

</decisions>

<specifics>
## Specific Ideas

- Both table and card grid views should be available with a view toggle — admin/developer picks their preferred layout
- Permission management should be accessible both per-artifact (inline edit) and globally (full matrix page)
- The staged permission apply model prevents accidental changes — admin must explicitly confirm
- Multiple artifact versions with an active flag enables safe rollback after updates

</specifics>

<deferred>
## Deferred Ideas

- Artifact marketplace / community sharing — future feature
- Plugin sandboxing for third-party artifacts — belongs in Phase 7 (Hardening)
- Live health check ping button for MCP servers — can be added later if needed
- Artifact dependency tracking (tool X requires MCP server Y) — future enhancement

</deferred>

---

*Phase: 06-extensibility-registries*
*Context gathered: 2026-02-28*
