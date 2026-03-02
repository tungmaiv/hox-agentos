# Phase 9: Tech Debt Code Fixes - Research

**Researched:** 2026-03-02
**Domain:** Backend Python — cache invalidation, Prometheus instrumentation, docstring correctness
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Cache invalidation scope**
- Invalidate only the specific tool's cache entry, not the entire tool registry cache
- Use targeted eviction keyed on tool name / tool ID — not a blanket flush
- Invalidation must happen synchronously before the function returns, so the caller sees the updated state immediately within the same request

**Metric label dimensions**
- `blitz_llm_calls_total` counter labels: `model_alias` (e.g. `blitz/master`) and `status` (`success` / `error`)
- No per-user label — avoids high cardinality and PII concerns
- Counter incremented at the point of actual LLM invocation, not at `get_llm()` client construction time (construction alone doesn't mean a call was made)

**Regression test coverage**
- Each bug fix must ship with at least one regression test that would have caught the original bug
- Tests should be unit-level where possible (mock cache / Prometheus registry) — no new integration test infrastructure needed

**Docstring fix scope**
- Fix `list_templates` docstring as scoped — this is the only endpoint named in the success criteria
- If other endpoints have identical inaccuracies and are trivially adjacent in the same file, fixing them in the same pass is acceptable at Claude's discretion

### Claude's Discretion
- All four gray areas above — the user delegated full decision authority for this phase
- Implementation patterns, specific cache key format, Prometheus registry setup
- Whether to use a pytest fixture for the Prometheus counter or reset it between test cases

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EXTD-03 | New registrations available without restart — currently partial: `patch_tool_status()` missing `invalidate_tool_cache()` call (60s window) | Targeted cache eviction by tool name in `_tool_cache` dict; add call after DB commit in `admin_tools.py` |
| EXTD-05 | Removing artifact prevents future invocations — currently partial: `activate_tool_version()` also missing cache invalidation | Same fix path as EXTD-03; `activate_tool_version()` deactivates old versions but cache still serves them for 60s |
| OBSV-01 | Grafana dashboards show agent performance — currently partial: `blitz_llm_calls_total` defined but never incremented | Wrap `ChatOpenAI` to intercept `.invoke()`/`.stream()` calls and increment counter; add `status` label to metric definition |
</phase_requirements>

---

## Summary

Phase 9 closes three backend bugs identified in the v1.1 milestone audit. All three bugs are localized to specific functions with clearly known fix paths — this is precision surgery, not refactoring. No new APIs, no schema changes, no new dependencies.

**Bug 1 (EXTD-03/05):** `patch_tool_status()` and `activate_tool_version()` in `backend/api/routes/admin_tools.py` commit DB changes but never evict the in-process cache. The cache key structure is a plain Python dict (`_tool_cache: dict[str, dict[str, Any]]`) keyed by tool name. Targeted eviction means deleting the specific tool's key from `_tool_cache` — not resetting the global timestamp. This is a one-line fix per function plus a new function `invalidate_tool_cache_entry(name: str)` in `tool_registry.py`.

**Bug 2 (OBSV-01):** `get_llm()` in `backend/core/config.py` constructs and returns a `ChatOpenAI` instance but never instruments it. The CONTEXT decision specifies that the counter must fire at actual invocation time (not construction time) and must carry a `status` label (`success` / `error`). This requires: (a) updating the `blitz_llm_calls_total` Counter in `core/metrics.py` to include the `status` label, (b) subclassing `ChatOpenAI` or wrapping it via LangChain callbacks so actual `.invoke()` / `.stream()` calls increment the counter, and (c) updating the existing test in `test_metrics.py` to use both labels.

**Bug 3 (WKFL-09):** The `list_templates` endpoint in `backend/api/routes/workflows.py` has a docstring stating `"no JWT required — templates are public read"` but uses `Depends(get_user_db)` which chains through `get_current_user` (JWT Gate 1). The fix is a one-line docstring update. No behavior change.

**Primary recommendation:** Fix all three bugs in a single atomic pass per bug (one commit each). Each fix ships with exactly one regression test. Total estimated diff: ~50 lines of code changes + ~60 lines of new tests.

---

## Standard Stack

### Core (already in use — no new dependencies)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `prometheus_client` | Current (in pyproject.toml) | Counter instrumentation | Already used in `core/metrics.py` and `security/acl.py` |
| `langchain_openai` | Current | `ChatOpenAI` base class | `get_llm()` already returns this |
| SQLAlchemy async | Current | DB access in admin routes | Already used in `admin_tools.py` |
| `pytest` | Current | Unit tests | All existing tests use this |
| `pytest-asyncio` | Current | Async test support | `test_tool_registry_db.py` uses `@pytest.mark.asyncio` |

**No new packages required.** All bugs are fixed using existing dependencies.

---

## Architecture Patterns

### Current Code Map

**Bug 1 — Cache invalidation:**
```
backend/api/routes/admin_tools.py
  patch_tool_status()    → commits to DB → MISSING invalidate_tool_cache_entry(tool.name)
  activate_tool_version() → commits to DB → MISSING invalidate_tool_cache_entry(tool.name)

backend/gateway/tool_registry.py
  _tool_cache: dict[str, dict[str, Any]]    ← keyed by tool name
  _tool_cache_timestamp: float              ← global TTL marker
  invalidate_tool_cache()                   ← already exists: resets timestamp (forces full refresh)
  ← MISSING: invalidate_tool_cache_entry(name) for single-key eviction
```

**Bug 2 — LLM metric instrumentation:**
```
backend/core/metrics.py
  blitz_llm_calls_total = Counter(..., ["model_alias"])
  ← NEEDS: add "status" label → Counter(..., ["model_alias", "status"])

backend/core/config.py
  get_llm(alias) → ChatOpenAI(model=..., base_url=..., ...)
  ← NEEDS: return InstrumentedChatOpenAI or wrap with callback

backend/tests/test_metrics.py
  test_llm_call_counter_increments() uses labels(model_alias="blitz/master")
  ← NEEDS: update to labels(model_alias="blitz/master", status="success")
```

**Bug 3 — Docstring:**
```
backend/api/routes/workflows.py  line 107
  """List all template workflows (no JWT required — templates are public read)."""
  ← NEEDS: accurate docstring reflecting that JWT IS required
```

### Pattern 1: Targeted Cache Eviction

**What:** Add a new function `invalidate_tool_cache_entry(name: str)` to `tool_registry.py` that deletes a single key from `_tool_cache` without resetting the global TTL timestamp.

**Why targeted, not blanket:** The CONTEXT locks this decision. Targeted eviction is also more correct: when you disable one tool, other tools in the cache should continue to be served from cache without forcing a full refresh.

**Implementation:**
```python
# In backend/gateway/tool_registry.py — add after invalidate_tool_cache()
def invalidate_tool_cache_entry(name: str) -> None:
    """Evict a single tool entry from the in-process cache.

    Use when a specific tool's status changes (enable/disable/version switch).
    Does NOT reset the global TTL timestamp — other cached entries remain valid.
    """
    _tool_cache.pop(name, None)
    logger.debug("tool_cache_entry_evicted", name=name)
```

**Call site in admin_tools.py:**
```python
# At end of patch_tool_status() — after session.commit()
from gateway.tool_registry import invalidate_tool_cache_entry
invalidate_tool_cache_entry(tool.name)

# At end of activate_tool_version() — after session.commit()
# Note: activate deactivates ALL versions of the same name — evict by name
invalidate_tool_cache_entry(tool.name)
```

**Synchronous guarantee:** Both `patch_tool_status()` and `activate_tool_version()` are async route handlers. The `invalidate_tool_cache_entry()` call is synchronous (dict mutation). It executes before the function returns, so the cache is updated before any subsequent `get_tool()` call within the same process.

### Pattern 2: LangChain Callback-Based LLM Instrumentation

**What:** Use LangChain's built-in callback mechanism to intercept LLM call events and increment the Prometheus counter.

**Why callbacks, not subclassing:** LangChain's `BaseCallbackHandler` is the idiomatic extension point. It avoids touching the `ChatOpenAI` class hierarchy and works with `.invoke()`, `.stream()`, `.ainvoke()`, and `.astream()` transparently.

**Relevant LangChain callback events:**
- `on_llm_start`: fires when LLM call begins (not used for counting — start doesn't guarantee completion)
- `on_llm_end`: fires on successful completion (use for `status="success"` increment)
- `on_llm_error`: fires on error (use for `status="error"` increment)

**Implementation:**
```python
# In backend/core/config.py — add before get_llm()
from langchain_core.callbacks import BaseCallbackHandler
from core.metrics import blitz_llm_calls_total

class _LLMMetricsCallback(BaseCallbackHandler):
    """LangChain callback that increments blitz_llm_calls_total on each LLM call."""

    def __init__(self, model_alias: str) -> None:
        super().__init__()
        self._alias = model_alias

    def on_llm_end(self, response: object, **kwargs: object) -> None:
        blitz_llm_calls_total.labels(model_alias=self._alias, status="success").inc()

    def on_llm_error(self, error: BaseException, **kwargs: object) -> None:
        blitz_llm_calls_total.labels(model_alias=self._alias, status="error").inc()
```

**Updated get_llm():**
```python
def get_llm(alias: str) -> ChatOpenAI:
    model_map: dict[str, str] = { ... }
    model_name = model_map.get(alias, alias)
    return ChatOpenAI(
        model=model_name,
        base_url=f"{settings.litellm_url}/v1",
        api_key=settings.litellm_master_key,
        streaming=True,
        callbacks=[_LLMMetricsCallback(alias)],  # ← add this
    )
```

**Metric definition update in core/metrics.py:**
```python
# Change:
blitz_llm_calls_total = Counter(
    "blitz_llm_calls_total",
    "Total LLM calls by model alias",
    ["model_alias"],
)
# To:
blitz_llm_calls_total = Counter(
    "blitz_llm_calls_total",
    "Total LLM calls by model alias and status",
    ["model_alias", "status"],
)
```

**CRITICAL — Breaking change to existing test:** `test_llm_call_counter_increments()` in `tests/test_metrics.py` currently uses `labels(model_alias="blitz/master")`. Adding the `status` label means calling `.inc()` without `status` will raise a `ValueError`. The test MUST be updated to include the `status` label.

### Pattern 3: Docstring Fix

**What:** Single-line docstring change in `backend/api/routes/workflows.py` line 107.

**Current:**
```python
"""List all template workflows (no JWT required — templates are public read)."""
```

**Fixed:**
```python
"""List all template workflows. Requires JWT — authenticated users only."""
```

**Adjacent endpoints to check:** The module-level docstring at line 7 says `GET /api/workflows/templates — list template workflows (public read)` — this is also inaccurate and is adjacent in the same file. Per CONTEXT discretion clause: fix it in the same pass.

### Anti-Patterns to Avoid

- **Blanket cache flush in admin routes:** Calling `invalidate_tool_cache()` (which resets the global timestamp) instead of per-entry eviction — violates CONTEXT locked decision
- **Incrementing at get_llm() construction time:** The counter must fire at invocation, not at client construction. `get_llm()` is often called at module import time via `lru_cache` patterns — counting construction would inflate the metric to meaningless values
- **Using `try/except` to swallow callback errors:** The callback must not silently fail — if the Prometheus counter registration breaks, a `ValueError` should surface during testing

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM call interception | Custom `ChatOpenAI` subclass overriding `_generate()` | `BaseCallbackHandler` with `on_llm_end` / `on_llm_error` | LangChain callback system is the blessed extension point; it handles streaming, async, retry, and batch modes automatically |
| Cache key management | Custom TTL cache class | Direct `dict.pop()` on the existing `_tool_cache` | The existing module-level dict is the cache — targeted eviction is just `dict.pop()` |
| Prometheus label validation | Runtime label checks | `prometheus_client` raises `ValueError` at first `.inc()` call with wrong labels | The library enforces label consistency — tests will catch mismatches automatically |

---

## Common Pitfalls

### Pitfall 1: `lru_cache` on `get_settings()` Does Not Affect `get_llm()`

**What goes wrong:** Assuming that because `get_settings()` uses `@lru_cache`, `get_llm()` also caches clients. It does not — `get_llm()` creates a new `ChatOpenAI` on every call.

**Why it matters:** The `_LLMMetricsCallback` instance is created fresh per `get_llm()` call. This is correct behavior — each client gets its own callback instance.

**How to avoid:** Do not add `@lru_cache` to `get_llm()`. The callback pattern works correctly without it.

### Pitfall 2: Prometheus Counter Label Mismatch Raises ValueError at Runtime

**What goes wrong:** Adding `status` to `blitz_llm_calls_total` labels in `metrics.py` but forgetting to update `test_metrics.py`. The existing `test_llm_call_counter_increments()` calls `labels(model_alias="blitz/master").inc()` — with 2 labels required, this raises `ValueError: Incorrect label count`.

**Why it happens:** `prometheus_client` enforces that every `.labels()` call provides exactly the declared number of labels.

**How to avoid:** Update `test_metrics.py` `test_llm_call_counter_increments()` to use `labels(model_alias="blitz/master", status="success")` in the same commit as the metrics.py change.

**Warning signs:** `ValueError: Incorrect label count` in test output.

### Pitfall 3: `activate_tool_version()` Deactivates Multiple Rows — Evict By Name Not By ID

**What goes wrong:** `activate_tool_version()` runs a bulk UPDATE to set `is_active=False` for ALL versions of `tool.name`, then sets `is_active=True` for the target. If the cache eviction only removes the target tool's cache entry by its UUID/ID, the other version entries (now deactivated) remain in the cache under their own names.

**Why it matters:** The cache key is `tool.name` (e.g. `"crm.get_project_status"`), not the UUID. All versions share the same name. A single `_tool_cache.pop(tool.name, None)` correctly evicts all entries for that tool name because they all live under the same key.

**How to avoid:** Evict by `tool.name` (the string key), not by `tool.id` (UUID).

### Pitfall 4: `on_llm_end` Receives a `LLMResult` Object — Signature Must Match

**What goes wrong:** LangChain's `on_llm_end` passes a `LLMResult` as the first positional argument (not a keyword). A callback signature like `def on_llm_end(self, **kwargs)` will fail.

**How to avoid:** Use the correct signature: `def on_llm_end(self, response: object, **kwargs: object) -> None`. The `response` parameter receives the `LLMResult` object. Since we only need to increment a counter, we can ignore it.

### Pitfall 5: pytest Prometheus Registry Is Shared Across Test Processes

**What goes wrong:** `prometheus_client.REGISTRY` is a module-level singleton. Tests that increment counters in one test case affect counter values in subsequent test cases within the same pytest process.

**Why it happens:** The existing `test_metrics.py` handles this correctly by reading the value before and after `.inc()` and asserting `after == before + 1.0` — not asserting an absolute value. Follow this pattern in new tests.

**How to avoid:** Always use delta assertions in metric tests: read before, increment, read after, assert `after == before + 1.0`.

---

## Code Examples

### Example 1: Existing `invalidate_tool_cache()` (reference — do not change)

```python
# Source: backend/gateway/tool_registry.py lines 31-34
def invalidate_tool_cache() -> None:
    """Force cache refresh on next get_tool/list_tools call."""
    global _tool_cache_timestamp
    _tool_cache_timestamp = 0.0
```

This function resets the global TTL — it does NOT remove individual entries from `_tool_cache`. The next `get_tool()` or `list_tools()` call with a session will call `_refresh_tool_cache()`, which replaces the entire dict. This is the "blanket flush" approach that CONTEXT says NOT to use for this phase.

### Example 2: Existing `register_tool()` already calls `invalidate_tool_cache()` (for contrast)

```python
# Source: backend/gateway/tool_registry.py lines 161-162
    await session.commit()
    invalidate_tool_cache()
```

`register_tool()` uses the blanket invalidation because inserting/updating a tool definition is a structural change (new tool appears). The phase 9 fixes are status changes on existing tools — targeted eviction is more precise and is what CONTEXT requires.

### Example 3: Existing `blitz_tool_calls_total` instrumentation (reference for LLM pattern)

```python
# Source: backend/security/acl.py lines 35, 73-100
from core.metrics import blitz_tool_calls_total, blitz_tool_duration_seconds

async def log_tool_call(user_id, tool_name, allowed, duration_ms):
    blitz_tool_calls_total.labels(
        tool=tool_name, success=str(allowed)
    ).inc()
    blitz_tool_duration_seconds.labels(tool=tool_name).observe(duration_ms / 1000)
```

The tool metric uses `str(allowed)` for the `success` label. The LLM metric should use the string literal `"success"` or `"error"` (not a boolean cast).

### Example 4: Existing delta assertion pattern in test_metrics.py (must follow for new tests)

```python
# Source: backend/tests/test_metrics.py lines 55-62
def test_llm_call_counter_increments() -> None:
    from core.metrics import blitz_llm_calls_total

    before = _get_counter_value(blitz_llm_calls_total, {"model_alias": "blitz/master"})
    blitz_llm_calls_total.labels(model_alias="blitz/master").inc()
    after = _get_counter_value(blitz_llm_calls_total, {"model_alias": "blitz/master"})
    assert after == before + 1.0
```

After the phase 9 fix, this test must be updated to include `"status": "success"` in the labels dict and the `.labels()` call.

### Example 5: Existing tool registry cache reset in test fixture (reference for new cache tests)

```python
# Source: backend/tests/test_tool_registry_db.py lines 42-52
@pytest.fixture(autouse=True)
def reset_cache():
    """Reset tool cache before each test to prevent cross-test pollution."""
    from gateway.tool_registry import invalidate_tool_cache
    import gateway.tool_registry as tr

    tr._tool_cache.clear()
    invalidate_tool_cache()
    yield
    tr._tool_cache.clear()
    invalidate_tool_cache()
```

New regression tests for cache invalidation in admin routes should use the same `reset_cache` autouse fixture pattern — or inline the cache reset within the test body if the test is in a different file.

---

## State of the Art

| Old Approach | Current Approach | Status in Codebase | Impact of Fix |
|---|---|---|---|
| Full cache flush on any status change | Targeted single-entry eviction by tool name | NOT YET implemented (no invalidation at all) | Disabled tools become unavailable within the same request |
| LLM metric always 0 | Counter incremented via LangChain callback on `on_llm_end`/`on_llm_error` | NOT YET implemented | `blitz_llm_calls_total` in Grafana shows real values |
| Inaccurate docstring | Accurate docstring reflecting JWT requirement | NOT YET fixed | Documentation correctness, no functional change |

---

## Open Questions

1. **`status` label on `blitz_llm_calls_total` — metric schema change**
   - What we know: The existing Counter in `metrics.py` has `["model_alias"]` only. CONTEXT requires `["model_alias", "status"]`.
   - What's unclear: Grafana dashboards querying `blitz_llm_calls_total` without the `status` label will still work (they will see both label dimensions). The Grafana dashboard provisioning files do not currently query this metric (it was never wired), so no Grafana config change is needed.
   - Recommendation: Update `metrics.py` to add `status` label, update `test_metrics.py` to use both labels, verify no other code references `blitz_llm_calls_total` directly.

2. **`bulk_status_update()` in admin_tools.py — also missing cache invalidation**
   - What we know: The phase scope names only `patch_tool_status()` and `activate_tool_version()` as the two functions to fix.
   - What's unclear: `bulk_status_update()` (the `PATCH /api/admin/tools/bulk-status` endpoint) performs the same status change via bulk UPDATE but also has no cache invalidation. It would have the same 60s window bug.
   - Recommendation: Per CONTEXT discretion clause ("trivially adjacent in the same file"), fix `bulk_status_update()` in the same pass. It requires iterating the tool IDs and evicting by tool name.
   - Blocker: `bulk_status_update()` only has the UUIDs (not names) at the point of the bulk UPDATE. Requires either a pre-fetch of names or post-fetch of affected tool names. Flag this for planner decision.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio |
| Config file | `backend/pyproject.toml` (pytest config section) |
| Quick run command | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/test_tool_registry_db.py tests/test_metrics.py tests/api/test_admin_tools.py -q` |
| Full suite command | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q` |
| Estimated runtime | ~15 seconds (quick), ~60 seconds (full) |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXTD-03 | `patch_tool_status()` evicts tool from cache immediately | unit | `PYTHONPATH=. .venv/bin/pytest tests/api/test_admin_tools.py -k "test_patch_status_invalidates_cache" -x` | Wave 0 gap |
| EXTD-05 | `activate_tool_version()` evicts tool from cache immediately | unit | `PYTHONPATH=. .venv/bin/pytest tests/api/test_admin_tools.py -k "test_activate_version_invalidates_cache" -x` | Wave 0 gap |
| EXTD-05 | `invalidate_tool_cache_entry(name)` removes only the named entry | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_tool_registry_db.py -k "test_cache_entry_eviction" -x` | Wave 0 gap |
| OBSV-01 | `blitz_llm_calls_total` increments on LLM invocation | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_metrics.py -k "test_llm" -x` | Exists (needs update) |
| OBSV-01 | `get_llm()` callback fires on mock invoke | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_llm_metrics.py -x` | Wave 0 gap |
| WKFL-09 | `list_templates` docstring does not say "no JWT required" | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_workflows_api.py -k "test_list_templates" -x` | Wave 0 gap |

### Nyquist Sampling Rate

- **Minimum sample interval:** After every committed task, run the quick run command above
- **Full suite trigger:** Before merging final task of this phase
- **Phase-complete gate:** Full suite green (`586+ tests passed`) before `/gsd:verify-work` runs
- **Estimated feedback latency per task:** ~15 seconds

### Wave 0 Gaps (must be created before implementation)

- [ ] `tests/api/test_admin_tools.py` — ADD two new test functions: `test_patch_status_invalidates_cache` and `test_activate_version_invalidates_cache` (file already exists, add to it)
- [ ] `tests/test_tool_registry_db.py` — ADD `test_cache_entry_eviction` test for the new `invalidate_tool_cache_entry()` function (file already exists, add to it)
- [ ] `tests/test_metrics.py` — UPDATE `test_llm_call_counter_increments` to use both `model_alias` and `status` labels (file already exists, modify it)
- [ ] `tests/test_llm_metrics.py` — CREATE new file: tests for `get_llm()` callback instrumentation using a mock LLM invocation

---

## Sources

### Primary (HIGH confidence)

- Direct code read: `backend/gateway/tool_registry.py` — cache structure, `invalidate_tool_cache()`, `_tool_cache` dict
- Direct code read: `backend/api/routes/admin_tools.py` — `patch_tool_status()` and `activate_tool_version()` functions, confirmed no cache eviction call present
- Direct code read: `backend/core/config.py` — `get_llm()` returns bare `ChatOpenAI` with no callbacks
- Direct code read: `backend/core/metrics.py` — `blitz_llm_calls_total` Counter has only `["model_alias"]` label
- Direct code read: `backend/api/routes/workflows.py` line 107 — confirmed incorrect docstring
- Direct code read: `backend/tests/test_metrics.py` — confirmed existing test uses single label
- Direct code read: `backend/tests/test_tool_registry_db.py` — cache fixture pattern for new tests
- Direct code read: `.planning/v1.1-MILESTONE-AUDIT.md` — bug descriptions and integration check findings

### Secondary (MEDIUM confidence)

- LangChain documentation pattern: `BaseCallbackHandler` with `on_llm_end` / `on_llm_error` is the documented extension point for LLM call interception (verified against codebase usage of `langchain_openai` and `langchain_core`)

---

## Metadata

**Confidence breakdown:**
- Bug identification: HIGH — all three bugs directly confirmed by reading source files
- Fix approach for cache eviction: HIGH — `_tool_cache` is a plain dict; `pop()` is unambiguous
- Fix approach for LLM metrics: HIGH — LangChain callback pattern is the standard extension point; `on_llm_end` / `on_llm_error` are stable API
- Fix approach for docstring: HIGH — one-line change, confirmed incorrect text
- Open question on `bulk_status_update()`: LOW — requires planner decision (in-scope or not)
- Label mismatch impact on Grafana: HIGH — current `blitz_llm_calls_total` is never queried in Grafana dashboards (metric was never wired), so no dashboard config change needed

**Research date:** 2026-03-02
**Valid until:** 2026-04-01 (stable dependencies — LangChain callback API is stable)
