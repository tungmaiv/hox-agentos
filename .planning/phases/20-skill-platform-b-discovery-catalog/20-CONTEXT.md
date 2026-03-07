# Phase 20: Skill Platform B — Discovery & Catalog - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Add full-text search, filtering, and sorting to the skill catalog (both user-facing and admin); add name search + handler_type + status filtering to the admin tool catalog; harden the external registry browse with paginated results and a detail drawer before import. One-click import triggers the existing SecurityScanner + quarantine flow. Creating new skills, managing dependencies, and marketplace features are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Catalog surface — user /skills page
- The user /skills page becomes a full catalog with FTS + filters — not a "Coming soon" stub
- Shows ALL active skills (no ACL join) — users can browse and discover even skills they may not yet have access to
- Filters visible to users: category + skill_type (instructional/procedural) + status
- Layout: same ArtifactCardGrid + SkillMetadataPanel as the admin view — admin-only actions (edit/delete/review) are hidden for regular users
- Sort options: Newest (created_at DESC) / Oldest (created_at ASC) / Most Used (usage_count DESC)

### FTS implementation
- PostgreSQL tsvector with `'simple'` language config (as specified in ROADMAP for Vietnamese support)
- FTS applies to name + description columns
- Applies to both the user catalog (/skills) and the admin catalog (/admin/skills)

### Usage tracking
- Add `usage_count` INTEGER column to `skill_definitions` (migration 022 — next available, current head is 83f730920f5a)
- Increment `usage_count` in the skill executor on every invocation — fire-and-forget UPDATE, no Celery task
- No `usage_count` on `tool_definitions` — tools are admin infrastructure, filter + search only

### External registry browse — detail before import
- Clicking a registry skill card opens a side drawer/sheet showing full skill metadata: name, description, version, category, tags, license, author, source URL
- Import button lives inside the drawer (not just on the card)
- Existing confirm → importing → result dialog flow is preserved within the drawer
- After import: stay in registry browse, show security scan result inline (existing result phase behavior)
- Pagination: 20 skills per page + "Load More" button (cursor-based append) — replaces current unbounded fetch

### Tool catalog filter UI
- Inline filter bar above the existing tools table: `[Search by name...]` `[handler_type dropdown]` `[status dropdown]`
- Name search: debounced on keystroke, 300ms delay — consistent with SkillStoreBrowse's existing pattern
- handler_type options: all / backend / mcp / sandbox
- Filter logic added to `GET /api/admin/tools` endpoint (new `name` and `handler_type` query params)

### Claude's Discretion
- Exact tsvector column approach (stored generated column vs. app-level to_tsvector() in WHERE clause)
- GIN index creation details
- Drawer component choice (Sheet from shadcn/ui or custom)
- Exact cursor pagination implementation (offset vs. keyset)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ArtifactCardGrid` (frontend/src/components/admin/artifact-card-grid.tsx): reuse for user /skills catalog; admin-only actions are already conditionally rendered
- `SkillMetadataPanel` (frontend/src/components/admin/): renders in card-grid view — confirmed to reuse for user catalog
- `SkillStoreBrowse` (frontend/src/components/admin/skill-store-browse.tsx): extend with detail drawer + Load More pagination; existing confirm/import/result flow preserved
- `SkillStoreRepositories` (frontend/src/components/admin/skill-store-repositories.tsx): already exists for managing registry URLs

### Established Patterns
- Debounced search at 300ms: already in SkillStoreBrowse — use same hook pattern for new filter bars
- `GET /api/admin/skills` filters: existing status/skill_type/version query params — add `q` (FTS) + `category` + `author` + `sort`
- `GET /api/admin/tools` filters: existing status/version — add `name` (debounced search) + `handler_type`
- Migration chain: current head `83f730920f5a` — next migration is **022**
- JSON().with_variant(JSONB(), 'postgresql') pattern on all JSONB columns (for SQLite test compat)

### Integration Points
- `SkillDefinition` model: has `category`, `tags`, `status`, `created_by`, `created_at` — all filterable; `description` + `name` → FTS target; add `usage_count` column
- `ToolDefinition` model: has `handler_type`, `status`, `name` — all already present, just need query param wiring
- Skill executor (wherever skills are invoked): add `usage_count` increment after successful execution
- `/api/skill-repos/browse` endpoint: add `limit` + `cursor` query params for pagination support

</code_context>

<specifics>
## Specific Ideas

- The user /skills page should feel like a real product catalog — the card-grid + metadata panel pattern from admin is the right starting point
- "Sort by usage" is a first-class citizen: the usage_count column must exist from day one so the catalog is immediately useful
- The detail drawer before import should show enough information that an admin can make a confident yes/no decision without having to download the ZIP first
- Consistent 300ms debounce across all catalog search bars — user and admin

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 20-skill-platform-b-discovery-catalog*
*Context gathered: 2026-03-07*
