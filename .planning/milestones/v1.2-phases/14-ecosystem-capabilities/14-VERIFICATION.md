---
phase: 14-ecosystem-capabilities
verified: 2026-03-04T06:15:00Z
status: human_needed
score: 16/16 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 15/16
  gaps_closed:
    - "Registered OpenAPI tools are callable via the standard 3-gate security (JWT, RBAC, Tool ACL)"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "CapabilitiesCard UI rendering in web chat"
    expected: "Saying 'what can you do' produces a card with four collapsible sections (Agents, Tools, Skills, MCP Servers), each with a count badge. Sections start collapsed, expand on click."
    why_human: "Cannot verify React collapse/expand behavior, visual layout, or chat streaming without a browser."
  - test: "OpenAPI Connect Wizard 3-step flow"
    expected: "Clicking 'Connect OpenAPI' on admin MCP Servers page opens a dialog. Entering a valid OpenAPI spec URL, selecting endpoints, providing a server name and auth config, and clicking Register creates tools immediately visible in the MCP Servers list."
    why_human: "Multi-step interactive wizard with network fetch cannot be verified programmatically."
  - test: "Skill Store browse and import UI"
    expected: "Admin Skill Store tab is visible at /admin. Browse sub-tab shows a 3-column card grid with search. Import dialog shows security score (0-100) and recommendation before dismissing."
    why_human: "UI layout, responsive grid, and 2-step import dialog behavior require browser interaction."
  - test: "Skill Export download in browser"
    expected: "Clicking Export on a skill row triggers immediate download of {name}-{version}.zip containing SKILL.md with valid YAML frontmatter."
    why_human: "Browser file download behavior (createObjectURL + anchor click) requires manual verification."
---

# Phase 14: Ecosystem Capabilities Verification Report

**Phase Goal:** Ecosystem Capabilities — Agents and users can introspect what the platform can do, any OpenAPI-described service can be wired in as an MCP server in minutes, and external skill repositories can be browsed, imported, and exported in a standard format — turning AgentOS into an open, extensible ecosystem.
**Verified:** 2026-03-04T06:15:00Z
**Status:** human_needed (all automated checks pass; 4 items require browser verification)
**Re-verification:** Yes — after gap closure (Plan 14-05 closed the openapi_proxy dispatch gap)

---

## Re-Verification Context

The previous verification (2026-03-04T05:30:00Z) found 1 gap:

- **Gap:** `openapi_proxy` runtime dispatch not wired — `tools.py` returned HTTP 501 for all non-MCP tools including `openapi_proxy`. `call_openapi_tool()` was fully implemented but unreachable from any dispatch path.

Plan 14-05 was created and executed to close this gap. The fix added an `elif` branch in `call_tool()` in `backend/api/routes/tools.py` that dispatches to `call_openapi_tool()` with full Gate 2 (RBAC) + Gate 3 (ACL) enforcement and AES-GCM decryption of the API key from `McpServer.auth_token`.

**Gap closure verified:** The branch is present in source, 4 new tests pass, and the full suite grew from 714 to 718 passed with no regressions.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | system.capabilities tool returns live structured data from all four registries filtered by user permissions | VERIFIED | `capabilities/tool.py` queries agent_definitions, tool_definitions, skill_definitions, mcp_servers; filters tools+skills via `batch_check_artifact_permissions()` |
| 2 | Capabilities response is filtered by user permissions — users only see artifacts they are allowed to use | VERIFIED | `system_capabilities()` calls `batch_check_artifact_permissions(user=user_ctx, artifact_type=..., artifact_ids=..., session=session)` for both tools and skills |
| 3 | Master agent routes 'what can you do' and 'capabilities' keywords to the system.capabilities tool | VERIFIED | `_classify_by_keywords()` detects 9 phrases (line 456-468), `_pre_route()` routes to `capabilities_node`, graph edge to `delivery_router` wired |
| 4 | CapabilitiesCard A2UI component renders capabilities as collapsed sections with count badges in web chat | VERIFIED (human check needed) | `CapabilitiesCard.tsx` with Section component using useState, four sections, count badges, collapsed by default. `A2UIMessageRenderer.tsx` imports and renders on `agent="capabilities"` |
| 5 | Admin can paste an OpenAPI spec URL and see a parsed list of endpoints grouped by tags with method badges | VERIFIED (human check needed) | `fetch_and_parse_openapi()` in `parser.py` builds tag_groups; `openapi-connect-wizard.tsx` renders collapsible tag groups with method badges in Step 2 |
| 6 | Admin can select which endpoints to expose, name the server, configure auth, and register — MCP server + tools appear immediately | VERIFIED (human check needed) | Wizard Step 3 POSTs to `/api/admin/openapi/register`; `service.py` creates McpServer row + ToolDefinition rows with handler_type='openapi_proxy'; calls `invalidate_tool_cache()` |
| 7 | Registered OpenAPI tools are callable via the standard 3-gate security (JWT, RBAC, Tool ACL) | VERIFIED | `elif tool_def.get("handler_type") == "openapi_proxy"` branch in `call_tool()` (lines 71-154 of tools.py). Gate 2 iterates required_permissions + calls `has_permission()`. Gate 3 calls `check_tool_acl()`. Decrypts `McpServer.auth_token` (iv=raw[:12], ciphertext=raw[12:]). Dispatches to `call_openapi_tool(config_json, body.params, api_key)`. 4 new tests pass (TestToolsRouteOpenAPIProxy). |
| 8 | OpenAPI proxy constructs correct HTTP requests with path params, query params, headers, and request body | VERIFIED | `proxy.py` `_separate_arguments()` and `_build_url()` handle all four param locations; 4 auth types implemented; all proxy tests pass |
| 9 | Admin can add an external skill repository by URL from /admin and see it in the repository list | VERIFIED (human check needed) | `add_repo()` in service.py fetches index, creates SkillRepository row; admin_router GET+POST endpoints registered; Skill Store tab added to ADMIN_TABS in layout.tsx |
| 10 | Admin can remove a repository — imported skills from that repo remain in AgentOS | VERIFIED | `remove_repo()` deletes only the SkillRepository row; SkillDefinition rows have no FK dependency on skill_repositories |
| 11 | Admin can sync a repository to re-fetch its index | VERIFIED | `sync_repo()` re-fetches index, updates `cached_index` and `last_synced_at`; `/api/admin/skill-repos/{id}/sync` endpoint wired |
| 12 | User can browse and search skills from all registered repositories in a card grid UI | VERIFIED (human check needed) | `browse_skills()` aggregates from cached_index of all active repos, case-insensitive search; `skill-store-browse.tsx` card grid with debounced search bar |
| 13 | User can import a skill from a repository — it enters pending_review status and admin can approve it | VERIFIED | `import_from_repo()` calls SkillImporter + SecurityScanner, creates SkillDefinition with `status='pending_review'`, `is_active=False`; tests pass |
| 14 | Admin can click Export on any skill row and receive a downloadable zip file | VERIFIED (human check needed) | `skills/page.tsx` has `handleExport` using fetch+createObjectURL pattern; admin proxy returns `arrayBuffer()` for zip Content-Type |
| 15 | Exported zip contains a valid SKILL.md with agentskills.io-compliant YAML frontmatter | VERIFIED | `build_skill_zip()` builds YAML frontmatter with name, description, metadata (author, version, skill_type, exported_at); 18 tests pass |
| 16 | Export works for skills in any status (active, pending_review, disabled) | VERIFIED | Export route queries `SkillDefinition` by ID with no status filter; `build_skill_zip()` accepts any SkillDefinition regardless of status |

**Score:** 16/16 truths verified (4 require additional human browser verification for UI behavior)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/api/routes/tools.py` | openapi_proxy dispatch branch in call_tool() | VERIFIED | Lines 71-154: elif branch with Gate 2 RBAC, Gate 3 ACL, McpServer auth_token decryption, call_openapi_tool() dispatch, error handling |
| `backend/tests/test_openapi_bridge.py` (TestToolsRouteOpenAPIProxy) | 4 new tests for openapi_proxy dispatch | VERIFIED | Class at line 870; 4 tests: dispatch, encrypted auth, error result, 501 fallback preserved — all 4 pass |
| `backend/alembic/versions/019_ecosystem_capabilities.py` | Migration: skill_repositories, openapi_spec_url, config_json, system.capabilities seed | VERIFIED | Unchanged from initial verification |
| `backend/capabilities/tool.py` | system_capabilities() agent tool function | VERIFIED | Unchanged from initial verification |
| `backend/openapi_bridge/proxy.py` | call_openapi_tool(tool_config, arguments, api_key) -> dict | VERIFIED | Unchanged from initial verification; now invoked from tools.py dispatch |
| `backend/openapi_bridge/service.py` | register_openapi_endpoints(...) | VERIFIED | Unchanged from initial verification |
| `frontend/src/components/a2ui/CapabilitiesCard.tsx` | A2UI CapabilitiesCard with collapsed sections and count badges | VERIFIED | Unchanged from initial verification |
| `backend/skill_repos/service.py` | fetch_index, sync_repo, browse_skills, import_from_repo | VERIFIED | Unchanged from initial verification |
| `backend/skill_export/exporter.py` | build_skill_zip(skill_def) -> BytesIO | VERIFIED | Unchanged from initial verification |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/api/routes/tools.py` | `backend/openapi_bridge/proxy.py` | dispatch branch calls call_openapi_tool(config_json, params, api_key) | WIRED | `from openapi_bridge.proxy import call_openapi_tool` + `result = await call_openapi_tool(tool_config=config_json, arguments=body.params, api_key=api_key)` at lines 79, 136-140 of tools.py |
| `backend/api/routes/tools.py` | `backend/core/models/mcp_server.py` | loads McpServer by mcp_server_id, decrypts auth_token | WIRED | `from core.models.mcp_server import McpServer` + `_select(McpServer).where(McpServer.id == _uuid.UUID(mcp_server_id))` at lines 78, 124-128 |
| `backend/api/routes/tools.py` | `backend/security/rbac.py` | Gate 2 has_permission() call | WIRED | `from security.rbac import has_permission` + `await has_permission(user, permission, session)` at lines 82, 90 |
| `backend/api/routes/tools.py` | `backend/security/acl.py` | Gate 3 check_tool_acl() call | WIRED | `from security.acl import check_tool_acl` + `await check_tool_acl(user["user_id"], body.tool, session)` at lines 80, 105 |
| `backend/api/routes/tools.py` | `backend/security/credentials.py` | decrypt_token() for McpServer.auth_token AES-GCM decryption | WIRED | `from security.credentials import decrypt_token` + `api_key = decrypt_token(ciphertext, iv)` at lines 81, 134 |
| `backend/capabilities/tool.py` | `backend/security/rbac.py` | batch_check_artifact_permissions() to filter per user | WIRED | Unchanged from initial verification |
| `backend/agents/master_agent.py` | `backend/capabilities/tool.py` | _pre_route keyword routing | WIRED | Unchanged from initial verification |
| `backend/openapi_bridge/service.py` | `backend/core/models/tool_definition.py` | creates ToolDefinition rows with handler_type='openapi_proxy' | WIRED | Unchanged from initial verification |
| `backend/skill_repos/service.py` | `backend/skills/importer.py` | import_from_repo calls SkillImporter.import_from_url | WIRED | Unchanged from initial verification |
| `backend/skill_export/routes.py` | `backend/skill_export/exporter.py` | route calls build_skill_zip, returns StreamingResponse | WIRED | Unchanged from initial verification |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| ECO-01 | 14-01 | Agent or user can query `system.capabilities` tool to list all registered agents, tools, skills, and MCP servers with descriptions | SATISFIED | system_capabilities() tool + _capabilities_node in master_agent.py + CapabilitiesCard A2UI; 14/14 tests pass |
| ECO-02 | 14-02, 14-05 | User can run `api-to-mcp` skill: provide an app URL, have AgentOS fetch the OpenAPI spec, select endpoints to expose, and generate + register an MCP server with callable tools | SATISFIED | Admin wizard for parse+register fully works. Registered tools are now callable end-to-end via `/api/tools/call` with Gates 2+3 enforced. 14-02 tests (17) + 14-05 tests (4) = 21 tests, all pass. |
| ECO-03 | 14-03 | Admin can add and remove external skill/tool repositories by URL | SATISFIED | add_repo() + remove_repo() service functions + admin_router endpoints + SkillStoreRepositories UI; 26/26 tests pass |
| ECO-04 | 14-03 | User can search and browse skills/tools from registered external repositories inside AgentOS | SATISFIED | browse_skills() with case-insensitive search + SkillStoreBrowse UI card grid; tests pass |
| ECO-05 | 14-03 | User can import a skill or tool from an external repository into AgentOS (imported artifact enters security review flow before activation) | SATISFIED | import_from_repo() calls SkillImporter + SecurityScanner, creates SkillDefinition with status='pending_review', is_active=False; tests pass |
| ECO-06 | 14-04 | AgentOS skill definitions can be exported in agentskills.io-compliant manifest format | SATISFIED | build_skill_zip() produces SKILL.md with YAML frontmatter + optional procedure.json + schemas.json; 18/18 tests pass |

**Orphaned requirements:** None — all 6 ECO requirements claimed by plans and satisfied.

---

## Test Suite Results

| Test File | Count | Result |
|-----------|-------|--------|
| `test_capabilities.py` | 14 | All pass |
| `test_openapi_bridge.py` | 21 (17 original + 4 new in TestToolsRouteOpenAPIProxy) | All pass |
| `test_skill_repos.py` | 26 | All pass |
| `test_skill_export.py` | 18 | All pass (1 pre-existing RuntimeWarning — non-blocking) |
| **Full suite** | **718 passed, 1 skipped** | No regressions vs. 714 pre-plan-05 baseline |
| Frontend build | — | Zero TypeScript errors (pre-existing ESLint warnings, none blocking) |

---

## Commit Evidence (Plan 14-05)

| Commit | Type | Description |
|--------|------|-------------|
| `db71603` | test (RED) | Add failing tests for openapi_proxy dispatch in call_tool() |
| `8adb8ee` | feat (GREEN) | Implement openapi_proxy dispatch branch in call_tool() |
| `31b448f` | docs | Complete openapi_proxy dispatch plan — SUMMARY, STATE, ROADMAP |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/tests/test_skill_export.py` | (async cleanup) | Coroutine '_auth_override' never awaited | INFO | Pre-existing RuntimeWarning; does not affect test correctness — unchanged from initial verification |

No placeholders, empty implementations, stubs, or new anti-patterns introduced by Plan 14-05.

---

## Human Verification Required

### 1. CapabilitiesCard Chat Rendering

**Test:** In web chat, type "what can you do" and submit.
**Expected:** A structured card appears with a wrench icon header, summary text ("N agents, M tools, K skills, L MCP servers"), and four collapsible sections. Clicking a section header expands it to show items with names and one-line descriptions.
**Why human:** React collapse/expand state behavior, visual card layout, and SSE streaming cannot be verified programmatically.

### 2. OpenAPI Connect Wizard Full Flow

**Test:** Go to admin MCP Servers page. Click "Connect OpenAPI". In Step 1, paste a public OpenAPI spec URL (e.g., https://petstore3.swagger.io/api/v3/openapi.json). Click "Fetch & Parse".
**Expected:** Step 2 shows endpoints grouped by tag (Pets, Store, User). Each endpoint has a method badge (green GET, blue POST, etc.). Select a few endpoints. Proceed to Step 3, enter a server name, choose No Auth, and click Register.
**Why human:** Multi-step interactive wizard with network fetch, endpoint selection UI, and conditional auth form rendering require browser interaction.

### 3. Skill Store Browse and Import Flow

**Test:** Go to admin Skill Store tab. Click Browse. Add a test repository URL in Repositories sub-tab, sync it, then return to Browse and search for a skill. Click Import on a skill card.
**Expected:** Import dialog opens (Step 1: confirm), then shows security score (0-100) and recommendation (approve/review/reject) before auto-closing.
**Why human:** UI layout, responsive grid breakpoints, and 2-step import dialog state require browser verification.

### 4. Skill Export Browser Download

**Test:** Go to admin Skills tab. Click the Export button on any skill row.
**Expected:** Browser downloads a file named {skill-name}-{version}.zip immediately. Opening the zip reveals SKILL.md with YAML frontmatter including name, description, and metadata.exported_at timestamp.
**Why human:** Browser file download via fetch+createObjectURL+anchor pattern requires manual verification of download behavior and zip content integrity.

---

## Gap Closure Summary

The 1 gap from the initial verification is confirmed closed:

**Gap was:** `backend/api/routes/tools.py` returned HTTP 501 for all non-MCP tools. The `call_openapi_tool()` function in `proxy.py` was fully implemented but unreachable from any dispatch path.

**Fix applied (Plan 14-05):** Added an `elif tool_def.get("handler_type") == "openapi_proxy"` branch between the existing `mcp_server` branch and the `else` 501 fallback. The branch:
1. Enforces Gate 2 (RBAC) — iterates `required_permissions`, calls `has_permission()` with audit logging
2. Enforces Gate 3 (ACL) — calls `check_tool_acl()` with matching audit log pattern
3. Loads `McpServer` by `mcp_server_id` (UUID-cast from str cache value)
4. Decrypts `auth_token` using AES-GCM convention: `iv = raw[:12]; ciphertext = raw[12:]`
5. Calls `call_openapi_tool(tool_config=config_json, arguments=body.params, api_key=api_key)`
6. Maps error dicts (`{"error": True, ...}`) to `ToolCallResponse(success=False, error=detail)`

Non-openapi_proxy backend tools still return HTTP 501 (no regression).

ECO-02 is now fully satisfied: admin can parse an OpenAPI spec, select endpoints, register them as tools, and those tools are callable end-to-end through the standard 3-gate security flow.

---

_Verified: 2026-03-04T06:15:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — gap closure for Plan 14-05_
