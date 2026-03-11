---
phase: quick-9
plan: "01"
subsystem: security-scanner, artifact-builder, builder-frontend
tags: [bug-fix, security, ux]
dependency_graph:
  requires: []
  provides: [extended-scanner-window, accurate-fill-form-count, fork-draft-lock-clear]
  affects: [backend/skills/security_scanner.py, backend/agents/artifact_builder.py, frontend/src/components/admin/artifact-builder-client.tsx]
tech_stack:
  added: []
  patterns: [targeted-line-edit]
key_files:
  modified:
    - backend/skills/security_scanner.py
    - backend/agents/artifact_builder.py
    - frontend/src/components/admin/artifact-builder-client.tsx
decisions:
  - "[quick-9]: Raise scanner LLM window from 500 to 2000 chars — short window lets injected payloads escape truncation boundary undetected"
  - "[quick-9]: Add instruction_markdown to fill_form filled dict — omitting it caused the return message to under-count filled fields"
  - "[quick-9]: Clear manualDraftRef before setSimilarSkills(null) in handleFork — stale lock was silently overriding forked content with old manual edits"
metrics:
  duration: "< 5 minutes"
  completed: "2026-03-11"
  tasks_completed: 1
  files_changed: 3
---

# Quick-9: Fix Code Review Findings — Scanner Truncation, fill_form Count, Fork Draft Lock

**One-liner:** Three targeted fixes: extend LLM scanner instruction window to 2000 chars, include instruction_markdown in fill_form field count, and clear manualDraftRef on fork to prevent stale draft override.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Apply all three targeted fixes | 3269bbc | security_scanner.py, artifact_builder.py, artifact-builder-client.tsx |

## Changes Made

### Fix 1 — Security Scanner truncation window (security_scanner.py line 257)
Changed `instruction[:500]` to `instruction[:2000]` in the LLM prompt. The 500-char limit allowed prompt injection payloads longer than 500 chars to be silently truncated before the LLM reviewer saw them, creating a bypass vector.

### Fix 2 — fill_form field count (artifact_builder.py line 79)
Added `"instruction_markdown": instruction_markdown` to the `filled` dict comprehension. Previously `instruction_markdown` was accepted as a parameter but never included in the `filled` dict, so the return message always under-counted filled fields when `instruction_markdown` was set.

### Fix 3 — Fork draft lock (artifact-builder-client.tsx handleFork)
Added `manualDraftRef.current = null;` before `setSimilarSkills(null)` in `handleFork`. Without this, a user who had previously manually edited the JSON draft would find the forked skill's name/description immediately overridden by their stale manual JSON, because the manual draft lock remained active after forking.

## Verification

- All three grep patterns confirmed present in target files
- Backend tests: 867 passed, 1 skipped, 0 failed (27.45s)
- TypeScript check: `pnpm exec tsc --noEmit` exited 0

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] `backend/skills/security_scanner.py` — `instruction[:2000]` present at line 257
- [x] `backend/agents/artifact_builder.py` — `"instruction_markdown": instruction_markdown` present at line 79
- [x] `frontend/src/components/admin/artifact-builder-client.tsx` — `manualDraftRef.current = null` present at line 312 (handleFork)
- [x] Commit 3269bbc exists
