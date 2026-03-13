---
phase: 25-skill-builder-tool-resolver
verified: 2026-03-13T04:30:00Z
status: passed
score: 15/15 must-haves verified
re_verification: true
  previous_status: passed
  previous_score: 11/11
  gaps_closed:
    - "POST /api/admin/skills/builder-save no longer 500s — writes to registry_entries via UnifiedRegistryService"
    - "Bell dropdown renders on every click regardless of pendingCount (empty-state shown when count is 0)"
    - "Artifact wizard sends correct skill_type (formState.skill_type) and includes procedure_json for procedural skills"
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
    expected: "POST /api/admin/skills/builder-save returns 200 with a new RegistryEntry row in registry_entries table."
    why_human: "Requires live builder conversation and DB inspection."
---

# Phase 25: Skill Builder Tool Resolver Verification Report

**Phase Goal:** Eliminate hardcoded tool list and LLM-guessed tool names in the procedural skill builder. Insert a `resolve_tools` LangGraph node that maps each workflow step to a verified tool from the live registry. Skills with unresolved tool gaps are saved as `draft` and blocked from activation. When the missing tool is created, auto-promote the skill to `pending_activation` for admin review.
**Verified:** 2026-03-13T04:30:00Z
**Status:** passed
**Re-verification:** Yes — after plans 04 and 05 gap closures (UAT failures fixed)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Hardcoded tool list removed — LLM receives live registry via `_fetch_tool_reference_block()` | VERIFIED | `_RESOLVE_TOOLS_PROMPT` injects `tool_reference` from live registry; prompt instructs LLM to use only exact names from that list |
| 2 | `resolve_tools` node exists in LangGraph and runs before `generate_skill_content` for procedural skills | VERIFIED | `graph.add_node("resolve_tools", _resolve_tools_node)` at line 941; edge `resolve_tools → generate_skill_content` at line 993; both routing functions route procedural skills here |
| 3 | Skills with unresolved tool gaps are saved as `draft` regardless of requested status | VERIFIED | `SkillHandler.on_create()` reads `config.tool_gaps` and sets `entry.status = "draft"` when non-empty; test `test_skill_handler_forces_draft_when_tool_gaps_present` passes |
| 4 | Activating a skill with unresolved gaps returns HTTP 422 | VERIFIED | Registry `PUT /{entry_id}` gate pre-fetches entry, checks `tool_gaps`, raises `HTTPException(status_code=422)` when activating; wired and tested |
| 5 | When a missing tool is created, draft skills with matching gaps are auto-promoted to `pending_activation` | VERIFIED | `ToolHandler.on_create()` scans draft skills, matches slug, promotes to `pending_activation`, clears gaps; 3 tests pass |
| 6 | Resolver falls back to empty lists on LLM error — never crashes the builder graph | VERIFIED | `_resolve_tools_node` wraps entire LLM call in `try/except`, returns `{"resolved_tools": [], "tool_gaps": []}` on any exception; test `test_resolve_tools_node_falls_back_on_llm_error` passes |
| 7 | Gap summary card injected into `validate_and_present` output when gaps exist | VERIFIED | `_format_gap_summary` called in `_validate_and_present_node`; appended to `AIMessage` content; shows resolved items and missing "No tool found for:" slugs |
| 8 | `pending_activation` badge (amber/orange) and inline Activate button visible in admin skills table | VERIFIED | `StatusBadge` explicit case `bg-orange-100 text-orange-700`; `RowActions` renders blue "Activate" button for `pending_activation` items; `handleActivate()` calls `PUT /api/registry/{id}` |
| 9 | `draft` skills with tool gaps show grey badge and warning tooltip with gap count | VERIFIED | `StatusBadge` explicit `bg-gray-100 text-gray-600` for `draft`; warning icon with `title` showing gap count rendered when `tool_gaps.length > 0` |
| 10 | Bell icon in admin nav shows count of `pending_activation` skills with dropdown | VERIFIED | `layout.tsx` uses `useEffect` + plain `fetch` to `/api/registry?type=skill&status=pending_activation`; bell with orange badge and dropdown listing skill names |
| 11 | Tool creation API response includes `unblocked_skills` field | VERIFIED | `create_entry` route returns `dict` with `unblocked_skills` field listing newly-promoted skills when `entry.type == "tool"` (lines 247-252) |
| 12 | POST /api/admin/skills/builder-save succeeds and writes to registry_entries (not skill_definitions) | VERIFIED | `builder_save` calls `_registry_service.create_entry(session, create_data, owner_id=...)` using `UnifiedRegistryService`; no reference to `SkillDefinition` in the builder-save code path |
| 13 | Re-scan path updates existing RegistryEntry in registry_entries | VERIFIED | `body.skill_id` branch calls `_registry_service.get_entry()` then `update_entry()` then `scan_skill_with_fallback` manually; verified at lines 468-508 |
| 14 | Bell dropdown renders on every click (not gated on pendingCount > 0) with empty-state fallback | VERIFIED | Condition at line 173 is `{bellOpen && (` (no pendingCount gate); empty-state `<p>No skills pending activation</p>` rendered when `pendingSkills.length === 0` |
| 15 | Artifact wizard sends correct skill_type from user selection (not hardcoded "instructional") | VERIFIED | `artifact-wizard.tsx` line 282: `payload.skill_type = formState.skill_type \|\| "instructional"`; procedural path adds `procedure_json` from `aiArtifactDraft` |

**Score:** 15/15 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/agents/state/artifact_builder_types.py` | `resolved_tools` and `tool_gaps` fields | VERIFIED | Both fields present with correct type annotations |
| `backend/agents/artifact_builder.py` | `_resolve_tools_node`, graph wiring, `_format_gap_summary` | VERIFIED | All functions present; node registered at line 941; edge at line 993 |
| `backend/registry/handlers/skill_handler.py` | Draft enforcement on `tool_gaps` | VERIFIED | Gap check at end of `on_create()`, sets `entry.status = "draft"` |
| `backend/registry/handlers/tool_handler.py` | Gap auto-resolution promoting to `pending_activation` | VERIFIED | Slug matching; exception-safe; 3 tests pass |
| `backend/api/routes/registry.py` | 422 activation gate + `unblocked_skills` in create response | VERIFIED | Gate at update_entry (lines 268-275); `unblocked_skills` at create_entry (lines 242-252) |
| `backend/prompts/artifact_builder_skill.md` | No hardcoded permissions list; `DERIVED AUTOMATICALLY` note | VERIFIED | Lines 37-39 show `DERIVED AUTOMATICALLY` instruction |
| `frontend/src/app/(authenticated)/admin/skills/page.tsx` | Amber `pending_activation` badge, grey `draft` badge, warning tooltip, inline Activate button | VERIFIED | All four features present |
| `frontend/src/app/(authenticated)/admin/layout.tsx` | Bell with count, dropdown gated on `bellOpen` only, empty-state fallback | VERIFIED | `{bellOpen && (` condition at line 173; `pendingSkills.length === 0` empty-state at line 176-177 |
| `backend/api/routes/admin_skills.py` | `builder_save` using `UnifiedRegistryService.create_entry` and `update_entry` | VERIFIED | `_registry_service.create_entry()` in new-skill path; `_registry_service.get_entry()` + `update_entry()` in re-scan path |
| `frontend/src/components/admin/artifact-wizard.tsx` | `formState.skill_type` in payload; `procedure_json` from `aiArtifactDraft` | VERIFIED | Line 282: `formState.skill_type \|\| "instructional"`; line 289: `aiArtifactDraft?.procedure_json` |
| `backend/tests/registry/test_skill_handler.py` | 2 tests for draft enforcement | VERIFIED | Both tests pass (17 total registry tests pass) |
| `backend/tests/registry/test_tool_handler.py` | 3 tests for auto-resolution | VERIFIED | All 3 tests pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `_route_after_gather_type` | `resolve_tools` node | `return "resolve_tools"` for procedural | WIRED | Line 976 returns `"resolve_tools"` |
| `_route_intent` | `resolve_tools` node | `state.get("resolved_tools") is None` guard | WIRED | Lines 112-113 |
| `resolve_tools` → `generate_skill_content` | edge | `graph.add_edge(...)` | WIRED | Line 993 |
| `SkillHandler.on_create()` | `entry.status = "draft"` | `config.tool_gaps` check | WIRED | Lines 50-58 in skill_handler.py |
| `ToolHandler.on_create()` | `skill.status = "pending_activation"` | slug match | WIRED | Slug matching logic confirmed |
| `PUT /api/registry/{id}` | `HTTPException(422)` | pre-fetch `get_entry`, check `tool_gaps` | WIRED | Lines 268-275 in registry.py |
| `create_entry` route | `unblocked_skills` field | query `pending_activation` skills post-commit | WIRED | Lines 242-252 in registry.py |
| `handleActivate()` (frontend) | `PUT /api/registry/{id}` | `fetch` call with `{status: "active"}` | WIRED | Lines 137-145 in skills/page.tsx |
| `Bell useEffect` | `pending_activation` count display | `fetch` to backend, `setPendingCount` | WIRED | Lines 80-101 in layout.tsx |
| `builder_save` new-skill path | `_registry_service.create_entry` | `await _registry_service.create_entry(session, create_data, owner_id=...)` | WIRED | Line 549 in admin_skills.py |
| `builder_save` re-scan path | `_registry_service.get_entry` + `update_entry` | `await _registry_service.get_entry(session, existing_id)` | WIRED | Lines 475-490 in admin_skills.py |
| `artifact-wizard skill case` | `formState.skill_type` in POST payload | `payload.skill_type = formState.skill_type \|\| "instructional"` | WIRED | Line 282 in artifact-wizard.tsx |

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
| TRES-09 | 25-03 / 25-05 | Bell icon shows count of `pending_activation` skills; dropdown always opens on click | SATISFIED | Bell with `{bellOpen && (` condition; empty-state fallback added in 25-05 |
| TRES-10 | 25-03 | Tool creation API response includes `unblocked_skills` list | SATISFIED | `create_entry` returns `unblocked_skills` field for tool entries |
| TRES-11 | 25-02 | `artifact_builder_skill.md` removes hardcoded permissions list | SATISFIED | `DERIVED AUTOMATICALLY` replaces static list |

No orphaned requirements — all 11 TRES IDs claimed by plans and verified as implemented.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/registry/handlers/skill_handler.py` | ~40 | `session.add(entry)` with `AsyncMock` generates uncollected coroutine warning in tests | Info | Test-only warning; production uses real `AsyncSession` |

No blocker anti-patterns found.

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
**Expected:** POST to `/api/admin/skills/builder-save` succeeds (200) and a new RegistryEntry row appears in `registry_entries` with `type=skill`.
**Why human:** Requires running builder conversation + DB inspection to confirm correct table.

### Gaps Summary

No gaps. All 15 observable truths verified. Plans 04 and 05 correctly closed the two UAT blockers identified after the initial verification: (1) the `builder_save` endpoint was migrated from the dropped `skill_definitions` table to `UnifiedRegistryService` (plan 04), and (2) the bell dropdown empty-state and `artifact-wizard` `skill_type` hardcoding were fixed (plan 05). Backend test suite stands at 929 passed. TypeScript passes with 0 errors.

---

_Verified: 2026-03-13T04:30:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — after plans 04 and 05 gap closures_
