---
phase: 06-extensibility-registries
verified: 2026-02-28T17:00:00Z
status: human_needed
score: 6/6 must-haves verified
re_verification: false
human_verification:
  - test: "Verify admin dashboard runtime behavior with live backend"
    expected: "All 5 tabs show real data, table/card toggle works, permission matrix with staged apply functional, MCP dots colored correctly, non-admin users see 403 message"
    why_human: "Visual and interactive behavior cannot be verified programmatically. Backend and frontend must both be running with real DB data. Plan 06-07 included a human verification checkpoint (Task 3) which was recorded as passed with a bug fix commit (0b06cc6)."
  - test: "Verify /command autocomplete dropdown in chat input"
    expected: "Typing '/' in chat shows a dropdown with available skills; clicking one fills the input; pressing Enter/Tab selects and sends; Escape closes"
    why_human: "Frontend keyboard navigation and popover behavior requires live browser interaction. useSkills hook fetching from /api/skills and rendering in chat-panel.tsx is code-verified wired but visual/interactive behavior is unverifiable programmatically."
  - test: "Verify hot-registration: register a new tool via admin API, confirm it's available within 60 seconds without backend restart"
    expected: "POST /api/admin/tools creates entry; within 60s (TTL cache), tool appears in GET /api/tools and is usable by authorized users"
    why_human: "Cache TTL behavior requires timed observation in a live system. The code logic (DB query with 60s TTL) is verified but the end-to-end timing cannot be asserted with grep."
---

# Phase 6: Extensibility Registries Verification Report

**Phase Goal:** Admins and developers can manage the platform's agents, tools, skills, and MCP servers as runtime artifacts through database-backed registries with granular permissions, with a skill runtime supporting /command invocation, a secure skill import pipeline, and a frontend admin dashboard
**Verified:** 2026-02-28T17:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Every agent, tool, skill, and MCP server has a DB registry entry with name, description, version, status | VERIFIED | `agent_definitions`, `tool_definitions`, `skill_definitions`, `mcp_servers` tables with all required columns in ORM models; migration 014 creates + seeds them |
| 2 | Admin can add, edit, disable, re-enable any artifact via API and admin UI; disabled artifacts are unavailable to agents | VERIFIED | 4 admin route files registered in main.py; `get_tool()` only returns `status='active' AND is_active=True`; agent graph excludes disabled agents |
| 3 | Developer can register a new tool or MCP server and it becomes available without restarting the backend | VERIFIED | DB-backed tool registry with 60s TTL; `register_tool()` upserts to DB; `invalidate_tool_cache()` forces refresh; startup seeding in lifespan; MCP `refresh()` upserts to tool_definitions |
| 4 | Permissions can be assigned per artifact per role, with per-user overrides and staged apply model | VERIFIED | `artifact_permissions` + `user_artifact_permissions` tables; admin_permissions.py staged model (writes status='pending', POST /apply activates); `invalidate_permission_cache()` called on apply |
| 5 | Removing an artifact from the registry prevents all future invocations; existing running workflows complete gracefully | VERIFIED | `get_tool()` excludes disabled tools; agent graph excludes disabled agents; status PATCH returns `active_workflow_runs` count; existing workflows are queried but not terminated |
| 6 | Admin dashboard at /admin shows all artifacts with table/card views, permission matrix, and MCP connectivity indicators | VERIFIED (code) / HUMAN NEEDED (runtime) | 16 frontend files created; layout.tsx with role check; 5 tab pages; ArtifactTable, ArtifactCardGrid, PermissionMatrix, McpStatusDot, ViewToggle; useAdminArtifacts + useAdminPermissions hooks wired to /api/admin proxy |

**Score:** 6/6 truths verified (1 requires human confirmation of runtime behavior)

---

## Required Artifacts — Level 1 (Exists), Level 2 (Substantive), Level 3 (Wired)

### Plan 06-01: Registry Models and Schemas

| Artifact | Lines | Status | Details |
|----------|-------|--------|---------|
| `backend/core/models/agent_definition.py` | 80 | VERIFIED | `class AgentDefinition`, UNIQUE(name, version), is_active, last_seen_at, JSONB compat |
| `backend/core/models/tool_definition.py` | exists | VERIFIED | `class ToolDefinition`, same pattern |
| `backend/core/models/skill_definition.py` | 110 | VERIFIED | `class SkillDefinition`, slash_command unique, skill_type, security_score |
| `backend/core/models/artifact_permission.py` | exists | VERIFIED | `class ArtifactPermission`, staged status |
| `backend/core/models/user_artifact_permission.py` | exists | VERIFIED | `class UserArtifactPermission`, per-user overrides |
| `backend/core/models/role_permission.py` | exists | VERIFIED | `class RolePermission` |
| `backend/core/schemas/registry.py` | 324 | VERIFIED | 25+ Pydantic v2 classes, all CRUD schemas, cross-field validation on SkillDefinitionCreate |
| `backend/alembic/versions/014_extensibility_registries.py` | exists | VERIFIED | `def upgrade`, 6 `op.create_table` calls, seed data, tool_acl migration |
| `backend/core/models/__init__.py` | WIRED | VERIFIED | All 6 new models imported with `# noqa: F401` |

### Plan 06-02: DB-Backed RBAC

| Artifact | Lines | Status | Details |
|----------|-------|--------|---------|
| `backend/security/rbac.py` | exists | VERIFIED | `async def has_permission` with session param, `select(RolePermission)`, `check_artifact_permission`, `select(ArtifactPermission)`, `invalidate_permission_cache` |
| `backend/tests/test_rbac_db.py` | 317 | VERIFIED | 317 lines >= 60 minimum; 11 tests covering DB-backed RBAC, staged model, user overrides, cache |

### Plan 06-03: Admin CRUD APIs

| Artifact | Lines | Status | Details |
|----------|-------|--------|---------|
| `backend/api/routes/admin_agents.py` | exists | VERIFIED | Router exists; list, create, get, update, patch status (active_workflow_runs), activate, bulk-status |
| `backend/api/routes/admin_tools.py` | exists | VERIFIED | Same pattern as agents |
| `backend/api/routes/admin_skills.py` | exists | VERIFIED | Includes /import, /review, /security-report endpoints wired to SkillImporter + SecurityScanner |
| `backend/api/routes/admin_permissions.py` | exists | VERIFIED | Role permissions, artifact permissions (staged), per-user overrides, /apply endpoint |
| `backend/tests/api/test_admin_agents.py` | 311 | VERIFIED | 311 lines >= 80 minimum |
| `backend/tests/api/test_admin_tools.py` | 316 | VERIFIED | 316 lines >= 80 minimum |
| `backend/tests/api/test_admin_skills.py` | 392 | VERIFIED | 392 lines >= 80 minimum |
| `backend/tests/api/test_admin_permissions.py` | 392 | VERIFIED | 392 lines >= 80 minimum |
| `backend/main.py` | WIRED | VERIFIED | `include_router(admin_agents.router)`, `include_router(admin_tools.router)`, `include_router(admin_skills.router)`, `include_router(admin_permissions.router)` all present |

### Plan 06-04: Runtime Integration

| Artifact | Lines | Status | Details |
|----------|-------|--------|---------|
| `backend/gateway/tool_registry.py` | exists | VERIFIED | `async def get_tool`, `select(ToolDefinition)`, `seed_tool_definitions` all present; DB-backed with 60s TTL |
| `backend/agents/master_agent.py` | exists | VERIFIED | `select(AgentDefinition)`, `import_module(agent_def.handler_module)`, `create_master_graph_from_db`, slash command dispatch to skill_executor |
| `backend/tests/test_tool_registry_db.py` | 332 | VERIFIED | 332 lines >= 60 minimum |
| `backend/tests/test_agent_registry.py` | 323 | VERIFIED | 323 lines >= 60 minimum |
| `backend/tests/test_mcp_evolution.py` | 253 | VERIFIED | 253 lines >= 40 minimum |

### Plan 06-05: Skill System

| Artifact | Lines | Status | Details |
|----------|-------|--------|---------|
| `backend/skills/executor.py` | exists | VERIFIED | `class SkillExecutor`, `get_tool`, `check_tool_acl`, `get_llm`, `safe_eval_condition` all imported at module level |
| `backend/skills/validator.py` | exists | VERIFIED | `class SkillValidator`, `def validate_procedure` |
| `backend/skills/safe_eval.py` | exists | VERIFIED | `def safe_eval_condition`, AST-based, no eval() |
| `backend/skills/importer.py` | exists | VERIFIED | `class SkillImporter`, `def parse_skill_md`, `import_from_url` |
| `backend/skills/security_scanner.py` | exists | VERIFIED | `class SecurityScanner`, `def scan`, `INJECTION_PATTERNS` |
| `backend/tests/test_skill_executor.py` | 443 | VERIFIED | 443 lines >= 80 minimum |
| `backend/tests/test_security_scanner.py` | 221 | VERIFIED | 221 lines >= 60 minimum |
| `backend/tests/test_safe_eval.py` | 133 | VERIFIED | 133 lines >= 30 minimum |

### Plan 06-06: User Skill/Tool Layer + Slash Command

| Artifact | Lines | Status | Details |
|----------|-------|--------|---------|
| `backend/api/routes/user_skills.py` | exists | VERIFIED | router exported; GET /api/skills, POST /api/skills/{name}/run |
| `backend/api/routes/user_tools.py` | exists | VERIFIED | router exported; GET /api/tools |
| `backend/tests/api/test_user_skills.py` | 319 | VERIFIED | 319 lines >= 60 minimum |
| `backend/tests/api/test_user_tools.py` | 208 | VERIFIED | 208 lines >= 30 minimum |
| `backend/tests/test_slash_dispatch.py` | 209 | VERIFIED | 209 lines >= 40 minimum |
| `backend/tests/test_phase6_integration.py` | 333 | VERIFIED | 333 lines >= 40 minimum |
| `frontend/src/hooks/use-skills.ts` | exists | VERIFIED | `export function useSkills`, `fetch("/api/skills")` |
| `frontend/src/app/api/skills/route.ts` | exists | VERIFIED | `export async function GET`, proxies to backend with JWT |

### Plan 06-07: Admin Dashboard UI

| Artifact | Lines | Status | Details |
|----------|-------|--------|---------|
| `frontend/src/app/admin/page.tsx` | 8 | VERIFIED | `export default`, redirects to /admin/agents |
| `frontend/src/components/admin/artifact-table.tsx` | exists | VERIFIED | `ArtifactTable` generic component with status badges |
| `frontend/src/components/admin/artifact-card-grid.tsx` | exists | VERIFIED | `ArtifactCardGrid` responsive grid |
| `frontend/src/components/admin/permission-matrix.tsx` | exists | VERIFIED | `PermissionMatrix`, uses `useAdminPermissions` |
| `frontend/src/components/admin/mcp-status-dot.tsx` | exists | VERIFIED | `McpStatusDot`, green/yellow/red thresholds (5min/30min) |
| `frontend/src/hooks/use-admin-artifacts.ts` | exists | VERIFIED | `useAdminArtifacts`, fetches `/api/admin/${type}` |
| `frontend/src/hooks/use-admin-permissions.ts` | exists | VERIFIED | `useAdminPermissions`, `applyPending()` |
| `frontend/src/app/api/admin/[...path]/route.ts` | exists | VERIFIED | `export async function GET/POST/PUT/PATCH/DELETE`, `NEXT_PUBLIC_API_URL` |
| `frontend/src/lib/admin-types.ts` | 225 | VERIFIED | 225 lines >= 40 minimum; all required interfaces present |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/core/models/__init__.py` | all 6 new model files | import re-exports | WIRED | All 6 models imported with `from core.models.X import Y` |
| `backend/alembic/versions/014_extensibility_registries.py` | all new tables | `op.create_table` | WIRED | 6 `op.create_table` calls confirmed |
| `backend/security/rbac.py` | `role_permission.py` | `select(RolePermission)` | WIRED | Line 132 in rbac.py |
| `backend/security/rbac.py` | `artifact_permission.py` | `select(ArtifactPermission)` | WIRED | Line 268 in rbac.py |
| `backend/security/acl.py` | `backend/security/rbac.py` | `await has_permission` | WIRED | Callers updated in plan 06-02 |
| `backend/main.py` | all admin route modules | `app.include_router(admin_*)` | WIRED | Lines 124-133 in main.py |
| `backend/api/routes/admin_permissions.py` | `backend/security/rbac.py` | `invalidate_permission_cache` on apply | WIRED | Lines 116 and 320 in admin_permissions.py |
| `backend/gateway/tool_registry.py` | `backend/core/models/tool_definition.py` | `select(ToolDefinition)` | WIRED | Line 43, 120, 187 in tool_registry.py |
| `backend/agents/master_agent.py` | `backend/core/models/agent_definition.py` | `import_module(agent_def.handler_module)` | WIRED | Lines 619, 687, 755 in master_agent.py |
| `backend/mcp/registry.py` | `backend/core/models/tool_definition.py` | upsert via `register_tool` | WIRED | Confirmed in 06-04 summary; MCP refresh calls register_tool |
| `backend/main.py` | `backend/gateway/tool_registry.py` | `seed_tool_definitions_from_registry` | WIRED | Lines 48, 51 in main.py lifespan |
| `backend/skills/executor.py` | `backend/gateway/tool_registry.py` | `get_tool` lookup | WIRED | Line 28: `from gateway.tool_registry import get_tool` |
| `backend/skills/executor.py` | `backend/security/acl.py` | `check_tool_acl` | WIRED | Line 29: `from security.acl import check_tool_acl` |
| `backend/skills/executor.py` | `backend/core/config.py` | `get_llm` | WIRED | Line 27: `from core.config import get_llm` |
| `backend/skills/executor.py` | `backend/skills/safe_eval.py` | `safe_eval_condition` | WIRED | Line 30: `from skills.safe_eval import safe_eval_condition` |
| `backend/api/routes/admin_skills.py` | `backend/skills/importer.py` | `SkillImporter` on import endpoint | WIRED | Line 43, 168 in admin_skills.py |
| `backend/api/routes/admin_skills.py` | `backend/skills/security_scanner.py` | `SecurityScanner.scan()` | WIRED | Line 44, 169 in admin_skills.py |
| `backend/agents/master_agent.py` | `backend/skills/executor.py` | `skill_executor` node calls SkillExecutor | WIRED | Lines 504, 664 in master_agent.py |
| `backend/agents/master_agent.py` | `backend/core/models/skill_definition.py` | slash_command lookup in `_pre_route` | WIRED | Lines 435, 461, 473 in master_agent.py |
| `frontend/src/hooks/use-skills.ts` | `frontend/src/app/api/skills/route.ts` | `fetch('/api/skills')` | WIRED | Line 48 in use-skills.ts |
| `frontend/src/app/api/skills/route.ts` | `backend/api/routes/user_skills.py` | `NEXT_PUBLIC_API_URL` proxy with JWT | WIRED | Line 21, 23 in skills/route.ts |
| `frontend/src/hooks/use-admin-artifacts.ts` | `frontend/src/app/api/admin/[...path]/route.ts` | `fetch('/api/admin/${type}')` | WIRED | Line 41 in use-admin-artifacts.ts |
| `frontend/src/app/api/admin/[...path]/route.ts` | `backend/api/routes/admin_*.py` | `NEXT_PUBLIC_API_URL` proxy with JWT | WIRED | Lines 13, 85-113 in admin proxy route |
| `frontend/src/components/admin/permission-matrix.tsx` | `frontend/src/hooks/use-admin-permissions.ts` | `useAdminPermissions` | WIRED | Line 12, 38 in permission-matrix.tsx |

---

## Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| EXTD-01 | 06-01 | Every artifact type has a dedicated DB table with name, description, version, status | SATISFIED | 6 ORM models in `backend/core/models/`, migration 014, all with required columns |
| EXTD-02 | 06-03, 06-07 | Admin CRUD for all artifact types via API and UI | SATISFIED | 4 admin route files; admin dashboard at /admin with 5 tabs |
| EXTD-03 | 06-04 | New registrations available without restart | SATISFIED | DB-backed tool/agent registry with TTL cache; `register_tool()` upserts to DB; `seed_tool_definitions_from_registry()` at startup |
| EXTD-04 | 06-02, 06-03, 06-07 | Per-artifact per-role permissions with per-user overrides and staged apply | SATISFIED | `check_artifact_permission()` with default-allow semantics; staged model (pending->apply->active); per-user `user_artifact_permissions` table; admin UI with PermissionMatrix |
| EXTD-05 | 06-03, 06-04 | Removing artifact prevents future invocations; running workflows complete gracefully | SATISFIED | `get_tool()` only returns active tools; agent graph excludes disabled agents; status PATCH returns `active_workflow_runs` count |
| EXTD-06 | 06-05, 06-06 | Skill runtime with /command invocation, secure import pipeline | SATISFIED | SkillExecutor, SkillValidator, safe_eval_condition (AST-based), SecurityScanner, SkillImporter; slash command dispatch in `_pre_route`; import quarantine pipeline |

All 6 requirements are satisfied. No orphaned requirements found.

---

## Anti-Pattern Scan

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `frontend/src/components/admin/permission-matrix.tsx` | `ArtifactBase` imported but unused (warning) | Info | TypeScript warning only; build succeeds |
| `frontend/src/components/admin/permission-matrix.tsx` | `ArtifactPermission` imported but unused (warning) | Info | TypeScript warning only; build succeeds |

No blocker anti-patterns found. No TODO/FIXME/placeholder patterns found in implementation files. No stubs returning empty/null implementations. The frontend build shows only lint warnings (unused imports), not errors.

---

## Human Verification Required

### 1. Admin Dashboard Runtime Behavior

**Test:** Start backend (`just backend`) and frontend (`just frontend`). Log in as admin (it-admin role). Navigate to `http://localhost:3000/admin`.
**Expected:**
- 5 tabs visible: Agents, Tools, Skills, MCP Servers, Permissions
- Table and card grid toggle works (localStorage persistence)
- Clicking "Create" on any artifact tab opens a form dialog
- MCP Servers tab shows colored dots (green/yellow/red based on last_seen_at)
- Permissions tab shows role x artifact matrix; editing a checkbox shows pending state (yellow)
- Clicking "Apply Pending" activates the changes
- Logging in as regular employee and navigating to /admin shows "Access Denied" (403 message inline)

**Why human:** Visual rendering, interactive state, and real data display require a running browser session. Plan 06-07 included Task 3 (human verify checkpoint) that was marked as passed with a bug fix commit (0b06cc6 — KNOWN_ROLES mismatch corrected), so the code is in verified state.

### 2. Slash Command Autocomplete in Chat

**Test:** Navigate to `/chat`. In the message input, type `/`.
**Expected:**
- A dropdown popover appears below the input
- Built-in commands (/new, /clear) appear
- Any active skills with slash_command set also appear
- Arrow Up/Down navigates; Tab/Enter selects and fills the input; Escape closes
- Selected skill command is sent to agent as a regular message; backend _pre_route dispatches to skill_executor node

**Why human:** Frontend keyboard interaction, popover positioning, and live agent response to /commands require browser + running backend.

### 3. Hot-Registration End-to-End Timing

**Test:** With backend running, POST to `/api/admin/tools` to create a new tool. Wait 60 seconds. Check `GET /api/tools`.
**Expected:** New tool appears in the tools list within 60 seconds without a backend restart.
**Why human:** The 60s TTL cache behavior cannot be verified without a timed live system test. The implementation is verified (DB-backed cache with `_TOOL_CACHE_TTL = 60.0`), but observing the actual timing requires a running backend.

---

## Automated Verification Summary

- **Backend test suite:** 536 passed, 0 failures (confirmed by `PYTHONPATH=. .venv/bin/pytest tests/ -q`)
- **Frontend build:** Compiled successfully (0 TypeScript errors; 9 lint warnings, all non-blocking)
- **Git commits:** All 15 plan commits verified in git log (8a3746a through 0b06cc6)
- **Migration 014:** Exists with `op.create_table`, seed data, tool_acl migration
- **All 50+ artifacts** checked at Levels 1 (exists), 2 (substantive), and 3 (wired)

---

## Gaps Summary

No gaps found. All 6 success criteria have implementation evidence in the codebase. The 3 human verification items are functional tests that require a live running system — the underlying code is wired and tested. These are not gaps; they are items that cannot be verified programmatically.

---

_Verified: 2026-02-28T17:00:00Z_
_Verifier: Claude (gsd-verifier)_
