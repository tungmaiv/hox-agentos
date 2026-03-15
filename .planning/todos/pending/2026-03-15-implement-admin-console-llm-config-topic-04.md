---
created: 2026-03-15T06:51:58.504Z
title: "Implement Admin Console LLM Config (Topic #04)"
area: infrastructure
priority: high
target: v1.5-enhancement
effort: 3 weeks
existing_code: 20%
depends_on: []
design_doc: docs/enhancement/topics/04-admin-console-llm-config/00-specification.md
files:
  - backend/api/routes/admin_llm.py
  - frontend/src/app/(authenticated)/admin/system/llm/page.tsx
---

## Problem

LLM configuration has a basic add/delete UI (3 API endpoints, 1 page) that is a thin wrapper around LiteLLM's in-memory API. Changes don't persist across restarts. No fallback chain management, no health monitoring, no cost tracking, no module framework for future extensibility.

## What Exists (20%)

- Admin LLM page at `/admin/system/llm/page.tsx` — list models, add model (alias, provider_model, api_base), delete model
- 3 API endpoints at `/api/admin/llm/models` — GET (list via LiteLLM /model/info), POST (add via /model/new), DELETE (via /model/delete)
- Direct LiteLLM proxy calls — in-memory only, no persistence
- Admin permission gate (requires `tool:admin`)

## What's Needed (80% new — full architectural change)

- **BaseModule framework** — `backend/modules/base/` with 5 new files:
  - `module.py` — BaseModule abstract class with CLI execution
  - `client.py` — ModuleClient with circuit breaker + retry
  - `registry.py` — Redis-backed module discovery
  - `circuit_breaker.py` — circuit breaker pattern
  - `retry.py` — retry policy with exponential backoff
- **Sidecar Docker service** — `litellm-config` container running its own FastAPI app
  - Dockerfile, docker-compose entry, health check
  - 7 CLI commands: add/remove/list/test/update/health/metrics
- **Module Registry in Redis** — `agentos:modules` hash for dynamic module discovery
- **4 new database tables:**
  - `module_metadata` — registered modules with heartbeat tracking
  - `llm_usage_stats` — aggregated daily usage per model
  - `fallback_chains` — fallback chain configurations (JSONB)
  - `model_quotas` — per-model request/token/cost limits
- **4 new frontend pages:**
  - `/admin/llm-configuration/models` — enhanced model management with test connectivity
  - `/admin/llm-configuration/fallbacks` — visual fallback chain builder (drag-and-drop)
  - `/admin/llm-configuration/health` — real-time health dashboard with latency charts
  - `/admin/llm-configuration/costs` — cost tracking with budget alerts and quota management
- **Persistent configuration** — changes survive container restarts
- **Runtime model switching** — per user/role model selection

## Solution

Follow specification at `docs/enhancement/topics/04-admin-console-llm-config/00-specification.md`. Sidecar pattern confirmed for scalability trajectory (100 → 3,000+ users).
