---
phase: quick-7
plan: 01
subsystem: frontend
tags: [skill-platform, builder, import, admin]
dependency_graph:
  requires: []
  provides: [import-url-panel]
  affects: [artifact-builder-client]
tech_stack:
  added: []
  patterns: [fetch-post, collapsible-panel, inline-error]
key_files:
  created: []
  modified:
    - frontend/src/components/admin/artifact-builder-client.tsx
decisions:
  - Import panel not gated on is_complete — accessible at all times for direct URL import bypass of AI builder flow
  - Uses same securityReport + savedSkillId state path as builder-save flow — SecurityReportCard renders identically after import
  - catch-all admin proxy at /api/admin/[...path]/route.ts already handles POST /api/admin/skills/import — no new proxy file needed
metrics:
  duration: 5m
  completed: "2026-03-11"
  tasks_completed: 1
  files_modified: 1
---

# Quick Task 7: Add Import from URL Panel to Builder Right Panel Summary

**One-liner:** Collapsible "Import from URL" panel in builder right panel that POSTs a GitHub blob URL to /api/admin/skills/import and renders SecurityReportCard on success.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add import URL state, handler, and panel UI | 98a1d3e | frontend/src/components/admin/artifact-builder-client.tsx |

## What Was Built

Added an "Import from URL" feature to `artifact-builder-client.tsx` (`BuilderInner` component) with:

- **4 state variables:** `showImport`, `importUrl`, `importing`, `importError`
- **`handleImport` callback:** POSTs `{ source_url }` to `/api/admin/skills/import`, on success calls `setSecurityReport(data.security_report)` and `setSavedSkillId(data.skill.id)`, collapses panel
- **Collapsible UI panel:** "Import from URL" link always visible when `!securityReport`; clicking reveals an inline form with URL input, Import button, Cancel link, and inline error display
- **SecurityReportCard integration:** After successful import the existing `securityReport && !saveSuccess && savedSkillId` guard automatically renders SecurityReportCard with Approve & Activate

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] `frontend/src/components/admin/artifact-builder-client.tsx` exists and modified
- [x] Commit `98a1d3e` exists
- [x] `pnpm exec tsc --noEmit` passes with no errors
