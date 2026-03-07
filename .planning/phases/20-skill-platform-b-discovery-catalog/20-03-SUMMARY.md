---
phase: 20-skill-platform-b-discovery-catalog
plan: "03"
subsystem: frontend/skill-catalog
tags: [skill-catalog, frontend, filter-ui, fts, artifact-card-grid]
dependency_graph:
  requires: [20-02]
  provides: [SKCAT-01, SKCAT-02, SKCAT-03]
  affects: [frontend/skills-page, frontend/admin-skills-page, frontend/admin-tools-page]
tech_stack:
  added: []
  patterns:
    - "300ms debounce useEffect pattern for filter inputs"
    - "ArtifactCardGrid read-only mode by omitting all action props"
    - "Client-side filtering on fetched items for admin catalogs"
    - "Server-side FTS via /api/skills?q= for user catalog"
key_files:
  created: []
  modified:
    - frontend/src/app/(authenticated)/skills/page.tsx
    - frontend/src/app/(authenticated)/admin/skills/page.tsx
    - frontend/src/app/(authenticated)/admin/tools/page.tsx
decisions:
  - "User skills page uses ArtifactCardGrid + SkillMetadataPanel without any admin action props — locked in CONTEXT.md"
  - "Admin catalog filters are client-side (no refetch) — acceptable for small admin datasets (~100 skills)"
  - "User catalog FTS is server-side (requires Postgres GIN index from 20-01)"
metrics:
  duration: "~2m"
  completed_date: "2026-03-07"
  tasks_completed: 2
  files_modified: 3
---

# Phase 20 Plan 03: User Skills Catalog + Admin Filter Bars Summary

**One-liner:** User /skills catalog with ArtifactCardGrid + SkillMetadataPanel (FTS, category, skill_type, sort) and admin skills/tools filter bars with 300ms debounce.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Build user /skills catalog page with FTS + filters + sort using ArtifactCardGrid | 0484bdf | frontend/src/app/(authenticated)/skills/page.tsx |
| 2 | Add FTS filter bar to admin skills + name/handler_type filter to admin tools | 9adec14 | frontend/src/app/(authenticated)/admin/skills/page.tsx, frontend/src/app/(authenticated)/admin/tools/page.tsx |

## What Was Built

**Task 1 — User /skills catalog page** (`skills/page.tsx`):
- Replaced "Coming soon" stub with full `ArtifactCardGrid` catalog (read-only — no admin action props)
- `SkillMetadataPanel` function copied verbatim (adjusted type from `SkillDefinition` to local `SkillItem`) to render license, category, tags, allowedTools, compatibility, sourceUrl
- Filter bar: full-text search (server-side, 300ms debounce drives `?q=`), category text input, skill_type select (All / Instructional / Procedural), sort select (Newest / Oldest / Most Used)
- Maps snake_case API response fields to camelCase `SkillItem` interface
- Loading, empty, and error states all handled before rendering the grid
- Skill type badge (instructional/procedural) and usage count shown in `renderExtra`

**Task 2 — Admin filter bars**:
- `admin/skills/page.tsx`: search + category + author + sort filter bar; `useState`/`useEffect` added; client-side filtering on `items` array from `useAdminArtifacts`; filtered + sorted items passed to both `ArtifactTable` and `ArtifactCardGrid`
- `admin/tools/page.tsx`: name search (300ms debounce) + handler_type dropdown; `filteredTools` passed to both views

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

**Files exist:**
- [x] `frontend/src/app/(authenticated)/skills/page.tsx` — present (268+ lines)
- [x] `frontend/src/app/(authenticated)/admin/skills/page.tsx` — present (modified)
- [x] `frontend/src/app/(authenticated)/admin/tools/page.tsx` — present (modified)

**Commits exist:**
- [x] `0484bdf` — feat(20-03): build user /skills catalog page with FTS, filters, sort
- [x] `9adec14` — feat(20-03): add FTS filter bar to admin skills + name/handler_type filter to admin tools

**TypeScript:** Clean — `pnpm exec tsc --noEmit` exits 0 with no output.

**Verification greps:**
- `ArtifactCardGrid` used in user skills page: PASS
- `SkillMetadataPanel` used in user skills page: PASS
- `debouncedSearch` in admin skills: PASS
- `filterHandlerType` in admin tools: PASS
- `debouncedToolSearch` in admin tools: PASS
- "Coming soon" removed from user skills page: PASS

## Self-Check: PASSED
