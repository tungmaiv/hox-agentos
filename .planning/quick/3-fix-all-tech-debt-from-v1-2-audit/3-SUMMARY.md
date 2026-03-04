---
phase: quick-3
plan: "01"
subsystem: "code-quality"
tags: [tech-debt, dead-code, security, testing]
dependency_graph:
  requires: []
  provides: [clean-docstrings, tightened-admin-rbac, clean-test-output]
  affects: [backend/agents/master_agent.py, backend/core/prompts.py, backend/tests/test_skill_export.py, frontend/src/lib/api-client.ts, frontend/src/app/admin/layout.tsx]
tech_stack:
  added: []
  patterns: [AsyncMock-side_effect-for-async-dependencies]
key_files:
  created: []
  modified:
    - backend/agents/master_agent.py
    - backend/core/prompts.py
    - backend/tests/test_skill_export.py
    - frontend/src/lib/api-client.ts
    - frontend/src/app/admin/layout.tsx
decisions:
  - "prompts.py function docstring example updated to use artifact_builder prompt (with vars) to preserve the substitution example while removing stale intent_classifier reference"
  - "test_skill_export.py uses AsyncMock(side_effect) pattern — cleaner than shadowing the @patch argument"
  - "Item 4 (sub-agent .md files) intentionally skipped — informational only, no code change warranted"
metrics:
  duration: "2 minutes"
  completed: "2026-03-04T16:07:10Z"
  tasks_completed: 2
  files_changed: 5
---

# Quick-3: Fix All Tech Debt from v1.2 Audit — Summary

**One-liner:** Removed 3 stale dead-code TODO comments, fixed stale intent_classifier docstring reference, tightened admin RBAC zero-roles bypass, and eliminated RuntimeWarning from unawaited coroutine in skill export tests.

---

## What Was Changed

### Task 1: Remove dead-code TODOs, fix stale prompts.py docstring (commit 22d9de3)

**backend/agents/master_agent.py**
- Removed `# TODO: verify dead — update_agent_last_seen has no production callers` two-line comment block above the function
- Replaced with forward-compatibility note inside the function docstring: explains no production callers yet, called from tests to validate batching logic, and when to wire it in

**backend/core/prompts.py**
- Module docstring example: replaced `load_prompt("intent_classifier", message="check my emails")` with `load_prompt("master_agent")` — `intent_classifier.md` was deleted with `router.py` in Phase 11 DEBT-01
- Function docstring example: replaced `load_prompt("intent_classifier", ...)` with `load_prompt("artifact_builder", context="my api spec")` — preserves the substitution usage example while referencing an existing file

**frontend/src/lib/api-client.ts**
- Replaced 3-line `TODO: verify dead` comment block with a forward-compatibility note referencing `auth.ts:178` where `accessToken` is set on the session (established in Phase 13 local auth)
- Phase 12 removal deadline removed (Phase 12 has passed; function is still valid)

---

### Task 2: Tighten admin RBAC guard, fix test RuntimeWarning (commit 2044ab2)

**frontend/src/app/admin/layout.tsx**
- Changed line 74: `const allowAccess = hasAdminRole || allRoles.length === 0;` → `const allowAccess = hasAdminRole;`
- Rationale: Both Keycloak sessions (`auth.ts:112`) and local-auth sessions (`auth.ts:135`) propagate `realm_roles` from the JWT token. A session with no roles means the user has no admin role — the zero-roles fallback was security-loosening. Backend RBAC (Gate 2) remains the authoritative enforcement gate; this is defense-in-depth.

**backend/tests/test_skill_export.py**
- Removed `async def _auth_override()` wrapper function (lines 264-266)
- Changed `mock_auth.return_value = _auth_override()` (which created an unawaited coroutine) to `mock_auth.side_effect = AsyncMock(return_value=mock_user)`
- The `_require_registry_manager` dependency is `async def`, so when patched it must be awaitable. `AsyncMock` handles this correctly.

---

## Item 4: Intentionally Skipped

**Item 4 from the audit:** Sub-agent `.md` files (`email_agent.md`, `calendar_agent.md`, `project_agent.md`) created but not loaded by sub-agent code.

**Why skipped:** Informational only. Sub-agents are Phase 3 mocks that do not make LLM calls. The prompt files are forward-compatibility assets — they will be loaded when sub-agents graduate from mock state. No code change is warranted. This is explicitly noted in the audit's `gaps.integration[0].evidence` field.

---

## Test Results

| Suite | Result |
|-------|--------|
| `tests/test_skill_export.py -W error::RuntimeWarning` | 18 passed, 0 failed, 0 warnings |
| `tests/ -q` (full suite) | 718 passed, 1 skipped, 0 failed |
| `pnpm exec tsc --noEmit` | Exit 0, no errors |

---

## Deviations from Plan

**1. [Rule 1 - Bug] prompts.py had two intent_classifier references, not one**
- **Found during:** Task 1 verification — `grep "intent_classifier" core/prompts.py` returned a hit at line 52 inside the `load_prompt` function docstring
- **Issue:** The plan specified only the module-level docstring (line 12). The function-level docstring at line 52 also contained an `intent_classifier` example. Both needed to be fixed to satisfy the success criterion.
- **Fix:** Updated `load_prompt()` function docstring example from `load_prompt("intent_classifier", message="check my emails")` to `load_prompt("artifact_builder", context="my api spec")` — preserves the variable substitution example while referencing an existing prompt file
- **Files modified:** `backend/core/prompts.py`
- **Commit:** 22d9de3

---

## Self-Check: PASSED

All 5 modified files present. Both task commits (22d9de3, 2044ab2) verified in git log.
