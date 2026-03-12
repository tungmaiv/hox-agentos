# Phase 25: Skill Builder Tool Resolver - Research

**Researched:** 2026-03-13
**Domain:** LangGraph node insertion, registry handler side effects, frontend badge UX
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Builder chat gap output**
- Gap summary is rendered as a structured card (distinct visual component, bordered/boxed), not inline chat text
- Tone: actionable and forward-looking — "Saved as draft. Next: build the missing tool in Tool Builder, then return here to activate."
- All steps shown (both resolved and missing) — not just gap steps
- Missing tool label uses plain language: "No tool found for: send Slack message" (not "MISSING:send-slack-message")
- Each gap also shows a suggested tool name for auto-resolution: "Suggested name: `send-slack-message`"

**Skills list UX (pending_activation)**
- `pending_activation` status: amber badge + inline "Activate" button directly in the table row (no need to navigate to detail page)
- `draft` skills with gaps: grey badge + tooltip on hover showing "X unresolved tool gap(s)" — no new columns
- Activate action: no confirmation dialog — admin action is intentional
- List default sort: unchanged — amber badge provides sufficient visual signal; no reorder or filter tab added

**Admin notification on auto-promotion**
- When a tool is created and resolves skill gaps, the tool creation success message mentions the unblocked skills: "Tool created. 1 skill (daily-standup) moved to pending activation."
- Admin UI: simple query-based bell icon in admin nav showing count of `pending_activation` skills. Clicking opens a dropdown list. No separate notifications table — live query only.
- Bell covers skills needing attention (pending_activation) for MVP scope

**Slug matching**
- Strict substring match: new tool's name must contain the gap's suggested slug as a substring (e.g., tool name `send-slack-message` resolves `MISSING:send-slack-message`)
- If admin named their tool differently: manual gap clear via skill detail page — admin picks the actual tool from a dropdown to resolve each gap explicitly
- Partial gap resolution stays as draft — all gaps must be resolved before promotion to `pending_activation`

### Claude's Discretion
- Exact card styling (border color, padding, icon sizes) for the gap summary block
- Exact dropdown UI for manual gap resolution in skill detail page
- Bell icon placement and popover layout in admin nav

### Deferred Ideas (OUT OF SCOPE)
- Full notification system — Database-backed notifications with read/unread state, timestamps, dismissal, all admin action items
- Fuzzy/semantic slug matching — LLM-assisted gap matching to handle name variations
- MCP tool resolution — Same resolve_tools pattern applied to MCP tools
- Re-run resolver on existing skills — Admin-triggered re-resolution on draft skills
</user_constraints>

---

## Summary

Phase 25 adds a `resolve_tools` LangGraph node to the artifact builder graph that runs exclusively for procedural skills. The node queries the live tool registry (reusing the existing `_fetch_tool_reference_block()` function), sends a bounded matching prompt to `blitz/fast`, and partitions results into `resolved_tools` (matched) and `tool_gaps` (MISSING:intent-name). Skills with non-empty `tool_gaps` are forced to `draft` status by `SkillHandler.on_create()` and blocked from activation at the `PUT /api/registry/{id}` route. When a new tool is created, `ToolHandler.on_create()` scans all draft skills for matching gaps and auto-promotes fully-resolved skills to `pending_activation`. The frontend adds an amber badge for `pending_activation` status and a bell icon in admin nav showing pending count.

The design doc and implementation plan are approved and already exist in `docs/plans/`. The plan is a 9-task TDD sequence with specific file targets, test names, and exact code to insert. All referenced source files have been read and verified. The key finding from code inspection is that the plan's line-number references for `_validate_and_present_node`, `_generate_skill_content_node`, and `create_artifact_builder_graph()` match the actual codebase and the plan's implementation steps are accurate. The `tests/registry/` directory does not yet exist — it must be created in Task 5/6 (Wave 0 gap).

**Primary recommendation:** Execute the implementation plan as written. No architecture changes needed — the plan's design is correct and all integration points match the actual codebase.

---

<phase_requirements>
## Phase Requirements

The phase has no REQUIREMENTS.md-style requirement IDs — the requirements are captured in the design doc and implementation plan. The implementation plan itself constitutes the requirement spec. Below is the behavioral map derived from the design doc and CONTEXT.md:

| ID | Description | Research Support |
|----|-------------|-----------------|
| TRES-01 | `resolve_tools` node runs before `generate_skill_content` for procedural skills only | Graph topology confirmed: `generate_skill_content → validate_and_present` edge exists; `resolve_tools` node is added between gather and generate |
| TRES-02 | Node uses `blitz/fast` for bounded matching, falls back to empty lists on error | `get_llm("blitz/fast")` is the standard pattern via `core/config.py`; fallback pattern matches existing nodes |
| TRES-03 | `ArtifactBuilderState` has `resolved_tools` and `tool_gaps` fields | State file at `backend/agents/state/artifact_builder_types.py` — currently ends at `handler_code` (line 54); two new fields go here |
| TRES-04 | `SkillHandler.on_create()` forces `draft` status when `tool_gaps` is non-empty | Current `on_create` runs security scan then logs — gap enforcement is addable at the end before the final log |
| TRES-05 | `PUT /api/registry/{id}` route blocks `status → active` when `tool_gaps` non-empty, returns 422 | `update_entry` at line 238 delegates to service; gate must be added before the service call |
| TRES-06 | `ToolHandler.on_create()` scans draft skills for matching gaps and promotes to `pending_activation` | Currently a no-op log only — full replacement as per plan |
| TRES-07 | Gap summary rendered as structured card after `validate_and_present` output | Node at line 526 assembles an AIMessage; gap summary appends to its content |
| TRES-08 | `pending_activation` shows amber badge in skills list | `StatusBadge` component at line 120 of skills/page.tsx — exact replacement confirmed |
| TRES-09 | Bell icon in admin nav shows count of `pending_activation` skills | admin/layout.tsx header at line 119 — bell component goes in the right side of the header div |
| TRES-10 | Tool creation API response includes `unblocked_skills` list | `create_entry` route at line 208 returns `RegistryEntryResponse` — needs extension or a separate response field |
| TRES-11 | `artifact_builder_skill.md` removes hardcoded permissions list, adds gap summary template | Prompt file at lines 37-51 contains the static list to replace |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| LangGraph | 0.2+ | Graph node insertion, conditional routing | Already used for all artifact builder nodes |
| SQLAlchemy async | 2.x | Draft skill scan in `ToolHandler.on_create()` | Existing pattern: `async with async_session()` |
| FastAPI | 0.115+ | 422 activation gate in registry route | Already used throughout |
| structlog | Latest | Logging in new nodes and handlers | Project standard — never `print()` or `logging` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `json` (stdlib) | — | Parse LLM JSON array output in `_resolve_tools_node` | Standard; already imported in artifact_builder.py |
| `re` (stdlib) | — | Strip markdown fences from LLM response | Already imported in artifact_builder.py |
| React (hooks) | 18+ | Bell icon state and popover in admin layout | Layout is already `"use client"` with `usePathname` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `blitz/fast` for resolver | `blitz/master` | `blitz/fast` is correct — task is bounded matching, not reasoning. Lower latency. |
| Slug substring matching | Semantic/LLM matching | Slug match is MVP-sufficient; semantic matching deferred per CONTEXT.md |
| Query-based bell icon | DB notifications table | No notifications table needed — live query is simpler and sufficient at 100-user scale |

---

## Architecture Patterns

### Graph Topology

**Existing (all skill types):**
```
START → route_intent → gather_type → [generate_skill_content] → validate_and_present → END
```

**After (procedural skill only):**
```
START → route_intent → gather_type → resolve_tools → generate_skill_content → validate_and_present → END
```

`_route_intent` and `_route_after_gather_type` both need `"resolve_tools"` added to their routing maps. The graph uses `set_conditional_entry_point` for entry and `add_conditional_edges` for post-gather_type routing.

### LangGraph Node Pattern

All existing nodes follow this exact signature:
```python
async def _node_name(state: ArtifactBuilderState, config: RunnableConfig) -> dict:
    ...
```

`_resolve_tools_node` must follow the same pattern. It reads `state.get("artifact_draft")` and must always return a dict with at minimum `resolved_tools` and `tool_gaps` keys (even on error).

### Registry Handler Pattern

`SkillHandler` and `ToolHandler` both implement `on_create(self, entry: object, session: AsyncSession) -> None`. The `entry` parameter uses `getattr()` for attribute access since it is typed as `object`. The session is NOT committed inside the handler — the caller (`UnifiedRegistryService.create_entry()`) owns the transaction.

```python
# CORRECT — no commit inside handler
session.add(skill)
# WRONG — do not commit
await session.commit()
```

### Routing Corrections Needed

The implementation plan's `_route_after_gather_type` replacement (Task 3, Step 4) contains a routing bug to be aware of: the current `_route_after_gather_type` returns `generate_skill_content` for procedural skills without `procedure_json`. The plan replaces this with `resolve_tools` for procedural skills without `procedure_json` AND without `resolved_tools`. The conditional edges map for `gather_type` needs `"resolve_tools": "resolve_tools"` added.

The `_route_intent` function (line 110) also routes procedural skills without `procedure_json` directly to `generate_skill_content`. This routing must be changed to go through `resolve_tools` when `state.get("resolved_tools") is None`.

### Frontend Bell Icon Pattern

Admin layout is already a Client Component (`"use client"` at line 1). It uses `usePathname()` and `useSession()`. The bell component needs:
1. A `useEffect` or SWR call to fetch `GET /api/registry?type=skill&status=pending_activation` count
2. A state variable for count
3. Render a bell icon in the header's right side (where `session?.user?.email ?? "Admin"` currently sits at line 129)

Given the [TECH-DEBT] note in STATE.md about SWR in Server Components causing prerender crashes, the bell must be in the Client Component admin layout (which it already is), NOT in any server component. No SWR issue here.

### Anti-Patterns to Avoid

- **Committing inside a handler:** `on_create` must not call `await session.commit()` — caller owns transaction
- **Mutating JSONB without reassignment:** SQLAlchemy won't track dirty state if you mutate `skill.config` in-place. Always `skill.config = {**old_config, "tool_gaps": remaining}` — the existing `SkillHandler.on_create()` already demonstrates this pattern
- **Checking `resolved_tools is None` vs `resolved_tools == []`:** The node sets `resolved_tools = []` (empty list) on success. Routing must check `is None` to distinguish "resolver not yet run" from "resolver ran with no matches"
- **Matching against full MISSING: prefix:** The slug matching strips `"MISSING:"` before comparing. Matching against `"MISSING:send-slack-message"` as a substring of the tool name would never match

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSONB dirty tracking | Manual dict mutation in-place | Reassign full dict `skill.config = {**skill.config, ...}` | SQLAlchemy tracks object identity, not deep equality |
| LLM JSON parsing | Custom regex parser | `json.loads()` + strip markdown fences | Already in codebase; `re.sub` for fence stripping already imported |
| Permission deduplication | Custom set logic from scratch | Simple seen-set loop as in plan | Five lines; no library needed |
| Notification persistence | DB notifications table | Live query on `status=pending_activation` | 100-user scale; no notification infra needed |

---

## Common Pitfalls

### Pitfall 1: `tool_gaps` check order in `SkillHandler.on_create()`
**What goes wrong:** The scan block runs first and may update `entry.config`. If gap enforcement reads `entry.config` before the scan updates it, the gap check operates on stale config.
**Why it happens:** The scan block does `entry.config = {**config, "security_score": ..., "security_report": ...}`. If gap check reads the local `config` variable (captured before scan), it sees pre-scan state. If it reads `entry.config` (post-scan), it sees the updated dict.
**How to avoid:** The plan adds gap enforcement AFTER the scan block (`try/except` exits), reading `getattr(entry, "config", {}) or {}` from the entry object (post-scan). This is correct — follow the plan's ordering exactly.

### Pitfall 2: Graph conditional edges map missing `resolve_tools`
**What goes wrong:** LangGraph raises a routing error at runtime if `_route_after_gather_type` returns `"resolve_tools"` but the conditional edges map does not include it as a key.
**Why it happens:** The map `{"generate_skill_content": ..., "validate_and_present": ..., END: END}` is exhaustive for the current return values. Adding a new return value requires updating the map.
**How to avoid:** Whenever adding a new return value from a routing function, add the matching key to the edges map in the same commit.

### Pitfall 3: `_route_intent` vs `_route_after_gather_type` — two separate routing paths
**What goes wrong:** Updating only one of the two routing functions means procedural skills reach `generate_skill_content` via one path but correctly go to `resolve_tools` via the other. Behavior is inconsistent based on which path is taken.
**Why it happens:** `_route_intent` is the conditional entry point (fires on every message turn). `_route_after_gather_type` is the post-`gather_type` conditional edge (fires only after `gather_type` node runs). Both route procedural skills, so both must be updated.
**How to avoid:** Task 3 of the plan addresses both. Read both routing functions before implementing.

### Pitfall 4: `update_entry` service call wraps the gap check
**What goes wrong:** The plan adds the gap gate in the route handler before `_registry_service.update_entry()`, but `update_entry` delegates to the service which may also change status. If the service changes status independently, the gate may be bypassed.
**Why it happens:** The service method is a passthrough for the update body. The gate must intercept the `body.status == "active"` check before the service, not after.
**How to avoid:** Fetch the entry first (or query its current config), check `tool_gaps`, then either raise 422 or proceed to the service call. The plan uses `entry = await _registry_service.get_entry(session, entry_id)` to fetch before updating — but the current route does NOT fetch before updating. The plan needs to add a `get_entry` call. Verify the plan's exact implementation against the actual update route (lines 238-261) during execution.

### Pitfall 5: `tests/registry/` directory does not exist
**What goes wrong:** `pytest` cannot discover `tests/registry/test_skill_handler.py` if the directory has no `__init__.py` or if the directory itself does not exist.
**Why it happens:** The directory was never created — no registry handler tests exist in the codebase yet.
**How to avoid:** In Wave 0, create `backend/tests/registry/__init__.py` (empty) alongside the test files. The plan mentions checking with `ls` — follow through.

### Pitfall 6: `RegistryEntryUpdate.status` field type
**What goes wrong:** `body.status == "active"` may fail if `body.status` is `None` (optional field) or if `RegistryEntryUpdate` does not expose a `status` field directly.
**Why it happens:** `RegistryEntryUpdate` is a Pydantic schema. If `status` is optional (`str | None = None`), a comparison with `"active"` when value is `None` raises no error (Python equality is safe) but the gate would never trigger on status-less updates.
**How to avoid:** Read `backend/core/schemas/registry.py` to confirm `RegistryEntryUpdate` has a `status` field. Add `if body.status == "active" and entry.type == "skill":` to avoid false positives on non-skill entries.

---

## Code Examples

### LangGraph Node — Fallback Pattern (verified from existing code)

```python
# Source: backend/agents/artifact_builder.py, all existing nodes
async def _resolve_tools_node(
    state: ArtifactBuilderState, config: RunnableConfig
) -> dict:
    draft = state.get("artifact_draft") or {}
    try:
        llm = get_llm("blitz/fast")
        response = await llm.ainvoke([SystemMessage(content=prompt)])
        ...
        return {"resolved_tools": resolved, "tool_gaps": gaps, ...}
    except Exception as exc:
        logger.warning("tool_resolver_failed", error=str(exc))
        return {"resolved_tools": [], "tool_gaps": [], ...}
```

### JSONB Mutation Pattern (verified from SkillHandler.on_create())

```python
# Source: backend/registry/handlers/skill_handler.py
updated_config = {**config, "security_score": ..., "security_report": ...}
entry.config = updated_config   # reassign full dict — SQLAlchemy dirty tracking
session.add(entry)
# DO NOT commit — caller owns the transaction
```

### Conditional Graph Routing (verified from create_artifact_builder_graph())

```python
# Source: backend/agents/artifact_builder.py lines 793-802
graph.add_conditional_edges(
    "gather_type",
    _route_after_gather_type,
    {
        "generate_skill_content": "generate_skill_content",
        "validate_and_present": "validate_and_present",
        END: END,
        # ADD: "resolve_tools": "resolve_tools"
    },
)
```

### Registry Route — Update Entry (verified from registry.py lines 238-261)

```python
# Source: backend/api/routes/registry.py
@router.put("/{entry_id}")
async def update_entry(entry_id: UUID, body: RegistryEntryUpdate, ...):
    # Gate must be added HERE, before the service call:
    # if body.status == "active" and entry.type == "skill": check tool_gaps
    try:
        entry = await _registry_service.update_entry(session, entry_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    ...
```

Note: The current route does not fetch the entry before updating. The gap gate requires fetching the current entry first to read `config.tool_gaps`. Implementor must add a `get_entry()` call before `update_entry()`, or extend the service to accept pre-validation.

### StatusBadge — Current Implementation (verified from skills/page.tsx line 120)

```tsx
// Source: frontend/src/app/(authenticated)/admin/skills/page.tsx
const StatusBadge = ({ status }: { status: string }) => (
  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
    status === "active" ? "bg-green-100 text-green-700"
    : status === "archived" ? "bg-gray-100 text-gray-500"
    : "bg-yellow-100 text-yellow-700"   // catches draft + pending_activation
  }`}>{status}</span>
);
```

The "else" branch currently catches both `draft` and `pending_activation`. The update adds `pending_activation` as an explicit case with `bg-orange-100 text-orange-700`.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded tool list in `artifact_builder_skill.md` | Live registry query via `_fetch_tool_reference_block()` | Phase 25 | Permissions always accurate |
| LLM-guessed tool names in `generate_skill_content` | Verified tool names from `resolved_tools` injected into prompt | Phase 25 | No hallucinated tool references |
| `ToolHandler.on_create()` was no-op log | Scans draft skills and auto-promotes on gap match | Phase 25 | Skills auto-progress without admin intervention |

---

## Open Questions

1. **`update_entry` service fetch-before-gate pattern**
   - What we know: The current route does NOT fetch the entry before updating — it passes `body` directly to the service.
   - What's unclear: Does `_registry_service.update_entry()` return the fetched entry before applying changes, or does it apply changes blindly?
   - Recommendation: Read `backend/registry/service.py` in the executor session to confirm. If the service returns the entry, extract `config.tool_gaps` from the returned entry and raise 422 post-update (but before commit). If not, add a `get_entry()` pre-fetch.

2. **`RegistryEntryUpdate.status` optional vs required**
   - What we know: The schema is in `backend/core/schemas/registry.py` (not yet read).
   - What's unclear: Whether `status` is always present or optional.
   - Recommendation: Read the schema file in the executor session. Add `if body.status is not None and body.status == "active"` as the gate condition to be safe.

3. **Tool creation response for `unblocked_skills`**
   - What we know: `create_entry` returns `RegistryEntryResponse.model_validate(e)` — a standard response.
   - What's unclear: Whether the plan expects a new response field or a side-channel message.
   - Recommendation: The CONTEXT.md says "tool creation success message mentions the unblocked skills." The simplest approach is to return a custom dict from `create_entry` that includes `unblocked_skills: [{id, name}]`. This requires either extending `RegistryEntryResponse` or returning a `dict` with a `response_model=None` override. Read what the plan specifies in Task 6 for the API response shape.

4. **Bell icon — fetch on every render vs SWR vs polling**
   - What we know: Admin layout is a client component. STATE.md warns about SWR prerender crashes in Server Components (not client components).
   - What's unclear: The plan does not specify the bell's data-fetching strategy.
   - Recommendation: Use `useEffect` with `useState` to fetch count on mount. No SWR — plain `fetch` is fine for a count that changes infrequently. No polling needed — count refreshes on navigation (component remounts).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | `backend/pytest.ini` or `pyproject.toml` |
| Quick run command | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py -q` |
| Full suite command | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TRES-01 | `resolve_tools` node in graph | unit | `pytest tests/agents/test_artifact_builder.py::test_graph_has_resolve_tools_node -x` | ✅ (add to existing) |
| TRES-02 | Node matches known tool, flags missing, falls back on error | unit async | `pytest tests/agents/test_artifact_builder.py::test_resolve_tools_node_matches_known_tool -x` | ✅ (add to existing) |
| TRES-03 | State has resolver fields | unit | `pytest tests/agents/test_artifact_builder.py::test_artifact_builder_state_has_resolver_fields -x` | ✅ (add to existing) |
| TRES-04 | SkillHandler forces draft on gaps | unit async | `pytest tests/registry/test_skill_handler.py -x` | ❌ Wave 0 |
| TRES-05 | Activation gate returns 422 | integration | `pytest tests/api/test_registry_routes.py -x` | ❌ Wave 0 (test added to existing if file exists) |
| TRES-06 | ToolHandler promotes to pending_activation | unit async | `pytest tests/registry/test_tool_handler.py -x` | ❌ Wave 0 |
| TRES-07 | `_format_gap_summary` produces expected output | unit | `pytest tests/agents/test_artifact_builder.py::test_format_gap_summary_with_gaps -x` | ✅ (add to existing) |
| TRES-08 | `pending_activation` badge amber (visual/TypeScript) | TypeScript | `pnpm exec tsc --noEmit` | ✅ (modify existing) |
| TRES-09 | Bell icon renders count (visual) | manual | — | manual-only |
| TRES-10 | `unblocked_skills` in tool create response | integration | manual or API smoke test | manual-only |
| TRES-11 | Prompt updated (doc change) | none | — | manual-only |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py tests/registry/ -q`
- **Per wave merge:** `PYTHONPATH=. .venv/bin/pytest tests/ -q`
- **Phase gate:** Full suite green (920 baseline) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/registry/__init__.py` — empty init, enables pytest discovery
- [ ] `backend/tests/registry/test_skill_handler.py` — covers TRES-04 (created in Task 5)
- [ ] `backend/tests/registry/test_tool_handler.py` — covers TRES-06 (created in Task 6)

---

## Sources

### Primary (HIGH confidence)
- Direct code read: `backend/agents/artifact_builder.py` — current graph structure, routing functions, node patterns, `_fetch_tool_reference_block()`, line numbers verified
- Direct code read: `backend/agents/state/artifact_builder_types.py` — current fields, insertion point confirmed (after line 54)
- Direct code read: `backend/registry/handlers/skill_handler.py` — current `on_create()` structure, scan block, JSONB mutation pattern
- Direct code read: `backend/registry/handlers/tool_handler.py` — current no-op `on_create()`, ready for replacement
- Direct code read: `backend/api/routes/registry.py` — `update_entry` at line 238, no pre-fetch before service call
- Direct code read: `frontend/src/app/(authenticated)/admin/skills/page.tsx` — `StatusBadge` at line 120, `RowActions` at line 128
- Direct code read: `frontend/src/app/(authenticated)/admin/layout.tsx` — client component structure, header at line 119
- Direct code read: `docs/plans/2026-03-13-tool-resolver-design.md` — approved design
- Direct code read: `docs/plans/2026-03-13-tool-resolver-implementation.md` — 9-task TDD plan
- Direct code read: `.planning/phases/25-skill-builder-tool-resolver/25-CONTEXT.md` — locked decisions

### Secondary (MEDIUM confidence)
- `PYTHONPATH=. .venv/bin/pytest tests/ --co 2>&1 | tail -5` — confirmed 920 tests collected as baseline

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in use, no new dependencies
- Architecture: HIGH — code read directly; all integration points verified
- Pitfalls: HIGH — derived from direct code inspection, not speculation
- Open questions: MEDIUM — unread files (registry/service.py, core/schemas/registry.py) create known unknowns

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (stable codebase, no fast-moving dependencies)
