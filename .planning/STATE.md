# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** Every Blitz employee gets an intelligent, context-aware assistant that automates daily work routines and lets them build custom automations without writing code -- all within an enterprise-secure, on-premise environment.
**Current focus:** Phase 2: Agent Core — begin LangGraph master agent, tool registration, and memory foundation

## Current Position

Phase: 2 of 8 IN PROGRESS (Agent Core and Conversational Chat)
Plan: 1 of 5 — COMPLETE (02-01 done)
Status: In progress — 02-01 complete, 02-02 through 02-05 remaining
Last activity: 2026-02-25 -- Completed 02-01-PLAN.md (LiteLLM config + get_llm() TDD tests)

Progress: [██░░░░░░░░] 25% (5/20 plans estimated)

## Performance Metrics

**Velocity:**
- Total plans completed: 5
- Average duration: 6.3 min
- Total execution time: 0.51 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 (complete) | 4 | ~26 min | 6.5 min |
| 02 (in progress) | 1 | ~5 min | 5 min |

**Recent Trend:**
- Last 5 plans: 7 min, 4 min, 3 min, 9 min, 20 min (includes checkpoint wait)
- Trend: Stable

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

### Pending Todos

- [ ] Start WhatsApp Business API verification process (takes 1-4 weeks, needed for Phase 5)
- [ ] Plan Phase 2 (Agent Core): LangGraph master agent, tool registration, memory foundation

### Blockers/Concerns

- WhatsApp Business API verification takes 1-4 weeks -- start process early even though adapter is Phase 5
- A2UI is in Public Preview (v0.8) -- monitor for breaking changes before Phase 3
- CopilotKit + LangGraph HITL has known ZodError -- use graph interrupt nodes instead (affects Phase 4)
- uv run subcommands time out on this machine; use .venv/bin/ paths directly for CLI tools
- python-jose uses datetime.utcnow() internally (deprecated in Python 3.12) -- harmless warning in tests, not actionable
- Alembic migration 001 requires pgvector-enabled PostgreSQL to run; test only possible when Docker stack is up

## Session Continuity

Last session: 2026-02-25T03:31:36Z
Stopped at: Completed 02-01-PLAN.md — LiteLLM config + get_llm() TDD (61 tests pass)
Resume file: None
