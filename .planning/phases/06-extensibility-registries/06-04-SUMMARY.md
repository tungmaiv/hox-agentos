---
phase: 06-extensibility-registries
plan: 04
subsystem: runtime
tags: [tool-registry, agent-graph, mcp, db-backed, cache, last-seen-at]

# Dependency graph
requires:
  - phase: 06-extensibility-registries/01
    provides: "ToolDefinition, AgentDefinition, McpServer ORM models"
  - phase: 06-extensibility-registries/02
    provides: "Async has_permission, check_artifact_permission"
provides:
  - "DB-backed tool registry with 60s TTL cache and last_seen_at tracking"
  - "Dynamic agent graph wiring from agent_definitions table"
  - "MCP server status filtering, health-check, and client eviction"
  - "Startup seeding of tool_definitions from legacy registry"
  - "Keyword routing from DB agent_definitions.routing_keywords"
affects: [06-05-PLAN, 06-06-PLAN, 06-07-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "DB-backed registry with in-process TTL cache (60s) for hot reads"
    - "Startup seed pattern: INSERT if not exists for migration bootstrap"
    - "Batched last_seen_at updates (60s threshold) to avoid DB churn"
    - "Dynamic importlib.import_module for agent handler dispatch"
    - "Module-level keyword routing map populated from DB or hardcoded fallback"
    - "SQLite offset-naive datetime normalization for comparison"

key-files:
  created:
    - backend/tests/test_tool_registry_db.py
    - backend/tests/test_agent_registry.py
    - backend/tests/test_mcp_evolution.py
  modified:
    - backend/gateway/tool_registry.py
    - backend/agents/master_agent.py
    - backend/mcp/registry.py
    - backend/api/routes/mcp_servers.py
    - backend/main.py
    - backend/api/routes/tools.py
    - backend/agents/node_handlers.py
    - backend/tests/agents/test_master_agent_routing.py
    - backend/tests/mcp/test_mcp_registry.py

decisions:
  - "get_tool() and register_tool() are now async -- session=None fallback preserves backward compat"
  - "Tool required_permissions stored in input_schema JSONB field -- avoids new column"
  - "MCP server mcp_server name derived from tool name convention (server.tool) in cache"
  - "_classify_by_keywords returns agent names directly (not intent labels) for unified routing"
  - "create_master_graph() accepts _db_agents list; async wrapper create_master_graph_from_db() does DB query"
  - "SQLite stores offset-naive datetimes; normalize with .replace(tzinfo=utc) before comparison"

metrics:
  duration: 11 min
  completed: 2026-02-28
---

# Phase 06 Plan 04: Runtime Integration Summary

DB-backed tool/agent registries with TTL cache, dynamic graph wiring, MCP evolution with health-check

## One-liner

Tool registry migrated to DB-backed 60s cache, agent graph dynamically wired from agent_definitions, MCP servers filtered by status with health-check and eviction

## Changes Made

### Task 1: Tool Registry DB Migration + MCP Server Evolution + Startup Seeding (6a082de)

**Tool registry (gateway/tool_registry.py):**
- Replaced `_registry: dict` with DB-backed `_tool_cache` with 60s TTL
- `get_tool()` now async, accepts optional `AsyncSession`, refreshes from DB on TTL expiry
- `register_tool()` now async, upserts into tool_definitions table
- `list_tools()` returns active-only tool names from cache
- `invalidate_tool_cache()` forces refresh on next access
- `update_tool_last_seen()` updates timestamp with 60s batching
- `seed_tool_definitions_from_registry()` seeds DB from `_LEGACY_REGISTRY` on startup
- `session=None` backward compat returns stale cache without refresh

**MCP registry (mcp/registry.py):**
- `MCPToolRegistry.refresh()` filters by `status='active'` instead of `is_active=True`
- Discovered tools upserted into tool_definitions via async `register_tool()`
- Disabled servers have clients evicted from `_clients` cache
- `evict_client()` class method for explicit eviction
- `call_mcp_tool()` updates tool last_seen_at after successful dispatch

**MCP server routes (api/routes/mcp_servers.py):**
- `GET /{server_id}/health` -- HTTP health-check with 5s timeout, returns `{reachable, latency_ms}`
- `PATCH /{server_id}/status` -- update status to active/disabled/deprecated
- Disabling evicts client and invalidates tool cache
- List endpoint now returns actual `status` field from DB

**Main.py lifespan:**
- Added seed_tool_definitions_from_registry + _refresh_tool_cache at startup
- Runs before MCP refresh so legacy tools are available immediately

**Caller updates:**
- `api/routes/tools.py`: `await get_tool(body.tool, session)`
- `agents/node_handlers.py`: `await get_tool(tool_name)` (session=None stale cache)
- `tests/agents/test_master_agent_routing.py`: Updated CRM tool test to use DB-backed seeding
- `tests/mcp/test_mcp_registry.py`: Updated mocks for async get_tool + update_tool_last_seen

### Task 2: Dynamic Agent Graph Wiring from DB Registry (dc23740)

**Master agent (agents/master_agent.py):**
- `create_master_graph(_db_agents=None)` accepts DB agent list for dynamic wiring
- `create_master_graph_from_db(session)` async entry point queries agent_definitions
- Dynamic agents loaded via `importlib.import_module(handler_module)` + `getattr(handler_function)`
- `_keyword_to_agent` module-level map populated from `routing_keywords` DB field
- `_classify_by_keywords()` uses DB keyword map or `_FALLBACK_KEYWORD_MAP` for backward compat
- `_pre_route()` routes by agent name from keyword map, checks system_config for enabled/disabled
- `update_agent_last_seen()` with 60s batching, SQLite datetime normalization
- `session=None` / empty `_db_agents` falls back to hardcoded agent wiring

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQLite offset-naive datetime comparison**
- **Found during:** Task 1, test_update_tool_last_seen_batches
- **Issue:** SQLite stores offset-naive datetimes; comparing with timezone-aware cutoff raised TypeError
- **Fix:** Normalize with `.replace(tzinfo=timezone.utc)` before comparison
- **Files modified:** gateway/tool_registry.py, agents/master_agent.py

**2. [Rule 3 - Blocking] Lazy import patching in tests**
- **Found during:** Task 1, MCP evolution tests
- **Issue:** `invalidate_tool_cache` and `update_tool_last_seen` imported lazily, cannot patch at consumer module level
- **Fix:** Patch at definition site (`gateway.tool_registry.invalidate_tool_cache`)
- **Files modified:** tests/test_mcp_evolution.py, tests/mcp/test_mcp_registry.py

**3. [Rule 3 - Blocking] async_session mock pattern for refresh test**
- **Found during:** Task 1, test_refresh_skips_disabled_servers
- **Issue:** `async_session()` returns a context manager, AsyncMock doesn't support `async with` protocol
- **Fix:** Use `MagicMock(return_value=cm)` where cm has `__aenter__/__aexit__` as AsyncMock
- **Files modified:** tests/test_mcp_evolution.py

**4. [Rule 1 - Bug] Existing test_classify_by_keywords expected old return values**
- **Found during:** Task 2
- **Issue:** Tests expected "email", "calendar", "project" but new code returns agent names
- **Fix:** Updated test assertions to match new return values ("email_agent", etc.)
- **Files modified:** tests/agents/test_master_agent_routing.py

## Verification

- `PYTHONPATH=. .venv/bin/pytest tests/test_tool_registry_db.py tests/test_agent_registry.py tests/test_mcp_evolution.py -v` -- 31 tests pass
- `PYTHONPATH=. .venv/bin/pytest tests/ -q` -- 379 tests pass, 0 failures (baseline was 348)
- No regressions in existing test suite

## Self-Check: PASSED

All 8 key files verified on disk. Both task commits (6a082de, dc23740) confirmed in git log. Test files exceed minimum line counts: test_tool_registry_db.py (332 lines >= 60), test_agent_registry.py (323 lines >= 60), test_mcp_evolution.py (253 lines >= 40). All 4 key_links verified via grep: select(ToolDefinition) in tool_registry.py, select(AgentDefinition)+import_module in master_agent.py, register_tool in mcp/registry.py, seed_tool_definitions in main.py.
