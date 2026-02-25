# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** Every Blitz employee gets an intelligent, context-aware assistant that automates daily work routines and lets them build custom automations without writing code -- all within an enterprise-secure, on-premise environment.
**Current focus:** Phase 2: Agent Core — 02-03 (memory) complete; only 02-05 (chat UI + slash commands) remaining

## Current Position

Phase: 2 of 8 IN PROGRESS (Agent Core and Conversational Chat)
Plan: 5 of 5 — IN PROGRESS (02-05 remaining)
Status: In progress — 02-01, 02-02, 02-03, 02-04 complete; 02-05 remaining
Last activity: 2026-02-25 -- Completed 02-03-PLAN.md (memory_conversations migration, short-term memory, load/save nodes, GET /api/conversations)

Progress: [█████░░░░░] 40% (8/20 plans estimated)

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Average duration: 9.9 min
- Total execution time: 0.79 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 (complete) | 4 | ~26 min | 6.5 min |
| 02 (in progress) | 4 | ~73 min | 18.3 min |

**Recent Trend:**
- Last 5 plans: 9 min, 20 min, 23 min, 15 min, 19 min
- Trend: consistent 15-23 min for TDD plans in Phase 2

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Split Phase 2 vertically into "Agent Core" (Phase 2) and "Sub-Agents + Memory + Integrations" (Phase 3) to create testable delivery boundaries
- [Roadmap]: Phases 4 (Canvas) and 5 (Channels) can run in parallel -- no mutual dependencies
- [Research]: MCP transport should use Streamable HTTP (not SSE) per spec update 2025-03-26; SDK supports both
- [Research]: Start WhatsApp Business API verification process during Phase 1 (takes 1-4 weeks)
- [Research]: Use Next.js 15.5 (not 16) until CopilotKit confirms 16.x compatibility
- [01-01]: next-auth@5 tag does not exist on npm; use next-auth@beta (5.0.0-beta.30) for Auth.js v5 API
- [01-01]: uv run subcommands time out on this machine; use direct .venv/bin/ binary paths for alembic and pytest
- [01-01]: alembic.ini must use relative script_location = alembic (not absolute path) for portability
- [01-01]: pythonpath = ["."] required in pytest config so core/ module is importable from tests/
- [01-02]: _fetch_jwks_from_remote() separated from _get_jwks() cache manager so cache-hit test can mock only HTTP, not cache logic
- [01-02]: conftest.py uses os.environ.setdefault() so unit tests run without .env but real .env values are not overridden
- [01-02]: make_token fixture reads iss/aud from live core.config.settings at call time (not hardcoded) to survive module reload side effects from test_config.py
- [01-03]: ROLE_PERMISSIONS uses explicit enumeration per role (no inheritance chain) -- readable, auditable, testable
- [01-03]: Tool ACL default policy is ALLOW (no row = True); deny requires explicit row with allowed=False
- [01-03]: structlog with LoggerFactory() writes to stdout; use capsys in tests (not caplog) to capture audit log output
- [01-03]: aiosqlite for ACL unit tests -- no real PostgreSQL needed; all ACL queries are standard SQL
- [01-04]: GET /health has no /api prefix so Docker/load balancer health checks can reach it without credentials
- [01-04]: Integration tests that reach Gate 3 (check_tool_acl) need SQLite session override; employee/executive pass RBAC and hit DB
- [01-04]: conftest.py calls configure_logging() at session start -- prevents structlog config ordering failures in full test suite
- [01-04]: test_config.py must not call reload() inside patch.dict -- reload persists module state after patch exits, contaminating JWT issuer in subsequent tests
- [01-04]: test_acl.py audit log test now uses caplog+capsys combined -- stdlib.LoggerFactory routes to caplog, not capsys
- [01-04]: auth.ts uses double cast (session as unknown as Record) to satisfy TypeScript strict TS2352
- [02-01]: ChatOpenAI stores base_url as openai_api_base and model as model_name (langchain-openai internal attr names); constructor uses aliases base_url/model
- [02-01]: LiteLLM general_settings.master_key uses os.environ/VAR_NAME interpolation syntax (not ${VAR} shell syntax)
- [02-01]: get_llm() tests can call the function directly without settings override -- module settings already has litellm_url from conftest/env
- [02-02]: CopilotKitSDK is deprecated since 0.1.31 -- use CopilotKitRemoteEndpoint instead (identical API)
- [02-02]: LangGraph 0.4.10 uses compiled.builder.branches (not compiled.graph.branches) to inspect conditional edges; compiled.graph attribute does not exist
- [02-02]: Never use importlib.reload() inside patch() for mocking module-level names -- reload rebinds from real source, bypassing patch; patch the module-level name directly
- [02-02]: copilotkit.integrations.fastapi.handler() used as delegate inside secured FastAPI route -- avoids add_fastapi_endpoint() which would bypass security
- [02-02]: CopilotKit agent name is 'blitz_master' -- frontend useCopilotAgent/useCoAgent must reference this exact string
- [02-03]: current_user_ctx moved from gateway/runtime.py to core/context.py -- breaks circular import between runtime.py and master_agent.py; both import from core/context.py
- [02-03]: Alembic merge migration 9754fd080ee2 required when both 002 and 003 branch from 001 -- created via .venv/bin/alembic merge 002 003; alembic_version single head is now 9754fd080ee2
- [02-03]: SQLite timestamp ordering non-deterministic in in-memory tests -- test load_recent_turns by checking len()==n not specific content at turns[0]
- [02-03]: load_recent_turns uses ORDER BY created_at DESC LIMIT n then list(reversed()) -- gets newest n turns in chronological order
- [02-03]: CopilotKit sends threadId (not thread_id) as conversation UUID in AG-UI request body; fallback check added for both field names
- [02-04]: Credential vault upsert uses select-then-insert/update (not ON CONFLICT DO UPDATE) -- needed for SQLite compatibility in TDD tests; works on both SQLite and PostgreSQL
- [02-04]: Migration 003 branches from 001 (down_revision="001") -- parallel with 002 (memory_conversations); merge migration required when both exist
- [02-04]: Alembic upgrade from host fails without .env; applied migration via docker exec psql trust auth -- same constraint as 001
- [02-04]: _get_key() checks CREDENTIAL_ENCRYPTION_KEY env var before settings -- allows os.environ.setdefault() injection in TDD tests

### Pending Todos

- [ ] Start WhatsApp Business API verification process (takes 1-4 weeks, needed for Phase 5)
- [ ] Add CREDENTIAL_ENCRYPTION_KEY to production .env before Phase 3 OAuth flows (generate: python -c "import secrets; print(secrets.token_hex(32))")

### Blockers/Concerns

- WhatsApp Business API verification takes 1-4 weeks -- start process early even though adapter is Phase 5
- A2UI is in Public Preview (v0.8) -- monitor for breaking changes before Phase 3
- CopilotKit + LangGraph HITL has known ZodError -- use graph interrupt nodes instead (affects Phase 4)
- uv run subcommands time out on this machine; use .venv/bin/ paths directly for CLI tools
- python-jose uses datetime.utcnow() internally (deprecated in Python 3.12) -- harmless warning in tests, not actionable
- Alembic migration from host requires .env (not present); migrations applied via docker exec psql trust auth inside container

## Session Continuity

Last session: 2026-02-25T04:41:01Z
Stopped at: Completed 02-03-PLAN.md — memory_conversations migration, short-term memory, load/save graph nodes, GET /api/conversations (90 tests pass)
Resume file: None
