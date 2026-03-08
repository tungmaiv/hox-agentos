# Phase 22 Design: Skill Platform D — Sharing & Marketplace

**Date:** 2026-03-09
**Requirements:** SKMKT-01, SKMKT-02, SKMKT-03
**Depends on:** Phase 20 (catalog UI), Phase 21 (security hardening)

---

## What Already Exists (Reusable)

- `skill_export/exporter.py` — `build_skill_zip()` complete, tested
- `GET /api/admin/skills/{id}/export` — admin-only ZIP export route
- `ArtifactCardGrid` / `ArtifactTable` — already have `onExport` prop (not wired on user page)
- `artifact_permissions` + `user_artifact_permissions` ORM models
- `user_skills.py` — user-facing skills list returns all active skills (SKCAT-03 decision)

---

## Feature 1: Promoted Skills (SKMKT-01)

### Backend

- Add `is_promoted: bool` column to `skill_definitions` (migration 025, default `false`)
- `PATCH /api/admin/skills/{id}/promote` — toggle `is_promoted`, returns updated skill record
- `GET /api/skills` — add `isPromoted` field to `SkillListItem` response schema
- Promoted filter: `GET /api/skills?promoted=true` — returns only promoted skills (for section query)

### Admin UI

- Promoted toggle button in the skill detail drawer (star/bookmark icon)
- Single click → PATCH → optimistic UI update
- Promoted state shown on skill card (badge or star icon)

### User Catalog (`/skills` page)

- "Promoted" curated section at the top of the page
- Shows promoted skills in a horizontal scroll row or small 3-column grid
- Section hidden when no promoted skills exist
- Main skill grid unchanged below the promoted section

---

## Feature 2: Export Download (SKMKT-02)

### Backend

- `GET /api/skills/{id}/export` — user-facing route
- Requires `chat` permission (same as `list_user_skills`)
- Reuses `build_skill_zip()` from `skill_export/exporter.py`
- Returns `StreamingResponse` with `Content-Disposition: attachment; filename="{name}-{version}.zip"`
- Skill must be `status='active'` and `is_active=True` — 404 otherwise

### User Catalog (`/skills` page)

- Wire `onExport` prop on `ArtifactCardGrid` (same pattern as admin page)
- Handler: `fetch(/api/skills/{id}/export)` → create blob URL → programmatic download
- No confirmation dialog — immediate download

---

## Feature 3: Skill Sharing (SKMKT-03)

### Design Decision: Additive sharing, not visibility restriction

Consistent with SKCAT-03 (all active skills visible to all users), sharing is additive: a "Shared with me" section shows skills explicitly granted to the current user via `user_artifact_permissions`. No skill has its visibility restricted. Sharing is admin-only.

### Backend

- `POST /api/admin/skills/{id}/share` — body: `{user_id: UUID}` → create `UserArtifactPermission(artifact_type='skill', artifact_id=id, user_id=user_id, allowed=True, status='active')`; 409 if already shared
- `DELETE /api/admin/skills/{id}/share/{user_id}` — revoke sharing (delete the row)
- `GET /api/admin/skills/{id}/shares` — list all users the skill is shared with (returns `[{user_id, granted_at}]`)
- `GET /api/skills/shared-with-me` — user-facing: queries `user_artifact_permissions` for current user's `user_id` with `artifact_type='skill'`, joins to `skill_definitions`, returns `list[SkillListItem]`

### Admin UI

- "Shared with" panel in the skill detail drawer (below metadata)
- Shows current share list with user_id and revoke button
- Text input + "Share" button to add a user by UUID (or username if user lookup is available)

### User Catalog (`/skills` page)

- "Shared with me" section below the main grid
- Fetches from `GET /api/skills/shared-with-me`
- Hidden when empty
- Same card component as main grid

---

## Plan Breakdown

### Plan 22-01: Backend Foundations
- Migration 025: `is_promoted` column
- `PATCH /api/admin/skills/{id}/promote` endpoint
- `GET /api/skills/{id}/export` user-facing route
- `POST /api/admin/skills/{id}/share`, `DELETE /api/admin/skills/{id}/share/{user_id}`, `GET /api/admin/skills/{id}/shares`
- `GET /api/skills/shared-with-me` endpoint
- `SkillListItem` schema: add `isPromoted` field
- Tests for all new endpoints

### Plan 22-02: Admin UI
- Promoted toggle button in skill detail drawer (admin skills page)
- Promoted badge on skill cards in admin table/grid
- "Shared with" panel in skill detail drawer (list + revoke + add-user input)

### Plan 22-03: User Catalog UI
- "Promoted" curated section at top of `/skills` page
- Export download button wired via `onExport` on `ArtifactCardGrid`
- "Shared with me" section below main grid

---

## Security Notes

- Promote endpoint: requires `registry:manage` (admin/developer/it-admin roles)
- User export endpoint: requires `chat` permission; skill must be active
- Share/unshare endpoints: requires `registry:manage`
- `shared-with-me` endpoint: reads `user_artifact_permissions` filtered by JWT `user_id` — isolation guaranteed by parameterized query

---

## Migration Plan

- Migration 025: single `ALTER TABLE skill_definitions ADD COLUMN is_promoted BOOLEAN NOT NULL DEFAULT false`
- No data migration needed (all existing skills default to `is_promoted=false`)
- Next migration after 025 will be 026
