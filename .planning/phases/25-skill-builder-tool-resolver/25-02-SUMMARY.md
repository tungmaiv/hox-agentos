---
phase: 25
plan: 02
subsystem: skill-builder-tool-resolver
tags: [skill-builder, tool-resolver, enforcement, gap-summary, tdd]
dependency_graph:
  requires: [25-01]
  provides: [gap-enforcement, gap-auto-resolution, gap-summary-ui]
  affects: [artifact_builder, skill_handler, tool_handler, registry_route]
tech_stack:
  added: []
  patterns: [tdd-red-green, handler-hook, jsonb-dirty-tracking, activation-gate]
key_files:
  created:
    - backend/tests/registry/test_skill_handler.py
    - backend/tests/registry/test_tool_handler.py
  modified:
    - backend/agents/artifact_builder.py
    - backend/tests/agents/test_artifact_builder.py
    - backend/registry/handlers/skill_handler.py
    - backend/registry/handlers/tool_handler.py
    - backend/api/routes/registry.py
    - backend/prompts/artifact_builder_skill.md
decisions:
  - "[25-02]: activation gate uses pre-fetch get_entry before update call — Pattern A chosen over post-update check (simpler, no rollback needed)"
  - "[25-02]: _format_gap_summary returns empty string for None/empty gaps — safe default for non-skill artifact types"
  - "[25-02]: ToolHandler gap matching uses substring check (tool_slug in gap_slug) — handles dot-to-hyphen normalization correctly"
metrics:
  duration: 4m
  completed_date: "2026-03-12"
  tasks_completed: 3
  files_changed: 8
---

# Phase 25 Plan 02: Gap Summary, Enforcement Gates, Auto-Resolution, Prompt Update Summary

**One-liner:** TDD implementation of skill gap enforcement gates — `_format_gap_summary` card in validate_and_present, `SkillHandler` draft-lock, registry route 422 activation gate, `ToolHandler` auto-promotion to `pending_activation`, and prompt cleanup removing hardcoded permissions list.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 25-02-T1 | `_format_gap_summary` helper + injection into `_validate_and_present_node` | f00c4e1 |
| 25-02-T2 | `SkillHandler.on_create()` draft enforcement + `PUT /api/registry/{id}` activation gate | 465e6bd |
| 25-02-T3 | `ToolHandler.on_create()` gap auto-resolution + `artifact_builder_skill.md` prompt update | eb05757 |

## What Was Built

### Task T1 — Gap Summary Card
- Added `_format_gap_summary(resolved_tools, tool_gaps) -> str` to `artifact_builder.py`
- Shows all steps: resolved with ✅, missing with "No tool found for: {intent}" phrasing
- Each gap shows suggested tool name (MISSING: prefix stripped)
- Returns empty string when no gaps (safe default for all non-skill paths)
- Injected into `_validate_and_present_node` — appends gap summary to AIMessage content when gaps present

### Task T2 — Enforcement Gates
- `SkillHandler.on_create()`: adds draft status enforcement AFTER scan block — reads `config.tool_gaps`, sets `entry.status = "draft"` when non-empty, logs warning with gap count
- `PUT /api/registry/{id}`: pre-fetch activation gate — when `body.status == "active"`, fetches existing entry and raises HTTP 422 if `tool_gaps` is non-empty; gate is a no-op for non-skills (no `tool_gaps` key)

### Task T3 — Auto-Resolution + Prompt Update
- `ToolHandler.on_create()`: scans all draft skills, converts tool name to slug (`dots/underscores → hyphens`), removes matching gaps, promotes to `pending_activation` when all gaps cleared, stays `draft` when gaps remain; exception-safe (never propagates DB errors)
- `artifact_builder_skill.md`: replaced hardcoded 12-item permissions list with "DERIVED AUTOMATICALLY" note; added gap summary documentation in Phase 6 section

## Test Results

```
7 new tests added, all pass:
  tests/agents/test_artifact_builder.py::test_format_gap_summary_with_gaps PASSED
  tests/agents/test_artifact_builder.py::test_format_gap_summary_no_gaps PASSED
  tests/registry/test_skill_handler.py::test_skill_handler_forces_draft_when_tool_gaps_present PASSED
  tests/registry/test_skill_handler.py::test_skill_handler_does_not_force_draft_when_no_gaps PASSED
  tests/registry/test_tool_handler.py::test_tool_handler_resolves_matching_skill_gap PASSED
  tests/registry/test_tool_handler.py::test_tool_handler_does_not_promote_skill_with_remaining_gaps PASSED
  tests/registry/test_tool_handler.py::test_tool_handler_gap_resolution_survives_db_error PASSED

Full suite: 926 passed, 7 skipped (was 919 before plan 25-01, grew with each plan)
```

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

All files exist and all commits verified:
- `backend/tests/registry/test_skill_handler.py` FOUND
- `backend/tests/registry/test_tool_handler.py` FOUND
- `backend/agents/artifact_builder.py` FOUND
- `backend/registry/handlers/skill_handler.py` FOUND
- `backend/registry/handlers/tool_handler.py` FOUND
- `backend/prompts/artifact_builder_skill.md` FOUND
- Commit f00c4e1 FOUND
- Commit 465e6bd FOUND
- Commit eb05757 FOUND
