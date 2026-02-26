# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** Every Blitz employee gets an intelligent, context-aware assistant that automates daily work routines and lets them build custom automations without writing code -- all within an enterprise-secure, on-premise environment.
**Current focus:** Phase 3: Sub-Agents + Memory Expansion + OAuth Integrations (Phases 1, 2, 2.1 complete)

## Current Position

Phase: 3 of 9 IN PROGRESS (Sub-Agents + Memory Expansion + OAuth Integrations)
Plan: 6 of 6 — awaiting human checkpoint (03-05: A2UI components + useMcpTool hook + POST /api/tools/call + Settings Memory + Chat Preferences built; pnpm build 0 errors; 3 backend tests passing)
Status: Phase 3 in progress — A2UI rendering pipeline complete (CalendarCard/EmailSummaryCard/ProjectStatusWidget); useMcpTool hook; memory settings API; settings pages; awaiting visual verification checkpoint
Last activity: 2026-02-26 -- Completed 03-05-PLAN.md automated tasks; checkpoint:human-verify awaiting user sign-off

Progress: [█████████░] 68% (15/22 plans estimated)

## Performance Metrics

**Velocity:**
- Total plans completed: 12
- Average duration: 13.9 min
- Total execution time: ~2.76 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 (complete) | 4 | ~26 min | 6.5 min |
| 02 (complete) | 5 | ~98 min | 19.6 min |
| 03 (in progress) | 4/6 | 58 min | 14.5 min |

**Recent Trend:**
- Last 5 plans: 15 min, 19 min, 9 min, 27 min, 17 min
- Trend: 17 min for 03-02 (medium_term + long_term + master agent memory wiring, 3 auto-fixes)

*Updated after each plan completion*
| Phase 03-sub-agents-memory-and-integrations P03 | 5 | 3 tasks | 12 files |
| Phase 03-sub-agents-memory-and-integrations P04 | 6 | 3 tasks | 15 files |
| Phase 03-sub-agents-memory-and-integrations P05 | 35 | 2 tasks | 19 files |

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
- [02-05]: useCopilotChatInternal (not useCopilotChat) exposes messages and reset -- public hook omits messages via Omit<...>
- [02-05]: Custom Input component (not onSubmitMessage) for slash command interception -- onSubmitMessage is void|Promise<void>, cannot cancel; Input.onSend is the correct interception point
- [02-05]: pendingInputRef pattern for edit message re-populate -- CopilotChat has no setInput API; MutableRefObject shared between custom Input and custom UserMessage
- [02-05]: @copilotkit/shared not importable as direct dep in pnpm virtual store -- define local ChatMessage interface instead
- [02-05]: Migration 004 down_revision = '9754fd080ee2' (the merge head); applied via docker exec psql (no .env on host)
- [Phase 03]: SystemConfig.value uses JSON().with_variant(JSONB(), 'postgresql') for SQLite test compatibility while preserving JSONB in production
- [Phase 03]: Admin permission check uses has_permission(user, 'tool:admin') not 'admin' — it-admin role grants tool:admin per RBAC map
- [03-01]: asyncio.run() pattern in Celery tasks — Celery workers are sync; async DB/LLM calls wrapped in asyncio.run(_run()) inside each task
- [03-01]: No FK from memory tables to users table — Keycloak manages user identity; no PostgreSQL users table; user_id validated at Gate 1 (JWT), not DB constraint
- [03-01]: Pin transformers<5.0 (4.57.6) — FlagEmbedding 1.3.x uses is_torch_fx_available removed in transformers 5.0; pinned to fix ImportError
- [03-01]: Split Celery workers by queue — embedding (concurrency=2, CPU-intensive bge-m3) + default (concurrency=4, I/O-bound LLM) prevent OOM
- [03-02]: Mock session approach for pgvector tests — SQLite+aiosqlite cannot create VECTOR(1024) DDL; tests verify WHERE clause security via stmt.compile() string assertion
- [03-02]: _get_episode_threshold() as top-level async function — nested functions cannot be patched with patch("module.func"); top-level name is patchable in tests
- [03-02]: Graceful degradation in _load_memory_node — embedding failure (GPU OOM) must not block agent; wrapped in try/except with warning log, agent continues without long-term context
- [03-02]: BlitzState.delivery_targets pre-registered as placeholder for DeliveryRouterNode in 03-04 — avoids mid-graph state schema changes
- [Phase 03-sub-agents-memory-and-integrations]: tool_registry.register_tool() changed to keyword-arg API to support mcp_server/mcp_tool metadata cleanly
- [Phase 03-sub-agents-memory-and-integrations]: Auth token storage in mcp_servers: iv[:12]+ciphertext blob using encrypt_token/decrypt_token from security.credentials (not a vault.py that doesn't exist)
- [Phase 03-sub-agents-memory-and-integrations]: crm.update_task_status registered in 03-03 for 03-05 kanban — avoids mid-graph state schema changes
- [Phase 03-04]: call_mcp_tool imported at top level in project_agent.py (not lazily) — lazy import not patchable in tests
- [Phase 03-04]: Disabled agent routing: when system_config disables an agent, _route_after_master returns 'delivery_router' — master agent's existing response is delivered unchanged
- [Phase 03-04]: CRM tools pre-registered statically in tool_registry.py at module load; MCPToolRegistry.refresh() overwrites idempotently
- [Phase 03-sub-agents-memory-and-integrations]: useMcpTool generic signature requires TParams in return type UseMcpToolResult<TParams,TResult> — TypeScript strict mode requires both type params
- [Phase 03-sub-agents-memory-and-integrations]: react-markdown v10 removed className prop — wrap in div with className instead of passing to ReactMarkdown component

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

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 1 | Fix Phase 2.1 tech debt: BACKEND_URL env consistency across 5 frontend routes, user_instructions.updated_at onupdate fix + migration, REQUIREMENTS.md and ROADMAP.md checkbox accuracy | 2026-02-26 | 5e51921 | [1-fix-phase-2-1-tech-debt-backend-url-env-](./quick/1-fix-phase-2-1-tech-debt-backend-url-env-/) |

## Session Continuity

Last session: 2026-02-26T12:46:51Z
Stopped at: 03-05 checkpoint:human-verify — A2UI components built, pnpm build passing (0 TypeScript errors), 3 backend tests passing; awaiting visual verification of 6 rendering scenarios
Resume file: None
