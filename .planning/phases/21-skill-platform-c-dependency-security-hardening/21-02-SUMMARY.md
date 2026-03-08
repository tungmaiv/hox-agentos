---
phase: 21-skill-platform-c-dependency-security-hardening
plan: "02"
subsystem: skills/security
tags: [security, skills, acl, audit-logging, tdd]
dependency_graph:
  requires: []
  provides: [SKSEC-02]
  affects: [skills/executor.py, security/acl]
tech_stack:
  added: []
  patterns: [pre-gate check before DB lookup, audit_logger.info for security denials]
key_files:
  created: []
  modified:
    - backend/skills/executor.py
    - backend/tests/test_skill_executor.py
decisions:
  - "allowed_tools=None or [] is permissive — backwards-compatible with all existing skills that have no allowed_tools declaration"
  - "Pre-gate fires before get_tool() call — no DB lookup on denied tool calls"
  - "_current_skill_name/_current_skill_id as instance attributes on SkillExecutor — internal state for audit log context, not public API"
metrics:
  duration: "~2 minutes"
  completed_date: "2026-03-08"
  tasks_completed: 1
  files_changed: 2
requirements_satisfied: [SKSEC-02]
---

# Phase 21 Plan 02: Skill Allowed-Tools Pre-Gate Summary

**One-liner:** Injected `allowed_tools` pre-gate into `SkillExecutor._run_tool_step()` that blocks undeclared tool calls before Gate 3 ACL with structlog audit logging.

## What Was Built

Added a SKSEC-02 enforcement pre-gate to `SkillExecutor._run_tool_step()`. When a skill declares `allowed_tools=["email.fetch"]`, any step attempting to call `"email.send"` (or any other undeclared tool) is blocked immediately — before `get_tool()` is called, before `check_tool_acl()` is called, and before any DB lookup occurs.

Denials emit a `"skill_allowed_tools_denied"` audit log entry via `get_audit_logger()` with fields: `skill_name`, `skill_id`, `tool_name`, `user_id`, `declared_allowed_tools`.

Backwards compatibility: `allowed_tools=None` (existing skills without the field) and `allowed_tools=[]` (empty list) are both treated as permissive — no change to existing behavior.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Write failing TestAllowedTools tests | 95e8ded | backend/tests/test_skill_executor.py |
| 1 (GREEN) | Implement allowed_tools pre-gate | 8c40350 | backend/skills/executor.py |

## Decisions Made

- `allowed_tools=None` or `[]` is permissive — consistent with CONTEXT.md locked decision, backwards-compatible with all existing skill definitions
- Pre-gate fires before `get_tool()` — no DB lookup on denied calls (performance + principle of least privilege)
- `_current_skill_name` and `_current_skill_id` as instance attributes — internal state set in `run()` for audit log context in `_run_tool_step()`; acceptable since `SkillExecutor` is not shared across concurrent coroutines

## Verification

All verification checks passed:

- `grep -n "skill_allowed_tools_denied" backend/skills/executor.py` — confirms audit log event at line 230
- `grep -n "allowed_tools" backend/skills/executor.py` — confirms pre-gate at line 227 before `get_tool()` call at line 244
- All 17 executor tests pass including 6 new `TestAllowedTools` tests
- Full suite: 809 passed, 1 skipped — no regressions

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] `backend/skills/executor.py` — pre-gate logic present, audit_logger imported
- [x] `backend/tests/test_skill_executor.py` — `TestAllowedTools` class with 6 tests present
- [x] Commit `95e8ded` exists (RED: failing tests)
- [x] Commit `8c40350` exists (GREEN: implementation)
- [x] 17/17 executor tests pass; 809 total pass, 0 regressions
