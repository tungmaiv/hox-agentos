---
phase: 17
plan: "01"
subsystem: memory/embeddings
tags: [embedding, sidecar, docker, performance, tdd]
requirements: [PERF-01, PERF-02, PERF-03, PERF-04]
dependency_graph:
  requires: []
  provides: [embedding-sidecar-service, SidecarEmbeddingProvider, embedding_sidecar_url]
  affects: [memory/embeddings.py, docker-compose.yml, core/config.py]
tech_stack:
  added: [michaelf34/infinity, embedding_model_cache volume]
  patterns: [HTTP-embedding-sidecar, fallback-to-in-process, OpenAI-compat-embedding-API]
key_files:
  created:
    - backend/tests/memory/test_sidecar_embedding.py
  modified:
    - docker-compose.yml
    - backend/core/config.py
    - backend/memory/embeddings.py
decisions:
  - "[17-01]: SidecarEmbeddingProvider falls back to BGE_M3Provider on ConnectError — preserves correctness when sidecar is not yet warm"
  - "[17-01]: validate_dimension() checks /health endpoint at startup — catches EMBEDDING_MODEL misconfiguration early"
  - "[17-01]: embedding_model_cache named volume persists bge-m3 download across container restarts"
metrics:
  duration_minutes: 12
  tasks_completed: 4
  tasks_total: 4
  files_modified: 4
  tests_added: 4
  tests_total: 729
  completed_date: "2026-03-05T12:24:02Z"
---

# Phase 17 Plan 01: Embedding Sidecar Implementation Summary

**One-liner:** Infinity-emb HTTP sidecar for BAAI/bge-m3 with `SidecarEmbeddingProvider` — non-blocking embed calls from FastAPI with automatic fallback to Celery BGE_M3Provider.

## What Was Built

### Task 1: `embedding-sidecar` Docker Compose service (commit: e8e069b)

Added `embedding-sidecar` service using `michaelf34/infinity:latest` image:
- Port 7997, 120s `start_period` to allow model download on first run
- Named volume `embedding_model_cache` to persist downloaded model weights
- Health check via `curl http://localhost:7997/health`
- `EMBEDDING_SIDECAR_URL` and `EMBEDDING_MODEL` added to both `.env` and `backend/.env`

**Files modified:** `docker-compose.yml`

### Task 2: `embedding_sidecar_url` config setting (commit: 498a21c)

Added to `backend/core/config.py` `Settings` class:
```python
embedding_sidecar_url: str = "http://embedding-sidecar:7997"
```
Settable via `EMBEDDING_SIDECAR_URL` env var. Default matches Docker Compose service name.

**Files modified:** `backend/core/config.py`

### Task 3 + 4: `SidecarEmbeddingProvider` TDD (commit: f68075f)

Wrote 4 failing tests first, then implemented the class in `memory/embeddings.py`.

**`SidecarEmbeddingProvider` key behaviors:**
- `embed(texts)`: calls `POST {sidecar_url}/embeddings` with OpenAI-compat payload `{"input": [...], "model": "BAAI/bge-m3"}`, parses `data[].embedding` sorted by `index`
- On `httpx.ConnectError`: falls back to `BGE_M3Provider().embed()` and logs a warning
- `validate_dimension()`: calls `GET {sidecar_url}/health`, checks `dimensions` or `dim` field, raises `RuntimeError` if != 1024

**Files created/modified:**
- `backend/memory/embeddings.py` — added `SidecarEmbeddingProvider` class (66 lines) and updated imports/docstring
- `backend/tests/memory/test_sidecar_embedding.py` — 4 tests (created)

## Verification Evidence

```
PYTHONPATH=. .venv/bin/pytest tests/memory/test_sidecar_embedding.py -v
  test_embed_calls_sidecar                  PASSED
  test_embed_falls_back_on_connect_error    PASSED
  test_validate_dimension_mismatch_raises   PASSED
  test_validate_dimension_ok               PASSED
  4 passed in 1.74s

PYTHONPATH=. .venv/bin/pytest tests/ -q
  729 passed, 1 skipped, 19 warnings in 17.04s
```

Must-haves verified:
1. `grep -n "embedding-sidecar" docker-compose.yml` — service defined at line 59
2. `grep -n "SidecarEmbeddingProvider" backend/memory/embeddings.py` — class at line 108
3. `grep -n "embedding_sidecar_url" backend/core/config.py` — setting at line 75
4. 4 sidecar tests pass
5. Total test count: 729 (> 719 baseline)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

All required files exist and all commits present:
- FOUND: docker-compose.yml
- FOUND: backend/memory/embeddings.py
- FOUND: backend/tests/memory/test_sidecar_embedding.py
- FOUND: backend/core/config.py
- Commits: e8e069b, 498a21c, f68075f — all present in git log
