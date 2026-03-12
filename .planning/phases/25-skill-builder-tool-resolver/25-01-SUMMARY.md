---
phase: 25-skill-builder-tool-resolver
plan: "01"
subsystem: agents
tags: [langgraph, artifact-builder, tool-resolver, tdd, procedural-skill]

# Dependency graph
requires:
  - phase: 23-skill-builder
    provides: artifact_builder.py, ArtifactBuilderState, _fetch_tool_reference_block
  - phase: 24-unified-registry-mcp-platform
    provides: RegistryEntry model, active tool registry

provides:
  - ArtifactBuilderState.resolved_tools and tool_gaps fields
  - _resolve_tools_node: maps procedural skill steps to registry tools via blitz/fast LLM
  - _derive_permissions_from_resolved_tools: deduplicates permission union from resolved steps
  - resolve_tools wired into LangGraph topology before generate_skill_content
  - Verified tool context injected into _generate_skill_content_node prompt
  - tests/registry/__init__.py for plan 25-02 test discovery

affects:
  - 25-02 (registry ACL enforcement uses resolved_tools and tool_gaps from state)
  - future skill execution (required_permissions derived from resolver, not guessed by LLM)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tool resolver: single blitz/fast LLM call maps step intents to exact registry tool names"
    - "MISSING: prefix convention for unresolvable steps — tool_gaps list"
    - "resolved_tools is None guard: distinguishes not-yet-run from ran-with-no-matches"
    - "TDD: write failing test, verify FAIL, implement, verify PASS, commit"

key-files:
  created:
    - backend/tests/registry/__init__.py
  modified:
    - backend/agents/state/artifact_builder_types.py
    - backend/agents/artifact_builder.py
    - backend/tests/agents/test_artifact_builder.py

key-decisions:
  - "resolved_tools: list[dict] | None — None means not yet run, [] means ran with no matches (guard: state.get('resolved_tools') is None)"
  - "blitz/fast (not blitz/master) for resolver — bounded matching task, faster/cheaper than complex reasoning"
  - "Falls back to empty lists on ANY exception — resolver must never crash the builder graph"
  - "resolve_tools node wired before generate_skill_content — tool names locked before content generation"
  - "required_permissions derived from resolved_tools in generate node, not guessed in gather_details"

patterns-established:
  - "Resolver guard pattern: if state.get('resolved_tools') is None: route to resolve_tools"
  - "Fallback-safe LLM node: try/except returning empty state on any error"

requirements-completed: [TRES-01, TRES-02, TRES-03]

# Metrics
duration: 4min
completed: 2026-03-12
---

# Phase 25 Plan 01: State Extension, resolve_tools Node, and Graph Wiring Summary

**LangGraph tool resolver node that maps procedural skill steps to exact registry tool names via blitz/fast LLM, with MISSING: prefix for gaps, wired into artifact builder graph before content generation**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-12T19:01:59Z
- **Completed:** 2026-03-12T19:05:54Z
- **Tasks:** 3
- **Files modified:** 3 (+ 1 created)

## Accomplishments

- Extended ArtifactBuilderState with `resolved_tools: list[dict] | None` and `tool_gaps: list[dict] | None` fields
- Implemented `_resolve_tools_node`: single blitz/fast LLM call, splits results into resolved (matched) and gaps (MISSING: prefix), falls back to empty lists on any error
- Wired resolve_tools into graph topology: gather_type → resolve_tools → generate_skill_content for procedural skills; _route_intent also routes procedural skills with resolved_tools=None to resolver
- Added `_derive_permissions_from_resolved_tools`: deduplicates permission union from all resolved tool steps
- Injected verified tool mapping context into `_generate_skill_content_node` prompt — LLM uses exact tool names from registry
- Created `tests/registry/__init__.py` to enable plan 25-02 test discovery
- 6 new TDD tests — all passing, full suite 919 passed no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend ArtifactBuilderState with resolver fields** - `4440e8d` (feat)
2. **Task 2: Implement _resolve_tools_node with fallback** - `635f6e0` (feat)
3. **Task 3: Wire resolve_tools into graph, add permission helper, inject context** - `4448ba1` (feat)

## Files Created/Modified

- `backend/agents/state/artifact_builder_types.py` - Added resolved_tools and tool_gaps TypedDict fields
- `backend/agents/artifact_builder.py` - Added _RESOLVE_TOOLS_PROMPT, _resolve_tools_node, _derive_permissions_from_resolved_tools; updated graph wiring; injected context in generate node
- `backend/tests/agents/test_artifact_builder.py` - 6 new TDD tests for resolver functionality
- `backend/tests/registry/__init__.py` - Empty init for pytest discovery (new file)

## Decisions Made

- `resolved_tools is None` guards routing — distinguishes "not yet run" from "ran with no matches"; critical for graph to not loop
- Used `blitz/fast` alias for resolver (not `blitz/master`) — bounded matching task doesn't need complex reasoning
- Fallback to empty lists on ANY exception — resolver must never propagate errors into the builder graph
- `required_permissions` derived from resolved_tools in generate node, injected into draft before LLM generates content

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Tool resolver foundation complete — plan 25-02 can implement ACL enforcement using resolved_tools and tool_gaps
- `tests/registry/` directory ready for plan 25-02 registry-level tests
- `_resolve_tools_node` importable from `agents.artifact_builder` as required by plan 25-02

## Self-Check: PASSED

All files verified present. All task commits found.

---
*Phase: 25-skill-builder-tool-resolver*
*Completed: 2026-03-12*
</content>
</invoke>