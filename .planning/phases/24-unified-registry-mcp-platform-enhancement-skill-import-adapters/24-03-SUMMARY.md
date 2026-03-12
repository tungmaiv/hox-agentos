---
phase: 24-unified-registry-mcp-platform-enhancement-skill-import-adapters
plan: "03"
subsystem: mcp
tags: [mcp, stdio, subprocess, json-rpc, alembic, migration, catalog]
dependency_graph:
  requires:
    - registry_entries table (24-02)
    - McpServerCatalog ORM (this plan)
  provides:
    - StdioMCPClient wrapping JSON-RPC over stdio subprocess
    - MCPInstaller for npm/pip package management
    - mcp_server_catalog table with 3 pre-seeded entries
    - GET /api/registry/mcp-catalog endpoint
    - stdio server_type validation in MCPHandler
    - openapi_bridge server_type with openapi_url validation
  affects:
    - backend/mcp/stdio_client.py (new)
    - backend/mcp/installer.py (new)
    - backend/registry/models.py (McpServerCatalog added)
    - backend/registry/handlers/mcp_handler.py (validate_config extended)
    - backend/api/routes/registry.py (mcp-catalog endpoint)
tech_stack:
  added:
    - mcp>=1.26.0 in pyproject.toml (SDK installed but not used directly due to naming conflict)
    - StdioMCPClient: custom JSON-RPC 2.0 over asyncio subprocess (avoids SDK shadowing)
  patterns:
    - JSON-RPC 2.0 over stdio subprocess (asyncio.create_subprocess_exec)
    - asyncio.wait_for timeout guard on call_tool
    - McpServerCatalog ORM with JSON().with_variant(JSONB()) for SQLite compat
    - Static route /mcp-catalog declared before /{entry_id} to avoid FastAPI UUID match
key_files:
  created:
    - backend/mcp/stdio_client.py
    - backend/mcp/installer.py
    - backend/alembic/versions/617b296e937a_030_mcp_catalog.py
    - backend/tests/mcp/test_stdio_client.py
    - backend/tests/mcp/test_installer.py
  modified:
    - backend/mcp/__init__.py (comment-only, reset to clean state)
    - backend/registry/models.py (McpServerCatalog added)
    - backend/registry/handlers/mcp_handler.py (stdio + openapi_bridge server_types)
    - backend/api/routes/registry.py (mcp-catalog endpoint + McpServerCatalog import)
    - backend/tests/test_registry_service.py (openapi_spec_url → openapi_url)
    - backend/pyproject.toml (mcp>=1.26.0)
    - backend/uv.lock (updated)
decisions:
  - "[24-03]: StdioMCPClient uses custom JSON-RPC 2.0 over asyncio subprocess — avoids mcp SDK import shadowing (backend/mcp/ package shadows installed mcp SDK on PYTHONPATH)"
  - "[24-03]: mcp SDK dependency added to pyproject.toml for ecosystem compatibility even though StdioMCPClient doesn't use SDK classes directly"
  - "[24-03]: openapi_bridge validates openapi_url (not openapi_spec_url) per plan spec — updated existing test"
  - "[24-03]: McpServerCatalog stored in separate table (not registry_entries) — catalog = pre-built definitions, installation creates registry_entries row"
  - "[24-03]: GET /mcp-catalog route placed before /{entry_id} in registry router — prevents FastAPI from matching 'mcp-catalog' as a UUID"
metrics:
  duration: "~14 minutes"
  completed: "2026-03-12T02:59:47Z"
  tasks_completed: 2
  files_created: 5
  files_modified: 8
  tests_added: 9
  test_count_before: 880
  test_count_after: 889
---

# Phase 24 Plan 03: MCP Platform Enhancement Summary

**One-liner:** StdioMCPClient (custom JSON-RPC over asyncio subprocess), MCPInstaller (npm/pip), mcp_server_catalog table with 3 pre-seeded entries, and OpenAPI bridge registry support.

## What Was Built

### Task 1: StdioMCPClient + MCPInstaller (TDD)

**RED phase:** 9 failing tests created in:
- `tests/mcp/test_stdio_client.py` — 3 tests (list_tools, call_tool timeout, call_tool result)
- `tests/mcp/test_installer.py` — 6 tests (npm/pip commands, nonzero exit, unknown pm, is_installed)

**GREEN phase — `backend/mcp/stdio_client.py`:**
- `StdioMCPClient` with `list_tools()` and `call_tool(tool_name, arguments, timeout=30.0)`
- Custom JSON-RPC 2.0 protocol over `asyncio.create_subprocess_exec` — no SDK dependency
- MCP initialize handshake → tools/list or tools/call request → response parsing
- `asyncio.wait_for(timeout)` guard on `call_tool` — raises `asyncio.TimeoutError` instead of hanging

**GREEN phase — `backend/mcp/installer.py`:**
- `MCPInstaller.install("npm"|"pip", package_name)` — runs correct subprocess command
- `MCPInstaller.is_installed("npm"|"pip", package_name)` — returns bool from exit code
- `MCPInstallError` raised on non-zero exit
- `ValueError` raised for unknown package managers

### Task 2: MCP Catalog Migration + OpenAPI Bridge Registry Support

**Migration 617b296e937a (030):**
- `mcp_server_catalog` table: id, name, display_name, description, package_manager, package_name, command, args (JSONB), env_vars (JSONB), created_at
- 3 pre-seeded entries:
  - `context7` — npm `@upstash/context7-mcp` — `npx -y @upstash/context7-mcp@latest`
  - `mcp-server-fetch` — pip `mcp-server-fetch` — `python -m mcp_server_fetch`
  - `mcp-server-filesystem` — npm `@modelcontextprotocol/server-filesystem` — `npx -y ...`

**`registry/models.py`:** `McpServerCatalog` ORM model with `JSON().with_variant(JSONB(), "postgresql")` for SQLite test compatibility.

**`registry/handlers/mcp_handler.py` — extended `validate_config`:**
- `http_sse`: requires `url` (default, backwards compatible)
- `stdio`: requires `command` and `args`
- `openapi_bridge`: requires `openapi_url` (valid http/https URL via urllib.parse)
- unknown: requires `url`

**`api/routes/registry.py`:** `GET /api/registry/mcp-catalog` endpoint — queries `mcp_server_catalog` ordered by name, returns list of dicts.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] mcp SDK shadowed by local backend/mcp/ package**
- **Found during:** Task 1, GREEN phase
- **Issue:** `PYTHONPATH=.` puts `backend/` first in sys.path, making `import mcp` resolve to `backend/mcp/__init__.py` instead of the installed mcp SDK. The SDK uses `import mcp.types`, `from mcp.client.session import ClientSession` etc. internally — all fail because our local package doesn't have those submodules.
- **Fix:** Implemented `StdioMCPClient` using custom JSON-RPC 2.0 over `asyncio.create_subprocess_exec` instead of wrapping the mcp SDK's `stdio_client` context manager. This avoids the package shadowing entirely. The mcp SDK is still listed as a dependency in `pyproject.toml` for ecosystem compatibility.
- **Files modified:** `backend/mcp/stdio_client.py`, `tests/mcp/test_stdio_client.py` (tests updated to patch `asyncio.create_subprocess_exec` instead of mcp SDK's `stdio_client`)
- **Commits:** 67c7013 (RED), 0faddc3 (GREEN)

**2. [Rule 1 - Bug] openapi_spec_url → openapi_url field name mismatch**
- **Found during:** Task 2
- **Issue:** Existing `test_handler_validate_config_mcp_http` test used `openapi_spec_url` but the plan spec requires `openapi_url`. Our updated handler correctly enforces `openapi_url`.
- **Fix:** Updated the test to use `openapi_url` matching the plan spec.
- **Files modified:** `backend/tests/test_registry_service.py`

## Verification

- `backend/mcp/stdio_client.py` exists with `StdioMCPClient` class
- `backend/mcp/installer.py` exists with `MCPInstaller` and `MCPInstallError`
- `backend/alembic/versions/617b296e937a_030_mcp_catalog.py` with DDL + 3 INSERTs
- `PYTHONPATH=. .venv/bin/pytest tests/mcp/ -v` — 18 tests pass (9 new + 9 existing)
- `PYTHONPATH=. .venv/bin/pytest tests/ -q` — 889 passed, 7 skipped, 0 failures
- `mcp>=1.26.0` in `pyproject.toml`
- Alembic head: `617b296e937a`

## Self-Check: PASSED
