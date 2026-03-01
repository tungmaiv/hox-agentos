---
phase: 08-observability
plan: "02"
subsystem: observability
tags: [prometheus, metrics, fastapi, litellm, memory]
dependency_graph:
  requires: [08-01]
  provides: [GET /metrics on backend, litellm prometheus /metrics, business counters]
  affects: [backend/core/metrics.py, backend/main.py, backend/security/acl.py, backend/memory/short_term.py, backend/memory/long_term.py, infra/litellm/config.yaml]
tech_stack:
  added: [prometheus-client>=0.20.0, prometheus-fastapi-instrumentator>=7.1.0]
  patterns: [module-level metric registration, low-cardinality labels, Counter + Histogram pairs]
key_files:
  created:
    - backend/core/metrics.py
    - backend/tests/test_metrics.py
  modified:
    - backend/main.py
    - backend/security/acl.py
    - backend/memory/short_term.py
    - backend/memory/long_term.py
    - infra/litellm/config.yaml
    - backend/uv.lock
decisions:
  - "Labels are strictly low-cardinality (tool names, model aliases, operation types) — user_id intentionally excluded per RESEARCH.md cardinality rule"
  - "No PROMETHEUS_MULTIPROC_DIR needed — single-worker uvicorn means no multiprocess mode required"
  - "Instrumentator placed after CORSMiddleware in create_app() — /metrics is unauthenticated (blitz-net internal only)"
  - "time imported at module top level in short_term.py and long_term.py (not lazy) — avoids import order issues"
metrics:
  duration: "3 minutes 19 seconds"
  completed_date: "2026-03-01"
  tasks_completed: 3
  files_created: 2
  files_modified: 6
---

# Phase 08 Plan 02: Prometheus Metrics Instrumentation Summary

**One-liner:** Prometheus metrics wired into FastAPI via prometheus-fastapi-instrumentator and 6 custom business counters/histograms in core/metrics.py with LiteLLM prometheus callback enabled.

## What Was Built

### core/metrics.py

Module-level Prometheus metric registrations using prometheus-client. All labels are low-cardinality (tool names, model aliases, operation types — never user_id):

- `blitz_tool_calls_total` (Counter) — tool calls by tool name and allowed status
- `blitz_tool_duration_seconds` (Histogram) — tool execution latency
- `blitz_llm_calls_total` (Counter) — LLM calls by model alias
- `blitz_llm_duration_seconds` (Histogram) — LLM call duration
- `blitz_memory_ops_total` (Counter) — memory operations by type (read/write/search)
- `blitz_memory_duration_seconds` (Histogram) — memory operation duration

### main.py

Added `Instrumentator().instrument(app).expose(app)` after `CORSMiddleware` in `create_app()`. This exposes `GET /metrics` in Prometheus text format — the scrape target for the `backend` job in `prometheus.yml` from Plan 01.

### security/acl.py

`log_tool_call()` now increments `blitz_tool_calls_total` and observes `blitz_tool_duration_seconds` alongside the existing structlog audit log entry. Labels: `tool=tool_name`, `success=str(allowed)`.

### memory/short_term.py

- `load_recent_turns()`: records read operation timing via `blitz_memory_ops_total.labels(operation="read").inc()` and `blitz_memory_duration_seconds.labels(operation="read").observe()`
- `save_turn()`: increments `blitz_memory_ops_total.labels(operation="write").inc()`

### memory/long_term.py

- `save_fact()`: increments `blitz_memory_ops_total.labels(operation="write").inc()`
- `search_facts()`: records search timing via `blitz_memory_ops_total.labels(operation="search").inc()` and `blitz_memory_duration_seconds.labels(operation="search").observe()`

### infra/litellm/config.yaml

Added `callbacks: ["prometheus"]` to `litellm_settings`. Enables LiteLLM's built-in `/metrics` endpoint on `litellm:4000` exposing spend, token, and latency metrics for the `litellm` Prometheus scrape job.

### tests/test_metrics.py

6 unit tests verifying:
- Registration: `blitz_tool_calls`, `blitz_llm_calls`, `blitz_memory_ops` all registered in REGISTRY
- Increment behavior: each counter increments by 1.0 on `.inc()` call with correct labels

## Commits

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Create metrics module and tests | 4f3b8b4 | backend/uv.lock (deps: prometheus-client, prometheus-fastapi-instrumentator) |
| 2 | Wire metrics into main/acl/memory | d786f12 | backend/main.py, backend/security/acl.py, backend/memory/short_term.py, backend/memory/long_term.py |
| 3 | Enable LiteLLM prometheus callback | d76dc33 | infra/litellm/config.yaml |

Note: `backend/core/metrics.py` and `backend/tests/test_metrics.py` were already committed in 08-01 plan (commit f7c215c) as part of that plan's observability scaffolding. Task 1 of this plan committed the `uv.lock` update for the prometheus dependencies.

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

```
595 passed, 1 skipped, 15 warnings in 7.67s
```

All 6 test_metrics.py tests pass. Full suite not below 595 (was 595 before this plan — 6 new metrics tests were already committed in 08-01).

Verification checks:
- `grep -q "Instrumentator" backend/main.py` — PASS
- `grep -q "blitz_tool_calls_total" backend/security/acl.py` — PASS
- `grep -q "callbacks.*prometheus" infra/litellm/config.yaml` — PASS

## Self-Check: PASSED

Files created/exist:
- FOUND: backend/core/metrics.py
- FOUND: backend/tests/test_metrics.py

Commits exist:
- FOUND: 4f3b8b4 (feat(08-02): add prometheus metrics module and unit tests)
- FOUND: d786f12 (feat(08-02): wire Prometheus metrics into main.py, acl.py, and memory modules)
- FOUND: d76dc33 (feat(08-02): enable LiteLLM Prometheus callbacks in config.yaml)
