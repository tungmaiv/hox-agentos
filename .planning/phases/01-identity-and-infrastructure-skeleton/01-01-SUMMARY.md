---
phase: 01-identity-and-infrastructure-skeleton
plan: "01"
subsystem: infra
tags: [docker-compose, fastapi, nextjs, litellm, sqlalchemy, structlog, alembic, pydantic-settings, next-auth, keycloak]

# Dependency graph
requires: []
provides:
  - 6-service Docker Compose stack on blitz-net (postgres, redis, litellm, backend, frontend, celery-worker)
  - LiteLLM proxy config with 4 blitz/* model aliases routing to host Ollama
  - FastAPI backend with core modules (config, logging, db)
  - get_llm() — sole entry point for all LLM clients
  - async SQLAlchemy engine and session factory with Base
  - structlog JSON logging with get_audit_logger()
  - Next.js 15.5 frontend with next-auth v5 Keycloak OIDC (server-side JWT)
  - Alembic async migration environment
affects:
  - 01-02 (Keycloak OIDC + JWT validation — uses core/config Settings, keycloak_jwks_url)
  - 01-03 (database models — uses core/db Base, async_session)
  - 01-04 (FastAPI routes — uses main.py app factory, core modules)
  - All subsequent plans — core/config.py is the sole source of settings

# Tech tracking
tech-stack:
  added:
    - fastapi==0.115.0
    - uvicorn[standard]==0.34.0
    - sqlalchemy==2.0.36 (async)
    - asyncpg==0.30.0
    - alembic==1.14.0
    - pydantic==2.10.0
    - pydantic-settings==2.7.0
    - python-jose[cryptography]==3.3.0
    - structlog==25.1.0
    - celery[redis]==5.4.0
    - langchain-openai==0.3.0
    - next-auth 5.0.0-beta.30 (Auth.js v5)
    - zod 4.3.6
    - next 15.5.12
    - tailwindcss 4.2.1
  patterns:
    - Settings loaded via pydantic-settings from .env; get_settings() is lru_cache singleton
    - get_llm(alias) is the ONLY way to create LLM clients — never provider SDKs directly
    - All logging via structlog (configure_logging + get_audit_logger) — never print() or logging.info()
    - Async SQLAlchemy: create_async_engine + async_sessionmaker + AsyncSession
    - Alembic env.py uses asyncio.run(run_async_migrations()) pattern
    - next-auth JWT strategy: access_token stored server-side only, never sent to browser

key-files:
  created:
    - docker-compose.yml
    - .env.example
    - infra/litellm/config.yaml
    - infra/postgres/init.sql
    - backend/core/config.py
    - backend/core/logging.py
    - backend/core/db.py
    - backend/core/schemas/common.py
    - backend/main.py
    - backend/gateway/tool_registry.py
    - backend/alembic/env.py
    - backend/pyproject.toml
    - backend/Dockerfile
    - backend/tests/test_config.py
    - backend/tests/test_logging.py
    - frontend/src/auth.ts
    - frontend/src/app/layout.tsx
    - frontend/src/app/page.tsx
    - frontend/src/app/login/page.tsx
    - frontend/src/app/chat/page.tsx
    - frontend/src/app/api/auth/[...nextauth]/route.ts
    - frontend/src/hooks/use-auth.ts
    - frontend/src/lib/types.ts
    - frontend/Dockerfile
  modified:
    - .gitignore (pre-existing, no changes needed)

key-decisions:
  - "Used next-auth@beta (5.0.0-beta.30) — next-auth@5 tag does not exist; beta is the v5 API"
  - "alembic.ini uses relative script_location=alembic (not absolute) for portability"
  - "pythonpath=['.''] added to pytest config so core/ module is importable from tests/"
  - "LiteLLM fallbacks use list format (not dict) for proper YAML sequence syntax"
  - "Frontend .env.example uses KEYCLOAK_ISSUER pointing to localhost:8080 for local dev"

patterns-established:
  - "get_llm(alias): single LLM entry point — all agents use this, never provider SDKs"
  - "configure_logging() called once in create_app() at startup"
  - "get_audit_logger() for security events: tool calls, ACL, credential access"
  - "async with async_session() as session: pattern for all DB access"
  - "Settings.derive_keycloak_urls model_validator: auto-derive JWKS URL from URL+realm"

requirements-completed:
  - AUTH-01
  - AUTH-06

# Metrics
duration: 7min
completed: "2026-02-24"
---

# Phase 1 Plan 01: Infrastructure and Project Scaffold Summary

**Docker Compose 6-service stack + FastAPI backend with config/logging/db core modules + Next.js 15.5 frontend with server-side Keycloak JWT auth via next-auth v5**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-24T13:54:41Z
- **Completed:** 2026-02-24T14:01:46Z
- **Tasks:** 3
- **Files modified:** 52

## Accomplishments

- Docker Compose stack with all 6 services (postgres, redis, litellm, backend, frontend, celery-worker) on blitz-net with correct startup order and health checks
- LiteLLM proxy config routing 4 `blitz/*` model aliases to host Ollama via `host.docker.internal:11434` with Claude/GPT fallbacks
- FastAPI backend core modules: `core/config.py` (Settings + `get_llm()`), `core/logging.py` (structlog + `get_audit_logger()`), `core/db.py` (async SQLAlchemy session factory)
- 13 pytest tests passing for config and logging modules
- Next.js 15.5 frontend with next-auth v5 Keycloak OIDC — JWT stored server-side only (XSS protection), TypeScript strict mode, zero compile errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Docker Compose stack and infrastructure templates** - `ef59e9c` (feat)
2. **Task 2: Backend Python scaffold and core modules** - `b2d05cb` (feat)
3. **Task 3: Frontend Next.js 15.5 scaffold with next-auth v5** - `89d03ec` (feat)

## Files Created/Modified

- `docker-compose.yml` - 6-service stack with health checks, blitz-net, startup ordering
- `infra/litellm/config.yaml` - Model routing: blitz-master/fast/coder/summarizer with host Ollama
- `infra/postgres/init.sql` - Enables pgvector + uuid-ossp extensions
- `.env.example` - All required environment variables
- `backend/core/config.py` - Settings (pydantic-settings) + `get_llm()` factory (sole LLM entry point)
- `backend/core/logging.py` - `configure_logging()` (structlog JSON) + `get_audit_logger()`
- `backend/core/db.py` - `async_session`, `Base`, `engine`, `get_db()` FastAPI dependency
- `backend/core/schemas/common.py` - `HealthResponse`, `ErrorResponse` Pydantic models
- `backend/main.py` - FastAPI app factory with CORS middleware and `/health` endpoint
- `backend/gateway/tool_registry.py` - Single tool registry stub (populated Phase 2+)
- `backend/alembic/env.py` - Async Alembic migration environment
- `backend/pyproject.toml` - uv-managed Python 3.12 with all deps pinned
- `backend/tests/test_config.py` - 7 tests for Settings loading and `get_llm()` behavior
- `backend/tests/test_logging.py` - 6 tests for structlog configuration
- `backend/Dockerfile` - python:3.12-slim with uv
- `frontend/src/auth.ts` - next-auth v5 Keycloak config with JWT server-session callbacks
- `frontend/src/app/layout.tsx` - Root layout with SessionProvider
- `frontend/src/app/page.tsx` - Auth-aware redirect (chat or login)
- `frontend/src/app/login/page.tsx` - Keycloak OIDC initiation on mount
- `frontend/src/app/chat/page.tsx` - Protected route stub
- `frontend/src/app/api/auth/[...nextauth]/route.ts` - next-auth API route handler
- `frontend/src/hooks/use-auth.ts` - Client-side auth hook (useSession wrapper)
- `frontend/src/lib/types.ts` - `UserSession`, `ApiError` TypeScript interfaces
- `frontend/Dockerfile` - Node 20 Alpine multi-stage (pnpm + standalone output)

## Decisions Made

- **next-auth@beta used instead of next-auth@5**: The `next-auth@5` npm tag doesn't exist. The v5 rewrite of Auth.js is published as `next-auth@beta` (5.0.0-beta.30). Plan intent was Auth.js v5 API, so beta.30 was used.
- **alembic.ini uses relative `script_location = alembic`**: The `alembic init` command generated an absolute path. Changed to relative for portability (running from `backend/` directory).
- **`pythonpath = ["."]` added to pytest config**: The `core` module is not installed as a package, so pytest needs the `backend/` directory on `sys.path` to import it.
- **LiteLLM fallbacks use list-of-dicts YAML format**: The plan specified fallbacks as `blitz-master: ["anthropic/claude-sonnet-4-6"]` (mixed YAML types). Updated to proper YAML sequence format.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] next-auth@5 tag does not exist on npm**
- **Found during:** Task 3 (Frontend Next.js scaffold)
- **Issue:** `pnpm add next-auth@5` failed — no package version 5 exists; latest stable is 4.24.13
- **Fix:** Used `next-auth@beta` (5.0.0-beta.30) which is the Auth.js v5 rewrite with the exact API the plan code uses
- **Files modified:** frontend/package.json, frontend/pnpm-lock.yaml
- **Verification:** TypeScript compiles with zero errors, next-auth imports resolve correctly
- **Committed in:** `89d03ec` (Task 3 commit)

**2. [Rule 3 - Blocking] pytest ModuleNotFoundError for `core` module**
- **Found during:** Task 2 (Backend scaffold verification)
- **Issue:** `pytest tests/test_logging.py` failed with `ModuleNotFoundError: No module named 'core'`
- **Fix:** Added `pythonpath = ["."]` to `[tool.pytest.ini_options]` in pyproject.toml
- **Files modified:** backend/pyproject.toml
- **Verification:** All 13 tests pass
- **Committed in:** `b2d05cb` (Task 2 commit)

**3. [Rule 3 - Blocking] Alembic init generated absolute path in alembic.ini**
- **Found during:** Task 2 (Alembic initialization)
- **Issue:** `script_location` set to `/home/tungmv/Projects/hox-agentos/backend/alembic` — not portable between environments
- **Fix:** Changed to `script_location = alembic` (relative to where alembic commands are run)
- **Files modified:** backend/alembic.ini
- **Verification:** alembic.ini uses relative path
- **Committed in:** `b2d05cb` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 blocking)
**Impact on plan:** All fixes necessary for correct operation. No scope creep.

## Issues Encountered

- `uv run alembic init` timed out (exit code 120); used direct venv binary path `backend/.venv/bin/alembic init` instead. This is a uv subprocess behavior on this machine.

## User Setup Required

None - no external service configuration required for this plan. Credentials go in `.env` (copied from `.env.example`).

## Next Phase Readiness

- Infrastructure foundation complete; all subsequent Phase 1 plans can build on top of these modules
- Plan 01-02 (Keycloak OIDC + JWT validation) can import `core.config.settings.keycloak_jwks_url` and `settings.keycloak_issuer` directly
- Plan 01-03 (database models) can import `core.db.Base` and `core.db.async_session` directly
- Blockers: None for Phase 1 continuation. Keycloak service not yet in docker-compose (added in 01-02).

---
*Phase: 01-identity-and-infrastructure-skeleton*
*Completed: 2026-02-24*
