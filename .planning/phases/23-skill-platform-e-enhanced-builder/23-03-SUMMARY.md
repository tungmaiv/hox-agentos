---
phase: 23-skill-platform-e-enhanced-builder
plan: "03"
subsystem: skill-platform
tags:
  - skill-repos
  - pgvector
  - embeddings
  - find-similar
  - fork
  - frontend
dependency_graph:
  requires:
    - 23-01  # SkillRepoIndex ORM model, ArtifactBuilderState extension
  provides:
    - search_similar() service function
    - POST /api/admin/skill-repos/search-similar endpoint
    - skill_repo_index population in sync_repo()
    - Find Similar UI in artifact builder right panel
    - Fork action + Edit JSON toggle
  affects:
    - skill_repos/service.py
    - skill_repos/routes.py
    - skill_repos/schemas.py
    - frontend artifact builder UX
tech_stack:
  added:
    - pgvector cosine_distance() query pattern for skill similarity
  patterns:
    - TDD RED→GREEN for search_similar (mock AsyncSession pattern)
    - SidecarEmbeddingProvider embedded during sync_repo (admin-triggered, not hot path)
    - Route ordering: /search-similar declared before /{repo_id} catch-all
key_files:
  created: []
  modified:
    - backend/skill_repos/service.py
    - backend/skill_repos/routes.py
    - backend/skill_repos/schemas.py
    - backend/tests/skills/test_similar_skills.py
    - frontend/src/components/admin/artifact-builder-client.tsx
decisions:
  - "[23-03]: search_similar() resolves repository_name via secondary SkillRepository query (not SQL join) — preserves async simplicity, repo set is small"
  - "[23-03]: sync_repo() deletes+reinserts skill_repo_index rows on each sync — ensures stale entries removed; sidecar unavailability inserts row with embedding=None (search gracefully skips)"
  - "[23-03]: Route /search-similar declared before /{repo_id} pattern to avoid FastAPI routing conflict"
  - "[23-03]: Find Similar button visible only when both name and description fields are present in draft"
  - "[23-03]: Fork action is optimistic frontend-only — copies name+description into draft, sets fork_source; builder agent re-validates on next message"
  - "[23-03]: Edit JSON toggle pre-fills textarea with JSON.stringify(draft, null, 2); Parse button validates before applying"
metrics:
  duration_minutes: 8
  tasks_completed: 2
  files_modified: 5
  tests_added: 2
  tests_passing: 849
  completed_date: "2026-03-09"
---

# Phase 23 Plan 03: Similar Skill Discovery + Fork Summary

**One-liner:** pgvector cosine search over skill_repo_index with "Find Similar" + "Fork" UI in artifact builder right panel

## What Was Built

### Backend (Task 1 — TDD)

**`search_similar()` in `backend/skill_repos/service.py`:**
- Queries `skill_repo_index` using pgvector `cosine_distance()` ordered ascending (nearest first)
- Skips rows with `embedding=NULL` via `WHERE embedding IS NOT NULL`
- Resolves `repository_name` via a secondary `SkillRepository` query (no SQL join)
- Returns `list[dict]` with keys: `name`, `description`, `repository_name`, `source_url`, `category`, `tags`
- Returns empty list when no embedded rows exist — never raises

**`sync_repo()` extension in `backend/skill_repos/service.py`:**
- Deletes all existing `skill_repo_index` rows for the repository before re-inserting
- For each skill in the fetched index: embeds `"name description"` via `SidecarEmbeddingProvider`
- Graceful fallback: if sidecar unavailable, inserts row with `embedding=None`
- Logs `skill_repo_index_synced` with count

**`POST /api/admin/skill-repos/search-similar` in `backend/skill_repos/routes.py`:**
- Body: `{name: str, description: str, top_k: int = 5}`
- Embeds name+description text via `SidecarEmbeddingProvider`, calls `search_similar()`
- Returns `{results: list[SimilarSkillItem]}`
- Declared **before** `/{repo_id}` routes to avoid FastAPI path conflicts
- Auth: `require_registry_manager` (existing admin dependency)
- Handles sidecar failure gracefully: returns `{results: []}`

**New schemas in `backend/skill_repos/schemas.py`:**
- `SimilarSkillItem` — individual result with name, description, repository_name, source_url, category, tags
- `SearchSimilarRequest` — input with name, description, top_k
- `SearchSimilarResponse` — wraps `results: list[SimilarSkillItem]`

### Frontend (Task 2)

**`frontend/src/components/admin/artifact-builder-client.tsx`:**
- Extended `BuilderState` interface with `similar_skills`, `fork_source`, `handler_code`, `security_report`
- Added `SimilarSkill` interface for type-safe result cards
- `handleFindSimilar()`: POSTs to `/api/admin/skill-repos/search-similar`, updates `similarSkills` state
- `handleFork(skill)`: copies `name`+`description` into `artifact_draft`, sets `fork_source` as `"name@source_url"`, collapses results panel
- "Find Similar" button visible only when draft has both `name` and `description` (truthy strings)
- Similar skills rendered as cards with name (bold), description (2-line clamp), repository name (muted), Fork button
- Empty results show "No similar skills found" message
- Fork attribution badge shown when `builderState.fork_source` is set
- "Edit JSON" toggle below preview when `is_complete`; textarea pre-filled with `JSON.stringify(draft, null, 2)`; "Parse" button validates and applies; inline parse error on failure

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test assertion for top_k limit was testing mock behavior, not SQL**
- **Found during:** Task 1 GREEN phase
- **Issue:** Test asserted `len(results2) <= 2` with `top_k=2`, but mock returns all rows regardless of SQL LIMIT. The LIMIT is applied by pgvector at the DB level, not in Python.
- **Fix:** Changed mock to return only 2 rows (simulating DB honouring LIMIT), asserted `len(results2) == 2`
- **Files modified:** `tests/skills/test_similar_skills.py`
- **Commit:** d6798c9

## Tests

| Test | Status | Notes |
|------|--------|-------|
| `test_search_similar_returns_top_k` | PASS | Verifies result shape, keys, repository_name resolution |
| `test_fork_external_skill` | PASS | Verifies fork_source format and required dict keys |
| Full suite | 849 passed, 1 skipped | Up from 845 before this plan |

## Self-Check

**Files exist:**
- `backend/skill_repos/service.py` contains `search_similar` — verified
- `frontend/src/components/admin/artifact-builder-client.tsx` contains `Find Similar` — verified

**Commits exist:**
- `d6798c9` — Task 1: backend service + route + schemas + tests
- `d7ded60` — Task 2: frontend Find Similar + fork + Edit JSON
