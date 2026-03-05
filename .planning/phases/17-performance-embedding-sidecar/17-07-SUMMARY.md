---
phase: 17
plan: "07"
subsystem: security/frontend
tags: [performance, jwks, thundering-herd, asyncio, react, copilotkit, skills]
dependency_graph:
  requires: [17-03]
  provides: [PERF-12, PERF-13]
  affects: [security/jwt.py, frontend/chat-panel.tsx]
tech_stack:
  added: []
  patterns: [double-checked-locking, asyncio.Lock, react-prop-hoisting]
key_files:
  created:
    - backend/tests/security/test_jwks_lock.py
  modified:
    - backend/security/jwt.py
    - frontend/src/components/chat/chat-panel.tsx
decisions:
  - "[17-07]: asyncio.Lock at module level (not class-level) — matches the module-level cache globals it protects"
  - "[17-07]: Double-checked locking: fast-path read with no lock, slow-path acquires lock then re-checks — avoids lock contention on the happy path (warm cache)"
  - "[17-07]: useSkills() hoisted to ChatPanel (not moved to layout) — ChatPanel is the correct boundary: it owns the CopilotKit key= prop and the early-return for null conversationId"
metrics:
  duration: "3 minutes"
  completed_date: "2026-03-05"
  tasks_completed: 4
  files_changed: 3
requirements: [PERF-12, PERF-13]
---

# Phase 17 Plan 07: Hardening — JWKS Lock and Frontend useSkills Hoist Summary

**One-liner:** asyncio double-checked locking on JWKS refresh (PERF-12) + useSkills() hoisted above CopilotKit key boundary to eliminate re-fetch on conversation switch (PERF-13).

## What Was Built

### PERF-12: JWKS Thundering Herd Prevention

Added `_jwks_refresh_lock: asyncio.Lock` at module level in `backend/security/jwt.py`.

The `_get_jwks()` function now uses double-checked locking:
- **Fast path** (warm cache): returns immediately, no lock acquired — zero contention overhead
- **Slow path** (cold/expired cache): acquires lock, re-checks cache, fires exactly one HTTP request

Before this change, 5 concurrent requests with an expired cache would fire 5 Keycloak JWKS requests simultaneously. After: exactly 1 request fires; the other 4 wait, then hit the double-check cache branch.

### PERF-13: useSkills() Re-mount Prevention

Moved `const { skills } = useSkills()` from `ChatPanelInner` to `ChatPanel` (the parent).

`ChatPanelInner` is a child of `<CopilotKit key={conversationId}>`. When `conversationId` changes, React destroys and recreates the entire subtree, causing `useSkills()` to re-fetch on every conversation switch.

`ChatPanel` is outside the `key=` boundary — it survives conversation switches. `skills` is now passed as a typed prop (`skills: SkillItem[]`) to `ChatPanelInner`, which uses it for slash command autocompletion without triggering network requests.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Write failing test for JWKS lock (TDD RED) | 7fbfbbf |
| 2 | Add asyncio.Lock to jwt.py + full suite pass | 7fbfbbf |
| 3 | Hoist useSkills() above CopilotKit key boundary | fd25ded |
| 4 | Final verification (743 tests, build clean) | — |

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

- `grep -rn "_jwks_refresh_lock" backend/security/jwt.py` — 3 matches (declaration line 46, docstring reference, `async with` usage at line 101)
- `grep -n "useSkills" frontend/src/components/chat/chat-panel.tsx` — called at line 522 in `ChatPanel`, not in `ChatPanelInner`
- Backend tests: **743 passed, 1 skipped** (up from 742)
- Frontend build: **exit 0**, no TypeScript errors

## Self-Check: PASSED
