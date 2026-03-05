# Phase 17: Performance & Embedding Sidecar - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract bge-m3 embedding from in-process uvicorn into a dedicated Docker sidecar service (`infinity-emb`). Instrument 7 critical paths with `duration_ms` logging. Eliminate known performance bottlenecks: multiple DB sessions per request, uncached ACL/episode/preference queries, JWKS thundering herd, `useSkills()` re-mount spam.

Creating posts, user-facing UX improvements, and Grafana dashboard design are out of scope for this phase.

</domain>

<decisions>
## Implementation Decisions

### Embedding sidecar behavior
- Use `michaelf34/infinity:latest` as the sidecar image — pre-selected in plans
- **Startup model:** Backend starts immediately with Celery fallback active — sidecar warms up in background (~2-3 min for bge-m3). Once sidecar passes healthcheck, backend switches to it automatically. No blocking of backend boot.
- Celery `BGE_M3Provider` is removed from uvicorn imports only — it stays in Celery workers for the fallback path and scheduled embedding tasks
- Dimension is validated against sidecar health response on startup; mismatch blocks embedding operations with a clear error (does not block the full backend start)
- Model volume mounted at `embedding_model_cache:/app/.cache` — survives container restarts without re-download

### Fallback notification when sidecar is unreachable
- Silent fallback + structlog warning only — no admin alert or Prometheus counter increment
- Rationale: Fallback is expected behavior during startup warm-up; an alert would be noisy. The structured log warning is sufficient for debugging if fallback persists unexpectedly.

### Memory reindex UX (PERF-05)
- **Admin UI button + confirmation dialog** — not API-only
- Button location: Admin desk → Memory tab (new tab or existing Memory Management section)
- Confirmation dialog shows: "This will delete all embedding vectors and re-embed from source text. This cannot be undone. Are you sure?" with a red/destructive confirm button
- After confirmation: backend runs reindex asynchronously (Celery task); admin sees a "Reindex in progress" status indicator
- API endpoint `POST /api/admin/memory/reindex?confirm=true` exists independently for programmatic use

### Performance instrumentation (PERF-07)
- 7 critical paths instrumented: memory search, tool execution, LLM call, canvas compile, MCP call, channel delivery, workflow run
- `timed()` context manager in `core/logging.py` — wraps existing code blocks, logs `duration_ms` via structlog after block exits, logs even if block raises
- No dedicated Grafana dashboard in this phase — `duration_ms` values are searchable in Loki; dashboard deferred to observability work

### DB session optimization (PERF-08)
- Single `AsyncSession` per request via `ContextVar` in `core/db.py` — set by `RequestSessionMiddleware`, consumed by a `get_session()` helper
- All route handlers and service functions that currently do `async with async_session()` will call `get_session()` instead
- Celery tasks are excluded — they don't run in a request context and keep their own session lifecycle

### Caching (PERF-09, PERF-10, PERF-11)
- `cachetools.TTLCache` — 60s TTL, in-process (no Redis)
- Tool ACL: keyed by `(user_id, tool_name)` — cache per user per tool
- Episode threshold: keyed by `user_id`
- User instructions: keyed by `user_id`
- Rationale: In-process cache is sufficient at ~100 user scale; Redis adds complexity without benefit here

### JWKS lock (PERF-12)
- Module-level `asyncio.Lock` in `security/jwt.py` prevents concurrent JWKS refresh
- First request acquires lock, fetches JWKS, all concurrent requests wait and reuse result

### Frontend `useSkills()` hoisting (PERF-13)
- Move `useSkills()` from inside `ChatPanelInner` (inside the CopilotKit `key=` boundary) to parent `ChatPanel` component
- Pass skills as a prop to avoid re-mount on every agent response

### Claude's Discretion
- Exact Grafana alert thresholds (if any) — defer to observability phase
- Sidecar Docker resource limits (memory/CPU) — use reasonable defaults, no constraint needed at 100-user scale
- Exact TTL values for caches if 60s turns out to cause issues during testing
- `RequestSessionMiddleware` placement in FastAPI app middleware stack

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/memory/embeddings.py`: `BGE_M3Provider` class — keep in Celery workers as fallback; replace uvicorn import with `SidecarEmbeddingProvider`
- `backend/core/logging.py`: existing structlog config — add `timed()` context manager here
- `backend/core/db.py`: `async_session()` factory — add `ContextVar` and `get_session()` helper here
- `backend/security/jwt.py`: JWKS fetch logic — add `asyncio.Lock` here
- `frontend/src/components/chat/chat-panel.tsx`: `ChatPanel` + `ChatPanelInner` split — `useSkills()` is in inner, move to outer

### Established Patterns
- `structlog.get_logger(__name__)` for all logging — `timed()` should use the caller's logger, not create one
- Docker Compose services: healthcheck with `start_period: 120s` for slow-starting services (see `keycloak`, `litellm`)
- `cachetools`: new dependency — also used in Plan 17-03 for ACL cache

### Integration Points
- `docker-compose.yml`: new `embedding-sidecar` service after `litellm`, before `backend`
- `backend/core/config.py`: new `embedding_sidecar_url` and `embedding_model` settings
- `backend/main.py`: register `RequestSessionMiddleware`; add sidecar dimension validation on startup
- `backend/api/routes/admin.py` or new `admin_memory.py`: add `POST /api/admin/memory/reindex` endpoint + Celery task
- `frontend/src/app/(authenticated)/admin/`: admin Memory tab UI — add reindex button + confirmation dialog

</code_context>

<specifics>
## Specific Ideas

- The backend should log a `WARNING` level structlog event when it starts in fallback mode: `"embedding_fallback_active": true, "reason": "sidecar_unreachable"` — clear signal in logs without triggering alerts
- The memory reindex confirmation dialog should include an estimate of how long the operation takes (e.g., "This may take 5-15 minutes depending on memory volume") — reduces surprise
- `timed()` should pass through the block's return value transparently, so wrapping a function with `timed()` doesn't change its interface

</specifics>

<deferred>
## Deferred Ideas

- Grafana dashboard for p50/p95 latency visualization — future observability phase
- Prometheus counter for `blitz_embedding_fallback_total` — useful but not required for PERF-07
- GPU support for embedding sidecar — bge-m3 on CPU is sufficient at 100-user scale; GPU would be post-MVP
- Redis-backed distributed cache — in-process TTLCache is sufficient at 100-user scale

</deferred>

---

*Phase: 17-performance-embedding-sidecar*
*Context gathered: 2026-03-05*
