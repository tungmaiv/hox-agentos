---
phase: 20-skill-platform-b-discovery-catalog
plan: "02"
subsystem: backend-api
tags: [skill-catalog, fts, search, filtering, pagination]
dependency_graph:
  requires: [20-01]
  provides: [SKCAT-01, SKCAT-02, SKCAT-03, SKCAT-04]
  affects: [20-03, 20-04]
tech_stack:
  added: []
  patterns:
    - "SQLAlchemy FTS: func.to_tsvector('simple', ...).op('@@')(func.plainto_tsquery('simple', q))"
    - "offset-based cursor pagination: items[cursor:cursor+limit]"
    - "ilike substring filter: ToolDefinition.name.ilike(f'%{name}%')"
key_files:
  created: []
  modified:
    - backend/api/routes/admin_skills.py
    - backend/api/routes/user_skills.py
    - backend/api/routes/admin_tools.py
    - backend/skill_repos/routes.py
    - backend/skill_repos/service.py
    - backend/skill_repos/schemas.py
    - backend/tests/api/test_user_skills.py
decisions:
  - "[20-02]: user catalog (GET /api/skills) shows all active skills without ACL join — ACL enforced only at run time per SKCAT-03 decision from CONTEXT.md"
  - "[20-02]: browse_skills uses in-memory offset pagination (items[cursor:cursor+limit]) — index is already in-memory from cached_index; no DB-level OFFSET needed"
  - "[20-02]: SkillBrowseItem convenience fields (category, tags, license, author, source_url) extracted from metadata dict — avoids frontend having to unwrap metadata for display"
metrics:
  duration: "~8 minutes"
  completed_date: "2026-03-07"
  tasks_completed: 2
  files_modified: 7
---

# Phase 20 Plan 02: API Search Filtering & Pagination Summary

FTS (plainto_tsquery 'simple'), category/author/sort, handler_type, and limit+cursor pagination added to all four catalog API endpoints powering the skill discovery UIs.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | FTS + category + author + sort to admin/user skill routes | e677fc5 | admin_skills.py, user_skills.py, test_user_skills.py |
| 2 | name+handler_type to admin_tools; limit+cursor to browse_skills | 83c8032 | admin_tools.py, skill_repos/routes.py, service.py, schemas.py |

## What Was Built

### Task 1 — Skill route FTS + filtering

`GET /api/admin/skills` new params: `q` (FTS via `plainto_tsquery('simple', ...)`), `category`, `author` (UUID string → filters `created_by`), `sort` (newest/oldest/most_used).

`GET /api/skills` (user catalog) new params: `q`, `category`, `skill_type`, `sort`. The ACL join (`batch_check_artifact_permissions`) was removed per SKCAT-03 decision — the catalog shows all active skills; ACL is only enforced at execution time.

### Task 2 — Tool filter + browse pagination

`GET /api/admin/tools` new params: `name` (ilike substring), `handler_type` (exact match on backend/mcp/sandbox).

`GET /api/skill-repos/browse` new params: `limit` (1-100, default 20), `cursor` (offset, default 0). Pagination is applied as `items[cursor:cursor+limit]` in the service layer after building the full filtered list from cached_index.

`SkillBrowseItem` schema extended with convenience fields: `category`, `tags`, `license`, `author`, `source_url` — extracted from the `metadata` dict to simplify frontend display.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test to match intentional behavior change**
- **Found during:** Task 1
- **Issue:** `test_list_skills_excludes_denied` asserted that a skill denied by `artifact_permissions` would be hidden from `GET /api/skills`. This was the OLD behavior. The plan explicitly removes the ACL join per SKCAT-03 (user catalog shows ALL active skills).
- **Fix:** Renamed test to `test_list_skills_shows_all_active_regardless_of_acl` and updated assertion — denied skill is NOW visible in catalog (ACL only enforced at run time).
- **Files modified:** `backend/tests/api/test_user_skills.py`
- **Commit:** e677fc5

## Verification Results

```
794 passed, 1 skipped in 18.92s
```

Key pattern spot-checks:
- `plainto_tsquery` present in both `admin_skills.py` and `user_skills.py`
- `handler_type` filter in `admin_tools.py`
- `limit.*cursor` pagination in `skill_repos/routes.py`

## Self-Check

### Files Exist

- [x] `backend/api/routes/admin_skills.py` — contains `plainto_tsquery`
- [x] `backend/api/routes/user_skills.py` — contains `plainto_tsquery`
- [x] `backend/api/routes/admin_tools.py` — contains `handler_type`
- [x] `backend/skill_repos/routes.py` — contains `limit`, `cursor` params
- [x] `backend/skill_repos/service.py` — contains `limit`, `cursor` in signature and slice
- [x] `backend/skill_repos/schemas.py` — `SkillBrowseItem` has `category`, `tags`, `license`, `author`, `source_url`

### Commits Exist

- [x] e677fc5 — Task 1
- [x] 83c8032 — Task 2

## Self-Check: PASSED
