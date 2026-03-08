# Phase 22: Skill Platform D — Sharing & Marketplace - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Skills can be promoted for curated visibility, exported as agentskills.io-compliant ZIP downloads, and shared between users via the existing `UserArtifactPermission` system. This phase adds the `is_promoted` column, a promoted section to the user catalog, a download endpoint, and admin skill-sharing UI. Skill builder improvements and enhanced security scanning are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Promoted section layout (SKMKT-01)
- The promoted curated section renders **above** the main skill grid on the user `/skills` page — a "Featured Skills" header followed by a horizontal row of promoted cards
- Section is **hidden entirely** when no skills are promoted — no empty state to manage
- Promoted cards use the **same ArtifactCardGrid card** with a small "Featured" badge added — no new card component needed
- Admin promotes/unpromotes a skill from the **existing card action menu** (⋮ menu) in `/admin/skills` — consistent with the Promote/Unpromote toggle style of other admin actions

### Export download (SKMKT-02)
- Export button placement: **Claude's discretion** (user did not select this area for discussion)
- Who can export: **Claude's discretion** — follow requirements (SKMKT-02 says "users" can export from catalog)

### Sharing flow (SKMKT-03)
- Admin triggers sharing from the **card action menu** (⋮ menu) on admin skill cards — "Share with user..." action, consistent with Promote placement
- The share dialog contains a **username/email search field** that queries `GET /api/admin/users` — admin types name or email, selects from dropdown, and adds the share
- The dialog also **lists current shares** with a revoke button per user — admin can add and remove access from the same surface
- Shared skills appear in the recipient's `/skills` catalog **in the main grid with a 'Shared' badge** — no separate filter tab or section needed
- Sharing uses the existing `UserArtifactPermission` table with `artifact_type='skill'` — no new tables

### Claude's Discretion
- Exact badge styling for "Featured" and "Shared" tags — consistent with existing badge patterns in the UI
- Whether promoted skills also appear in the main grid below (deduplicated) or only in the featured section
- Export endpoint location (admin-only or user-facing) — follow SKMKT-02 requirement (user-facing from catalog)
- Pagination/scroll behavior of the horizontal promoted row (wrap to grid or horizontal scroll)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ArtifactCardGrid` (`frontend/src/components/admin/artifact-card-grid.tsx`): reuse for promoted section with badge prop; admin-only actions already conditionally rendered
- `UserArtifactPermission` (`backend/core/models/user_artifact_permission.py`): `artifact_type`, `artifact_id`, `user_id`, `allowed`, `status` — no new table needed for sharing
- `admin_permissions.py` (`backend/api/routes/admin_permissions.py`): existing per-user override endpoints — new sharing endpoints follow the same pattern
- `user_skills.py` (`backend/api/routes/user_skills.py`): user-facing skills list — extend to include promoted section data and shared badge logic
- `skills/importer.py` (`backend/skills/importer.py`): already handles ZIP import/parse — exporter logic mirrors importer in reverse
- `admin_skills.py` router: has `/import/zip` POST — add `/export/{skill_id}` GET returning `StreamingResponse`

### Established Patterns
- Card action menus (⋮): admin already has promote/edit/delete/clone actions — add "Share with user..." to same menu
- `UserArtifactPermission.status='active'` (no staged apply needed for sharing — immediate grant on add)
- `GET /api/admin/users` endpoint: exists for user search — use for recipient search in share dialog
- Badge patterns: existing status badges (`active`, `inactive`, `review`) in admin UI — "Featured" and "Shared" follow same badge component

### Integration Points
- `SkillDefinition` model: needs `is_promoted BOOLEAN` column (migration 025)
- User `/skills` page: add promoted section above `ArtifactCardGrid` — fetch promoted skills from `GET /api/skills?promoted=true` or a separate `/api/skills/promoted` endpoint
- Admin `/admin/skills` card actions: add "Promote/Unpromote" toggle and "Share with user..." modal trigger
- Sharing dialog: new frontend modal component (can reuse Dialog from shadcn/ui already in project)

</code_context>

<specifics>
## Specific Ideas

- No specific references given — open to standard patterns for catalog promotion sections (similar to app stores or package registries)
- "Shared" badge should be clearly distinct from "Featured" badge to avoid confusion

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 22-skill-platform-d-sharing-marketplace*
*Context gathered: 2026-03-09*
