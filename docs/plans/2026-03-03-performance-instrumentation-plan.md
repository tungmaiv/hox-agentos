# Performance Instrumentation Plan — Blitz AgentOS

**Date:** 2026-03-03
**Status:** Proposal
**Author:** Claude (performance assessment)

## Context

The system feels slow even with a single user. The current codebase has scattered Prometheus metrics (tool calls, LLM calls, memory ops) but **no end-to-end request timing** and **no per-node breakdown** for the LangGraph pipeline. We need to instrument every step so we can see exactly where time is spent, then fix the worst offenders.

This plan has two parts: **(A) Add measurement instrumentation**, then **(B) Fix the top bottlenecks** discovered during exploration.

---

## Current Performance Profile (Estimated)

### Per-message request breakdown (backend `agent/run`)

| Step | Estimated Time | Notes |
|------|---------------|-------|
| Gate 1: JWT validation | <1ms (cache hit) / 50-200ms (JWKS refresh) | JWKS cached 5 min |
| Gate 2: RBAC check | <1ms (cache hit) / 5-15ms (DB) | 60s TTL cache |
| Gate 3: Tool ACL check | 5-15ms **every request** | No cache at all |
| `load_memory` — BGE-M3 embed | **200-800ms** | CPU-bound, in request path |
| `load_memory` — pgvector search | 5-30ms | Depends on index type |
| `load_memory` — episode query | 5-15ms | Separate DB session |
| `_pre_route` — keyword classify | <1ms | In-process, no I/O |
| `_master_node` — user instructions | 5-15ms | DB query, no cache |
| `_master_node` — tool list | <1ms (cache hit) / 5-15ms (DB) | 60s TTL cache |
| `_master_node` — LLM call | **2,000-10,000ms** | Ollama via LiteLLM proxy |
| `save_memory` — count + insert | 10-30ms | DB writes |
| `save_memory` — Celery dispatch | 1-5ms | Redis LPUSH per AI turn |
| `save_memory` — episode threshold | 5-15ms | DB query, no cache |
| **Total pre-LLM overhead** | **~250-900ms** | Before user sees any streaming |
| **Total post-LLM overhead** | **~20-65ms** | After stream completes |

### DB session count per `agent/run` request

| Phase | Sessions Opened | Queries |
|-------|----------------|---------|
| Gate 2+3 | 1 | 2 (RBAC + ACL) |
| load_memory (short-term) | 0 or 1 | 0 or 1 SELECT turns |
| load_memory (long-term/pgvector) | 1 | 1 pgvector SELECT |
| load_memory (medium-term episodes) | 1 | 1 SELECT episodes |
| _pre_route (cache miss) | 0-2 | 0-2 SELECTs |
| master_node (user instructions) | 1 | 1 SELECT instructions |
| master_node (tool list, cache miss) | 0-1 | 0-1 SELECT tools |
| save_memory (count + inserts) | 1 | 1 COUNT + N INSERTs |
| save_memory (episode threshold) | 1 | 1 SELECT system_config |
| **Minimum per request** | **6** | **7+** |
| **Maximum (all caches cold)** | **9** | **10+** |

Default SQLAlchemy pool: 5 connections + 10 overflow = 15 max. With 6-9 sessions per request, effective concurrency is limited to ~2 simultaneous users.

### Frontend overhead per chat message

| Step | Estimated Time | Notes |
|------|---------------|-------|
| `auth()` cookie decrypt | 2-5ms | Called on every proxy request |
| Next.js → FastAPI proxy hop | 5-20ms | Same-machine localhost |
| `useSkills()` re-fetch on conversation switch | 50-100ms | Unnecessary remount |
| Conversation list refresh after AI response | 20-50ms | Full list re-fetch |

---

## Part A — Add Timing Instrumentation

### A1. Backend: Request-level timing middleware

**File:** `backend/core/middleware.py` (new)
**Wire in:** `backend/main.py`

Add a lightweight timing middleware that logs total request duration for every endpoint:

```
request_start → ... → request_end
Log: method, path, status, duration_ms
```

Add Prometheus histogram: `blitz_request_duration_seconds` with labels `[method, path, status]`.

### A2. Backend: Per-node timing wrapper for LangGraph nodes

**File:** `backend/agents/master_agent.py`

Wrap each graph node with `time.monotonic()` before/after and log via structlog:

| Node | What to measure |
|------|-----------------|
| `_load_memory_node` | Total + sub-timings: short-term query, BGE-M3 embed, pgvector search, episode query |
| `_pre_route` | Total (should be <1ms on cache hit) |
| `_master_node` | Total + sub-timings: user_instructions query, tool_list query, prompt load, LLM call (TTFT + total) |
| `delivery_router_node` | Total |
| `_save_memory_node` | Total + sub-timings: count query, inserts+commit, celery dispatch, episode threshold query |

Emit structured log per node:
```json
{"event": "node_timing", "node": "load_memory", "total_ms": 850, "embed_ms": 620, "pgvector_ms": 45, "episodes_ms": 12}
```

Add new Prometheus histogram: `blitz_graph_node_duration_seconds` with label `[node]`.

### A3. Backend: Gate timing (JWT + RBAC + ACL)

**File:** `backend/gateway/runtime.py` — `_check_gates()`

Currently only tracks total gate time. Split into:
- Gate 1 (JWT validation): time inside `get_current_user()`
- Gate 2 (RBAC `has_permission`): time inside the call
- Gate 3 (ACL `check_tool_acl`): time inside the call

Log each gate independently. Add to the existing `start_ms` pattern.

### A4. Backend: BGE-M3 embedding timing

**File:** `backend/memory/embeddings.py`

The embed call runs in `run_in_executor` — add timing around the executor call:
```python
t0 = time.monotonic()
result = await loop.run_in_executor(None, model.encode, ...)
embed_ms = (time.monotonic() - t0) * 1000
logger.info("bge_m3_embed", texts=len(texts), duration_ms=embed_ms)
```

### A5. Backend: `/debug/perf` endpoint (dev-only)

**File:** `backend/api/routes/debug.py` (new)

A simple GET endpoint (protected behind `ENVIRONMENT=development` check) that returns:
- Current Prometheus metric values (avg latencies from histograms)
- DB pool stats (`engine.pool.status()`)
- Cache hit rates (RBAC, slash, agent_enabled, JWKS)

### A6. Frontend: Proxy timing in Route Handlers

**Files:** `frontend/src/app/api/copilotkit/route.ts`, `frontend/src/app/api/conversations/route.ts`, etc.

Add `performance.now()` timing around:
1. `auth()` call duration
2. `fetch()` to backend duration
3. Total handler duration

Log to server console: `[PERF] POST /api/copilotkit auth=12ms fetch=1850ms total=1865ms`

### A7. Frontend: Client-side performance marks

**File:** `frontend/src/components/chat/chat-panel.tsx`

Add `performance.mark()` / `performance.measure()` for:
- Time from user pressing Enter to first SSE chunk received (TTFT)
- Time from first chunk to stream complete
- CopilotKit mount → info request → ready

Emit to `console.log` with `[PERF]` prefix for easy filtering in DevTools.

---

## Part B — Fix Top Bottlenecks (Quick Wins)

Based on exploration, these are the fixes ranked by impact:

### B1. BGE-M3 embedding in request path (CRITICAL — est. 200-800ms per request)

**File:** `backend/agents/master_agent.py` — `_load_memory_node()`

**Problem:** `BGE_M3Provider().embed()` runs synchronously in the request handler via `run_in_executor`. This blocks the response for 200-800ms before the LLM even starts. The architecture doc says "CPU-bound: ALWAYS called from Celery workers, NEVER from FastAPI request handlers" but this is violated here.

**Fix:** Cache the last N embeddings with an LRU cache keyed on message text hash. Most repeated/similar queries will hit cache. For genuinely new queries, the embedding still runs but we avoid redundant work.

```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=128)
def _cached_encode(text_hash: str, text: str) -> list[float]:
    return model.encode([text])[0].tolist()
```

**Alternative (more impactful but higher effort):** Move the embedding + pgvector search to a background task that runs concurrently with the LLM call. Facts arrive mid-stream and are appended to context. This eliminates the 200-800ms blocking entirely but requires restructuring the graph topology.

### B2. Fragmented DB sessions — 6-9 per request (HIGH — est. 30-60ms overhead)

**File:** `backend/agents/master_agent.py`

**Problem:** Each node opens its own `async with async_session()`. With default pool of 5, this causes pool contention even at low concurrency.

**Fix:** Create a single session in `event_generator()` (runtime.py), store it in a contextvar, and reuse across all nodes. This reduces 6-9 pool checkouts to 1.

```python
# core/context.py — add:
current_db_session_ctx: ContextVar[AsyncSession] = ContextVar("current_db_session")
```

### B3. Tool ACL has no cache (MEDIUM — 1 DB query per request)

**File:** `backend/security/acl.py`

**Problem:** `check_tool_acl()` queries PostgreSQL on every request with no cache. The ACL for "agents.chat" rarely changes.

**Fix:** Add 60s TTL in-process cache (same pattern as RBAC cache). Key: `(user_id, tool_name)` → `bool`.

### B4. `_get_episode_threshold()` queries DB every request (MEDIUM)

**File:** `backend/agents/master_agent.py`

**Problem:** Opens a DB session to read `system_config` on every `_save_memory_node` call, even though the value almost never changes.

**Fix:** Cache with 60s TTL (same pattern as other caches in the file).

### B5. `get_user_instructions()` queries DB every request (MEDIUM)

**File:** `backend/agents/master_agent.py`

**Problem:** Custom instructions are fetched from DB on every `agent/run` call. They rarely change.

**Fix:** Per-user LRU cache with 60s TTL.

### B6. Frontend: Hoist `useSkills()` above CopilotKit key boundary (LOW-MEDIUM)

**File:** `frontend/src/components/chat/chat-panel.tsx`

**Problem:** Skills are re-fetched on every conversation switch because `useSkills()` lives inside the `key={conversationId}` tree. The `key` forces full unmount/remount of CopilotKit + all children.

**Fix:** Move `useSkills()` to `ChatLayout` (parent component) and pass skills down as props. Skills are essentially static — they only change when an admin updates them.

### B7. JWKS cache thundering herd (LOW — every 5 min)

**File:** `backend/security/jwt.py`

**Problem:** After 5-min TTL expiry, all concurrent requests find `_JWKS_CACHE` stale and all call Keycloak simultaneously. At 100 users, this could fire 100 simultaneous Keycloak HTTP requests.

**Fix:** Add `asyncio.Lock` around the JWKS refresh so only one request refreshes. Others wait for the result.

---

## Critical Files to Modify

| File | Changes |
|------|---------|
| `backend/core/middleware.py` | NEW — request timing middleware |
| `backend/core/metrics.py` | Add `blitz_request_duration_seconds`, `blitz_graph_node_duration_seconds` |
| `backend/main.py` | Wire middleware |
| `backend/agents/master_agent.py` | Per-node timing + B1 embed cache + B2 session reuse + B4 threshold cache + B5 instructions cache |
| `backend/gateway/runtime.py` | Gate timing breakdown + B2 session contextvar |
| `backend/security/acl.py` | B3 ACL cache |
| `backend/security/jwt.py` | B7 JWKS lock |
| `backend/memory/embeddings.py` | A4 embed timing |
| `backend/core/context.py` | B2 add `current_db_session_ctx` |
| `backend/api/routes/debug.py` | NEW — dev-only perf endpoint |
| `frontend/src/app/api/copilotkit/route.ts` | A6 proxy timing |
| `frontend/src/app/api/conversations/route.ts` | A6 proxy timing |
| `frontend/src/components/chat/chat-panel.tsx` | A7 client perf marks + B6 hoist useSkills |

---

## Verification

1. **Timing logs visible:** Send a chat message, check backend logs for `node_timing` events showing ms breakdown for each node
2. **Prometheus metrics:** `curl localhost:8000/metrics | grep blitz_graph_node` shows histogram data
3. **Frontend timing:** Open DevTools Console, filter `[PERF]`, send a message — see TTFT and total stream time
4. **Debug endpoint:** `curl localhost:8000/debug/perf` returns pool stats and cache hit rates
5. **Run existing tests:** `cd backend && PYTHONPATH=. .venv/bin/pytest tests/ -q` — all 258 tests pass
6. **Manual smoke test:** Send 3 messages in chat, verify response time is measurably improved after B1-B5 fixes

---

## Expected Impact After Fixes

| Metric | Before (est.) | After (est.) | Improvement |
|--------|--------------|-------------|-------------|
| Pre-LLM overhead | 250-900ms | 50-150ms | 3-6x faster |
| DB sessions per request | 6-9 | 1-2 | 4-6x fewer pool checkouts |
| Conversation switch (frontend) | 150-250ms | 50-80ms | 2-3x faster |
| JWKS refresh storm (100 users) | 100 parallel requests | 1 request | 100x reduction |
