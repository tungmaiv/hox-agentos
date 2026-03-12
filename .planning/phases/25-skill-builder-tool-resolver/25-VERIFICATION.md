---
phase: 25-skill-builder-tool-resolver
verified: 2026-03-13T00:00:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
---

# Phase 25: Skill Builder Tool Resolver Verification Report

**Phase Goal:** Eliminate hardcoded tool list and LLM-guessed tool names in the procedural skill builder. Insert a `resolve_tools` LangGraph node that maps each workflow step to a verified tool from the live registry. Skills with unresolved tool gaps are saved as `draft` and blocked from activation. When the missing tool is created, auto-promote the skill to `pending_activation` for admin review.
**Verified:** 2026-03-13
**Status:** passed
**Re-verification:** No — initial verification

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
| 7 | Gap summary card injected into `validate_and_present` output when gaps exist | VERIFIED | `_format_gap_summary` called in `_validate_and_present_node`; appended to `AIMessage` content; shows resolved ✅ + missing "No tool found for:" with slugs and "Tool Builder" next steps |
| 8 | `pending_activation` badge (amber/orange) and inline Activate button visible in admin skills table | VERIFIED | `StatusBadge` explicit case `bg-orange-100 text-orange-700`; `RowActions` renders blue "Activate" button for `pending_activation` items; `handleActivate()` calls `PUT /api/registry/{id}` |
| 9 | `draft` skills with tool gaps show grey badge and warning tooltip with gap count | VERIFIED | `StatusBadge` explicit `bg-gray-100 text-gray-600` for `draft`; warning icon with `title` showing gap count rendered when `tool_gaps.length > 0` |
| 10 | Bell icon in admin nav shows count of `pending_activation` skills with dropdown | VERIFIED | `layout.tsx` uses `useEffect` + plain `fetch` to `/api/registry?type=skill&status=pending_activation`; bell with orange badge and dropdown listing skill names; errors silently swallowed |
| 11 | Tool creation API response includes `unblocked_skills` field | VERIFIED | `create_entry` route returns `dict` with `unblocked_skills` field listing up to 5 newly-promoted skills when `entry.type == "tool"` |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/agents/state/artifact_builder_types.py` | `resolved_tools: list[dict] | None` and `tool_gaps: list[dict] | None` fields | VERIFIED | Both fields present at lines 58-61 with correct type annotations |
| `backend/agents/artifact_builder.py` | `_resolve_tools_node`, `_derive_permissions_from_resolved_tools`, `_format_gap_summary`, `_RESOLVE_TOOLS_PROMPT`, graph wiring | VERIFIED | All functions present; `resolve_tools` node registered and wired; both routing functions updated |
| `backend/registry/handlers/skill_handler.py` | Draft enforcement on `tool_gaps` | VERIFIED | Gap check at end of `on_create()`, sets `entry.status = "draft"` when non-empty |
| `backend/registry/handlers/tool_handler.py` | Gap auto-resolution promoting to `pending_activation` | VERIFIED | Full implementation replacing prior no-op; slug matching; exception-safe |
| `backend/api/routes/registry.py` | 422 activation gate + `unblocked_skills` in create response | VERIFIED | Both features implemented: gate at `update_entry` (lines 268-275), `unblocked_skills` at `create_entry` (lines 242-252) |
| `backend/prompts/artifact_builder_skill.md` | No hardcoded permissions list; `DERIVED AUTOMATICALLY` note | VERIFIED | Lines 37-39 show `DERIVED AUTOMATICALLY` instruction; hardcoded list removed |
| `frontend/src/app/(authenticated)/admin/skills/page.tsx` | Amber `pending_activation` badge, grey `draft` badge, warning tooltip, inline Activate button | VERIFIED | All four features present; `StatusBadge` has explicit cases; `RowActions` has styled button; gap tooltip renders when `tool_gaps.length > 0` |
| `frontend/src/app/(authenticated)/admin/layout.tsx` | Bell icon with count and dropdown using `useEffect` + plain `fetch` | VERIFIED | Full implementation at lines 76-101 (state/effect) and 159-188 (UI); `useEffect` + plain `fetch` pattern confirmed |
| `backend/tests/registry/__init__.py` | Empty init for pytest discovery | VERIFIED | File exists at `backend/tests/registry/__init__.py` |
| `backend/tests/registry/test_skill_handler.py` | 2 tests for draft enforcement | VERIFIED | Both tests pass |
| `backend/tests/registry/test_tool_handler.py` | 3 tests for auto-resolution | VERIFIED | All 3 tests pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `_route_after_gather_type` | `resolve_tools` node | `return "resolve_tools"` for procedural without `procedure_json` | WIRED | Line 976 returns `"resolve_tools"`; conditional edges map includes `"resolve_tools": "resolve_tools"` key |
| `_route_intent` | `resolve_tools` node | `state.get("resolved_tools") is None` guard | WIRED | Lines 112-113: `if state.get("resolved_tools") is None: return "resolve_tools"` |
| `resolve_tools` node | `generate_skill_content` node | `graph.add_edge(...)` | WIRED | Line 993: `graph.add_edge("resolve_tools", "generate_skill_content")` |
| `_generate_skill_content_node` | verified tool context | `resolved_context` injected into prompt | WIRED | Lines 842-846: `_derive_permissions_from_resolved_tools` called; `resolved_context` appended to `tool_reference` in prompt |
| `SkillHandler.on_create()` | `entry.status = "draft"` | `config.tool_gaps` check | WIRED | Lines 50-58: reads `config.tool_gaps`, sets status to `"draft"` when non-empty |
| `ToolHandler.on_create()` | `skill.status = "pending_activation"` | slug match on `tool_gaps` in draft skills | WIRED | Lines 59-60: sets status to `"pending_activation"` when `remaining == []` |
| `PUT /api/registry/{id}` | `HTTPException(422)` | pre-fetch `get_entry`, check `tool_gaps` | WIRED | Lines 268-275: gate fires before `update_entry` service call |
| `create_entry` route | `unblocked_skills` field | query `pending_activation` skills post-commit | WIRED | Lines 242-252: queries `list_entries` with `status="pending_activation"`, appends to response dict |
| `handleActivate()` (frontend) | `PUT /api/registry/{id}` | `fetch` call with `{status: "active"}` | WIRED | Lines 137-145: calls `/api/registry/${id}` then `fetchSkills()` |
| Bell `useEffect` | `pending_activation` count display | `fetch` to backend, `setPendingCount` | WIRED | Lines 80-101: fetches count, updates `pendingCount` and `pendingSkills` state |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| TRES-01 | 25-01 | `resolve_tools` node runs before `generate_skill_content` for procedural skills | SATISFIED | Node in graph; both routing functions updated; edge confirmed |
| TRES-02 | 25-01 | Node uses `blitz/fast`, falls back to empty lists on error | SATISFIED | `get_llm("blitz/fast")` in `_resolve_tools_node`; `try/except` fallback tested |
| TRES-03 | 25-01 | `ArtifactBuilderState` has `resolved_tools` and `tool_gaps` fields | SATISFIED | Both fields present with correct types in `artifact_builder_types.py` |
| TRES-04 | 25-02 | `SkillHandler.on_create()` forces `draft` when `tool_gaps` non-empty | SATISFIED | Implementation present; test passes |
| TRES-05 | 25-02 | `PUT /api/registry/{id}` returns 422 blocking `status → active` when gaps exist | SATISFIED | Gate implemented; raises `HTTPException(422)` |
| TRES-06 | 25-02 | `ToolHandler.on_create()` promotes to `pending_activation` | SATISFIED | Implementation present; 3 tests pass including partial-resolution test |
| TRES-07 | 25-02 | Gap summary rendered as structured card in `validate_and_present` | SATISFIED | `_format_gap_summary` injected; correct phrasing and structure tested |
| TRES-08 | 25-03 | `pending_activation` amber badge in skills list | SATISFIED | `bg-orange-100 text-orange-700` explicit case in `StatusBadge` |
| TRES-09 | 25-03 | Bell icon in admin nav shows count of `pending_activation` skills | SATISFIED | Full bell implementation with dropdown in `layout.tsx` |
| TRES-10 | 25-03 | Tool creation API response includes `unblocked_skills` list | SATISFIED | `create_entry` returns `unblocked_skills` field for tool entries |
| TRES-11 | 25-02 | `artifact_builder_skill.md` removes hardcoded permissions list | SATISFIED | `DERIVED AUTOMATICALLY` replaces static list at line 37; gap summary template added in Phase 6 section |

No orphaned requirements — all 11 TRES IDs claimed by plans and verified as implemented.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/registry/handlers/skill_handler.py` | ~40 | `session.add(entry)` with `AsyncMock` generates uncollected coroutine warning in tests | Info | Test-only warning; production code uses real `AsyncSession` — no behavioral impact |

No blocker anti-patterns found. The test warning is cosmetic and pre-dates this phase (same pattern in `skill_repos/service.py`).

### Human Verification Required

#### 1. Resolver end-to-end in Artifact Builder conversation

**Test:** In the Artifact Builder UI, start creating a procedural skill. Provide a description like "Fetch Jira tasks and send a Slack summary." Step through the conversation to completion.
**Expected:** The builder uses exact tool names from the live registry in `procedure_json` steps. If no Slack tool exists, the gap summary card appears with "No tool found for: send Slack summary" and "Saved as draft."
**Why human:** The LLM prompt behavior and gap card rendering can only be verified with the running system.

#### 2. Auto-promotion flow

**Test:** After the above creates a draft skill with a gap, create the missing tool (e.g., `slack.send-message`) in Tool Builder.
**Expected:** The draft skill is automatically promoted to `pending_activation`. The admin bell icon count increments. The skill appears in the bell dropdown.
**Why human:** Requires live DB state transition and UI reactivity verification.

#### 3. Bell count refresh behavior

**Test:** Navigate between admin pages after a skill is promoted to `pending_activation`.
**Expected:** Bell count reflects current `pending_activation` count after each nav (component remount triggers `useEffect`).
**Why human:** `useEffect` re-run on remount cannot be verified statically.

### Gaps Summary

No gaps. All 11 observable truths verified. All 9 commits confirmed in git log. All 13 phase-25-specific tests pass. Full backend suite at 926 passed. TypeScript check passes with 0 errors.

---

_Verified: 2026-03-13_
_Verifier: Claude (gsd-verifier)_
