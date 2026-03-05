# Phase 17: Performance & Embedding Sidecar — Design

**Date:** 2026-03-05
**Status:** Approved
**Requirements:** PERF-01 through PERF-13

---

## Goal

Memory search and agent invocations are fast by default — embedding runs in a dedicated sidecar, critical paths are instrumented, and known bottlenecks are eliminated.

---

## Plan Split

| Plan | Scope | Requirements |
|------|-------|--------------|
| 17-01 | Embedding sidecar + fallback + reindex endpoint | PERF-01, PERF-02, PERF-03, PERF-04, PERF-05, PERF-06 |
| 17-02 | Instrumentation + single DB session per request | PERF-07, PERF-08 |
| 17-03 | TTL caches + JWKS lock + frontend hook stabilization | PERF-09, PERF-10, PERF-11, PERF-12, PERF-13 |

---

## Plan 17-01: Embedding Sidecar

### Sidecar Service

- Image: `michaelf34/infinity`
- Technology: `infinity-emb` — purpose-built embedding server, OpenAI-compat API
- Config: `EMBEDDING_MODEL=BAAI/bge-m3` env var (default); port 7997 internal
- Volume: model cache volume to avoid re-download on restart
- Health: `/health` endpoint reports model name, dimension, status

### Backend: `memory/embeddings.py`

- Add `SidecarEmbeddingProvider`:
  - Calls `POST http://embedding-sidecar:7997/embeddings` (OpenAI-compat format)
  - Returns `list[list[float]]`
- Startup validation: hit sidecar health, parse dimension, compare to `1024` — raise `RuntimeError` on mismatch (PERF-06)
- Fallback (PERF-03): if sidecar unreachable (`httpx.ConnectError`), log warning and route to existing `BGE_M3Provider` Celery path
- `BGE_M3Provider` stays in Celery workers only — removed from uvicorn process (PERF-04)
- `get_embedding_provider()` factory in `core/config.py` returns `SidecarEmbeddingProvider` by default

### Reindex Endpoint (PERF-05)

- `POST /api/admin/memory/reindex` with `{"confirm": true}` body
- Requires `admin` role
- Deletes all `memory_facts` and `memory_episodes` vectors
- Enqueues Celery task that re-embeds from source text
- Returns job ID for polling

### Tests

- Mock `httpx.AsyncClient` for sidecar calls
- Test fallback path by simulating `ConnectError`
- Test dimension mismatch raises `RuntimeError` at startup

---

## Plan 17-02: Instrumentation + DB Session

### `duration_ms` Logging (PERF-07)

Context manager in `core/logging.py`:

```python
@contextmanager
def timed(logger, event: str, **ctx):
    t0 = time.monotonic()
    yield
    logger.info(event, duration_ms=round((time.monotonic()-t0)*1000), **ctx)
```

Applied to 7 call sites:
1. Memory search (`memory/short_term.py`, `memory/long_term.py`)
2. Tool execution (`gateway/runtime.py`)
3. LLM call (`agents/master_agent.py` / subagents)
4. Canvas compile (`agents/graphs.py`)
5. MCP call (`mcp/client.py`)
6. Channel delivery (`channels/gateway.py`)
7. Workflow run (`agents/master_agent.py` `run_workflow`)

No new middleware — wrap existing call sites in each module.

### Single DB Session Per Request (PERF-08)

- `ContextVar[AsyncSession | None]` in `core/db.py`
- FastAPI middleware sets it at request start, clears in `finally`
- `get_session()` helper returns contextvar session if set, else opens a new one
- All `async with async_session()` blocks in route handlers replaced with `get_session()`

---

## Plan 17-03: Caching + Hardening

### In-Process TTL Caches (using `cachetools`)

| Cache | Location | Key | Size | TTL |
|-------|----------|-----|------|-----|
| Tool ACL (PERF-09) | `gateway/agui_middleware.py` | `(user_id, tool_name)` | 500 | 60s |
| Episode threshold (PERF-10) | `memory/medium_term.py` | `user_id` | 200 | 60s |
| User instructions (PERF-11) | wherever instructions loaded | `user_id` | 200 | 60s |

### JWKS Thundering Herd (PERF-12)

- Add `asyncio.Lock` as class-level attribute in `security/jwt.py`
- `_refresh_jwks()` acquires lock before HTTP fetch
- Concurrent requests wait rather than all firing simultaneously

### Frontend Hook Stabilization (PERF-13)

- Problem: `useSkills()` lives inside a component that re-mounts on every agent response (CopilotKit `key` prop changes)
- Fix: move hook call above `<CopilotKitProvider key={...}>` boundary, pass skills down as props
- Result: one mount, no re-fetch spam on every agent response

---

## Architectural Decisions

- **Sidecar technology:** `infinity-emb` (Option A) — purpose-built, already named in PERF-01, OpenAI-compat API, minimal custom code
- **Fallback strategy:** graceful degradation to Celery BGE_M3 path if sidecar unreachable — no hard dependency at boot
- **Caching library:** `cachetools` in-process TTLCache — sufficient at 100-user scale, no Redis overhead
- **Instrumentation:** thin context manager, not middleware — avoids adding latency to every request

## Risk: FlagEmbedding Dual-Load

STATE.md notes: "FlagEmbedding removal must be atomic with sidecar addition." Plan 17-01 must:
1. Add sidecar service
2. Verify sidecar healthy
3. Remove `BGE_M3Provider` from uvicorn process in same commit

Do NOT remove FlagEmbedding from uvicorn before sidecar is confirmed working.
