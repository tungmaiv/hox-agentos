---
phase: 22
plan: "01"
subsystem: backend-skills
tags:
  - skill-platform
  - sharing
  - marketplace
  - is_promoted
  - export
dependency_graph:
  requires:
    - "21-04: SkillDefinition model with security_score, source_hash"
    - "20-02: GET /api/skills endpoint established"
    - "19-01: UserArtifactPermission model + user_artifact_permissions table"
  provides:
    - "PATCH /api/admin/skills/{id}/promote (toggle is_promoted)"
    - "GET /api/skills with is_shared JOIN + promoted filter"
    - "GET /api/skills/{id}/export (ZIP download, any authenticated user)"
    - "POST/DELETE/GET /api/admin/skills/{id}/share* (admin sharing CRUD)"
    - "Alembic migration 025 (is_promoted column)"
  affects:
    - "22-02: Admin promote toggle UI consumes PATCH /promote"
    - "22-03: User skill export button consumes GET /{id}/export"
tech_stack:
  added:
    - "StreamingResponse for ZIP export"
    - "IntegrityError → 409 pattern for duplicate share"
    - "Correlated EXISTS subquery for is_shared field"
  patterns:
    - "EXISTS subquery on UserArtifactPermission for per-user sharing status"
    - "Router registration order: sharing endpoints before CRUD to prevent UUID shadowing"
key_files:
  created:
    - backend/alembic/versions/025_skill_is_promoted.py
    - backend/api/routes/admin_skill_sharing.py
    - backend/tests/api/test_admin_skill_promote.py
    - backend/tests/api/test_user_skill_export.py
    - backend/tests/api/test_skill_sharing.py
  modified:
    - backend/core/models/skill_definition.py
    - backend/core/schemas/registry.py
    - backend/api/routes/admin_skills.py
    - backend/api/routes/user_skills.py
    - backend/main.py
decisions:
  - "[22-01]: admin role in tests must be it-admin (not admin) — only it-admin maps to registry:manage in DEFAULT_ROLE_PERMISSIONS"
  - "[22-01]: admin_skill_sharing_router registered before admin_skills.router — literal path segments /share and /shares must resolve before /{skill_id} UUID catch-all"
  - "[22-01]: export endpoint uses get_user_db (not get_db) — consistent with other user-facing skill endpoints"
  - "[22-01]: SkillShareEntry.user_id comes from UserArtifactPermission.user_id (not a separate FK) — polymorphic artifact_type=skill pattern"
metrics:
  duration: "7 minutes"
  completed: "2026-03-08"
  tasks: 3
  files: 10
---

# Phase 22 Plan 01: Backend Foundations for Skill Sharing & Marketplace Summary

**One-liner:** Backend foundations for skill marketplace — is_promoted toggle, per-user is_shared JOIN, ZIP export, and admin skill-sharing CRUD endpoints.

## What Was Built

Three backend capabilities that Plans 22-02 and 22-03 build UI on top of:

**Task 1 — Migration 025 + ORM + Schemas**
- `025_skill_is_promoted.py`: Alembic migration adding `is_promoted BOOLEAN NOT NULL DEFAULT false` to `skill_definitions`
- `SkillDefinition.is_promoted`: New `Mapped[bool]` ORM column
- `SkillListItem`: Added `is_promoted: bool = False` and `is_shared: bool = False` fields
- `SkillDefinitionResponse`: Added `is_promoted: bool` field
- New schemas: `SkillShareRequest` (user_id) and `SkillShareEntry` (user_id + created_at)

**Task 2 — Promote Endpoint + GET /api/skills Enhancement**
- `PATCH /api/admin/skills/{id}/promote`: Toggles `is_promoted` boolean, requires `registry:manage` permission, returns `SkillDefinitionResponse`, 404 for unknown skill
- `GET /api/skills`: Now uses correlated EXISTS subquery on `UserArtifactPermission` to populate `is_shared` field; adds `promoted: bool | None = Query(None)` filter parameter

**Task 3 — Export Endpoint + Admin Sharing CRUD**
- `GET /api/skills/{id}/export`: Any authenticated user with `chat` permission can download a skill as an agentskills.io-compliant ZIP archive; uses existing `build_skill_zip()` from `skill_export.exporter`
- `admin_skill_sharing.py`: New router with 3 endpoints:
  - `POST /{skill_id}/share` → 201 + `SkillShareEntry`, 409 on duplicate
  - `DELETE /{skill_id}/share/{user_id}` → 204, 404 if not found
  - `GET /{skill_id}/shares` → `list[SkillShareEntry]` for all active shares

## Tests

11 new tests added across 3 test files (826 baseline → 837 total):

| File | Tests | Coverage |
|------|-------|----------|
| `test_admin_skill_promote.py` | 3 | promote (True), unpromote (False), 404 |
| `test_user_skill_export.py` | 2 | ZIP response + headers, 404 |
| `test_skill_sharing.py` | 5 | share 201, duplicate 409, list, revoke 204, revoke 404 |
| `test_user_skills.py` | +1 | is_shared + is_promoted fields present |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed admin test role: admin → it-admin**
- **Found during:** Task 2 (TDD RED phase — tests returned 403 instead of expected behavior)
- **Issue:** Tests used `roles=["admin"]` but `registry:manage` permission is mapped to `it-admin` in `security/rbac.py`'s `DEFAULT_ROLE_PERMISSIONS`. The `admin` role does not have `registry:manage`.
- **Fix:** Changed `make_admin_ctx()` to use `roles=["it-admin"], groups=["/it"]` in all new test files, consistent with `test_admin_skills.py` pattern
- **Files modified:** `tests/api/test_admin_skill_promote.py`, `tests/api/test_skill_sharing.py`

## Self-Check: PASSED

All created files exist on disk. All 3 task commits verified in git log.

| Item | Status |
|------|--------|
| `backend/alembic/versions/025_skill_is_promoted.py` | FOUND |
| `backend/api/routes/admin_skill_sharing.py` | FOUND |
| `backend/tests/api/test_admin_skill_promote.py` | FOUND |
| `backend/tests/api/test_user_skill_export.py` | FOUND |
| `backend/tests/api/test_skill_sharing.py` | FOUND |
| Commit d810995 (Task 1) | FOUND |
| Commit f1dc236 (Task 2) | FOUND |
| Commit 6385b35 (Task 3) | FOUND |
| 837 tests pass (826 baseline + 11 new) | PASSED |
