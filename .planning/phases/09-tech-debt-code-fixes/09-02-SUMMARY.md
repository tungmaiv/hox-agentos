---
phase: 09-tech-debt-code-fixes
plan: "02"
subsystem: observability
tags: [metrics, prometheus, langchain, llm-instrumentation, callbacks]
dependency_graph:
  requires: []
  provides: [blitz_llm_calls_total-instrumented, _LLMMetricsCallback]
  affects: [core/config.py, core/metrics.py, Grafana-ops-dashboard]
tech_stack:
  added: []
  patterns: [LangChain BaseCallbackHandler, lazy-import-in-callback, delta-assertion-in-tests]
key_files:
  created:
    - backend/tests/test_llm_metrics.py
  modified:
    - backend/core/metrics.py
    - backend/core/config.py
    - backend/tests/test_metrics.py
decisions:
  - "Lazy import blitz_llm_calls_total inside callback methods — prevents circular import risk at config.py load time"
  - "No @lru_cache on get_llm() — each call creates a new ChatOpenAI instance with its own callback keyed to the correct alias"
  - "Delta assertions in test_llm_metrics.py — robust against shared prometheus REGISTRY state across test sessions"
metrics:
  duration: "~2 min"
  completed: "2026-03-02"
  tasks_completed: 2
  files_modified: 4
---

# Phase 9 Plan 02: Wire blitz_llm_calls_total to LLM Invocations Summary

**One-liner:** Wired `blitz_llm_calls_total` Prometheus counter to real LLM calls via LangChain `_LLMMetricsCallback` with `model_alias` + `status` labels.

## What Was Done

### Task 1: Add status label to blitz_llm_calls_total and wire _LLMMetricsCallback into get_llm()

**backend/core/metrics.py:**
- Changed `blitz_llm_calls_total` label list from `["model_alias"]` to `["model_alias", "status"]`
- Updated the counter description from "Total LLM calls by model alias" to "Total LLM calls by model alias and status"

**backend/core/config.py:**
- Added `from langchain_core.callbacks import BaseCallbackHandler` import
- Defined `_LLMMetricsCallback(BaseCallbackHandler)` class:
  - `__init__(model_alias: str)` stores alias
  - `on_llm_end(response, **kwargs)` fires `blitz_llm_calls_total.labels(model_alias=alias, status="success").inc()`
  - `on_llm_error(error, **kwargs)` fires `blitz_llm_calls_total.labels(model_alias=alias, status="error").inc()`
  - Both methods use lazy `from core.metrics import blitz_llm_calls_total` to prevent circular imports
- Updated `get_llm()` to pass `callbacks=[_LLMMetricsCallback(alias)]` to `ChatOpenAI` constructor

### Task 2: Update test_metrics.py and create test_llm_metrics.py

**backend/tests/test_metrics.py:**
- Updated `test_llm_call_counter_increments` to use both `model_alias` and `status` labels (was single `model_alias` only, causing `ValueError: Incorrect label names` after metrics.py change)

**backend/tests/test_llm_metrics.py (new file):**
- `test_llm_metrics_callback_increments_on_success` — calls `_LLMMetricsCallback.on_llm_end()` directly, asserts delta +1.0 on `status="success"` counter
- `test_llm_metrics_callback_increments_on_error` — calls `_LLMMetricsCallback.on_llm_error()` directly, asserts delta +1.0 on `status="error"` counter
- `test_get_llm_returns_client_with_callback` — calls `get_llm()`, checks `llm.callbacks` contains `_LLMMetricsCallback` instance

## Key Decisions

1. **Lazy import in callback methods** — `blitz_llm_calls_total` is imported inside `on_llm_end`/`on_llm_error` bodies rather than at module top level. `config.py` is imported early in the startup chain; a top-level `from core.metrics import ...` in `config.py` could create subtle import ordering issues. Python's import cache makes repeated lazy imports cheap.

2. **No `@lru_cache` on `get_llm()`** — Each call creates a new `ChatOpenAI` instance with its own `_LLMMetricsCallback(alias)` instance. Caching would cause all calls from a cached client to share one callback, but more importantly it would prevent callback alias from being correctly keyed if the same client were reused for different aliases. Confirmed in plan RESEARCH.md pitfall section.

3. **Delta assertions in tests** — Tests read `before` value, fire callback, read `after` value, assert `after == before + 1.0`. Prometheus REGISTRY is a global singleton shared across the test session; absolute value assertions would fail if other tests have already incremented the same label combination.

4. **Direct callback invocation in tests** — Tests call `cb.on_llm_end(response=object())` directly rather than making real LLM requests. This avoids needing a live LiteLLM connection while fully testing the metric wiring path.

## Test Results

| Suite | Before | After |
|-------|--------|-------|
| tests/test_metrics.py | 6 pass, 0 fail | 6 pass, 0 fail |
| tests/test_llm_metrics.py | N/A (new) | 3 pass, 0 fail |
| Full suite | 598 pass, 1 skip | 601 pass, 1 skip |

Expected from plan: 258 baseline + 3 plan-01 + 3 plan-02 = 264+ passing. Actual: 601 passing (includes all prior phases).

## Commits

| Task | Hash | Message |
|------|------|---------|
| Task 1 | 45dd190 | feat(09-02): add status label to blitz_llm_calls_total and wire _LLMMetricsCallback into get_llm() |
| Task 2 | 89c69ed | test(09-02): update test_metrics.py and create test_llm_metrics.py |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED
