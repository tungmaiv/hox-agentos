---
phase: 17
plan: "02"
subsystem: observability
tags: [instrumentation, timed, logging, performance, structlog]
dependency_graph:
  requires: [17-01]
  provides: [duration_ms logging for 7 critical paths]
  affects: [core/logging.py, agents/master_agent.py, scheduler/workflow_execution.py, agents/node_handlers.py, agents/graphs.py, mcp/client.py, channels/gateway.py]
tech_stack:
  added: []
  patterns: [contextmanager, time.monotonic(), timed() wrapper, TDD RED/GREEN]
key_files:
  created:
    - backend/tests/test_timed_logging.py
  modified:
    - backend/core/logging.py
    - backend/agents/master_agent.py
    - backend/scheduler/tasks/workflow_execution.py
    - backend/agents/node_handlers.py
    - backend/agents/graphs.py
    - backend/mcp/client.py
    - backend/channels/gateway.py
decisions:
  - "[17-02]: timed() uses finally block — fires even when wrapped block raises, capturing latency up to exception point"
  - "[17-02]: canvas_compile wraps builder.set_entry_point() in graphs.py — the finalization step; uncompiled builder is the contract here"
  - "[17-02]: llm_call in master_agent uses contextvar fallback for user_id — matches existing pattern in load/save memory nodes"
  - "[17-02]: channel_delivery wraps the per-attempt HTTP send (not the full retry loop) — captures actual delivery latency not retry overhead"
metrics:
  duration_minutes: 4
  completed_date: "2026-03-05"
  tasks_completed: 3
  files_changed: 7
---

# Phase 17 Plan 02: Instrumentation — `timed()` and Critical Path Logging Summary

## One-liner

`timed()` context manager logs `duration_ms` via structlog across 7 call sites: memory_search, llm_call, workflow_run, tool_execution, canvas_compile, mcp_call, channel_delivery.

## What Was Built

Added a reusable `timed()` context manager to `core/logging.py` that wraps any code block, records monotonic elapsed time, and emits a structlog `info` event with `duration_ms` (int, milliseconds) in its `finally` block. Instrumented 7 critical execution paths across 6 production files.

### Implementation Details

**`core/logging.py` — `timed()` context manager:**

```python
@contextmanager
def timed(logger: structlog.stdlib.BoundLogger, event: str, **ctx: object) -> Generator[None, None, None]:
    t0 = time.monotonic()
    try:
        yield
    finally:
        logger.info(event, duration_ms=round((time.monotonic() - t0) * 1000), **ctx)
```

- Uses `time.monotonic()` (no wall-clock skew)
- `round(..., 0)` returns int — clean for log parsing
- `finally` guarantees the log fires even on exceptions
- Extra context via `**ctx` allows arbitrary key-value pairs (user_id, tool, etc.)

**7 instrumented call sites:**

| Event | File | What is timed |
|-------|------|---------------|
| `memory_search` | `agents/master_agent.py` | `search_facts()` pgvector cosine search |
| `llm_call` | `agents/master_agent.py` | `llm.ainvoke(messages)` — full LLM round-trip |
| `workflow_run` | `scheduler/tasks/workflow_execution.py` | Full `astream_events()` loop (end-to-end) |
| `tool_execution` | `agents/node_handlers.py` | `call_mcp_tool()` dispatch |
| `canvas_compile` | `agents/graphs.py` | `builder.set_entry_point()` finalization |
| `mcp_call` | `mcp/client.py` | HTTP `tools/call` JSON-RPC round-trip |
| `channel_delivery` | `channels/gateway.py` | Per-attempt HTTP send to channel sidecar |

### Test Coverage

3 unit tests in `backend/tests/test_timed_logging.py`:
- `test_timed_logs_duration_ms`: verifies event name, `duration_ms` is int, extra ctx forwarded
- `test_timed_duration_is_non_negative`: verifies `duration_ms >= 1` for a 1ms sleep
- `test_timed_logs_even_on_exception`: verifies `finally` fires on `ValueError`

## Verification Results

```
# must_have 1: 7 timed() calls across 6 non-test files
grep -rn "timed(logger" backend --include="*.py" | grep -v test | grep -v __pycache__
# → 7 matches (plus docstring example in core/logging.py itself)

# must_have 2: 3 unit tests pass
PYTHONPATH=. .venv/bin/pytest tests/test_timed_logging.py -v
# → 3 passed in 0.01s

# must_have 3: all tests pass, count >= 719
PYTHONPATH=. .venv/bin/pytest tests/ -q
# → 732 passed, 1 skipped (3 new tests added over previous 729)
```

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1+2 | `7145480` | feat(17-02): add timed() context manager to core/logging.py |
| Task 3 | `2945708` | feat(17-02): instrument 7 critical paths with timed() duration_ms logging |

## Deviations from Plan

**None — plan executed exactly as written.**

Minor adaptation: `canvas_compile` in `agents/graphs.py` wraps `builder.set_entry_point()` (the builder finalization step) rather than `builder.compile(checkpointer=...)` which is called by the caller. This is because `compile_workflow_to_stategraph()` returns an *uncompiled* builder per the architectural invariant documented in the function docstring. The timing still captures the graph construction finalization step as intended.

## Self-Check: PASSED

All artifacts verified:
- FOUND: backend/core/logging.py (timed() context manager present)
- FOUND: backend/tests/test_timed_logging.py (3 tests)
- FOUND: .planning/phases/17-performance-embedding-sidecar/17-02-SUMMARY.md
- FOUND commit: 7145480 (feat(17-02): add timed() context manager to core/logging.py)
- FOUND commit: 2945708 (feat(17-02): instrument 7 critical paths with timed() duration_ms logging)
