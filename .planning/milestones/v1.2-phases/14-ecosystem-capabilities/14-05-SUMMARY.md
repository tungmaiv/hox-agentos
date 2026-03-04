---
phase: 14-ecosystem-capabilities
plan: "05"
subsystem: api
tags: [openapi, proxy, tool-dispatch, security-gates, rbac, acl, aes-gcm, tdd]

# Dependency graph
requires:
  - phase: 14-02
    provides: "call_openapi_tool() proxy implementation and tool_registry config_json/mcp_server_id caching"
provides:
  - "openapi_proxy tools callable via /api/tools/call (end-to-end dispatch complete)"
  - "Gates 2+3 (RBAC + ACL) enforced for openapi_proxy route with audit logging"
  - "McpServer.auth_token decrypted and passed as api_key to call_openapi_tool()"
  - "Error dict from proxy surfaced as ToolCallResponse(success=False)"
affects:
  - "ECO-02 requirement fully satisfied"
  - "frontend useMcpTool hook: openapi_proxy tools now callable just like MCP tools"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "openapi_proxy dispatch branch follows same Gate 2+3 pattern as MCP tool call_mcp_tool()"
    - "iv = raw[:12]; ciphertext = raw[12:] convention for McpServer.auth_token storage"
    - "is_error = result.get('error') is True for distinguishing proxy error dicts"

key-files:
  created: []
  modified:
    - "backend/api/routes/tools.py"
    - "backend/tests/test_openapi_bridge.py"

key-decisions:
  - "openapi_proxy dispatch branch placed as elif between mcp_server branch and 501 fallback — preserves all existing behavior"
  - "Gates 2+3 enforced inline in the branch (not delegated) — matches call_mcp_tool pattern for consistency"
  - "mcp_server_id from cache is str; cast to uuid.UUID() before McpServer query — avoids type mismatch on PostgreSQL UUID columns"
  - "update_tool_last_seen wrapped in try/except — best-effort, should not fail the tool call"

patterns-established:
  - "Proxy error detection: result.get('error') is True (not truthy, checks exact bool True)"
  - "Auth token storage layout: iv (12 bytes) + ciphertext (rest) — decrypt with raw[:12] as iv, raw[12:] as ciphertext"

requirements-completed:
  - ECO-02

# Metrics
duration: 2min
completed: 2026-03-04
---

# Phase 14 Plan 05: OpenAPI Proxy Dispatch Summary

**openapi_proxy tools now callable end-to-end via /api/tools/call — Gates 2+3 enforced, API key decrypted from McpServer.auth_token and passed to call_openapi_tool()**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-04T04:01:18Z
- **Completed:** 2026-03-04T04:03:28Z
- **Tasks:** 1 (TDD: 2 commits — test + feat)
- **Files modified:** 2

## Accomplishments

- Added `elif tool_def.get("handler_type") == "openapi_proxy"` dispatch branch in `call_tool()`
- Gate 2 (RBAC): iterates required_permissions, calls `has_permission()` with audit logging
- Gate 3 (ACL): calls `check_tool_acl()` with matching audit log pattern from MCP path
- Loads `McpServer` by `mcp_server_id` (UUID-cast from str cache value), decrypts `auth_token` using `iv = raw[:12]; ciphertext = raw[12:]` convention
- Passes decrypted `api_key` to `call_openapi_tool(tool_config, arguments, api_key)`
- Error dict (`{"error": True, ...}`) surfaced as `ToolCallResponse(success=False, error=detail)`
- All 4 new tests pass; full suite: 718 passed (up from 714 pre-plan baseline)

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Add failing tests for openapi_proxy dispatch** - `db71603` (test)
2. **Task 1 GREEN: Implement openapi_proxy dispatch branch** - `8adb8ee` (feat)

**Plan metadata:** (docs commit follows)

_Note: TDD task has 2 commits (test RED + feat GREEN)_

## Files Created/Modified

- `backend/api/routes/tools.py` - Added openapi_proxy elif branch with full Gate 2+3 enforcement and API key decryption
- `backend/tests/test_openapi_bridge.py` - Added `TestToolsRouteOpenAPIProxy` class with 4 tests

## Decisions Made

- Placed `elif` branch between the existing `mcp_server` branch and the `else` 501 fallback — preserves all existing behavior unchanged
- Gates 2+3 enforced inline in the new branch (not delegated to a helper function) — matches the pattern inside `call_mcp_tool()` for consistency
- `mcp_server_id` from cache is a `str` (tool_registry casts with `str(row.mcp_server_id)`); UUID-cast before `McpServer.id` query to avoid PostgreSQL type mismatch
- `update_tool_last_seen` wrapped in `try/except` so best-effort tracking never fails a tool call
- `is_error = result.get("error") is True` (strict bool check, not truthy) — avoids false positives when result contains a key named "error" with a non-True value

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ECO-02 fully satisfied: OpenAPI proxy tools are callable end-to-end through the standard security gates
- Phase 14 planning can now mark Plan 05 as the final gap-closure task for ECO-02
- Frontend `useMcpTool` hook will work for openapi_proxy tools without modification — same `/api/tools/call` endpoint

---
*Phase: 14-ecosystem-capabilities*
*Completed: 2026-03-04*
