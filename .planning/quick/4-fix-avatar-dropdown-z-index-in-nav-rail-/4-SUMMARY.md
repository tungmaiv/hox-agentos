---
phase: quick
plan: 4
subsystem: frontend/nav-rail
tags: [z-index, stacking-context, css, nav-rail, dropdown]
dependency_graph:
  requires: []
  provides: [avatar-dropdown-visible-above-page-content]
  affects: [frontend/src/components/nav-rail.tsx]
tech_stack:
  added: []
  patterns: [css-stacking-context-fix]
key_files:
  modified:
    - frontend/src/components/nav-rail.tsx
decisions:
  - Nav stacking context raised to z-50 so dropdown child (also z-50) escapes z-40 siblings
metrics:
  duration: "25 seconds"
  completed: "2026-03-05"
  tasks_completed: 1
  files_modified: 1
---

# Quick Task 4: Fix Avatar Dropdown Z-Index in NavRail Summary

**One-liner:** Raised `<nav>` stacking context from `z-40` to `z-50` so the avatar dropdown renders above all page content.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Raise nav element z-index from z-40 to z-50 | 8a45435 | frontend/src/components/nav-rail.tsx |

## What Was Done

Changed line 96 in `frontend/src/components/nav-rail.tsx`:

```
Before: className="hidden md:flex flex-col fixed left-0 top-0 h-screen w-16 z-40"
After:  className="hidden md:flex flex-col fixed left-0 top-0 h-screen w-16 z-50"
```

**Root cause:** The `<nav>` element creates its own CSS stacking context. The dropdown inside it (line 164) uses `z-50`, but that only elevates it within the nav's stacking context — it cannot escape the nav's own z-level of `z-40`. Any sibling page element with `z-40` or higher renders above the dropdown. Raising the nav to `z-50` ensures the entire nav stacking context sits above all `z-40` elements on the page.

**Verification:**
- `grep -n "z-40\|z-50" nav-rail.tsx` shows only `z-50` entries (no `z-40` remaining)
- `pnpm exec tsc --noEmit` passes with no errors
- Dropdown at line 164 retains `z-50` (unchanged)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] `frontend/src/components/nav-rail.tsx` modified — line 96 has `z-50` on `<nav>`
- [x] Commit `8a45435` exists: `git log --oneline | grep 8a45435`
- [x] No `z-40` remaining in file
- [x] TypeScript build passes
