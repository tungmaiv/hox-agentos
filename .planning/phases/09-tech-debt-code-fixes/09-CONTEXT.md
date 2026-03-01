# Phase 9: Tech Debt Code Fixes - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Close 3 specific backend bugs identified in the v1.1 audit:
1. Tool status cache not invalidated on `patch_tool_status()` / `activate_tool_version()` — disabled tools remain available until 60s TTL expires
2. `get_llm()` does not increment `blitz_llm_calls_total` Prometheus counter — metric always reads 0
3. `list_templates` endpoint docstring incorrectly describes its auth requirement

No new capabilities. No API surface changes. Fix existing behavior to match documented intent.

</domain>

<decisions>
## Implementation Decisions

### Cache invalidation scope
- Invalidate only the specific tool's cache entry, not the entire tool registry cache
- Use targeted eviction keyed on tool name / tool ID — not a blanket flush
- Invalidation must happen synchronously before the function returns, so the caller sees the updated state immediately within the same request

### Metric label dimensions
- `blitz_llm_calls_total` counter labels: `model_alias` (e.g. `blitz/master`) and `status` (`success` / `error`)
- No per-user label — avoids high cardinality and PII concerns
- Counter incremented at the point of actual LLM invocation, not at `get_llm()` client construction time (construction alone doesn't mean a call was made)

### Regression test coverage
- Each bug fix must ship with at least one regression test that would have caught the original bug
- Tests should be unit-level where possible (mock cache / Prometheus registry) — no new integration test infrastructure needed

### Docstring fix scope
- Fix `list_templates` docstring as scoped — this is the only endpoint named in the success criteria
- If other endpoints have identical inaccuracies and are trivially adjacent in the same file, fixing them in the same pass is acceptable at Claude's discretion

### Claude's Discretion
- All four gray areas above — the user delegated full decision authority for this phase
- Implementation patterns, specific cache key format, Prometheus registry setup
- Whether to use a pytest fixture for the Prometheus counter or reset it between test cases

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches consistent with the existing codebase patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 09-tech-debt-code-fixes*
*Context gathered: 2026-03-02*
