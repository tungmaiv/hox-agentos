---
phase: 03-sub-agents-memory-and-integrations
plan: "03"
subsystem: mcp
tags: [mcp, json-rpc, http-sse, tool-registry, rbac, acl, aes-256, docker, fastapi, next.js, zod]

# Dependency graph
requires:
  - phase: 03-00
    provides: mcp_servers table, McpServer ORM model, SystemConfig, Settings stub page
  - phase: 02
    provides: security gates (jwt.py Gate1, rbac.py Gate2, acl.py Gate3), vault encrypt/decrypt
provides:
  - MCPClient: list_tools() + call_tool() via HTTP+SSE JSON-RPC
  - MCPToolRegistry: startup discovery + dynamic registration in tool_registry
  - call_mcp_tool(): 3-gate secured MCP tool execution with audit logging
  - backend/api/routes/mcp_servers.py: GET/POST/DELETE CRUD admin API
  - infra/mcp-crm: Docker mock CRM MCP server with 3 tools
  - Settings → Integrations: live CRUD UI with Zod validation
affects:
  - 03-04 (project sub-agent uses crm.get_project_status via call_mcp_tool)
  - 03-05 (ProjectStatusWidget calls crm.update_task_status via useMcpTool hook)
  - future MCP servers follow same register pattern

# Tech tracking
tech-stack:
  added: []
  patterns:
    - MCPClient per server instance cached in _clients dict at startup
    - iv+ciphertext blob pattern for auth_token storage (iv[:12] + ciphertext[12:])
    - Tool name namespacing: {server_name}.{tool_name} (e.g. crm.get_project_status)
    - Server-side proxy pattern for admin frontend routes (Bearer token never in browser)
    - MCPToolRegistry.refresh() called in FastAPI lifespan (not deprecated on_event)

key-files:
  created:
    - backend/mcp/__init__.py
    - backend/mcp/client.py
    - backend/mcp/registry.py
    - backend/api/routes/mcp_servers.py
    - infra/mcp-crm/main.py
    - infra/mcp-crm/Dockerfile
    - infra/mcp-crm/pyproject.toml
    - frontend/src/app/api/admin/mcp-servers/route.ts
    - frontend/src/app/api/admin/mcp-servers/[id]/route.ts
    - backend/tests/mcp/__init__.py
    - backend/tests/mcp/test_mcp_client.py
    - backend/tests/mcp/test_mcp_registry.py
  modified:
    - backend/gateway/tool_registry.py (keyword-arg API, mcp_server/mcp_tool fields)
    - backend/main.py (FastAPI lifespan + mcp_servers router)
    - frontend/src/app/settings/integrations/page.tsx (stub → live CRUD)
    - docker-compose.yml (mcp-crm service added)

key-decisions:
  - "tool_registry.register_tool() changed from positional dict to keyword-arg API to support mcp_server/mcp_tool metadata"
  - "Auth token storage: iv[:12] embedded at front of auth_token blob; decrypt_token(ciphertext, iv) called with split"
  - "MCPToolRegistry.refresh() wrapped in try/except in lifespan — MCP failure never blocks startup"
  - "Admin permission check uses tool:admin (not admin) — consistent with system_config.py pattern"
  - "crm.update_task_status included in mock server for 03-05 kanban drag-drop (ProjectStatusWidget)"
  - "Mock CRM server returns JSON directly (not SSE stream) — valid per MCP spec for request/response tools"

patterns-established:
  - "MCP tool name format: {server_name}.{tool_name} — e.g. crm.get_project_status"
  - "call_mcp_tool() is the single secure entry point for all MCP tool calls"
  - "Frontend admin proxy: server-side auth injection via auth() from @/auth"

requirements-completed: [INTG-01, INTG-02, INTG-03]

# Metrics
duration: 5min
completed: 2026-02-26
---

# Phase 3 Plan 03: MCP HTTP+SSE Client + 3-Gate Security + CRM Mock Server Summary

**MCPClient (HTTP+SSE JSON-RPC) + MCPToolRegistry (startup discovery + 3-gate gated execution) + mock CRM Docker service (get_project_status, list_projects, update_task_status) + live Settings Integrations CRUD**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-02-26T12:06:45Z
- **Completed:** 2026-02-26T12:11:58Z
- **Tasks:** 3/3
- **Files modified:** 12 (8 created, 4 modified)

## Accomplishments

- MCPClient class wraps tools/list and tools/call JSON-RPC over HTTP+SSE — one instance per server URL, cached in `_clients` dict
- MCPToolRegistry.refresh() discovers tools from active mcp_servers at FastAPI startup and registers them in tool_registry with required_permissions=["{server}:read"]
- call_mcp_tool() enforces all 3 security gates (Gate1 JWT at caller, Gate2 RBAC per permission, Gate3 ACL per user) with audit logging on every attempt
- infra/mcp-crm Docker service exposes 3 CRM tools; verified live with curl returning correct JSON-RPC responses
- Settings → Integrations replaced stub with live CRUD (Zod-validated API response, add/delete form, admin 403 guard)
- 8 TDD tests: 4 client tests (mocked httpx) + 4 registry security tests — all pass

## Task Commits

1. **Task 1: MCPClient + MCPToolRegistry with 3-gate security** - `e468307` (feat)
2. **Task 2: MCP servers CRUD API + CRM mock server + docker-compose** - `4d1d20a` (feat)
3. **Task 3: TDD tests for MCPClient + gated registry** - `5b28494` (test)

## Files Created/Modified

- `backend/mcp/client.py` - MCPClient: list_tools() + call_tool() HTTP+SSE JSON-RPC
- `backend/mcp/registry.py` - MCPToolRegistry.refresh() + call_mcp_tool() 3-gate security
- `backend/gateway/tool_registry.py` - Extended to keyword-arg API with mcp_server/mcp_tool fields
- `backend/main.py` - FastAPI lifespan with MCPToolRegistry.refresh() + mcp_servers router
- `backend/api/routes/mcp_servers.py` - GET/POST/DELETE /api/admin/mcp-servers (admin-only)
- `infra/mcp-crm/main.py` - Mock CRM server with 3 tools (FastAPI, JSON-RPC /sse endpoint)
- `infra/mcp-crm/Dockerfile` + `pyproject.toml` - Docker image definition
- `docker-compose.yml` - mcp-crm service on port 8001
- `frontend/src/app/api/admin/mcp-servers/route.ts` - GET+POST proxy (server-side Bearer injection)
- `frontend/src/app/api/admin/mcp-servers/[id]/route.ts` - DELETE proxy
- `frontend/src/app/settings/integrations/page.tsx` - Live CRUD (Zod validated, add/delete form)
- `backend/tests/mcp/test_mcp_client.py` + `test_mcp_registry.py` - 8 TDD tests

## CRM Tools Registered

| Tool Name | MCP Tool | required_permissions |
|-----------|----------|---------------------|
| crm.get_project_status | get_project_status | [crm:read] |
| crm.list_projects | list_projects | [crm:read] |
| crm.update_task_status | update_task_status | [crm:read] |

## Decisions Made

- `tool_registry.register_tool()` changed from `(name, definition_dict)` to keyword-arg API — cleaner call site in MCPToolRegistry.refresh() and future static tool registrations
- Auth token storage in mcp_servers: `iv[:12] + ciphertext[12:]` single blob in LargeBinary column; decrypted by splitting at byte 12 using `decrypt_token(ciphertext, iv)` from `security.credentials`
- Admin permission check uses `tool:admin` (not `admin`) — consistent with `system_config.py` pattern
- `crm.update_task_status` tool added now (in 03-03, not 03-05) per CONTEXT.md to avoid adding tools mid-graph in 03-05
- Mock CRM returns JSON directly (not SSE stream) — MCPClient.call_tool() reads response.json() which works for both

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] security.vault module doesn't exist — used security.credentials instead**
- **Found during:** Task 1 (MCPToolRegistry creation)
- **Issue:** Plan references `from security.vault import decrypt` but vault.py doesn't exist; the real module is `security/credentials.py` with `encrypt_token(token)` → `(ciphertext, iv)` and `decrypt_token(ciphertext, iv)` → `str`
- **Fix:** Used `security.credentials.encrypt_token/decrypt_token` with iv-prefixed blob storage pattern
- **Files modified:** backend/mcp/registry.py, backend/api/routes/mcp_servers.py
- **Committed in:** e468307, 4d1d20a (inline with task commits)

**2. [Rule 1 - Bug] UserContext has no 'permissions' field — make_user() test helper adapted**
- **Found during:** Task 3 (test_mcp_registry.py creation)
- **Issue:** Plan's make_user() sets `permissions=["chat", "crm:read"]` but UserContext TypedDict only has roles/groups; RBAC derives permissions via has_permission(user, perm)
- **Fix:** make_user() accepts permissions param but ignores it; tests use roles that would grant access (it-admin) and mock has_permission() directly
- **Files modified:** backend/tests/mcp/test_mcp_registry.py
- **Committed in:** 5b28494

**3. [Rule 1 - Bug] Admin permission is tool:admin not admin**
- **Found during:** Task 2 (mcp_servers.py route creation)
- **Issue:** Plan's `has_permission(user, "admin")` would always return False — RBAC map has no bare "admin" permission; it-admin role grants "tool:admin"
- **Fix:** Changed to `has_permission(user, "tool:admin")` matching system_config.py pattern
- **Files modified:** backend/api/routes/mcp_servers.py
- **Committed in:** 4d1d20a

---

**Total deviations:** 3 auto-fixed (all Rule 1 bugs — API mismatches with existing codebase)
**Impact on plan:** All fixes required for correctness. No scope creep. Core architecture unchanged.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None — mcp-crm container runs automatically via docker compose. No external credentials needed for mock server.

## Next Phase Readiness

- `call_mcp_tool("crm.get_project_status", {...}, user, db)` ready for use in 03-04 project sub-agent
- `crm.update_task_status` ready for 03-05 ProjectStatusWidget kanban
- Pattern established for future MCP servers (mcp-docs follows same Dockerfile + registration flow)

---
*Phase: 03-sub-agents-memory-and-integrations*
*Completed: 2026-02-26*

## Self-Check: PASSED

All files verified present on disk. All commits (e468307, 4d1d20a, 5b28494) verified in git log.
