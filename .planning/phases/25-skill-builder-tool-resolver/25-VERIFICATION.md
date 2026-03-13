---
phase: 25-skill-builder-tool-resolver
verified: 2026-03-14T01:45:00Z
status: passed
score: 16/16 must-haves verified
re_verification: true
  previous_status: passed
  previous_score: 15/15
  gaps_closed:
    - "create_skill endpoint now defaults to status=draft (not active), completing the draft→pending_activation→active promotion pipeline"
    - "test_create_skill_defaults_to_draft added and passes"
    - "test_crud_flow asserts is_active is False after create (corrected from True)"
    - "test_bulk_status_update asserts untouched skill has status=draft (corrected from active)"
    - "test_activate_skill passes without intermediate disable step — draft→active via /activate directly"
    - "Integration tests in test_phase6_integration.py updated to activate skills before employee operations"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "In the Artifact Builder UI, start creating a procedural skill with a description like 'Fetch Jira tasks and send a Slack summary.' Step through the conversation to completion."
    expected: "The builder uses exact tool names from the live registry in procedure_json steps. If no Slack tool exists, the gap summary card appears with 'No tool found for:' and the skill is saved as draft."
    why_human: "LLM prompt behavior and gap card rendering can only be verified with the running system."
  - test: "After a draft skill with a gap is created, create the missing tool in Tool Builder."
    expected: "The draft skill is automatically promoted to pending_activation. The admin bell icon count increments and skill appears in the bell dropdown."
    why_human: "Requires live DB state transition and UI reactivity verification."
  - test: "Click bell icon when there are zero pending_activation skills."
    expected: "Dropdown opens and shows 'No skills pending activation' empty-state message."
    why_human: "Requires the running UI to confirm the empty-state renders correctly."
  - test: "In the Artifact Builder, choose 'procedural' skill type and complete the flow. Submit from the wizard."
    expected: "POST /api/admin/skills/builder-save returns 200 with a new RegistryEntry row in registry_entries table with status=draft."
    why_human: "Requires live builder conversation and DB inspection."
---

# Phase 25: Skill Builder Tool Resolver Verification Report

**Phase Goal:** Eliminate hardcoded tool list and LLM-guessed tool names in the procedural skill builder. Insert a `resolve_tools` LangGraph node that maps each workflow step to a verified tool from the live registry. Skills with unresolved tool gaps are saved as `draft` and blocked from activation. When the missing tool is created, auto-promote the skill to `pending_activation` for admin review.
**Verified:** 2026-03-14T01:45:00Z
**Status:** passed
**Re-verification:** Yes — after plan 25-06 gap closure (create_skill default status fixed to draft)

## Note on Re-verification Context

The previous VERIFICATION.md (timestamp 2026-03-13T04:30:00Z) was created after plans 25-04 and 25-05 but before the UAT run that identified the final gap. The UAT (`test(25): complete UAT rerun` commit `6315250`) diagnosed that `create_skill` was defaulting to `status=active`, bypassing the entire promotion pipeline. Plan 25-06 was executed in commit `59c2b83` to close this gap. This re-verification confirms all 6 plans are complete and the full test suite (934 passed, 7 skipped) is clean.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Hardcoded tool list removed — LLM receives live registry via `_fetch_tool_reference_block()` | VERIFIED | `_RESOLVE_TOOLS_PROMPT` injects `tool_reference` from live registry; prompt instructs LLM to use only exact names from that list |
| 2 | `resolve_tools` node exists in LangGraph and runs before `generate_skill_content` for procedural skills | VERIFIED | `graph.add_node("resolve_tools", _resolve_tools_node)` in artifact_builder.py; edge `resolve_tools → generate_skill_content` wired; both routing functions route procedural skills here |
| 3 | Skills with unresolved tool gaps are saved as `draft` regardless of requested status | VERIFIED | `SkillHandler.on_create()` reads `config.tool_gaps` and sets `entry.status = "draft"` when non-empty; test `test_skill_handler_forces_draft_when_tool_gaps_present` passes |
| 4 | Activating a skill with unresolved gaps returns HTTP 422 | VERIFIED | Registry `PUT /{entry_id}` gate pre-fetches entry, checks `tool_gaps`, raises `HTTPException(status_code=422)` when activating; wired and tested |
| 5 | When a missing tool is created, draft skills with matching gaps are auto-promoted to `pending_activation` | VERIFIED | `ToolHandler.on_create()` scans draft skills, matches slug, promotes to `pending_activation`, clears gaps; 3 tests pass |
| 6 | Resolver falls back to empty lists on LLM error — never crashes the builder graph | VERIFIED | `_resolve_tools_node` wraps entire LLM call in `try/except`, returns `{"resolved_tools": [], "tool_gaps": []}` on any exception; test `test_resolve_tools_node_falls_back_on_llm_error` passes |
| 7 | Gap summary card injected into `validate_and_present` output when gaps exist | VERIFIED | `_format_gap_summary` called in `_validate_and_present_node`; appended to `AIMessage` content; shows resolved items and "No tool found for:" slugs |
| 8 | `pending_activation` badge (amber/orange) and inline Activate button visible in admin skills table | VERIFIED | `StatusBadge` explicit case `bg-orange-100 text-orange-700`; `RowActions` renders blue "Activate" button for `pending_activation` items; `handleActivate()` calls `PUT /api/registry/{id}` |
| 9 | `draft` skills with tool gaps show grey badge and warning tooltip with gap count | VERIFIED | `StatusBadge` explicit `bg-gray-100 text-gray-600` for `draft`; warning icon with `title` showing gap count rendered when `tool_gaps.length > 0` |
| 10 | Bell icon in admin nav shows count of `pending_activation` skills with dropdown | VERIFIED | `layout.tsx` uses `useEffect` + plain `fetch` to `/api/registry?type=skill&status=pending_activation`; bell with orange badge and dropdown listing skill names |
| 11 | Tool creation API response includes `unblocked_skills` field | VERIFIED | `create_entry` route returns `dict` with `unblocked_skills` field listing newly-promoted skills when `entry.type == "tool"` |
| 12 | POST /api/admin/skills/builder-save succeeds and writes to registry_entries (not skill_definitions) | VERIFIED | `builder_save` calls `_registry_service.create_entry(session, create_data, owner_id=...)` using `UnifiedRegistryService`; no reference to `SkillDefinition` in the builder-save code path |
| 13 | Bell dropdown renders on every click (not gated on pendingCount > 0) with empty-state fallback | VERIFIED | Condition is `{bellOpen && (` (no pendingCount gate); empty-state `<p>No skills pending activation</p>` rendered when `pendingSkills.length === 0` |
| 14 | Artifact wizard sends correct skill_type from user selection (not hardcoded "instructional") | VERIFIED | `artifact-wizard.tsx`: `payload.skill_type = formState.skill_type \|\| "instructional"`; procedural path adds `procedure_json` from `aiArtifactDraft` |
| 15 | POST /api/admin/skills always creates skill as `draft` — promotion pipeline is intact | VERIFIED | `admin_skills.py` line 234: `RegistryEntryCreate(..., status="draft")`; `test_create_skill_defaults_to_draft` asserts `status == "draft"` and `is_active is False`; `test_crud_flow` asserts `is_active is False`; `test_bulk_status_update` asserts untouched skill has `status == "draft"` |
| 16 | Full test suite passes with no regressions after all 6 plans | VERIFIED | 934 passed, 7 skipped, 0 failed (confirmed 2026-03-14) |

**Score:** 16/16 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/agents/state/artifact_builder_types.py` | `resolved_tools` and `tool_gaps` fields | VERIFIED | Both fields present with correct type annotations |
| `backend/agents/artifact_builder.py` | `_resolve_tools_node`, graph wiring, `_format_gap_summary` | VERIFIED | All functions present; node registered and edge wired |
| `backend/registry/handlers/skill_handler.py` | Draft enforcement on `tool_gaps` | VERIFIED | Gap check at end of `on_create()`, sets `entry.status = "draft"` |
| `backend/registry/handlers/tool_handler.py` | Gap auto-resolution promoting to `pending_activation` | VERIFIED | Slug matching; exception-safe; 3 tests pass |
| `backend/api/routes/registry.py` | 422 activation gate + `unblocked_skills` in create response | VERIFIED | Gate at update_entry; `unblocked_skills` at create_entry |
| `backend/prompts/artifact_builder_skill.md` | No hardcoded permissions list; `DERIVED AUTOMATICALLY` note | VERIFIED | `DERIVED AUTOMATICALLY` instruction present |
| `frontend/src/app/(authenticated)/admin/skills/page.tsx` | Amber `pending_activation` badge, grey `draft` badge, warning tooltip, inline Activate button | VERIFIED | All four features present |
| `frontend/src/app/(authenticated)/admin/layout.tsx` | Bell with count, dropdown gated on `bellOpen` only, empty-state fallback | VERIFIED | `{bellOpen && (` condition; `pendingSkills.length === 0` empty-state present |
| `backend/api/routes/admin_skills.py` | `create_skill` defaults to `status="draft"` + `builder_save` using `UnifiedRegistryService` | VERIFIED | Line 234: `status="draft"` in `RegistryEntryCreate`; `_registry_service.create_entry()` in new-skill path; `get_entry()` + `update_entry()` in re-scan path |
| `frontend/src/components/admin/artifact-wizard.tsx` | `formState.skill_type` in payload; `procedure_json` from `aiArtifactDraft` | VERIFIED | `formState.skill_type \|\| "instructional"` and `aiArtifactDraft?.procedure_json` present |
| `backend/tests/api/test_admin_skills.py` | `test_create_skill_defaults_to_draft` + corrected assertions in `test_crud_flow`, `test_bulk_status_update`, `test_activate_skill` | VERIFIED | All 16 tests in file pass (confirmed 2026-03-14) |
| `backend/tests/registry/test_skill_handler.py` | 2 tests for draft enforcement | VERIFIED | Both tests pass |
| `backend/tests/registry/test_tool_handler.py` | 3 tests for auto-resolution | VERIFIED | All 3 tests pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `_route_after_gather_type` | `resolve_tools` node | `return "resolve_tools"` for procedural | WIRED | Returns `"resolve_tools"` for procedural skill type |
| `_route_intent` | `resolve_tools` node | `state.get("resolved_tools") is None` guard | WIRED | Guard condition in routing function |
| `resolve_tools` | `generate_skill_content` | `graph.add_edge(...)` | WIRED | Edge wired in graph construction |
| `SkillHandler.on_create()` | `entry.status = "draft"` | `config.tool_gaps` check | WIRED | Sets draft status when tool_gaps non-empty |
| `ToolHandler.on_create()` | `skill.status = "pending_activation"` | slug match | WIRED | Slug matching promotes draft skills with matching gaps |
| `PUT /api/registry/{id}` | `HTTPException(422)` | pre-fetch `get_entry`, check `tool_gaps` | WIRED | Blocks activation when gaps present |
| `create_entry` route | `unblocked_skills` field | query `pending_activation` skills post-commit | WIRED | Returns newly-promoted skills for tool entries |
| `handleActivate()` (frontend) | `PUT /api/registry/{id}` | `fetch` call with `{status: "active"}` | WIRED | Frontend activation button triggers registry update |
| `Bell useEffect` | `pending_activation` count display | `fetch` to backend, `setPendingCount` | WIRED | Bell count updates via useEffect fetch |
| `builder_save` new-skill path | `_registry_service.create_entry` | `await _registry_service.create_entry(session, create_data, owner_id=...)` | WIRED | Uses UnifiedRegistryService |
| `builder_save` re-scan path | `_registry_service.get_entry` + `update_entry` | `await _registry_service.get_entry(session, existing_id)` | WIRED | Re-scan updates existing entry |
| `artifact-wizard skill case` | `formState.skill_type` in POST payload | `payload.skill_type = formState.skill_type \|\| "instructional"` | WIRED | Correct skill_type from user selection |
| `create_skill endpoint` | `status="draft"` in `RegistryEntryCreate` | `admin_skills.py` line 234 | WIRED | Confirmed by plan 25-06 commit `59c2b83` |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| TRES-01 | 25-01 | `resolve_tools` node runs before `generate_skill_content` for procedural skills | SATISFIED | Node in graph; both routing functions updated; edge confirmed |
| TRES-02 | 25-01 | Node uses `blitz/fast`, falls back to empty lists on error | SATISFIED | `get_llm("blitz/fast")` in `_resolve_tools_node`; `try/except` fallback tested |
| TRES-03 | 25-01 | `ArtifactBuilderState` has `resolved_tools` and `tool_gaps` fields | SATISFIED | Both fields present in `artifact_builder_types.py` |
| TRES-04 | 25-02 | `SkillHandler.on_create()` forces `draft` when `tool_gaps` non-empty | SATISFIED | Implementation present; test passes |
| TRES-05 | 25-02 | `PUT /api/registry/{id}` returns 422 blocking `status → active` when gaps exist | SATISFIED | Gate implemented; raises `HTTPException(422)` |
| TRES-06 | 25-02 | `ToolHandler.on_create()` promotes to `pending_activation` | SATISFIED | Implementation present; 3 tests pass |
| TRES-07 | 25-02 / 25-04 | Gap summary rendered in `validate_and_present` + builder_save writes RegistryEntry | SATISFIED | `_format_gap_summary` injected; builder_save uses `UnifiedRegistryService.create_entry()` |
| TRES-08 | 25-03 | `pending_activation` amber badge in skills list | SATISFIED | `bg-orange-100 text-orange-700` explicit case in `StatusBadge` |
| TRES-09 | 25-03 / 25-05 | Bell icon shows count of `pending_activation` skills; dropdown always opens on click | SATISFIED | `{bellOpen && (` condition; empty-state fallback added in 25-05 |
| TRES-10 | 25-03 | Tool creation API response includes `unblocked_skills` list | SATISFIED | `create_entry` returns `unblocked_skills` field for tool entries |
| TRES-11 | 25-02 | `artifact_builder_skill.md` removes hardcoded permissions list | SATISFIED | `DERIVED AUTOMATICALLY` replaces static list |
| uat-gap: create_skill_default_status | 25-06 | `create_skill` defaults to `status="draft"` to preserve promotion pipeline | SATISFIED | `admin_skills.py` line 234: `status="draft"`; `test_create_skill_defaults_to_draft` passes; 934 tests pass |

No orphaned requirements — all 12 IDs (11 TRES + 1 UAT gap) claimed by plans and verified as implemented.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/registry/handlers/skill_handler.py` | ~40 | `session.add(entry)` with `AsyncMock` generates uncollected coroutine warning in tests | Info | Test-only warning; production uses real `AsyncSession` |

No blocker anti-patterns found. The 66 warnings in the full test suite are all deprecation and resource warnings from third-party libraries, not from phase 25 code.

### Human Verification Required

#### 1. Resolver end-to-end in Artifact Builder conversation

**Test:** In the Artifact Builder UI, start creating a procedural skill. Provide a description like "Fetch Jira tasks and send a Slack summary." Step through the conversation to completion.
**Expected:** The builder uses exact tool names from the live registry in `procedure_json` steps. If no Slack tool exists, the gap summary card appears with "No tool found for: send Slack summary" and "Saved as draft."
**Why human:** The LLM prompt behavior and gap card rendering can only be verified with the running system.

#### 2. Auto-promotion flow

**Test:** After the above creates a draft skill with a gap, create the missing tool (e.g., `slack.send-message`) in Tool Builder.
**Expected:** The draft skill is automatically promoted to `pending_activation`. The admin bell icon count increments. The skill appears in the bell dropdown.
**Why human:** Requires live DB state transition and UI reactivity verification.

#### 3. Bell empty-state behavior

**Test:** Click the bell icon when there are zero `pending_activation` skills.
**Expected:** Dropdown opens and shows "No skills pending activation" empty-state message.
**Why human:** `{bellOpen && (` condition and empty-state rendering can only be confirmed visually in the running UI.

#### 4. Procedural skill submission via artifact wizard

**Test:** In the Artifact Builder, choose "procedural" skill type, complete the AI-guided flow, then click Save in the wizard.
**Expected:** POST to `/api/admin/skills/builder-save` succeeds (200) and a new RegistryEntry row appears in `registry_entries` with `type=skill` and `status=draft`.
**Why human:** Requires running builder conversation + DB inspection to confirm correct table and status.

### Gaps Summary

No gaps. All 16 observable truths verified. Plan 25-06 correctly closed the final UAT-identified gap: `create_skill` was defaulting to `status=active`, which short-circuited the entire draft→pending_activation→active promotion pipeline. The fix is a one-line change at `admin_skills.py` line 234 (`status="draft"`). Four test functions were updated to reflect the corrected lifecycle semantics. Three integration tests in `test_phase6_integration.py` were also repaired to add explicit activation steps before employee-facing operations. Backend test suite: 934 passed, 7 skipped, 0 failed.

---

_Verified: 2026-03-14T01:45:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — after plan 25-06 gap closure (create_skill default status draft)_
