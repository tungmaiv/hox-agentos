# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-26)

**Core value:** Every Blitz employee gets an intelligent, context-aware assistant that automates daily work routines and lets them build custom automations without writing code -- all within an enterprise-secure, on-premise environment.
**Current focus:** v1.1 MVP — Phase 5 (Scheduler & Channels) COMPLETE, all 6 plans done (including gap closure)

## Current Position

Milestone: v1.1 Phase 5 (Scheduler & Channels) — ALL PLANS COMPLETE (including gap closures)
Phases: 1, 2, 2.1, 3, 3.1, 4, 4.1 — all complete; Phase 5: Plan 06 of 6 complete
Current Plan: 05-06 complete — Phase 5 fully finished (CHAN-05 gap closed)
Status: Phase 5 complete — All channel infrastructure + ChannelAdapter Protocol
Last activity: 2026-02-28 -- 05-06 executed (2 min, 2 tasks, 4 new tests)

Progress: [████████████] 100% (26/26 plans estimated)

## Performance Metrics

**Velocity:**
- Total plans completed: 14
- Average duration: 13.6 min
- Total execution time: ~3.24 hours + 4 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 (complete) | 4 | ~26 min | 6.5 min |
| 02 (complete) | 5 | ~98 min | 19.6 min |
| 03 (in progress) | 5/6 | 98 min | 19.6 min |

**Recent Trend:**
- Last 5 plans: 19 min, 9 min, 27 min, 17 min, 40 min
- Trend: 40 min for 03-05 (A2UI pipeline + useMcpTool hook + 2 settings pages + 3 auto-fixes + human verification)

*Updated after each plan completion*
| Phase 03-sub-agents-memory-and-integrations P03 | 5 | 3 tasks | 12 files |
| Phase 03-sub-agents-memory-and-integrations P04 | 6 | 3 tasks | 15 files |
| Phase 03-sub-agents-memory-and-integrations P05 | 35 | 2 tasks | 19 files |
| Phase 04-canvas-and-workflows P01 | 15 | 6 tasks | 27 files |
| Phase 04-canvas-and-workflows P02 | 4 | 6 tasks | 9 files |
| Phase 04-canvas-and-workflows P03 | 7 | 5 tasks | 12 files |
| Phase 04-canvas-and-workflows P04 | 8 | 6 tasks | 22 files |
| Phase 04-canvas-and-workflows P05 | 4 | 4 tasks | 7 files |
| Phase 05-scheduler-and-channels P01 | 5 | 3 tasks | 13 files |
| Phase 05-scheduler-and-channels P02 | 5 | 2 tasks | 8 files |
| Phase 05-scheduler-and-channels P03 | 3 | 2 tasks | 8 files |
| Phase 05-scheduler-and-channels P04 | 4 | 2 tasks | 8 files |
| Phase 05-scheduler-and-channels P05 | 13 | 3 tasks | 13 files |
| Phase 05-scheduler-and-channels P06 | 2 | 2 tasks | 3 files |

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
- [Phase 03-05]: core.db exports get_db (not get_async_session) as the FastAPI dependency — same pattern used in all existing route files (credentials.py, acl.py)
- [03.1-01]: load_recent_episodes imported at top level in master_agent.py (not lazy) — lazy imports not patchable with patch('agents.master_agent.load_recent_episodes'); same pattern as call_mcp_tool in project_agent.py
- [03.1-01]: MCPToolRegistry imported lazily inside create_mcp_server() to avoid circular import; test patches 'mcp.registry.MCPToolRegistry' (class definition module) — intercepts lazy import correctly
- [Phase 04-canvas-and-workflows]: Workflow.definition_json uses JSON().with_variant(JSONB(),'postgresql') for SQLite test compatibility — same pattern as SystemConfig.value
- [Phase 04-01]: FastAPI route ordering: /templates and /runs/* declared BEFORE /{workflow_id} to prevent FastAPI matching string literals as UUID path params
- [Phase 04-01]: Alembic migration uses 010 revision — 009 was already taken by conversation_titles_timestamps; down_revision='009'
- [Phase 04-01]: Next.js 15 async params: params must be typed as Promise<{id: string}> and awaited — plan doc showed deprecated Next.js 14 sync pattern
- [Phase 04-01]: owner_user_id on Workflow is NULLABLE — template rows in 04-05 will have owner_user_id=NULL; no FK constraint (users in Keycloak)
- [04-02]: condition_evaluator.py is a standalone module (not inlined in node_handlers.py) — independently testable; node_handlers imports it via evaluate_condition()
- [04-02]: compile_workflow_to_stategraph() returns uncompiled StateGraph builder — caller injects checkpointer (MemorySaver in tests, AsyncPostgresSaver in 04-04 production)
- [04-02]: Default-arg closure pattern _make_node_fn(nid=node_id, ntype=...) prevents loop-variable capture bugs in LangGraph node factory
- [04-02]: condition_node router reads current_output bool directly (output of _handle_condition_node) — avoids extra state field and mutation
- [04-03]: workflow_events.py separates sync publish_event() (Celery) from async subscribe_events() (FastAPI SSE) — both Redis pub/sub, no in-process queue
- [04-03]: GraphInterrupt caught by type name check ("Interrupt" in type(exc).__name__) — avoids fragile import path, handles subclasses
- [04-03]: MemorySaver used in 04-03 execute_workflow — TODO(04-04): replace with AsyncPostgresSaver for HITL cross-process persistence
- [04-03]: approve/reject use HTTP 409 (Conflict) for wrong status — semantically correct vs 400 (Bad Request) for state machine violations
- [04-03]: TestClient + dependency_overrides pattern for workflow run API tests — AsyncClient caused 503 due to Celery/Redis import at module load
- [Phase 04-canvas-and-workflows]: AsyncPostgresSaver.from_conn_string() as async context manager; setup() idempotently creates LangGraph checkpoint tables; pg_conn_str strips postgresql+asyncpg:// to postgresql://
- [Phase 04-canvas-and-workflows]: langgraph upgraded 0.4.10->1.0.1 for checkpoint-postgres 3.0.4 compatibility; NodeStatus type in use-workflow-run.ts (imported by nodes); WorkflowCanvas syncs nodeStatuses on render (not useEffect) to avoid loop
- [Phase 04-05]: Fixture files as standalone JSON (not Python dicts) — readable, editable without code changes; migration 011 ON CONFLICT DO NOTHING for idempotency; TemplateCard fetch via relative URL through Next.js proxy to ensure JWT injection
- [05-01]: SQLite stores datetimes as offset-naive; handle_pairing normalizes pairing_expires to UTC-aware before comparing with datetime.now(timezone.utc)
- [05-01]: send_outbound uses 3x exponential backoff (1s, 2s, 4s) per design doc locked decision
- [05-01]: Channel routes router has /api/channels prefix built-in; registered in main.py without extra prefix
- [05-02]: Sidecar defines its own InternalMessage Pydantic model (mirrors backend channels.models) to keep standalone with no cross-project imports
- [05-02]: MarkdownV2 escaping via regex substitution of all 18 Telegram special characters
- [05-02]: InlineKeyboard buttons arranged in rows of 3, capped at 100 per Telegram limit; excess silently dropped
- [05-02]: Webhook registration on startup via FastAPI lifespan; gracefully skipped if TELEGRAM_WEBHOOK_URL not set
- [05-02]: Group @mention detection checks entity type 'mention' matching BOT_USERNAME and 'bot_command' entities
- [05-03]: Button capping applied at both /send endpoint and WhatsApp API wrapper for defense in depth -- test correctness requires capping at endpoint level since API is mocked
- [05-03]: Attachment rejection sends text reply to user explaining text-only MVP limitation
- [05-03]: Interactive button replies extract callback_data from button_reply.id into metadata dict
- [05-04]: Direct httpx calls to Bot Framework Connector API instead of botbuilder-core SDK -- lightweight, consistent with Telegram/WhatsApp sidecar patterns
- [05-04]: MVP token validation decodes JWT without signature verification, checks issuer and audience -- full JWKS rotation handling deferred
- [05-04]: hatch build config packages=['.'] required for flat project layout (main.py at root, no package directory)
- [05-05]: ChannelGateway._invoke_agent() uses create_master_graph() per invocation -- avoids shared checkpointer state between web and channel executions
- [05-05]: delivery_router.deliver() changed from sync to async -- runs inside LangGraph async context, cannot use asyncio.run()
- [05-05]: WHATSAPP added to DeliveryTarget enum alongside TELEGRAM and TEAMS
- [05-05]: Phase 4 scheduler already satisfies CHAN-06 -- user_context in initial_state flows to all node handlers; verified with tests, no code changes needed
- [05-06]: ChannelAdapter Protocol uses @runtime_checkable for isinstance() support at runtime, not just static type checking

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
| 2 | Fix HITL canvas amber ring: add node_id to hitl_paused SSE event (state_snapshot.next[0]) so frontend nodeStatuses.set activates on correct canvas node | 2026-02-27 | ee2d3fd | [2-phase-4-1-polish-hitl-amber-ring-node-id](./quick/2-phase-4-1-polish-hitl-amber-ring-node-id/) |

## Session Continuity

Last session: 2026-02-28
Stopped at: Completed 05-06-PLAN.md — Phase 5 gap closure complete: ChannelAdapter Protocol class (CHAN-05)
Resume file: .planning/phases/05-scheduler-and-channels/05-06-SUMMARY.md
