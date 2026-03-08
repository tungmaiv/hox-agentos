---
phase: 22
plan: "03"
subsystem: frontend
tags: [skills, promoted, shared, export, catalog]
dependency_graph:
  requires: [22-01]
  provides: [SKMKT-01, SKMKT-02, SKMKT-03]
  affects: [frontend/skills-page]
tech_stack:
  added: []
  patterns: [mapSkillItem-helper, promoted-section, shared-badge, blob-download]
key_files:
  created: []
  modified:
    - frontend/src/app/(authenticated)/skills/page.tsx
    - docs/dev-context.md
decisions:
  - "[22-03]: mapSkillItem extracted outside component — DRY, avoids repeating mapping in both fetchSkills and fetchPromotedSkills"
  - "[22-03]: Shared badge in renderExtra of main ArtifactCardGrid — locked decision, no separate Shared section"
  - "[22-03]: promotedLoading hidden check before rendering section — prevents flash of promoted section on load"
  - "[22-03]: handleExport uses blob URL pattern with anchor click — standard browser download without page navigation"
  - "[22-03]: TypeScript check via pnpm exec tsc --noEmit (not pnpm build) — .next dir owned by Docker root, build requires container context"
metrics:
  duration_seconds: 131
  completed_date: "2026-03-09"
  tasks_completed: 2
  files_modified: 2
---

# Phase 22 Plan 03: User Skills Page — Promoted Section, Shared Badge, Export

**One-liner:** User /skills page with amber promoted section above main grid, green Shared badge per card, and ZIP export button — all wired to 22-01 backend APIs.

## What Was Built

Three user-facing features added to the `/skills` catalog page in a single coordinated update:

### Task 1: skills/page.tsx — All Three Features

**isPromoted + isShared fields added to SkillItem interface:**
```typescript
isPromoted: boolean;
isShared: boolean;
```

**mapSkillItem helper extracted** to module level (DRY — avoids duplicating the 18-field mapping in both `fetchSkills` and `fetchPromotedSkills`).

**Promoted / Featured Skills section** — renders above filter bar using `GET /api/skills?promoted=true`. Hidden entirely when `promotedSkills.length === 0`. Amber styling (`border-amber-200 bg-amber-50`) with star indicator and "Curated picks" label.

**Shared badge** — green badge (`bg-green-100 text-green-700`) in `renderExtra` of the main `ArtifactCardGrid`. Appears on cards where `isShared=true`. No separate "Shared with me" section (locked decision).

**Export button** — `handleExport()` fetches `/api/skills/{id}/export`, reads `Content-Disposition` header for filename, creates blob URL, triggers anchor click download, then revokes URL.

### Task 2: docs/dev-context.md — Phase 22 Endpoints

Added to Skills (User-facing) table:
- `GET /api/skills` — updated note: now returns `is_promoted` and `is_shared` per item
- `GET /api/skills?promoted=true` — featured skills filter
- `GET /api/skills/{id}/export` — ZIP download

Added to Admin Skills table:
- `PATCH /api/admin/skills/{id}/promote`
- `POST /api/admin/skills/{id}/share`
- `DELETE /api/admin/skills/{id}/share/{user_id}`
- `GET /api/admin/skills/{id}/shares`

## Verification Results

```
pnpm exec tsc --noEmit   → 0 errors (no TypeScript issues)
grep isShared/isPromoted/handleExport → all three present in skills/page.tsx
grep "Shared" in page.tsx → badge in renderExtra only, no separate section
grep "is_promoted|is_shared|/promote|/share" in dev-context.md → 7 matches
```

Note: `pnpm run build` could not run on host — `.next` directory is owned by Docker root (pre-existing condition from container-only dev mode). TypeScript check via `tsc --noEmit` confirms code correctness.

## Deviations from Plan

None — plan executed exactly as written.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | `104cbd8` | feat(22-03): promoted section, Shared badge in main grid, export button on user /skills page |
| 2 | `9f6090b` | docs(22-03): update dev-context.md with Phase 22 endpoints |

## Requirements Satisfied

- **SKMKT-01:** Promoted/Featured Skills section above main grid (hidden when empty)
- **SKMKT-02:** Export button triggers ZIP download via GET /api/skills/{id}/export
- **SKMKT-03:** Shared badge in main grid on cards where is_shared=true

## Self-Check: PASSED

- [x] `frontend/src/app/(authenticated)/skills/page.tsx` — exists
- [x] `docs/dev-context.md` — exists
- [x] `22-03-SUMMARY.md` — exists
- [x] Commit `104cbd8` — exists (Task 1)
- [x] Commit `9f6090b` — exists (Task 2)
