---
phase: 24-unified-registry-mcp-platform-enhancement-skill-import-adapters
verified: 2026-03-12T10:00:00Z
status: human_needed
score: 27/28 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 22/28
  gaps_closed:
    - "POST /api/admin/system/rescan-skills background task now iterates registry_entries (not dropped skill_definitions table) — RegistryEntry query confirmed at lines 47-51 of admin_system.py; commit 8631c28"
    - "skill_handler.on_create() now calls scan_skill_with_fallback — lazy import guard + await call confirmed at lines 23-32 of skill_handler.py; commit 97c4032"
    - "openapi_bridge/service.py now inserts RegistryEntry rows (type=mcp_server and type=tool) — 0 references to McpServer/ToolDefinition, 8 references to RegistryEntry confirmed; commit 5305af8"
    - "All 913 backend tests pass with 0 regressions after gap closure"
  gaps_remaining:
    - "Gap 1 (admin_skills.router, admin_tools.router, admin_agents.router still registered in main.py) accepted as technical debt per plan 07 decision — frontend uses /api/registry/* correctly; old routes kept for 50+ test backward compatibility"
  regressions: []
human_verification:
  - test: "Start stack (just up), confirm migration 029 applied, call POST /api/admin/system/rescan-skills with admin JWT"
    expected: "202 response; server logs show rescan_skills_start and rescan_skills_complete without 'relation skill_definitions does not exist' PostgreSQL errors"
    why_human: "Cannot verify actual PostgreSQL runtime behavior without running against production DB with migration 029 applied — code is confirmed correct but live run needed to catch any remaining stale import at module load time"
  - test: "Navigate to http://localhost:3000/admin in a browser with admin-role session"
    expected: "Exactly 4 tabs visible: Registry, Access, System, Build"
    why_human: "Visual layout check — previously checkpoint-approved during plan 06; low-risk confirmation that plan 07 backend-only changes did not affect frontend layout"
---

# Phase 24: Unified Registry, MCP Platform Enhancement & Skill Import Adapters — Verification Report

**Phase Goal:** Unify all entity management (agents/skills/tools/MCP) into a single registry; add public MCP server support via stdio transport; build pluggable skill import adapters; replace WeightedSecurityScanner with standalone Docker security scan service; consolidate admin UI to 4 tabs; make LLM model/provider configurable in admin.

**Verified:** 2026-03-12T10:00:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (plan 07, commits 8631c28 / 97c4032 / 5305af8)

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | pnpm exec tsc --noEmit passes with zero errors | VERIFIED | Confirmed in initial verification; no frontend files modified in plan 07 |
| 2 | Backend starts without crashing when CREDENTIAL_ENCRYPTION_KEY is valid | VERIFIED | validate_encryption_key model_validator present in config.py |
| 3 | Backend raises clear ValueError at startup when CREDENTIAL_ENCRYPTION_KEY is invalid | VERIFIED | model_validator with bytes.fromhex check confirmed in config.py |
| 4 | Keycloak provider-config fetch in auth.ts retries with backoff before failing | VERIFIED | fetchWithRetry at line 40 in frontend/src/auth.ts |
| 5 | registry_entries table exists; old tables dropped; code uses RegistryEntry exclusively | VERIFIED | Migration 029 confirmed; all three plan-07 files now use RegistryEntry ORM only |
| 6 | GET /api/registry/?type=skill returns list of skills | VERIFIED | UnifiedRegistryService.list_entries() with type filter; route in api/routes/registry.py |
| 7 | POST /api/registry/ with type=tool creates entry and returns 201 | VERIFIED | 913 tests pass including registry route tests |
| 8 | DELETE /api/registry/{id} soft-deletes by setting deleted_at timestamp | VERIFIED | soft-delete via deleted_at in models.py |
| 9 | Old routes /api/admin/skills, /api/admin/tools, /api/gateway/registry, /api/mcp removed from main.py | PARTIAL | admin_agents, admin_tools, admin_skills routers still registered — ACCEPTED TECHNICAL DEBT per plan 07; frontend uses /api/registry/* correctly |
| 10 | backend/gateway/tool_registry.py is deleted | VERIFIED | File does not exist |
| 11 | Frontend admin pages for agents/skills/tools/mcp-servers fetch from /api/registry/* | VERIFIED | All 4 pages confirmed using /api/registry?type={type} |
| 12 | StdioMCPClient.list_tools() connects to stdio MCP server subprocess and returns tool dicts | VERIFIED | Custom JSON-RPC 2.0 over asyncio subprocess in mcp/stdio_client.py; 41 MCP tests pass |
| 13 | MCPInstaller.install('npm'/'pip') runs correct subprocess command | VERIFIED | npm/pip commands confirmed in installer.py; tests pass |
| 14 | MCP catalog migration (030) seeds 3 pre-built server entries | VERIFIED | 9 matches for context7/mcp-server-fetch/mcp-server-filesystem in 030 migration file |
| 15 | StdioMCPClient.call_tool() raises asyncio.TimeoutError on timeout | VERIFIED | asyncio.wait_for guard in stdio_client.py |
| 16 | SkillRepoAdapter.fetch_and_normalize(url) returns NormalizedSkill | VERIFIED | NormalizedSkill dataclass in adapters/base.py; SkillRepoAdapter in skill_repo.py |
| 17 | GitHubAdapter.get_skill_list() returns skill file paths for public GitHub repo | VERIFIED | GitHubAdapter in github.py uses GitHub Trees API; 4 tests pass |
| 18 | ClaudeMarketAdapter.can_handle() returns True for claude-market:// sources | VERIFIED | source.startswith("claude-market://") in claude_market.py |
| 19 | UnifiedImportService.import_skill() routes to correct adapter | VERIFIED | AdapterRegistry.detect_adapter() priority chain: ClaudeMarket to GitHub to SkillRepo |
| 20 | UnifiedImportService.import_skill() calls scan_skill_with_fallback before saving | VERIFIED | _HAS_SCANNER guard + scan_skill_with_fallback call in import_service.py |
| 21 | POST /api/registry/import accepts source URL and returns 201 with registry entry id | VERIFIED | Endpoint in api/routes/registry.py returns ImportSkillResponse |
| 22 | SecurityScanClient.scan_skill() calls POST to Docker scanner and returns scan_engine='docker' | VERIFIED | httpx POST to security-scanner:8003/scan; result["scan_engine"] = "docker" in scan_client.py |
| 23 | scan_skill_with_fallback() falls back to in-process SecurityScanner on connect error | VERIFIED | except Exception catches all; returns scan_engine="fallback"; 8 tests pass |
| 24 | curl http://localhost:8003/health returns 200 when security-scanner container running | VERIFIED | GET /health endpoint confirmed in infra/security-scanner/main.py |
| 25 | POST /api/admin/system/rescan-skills iterates registry_entries with type=skill and status=active | VERIFIED | Lines 47-51 of admin_system.py: select(RegistryEntry).where(type='skill', status='active', deleted_at IS NULL) — zero SkillDefinition references remain |
| 26 | security-scanner service appears in docker-compose.yml on port 8003 | VERIFIED | security-scanner service with ports: 8003:8003 confirmed |
| 27 | Admin layout shows exactly 4 top-level tabs: Registry, Access, System, Build | VERIFIED | layout.tsx has 4 ADMIN_TABS entries; checkpoint approved during plan 06 |
| 28 | LLM model/provider configurable in admin; POST /api/admin/llm/models calls LiteLLM /model/new; disclaimer visible | VERIFIED | admin_llm.py POST delegates to LiteLLM /model/new; disclaimer text confirmed in llm/page.tsx |

**Score:** 27/28 truths verified (1 partial — accepted tech debt, no automated fix needed)

---

## Re-verification: Gap Closure Detail

### Gaps Closed by Plan 07

**Gap 2 (rescan uses dropped table) — CLOSED**

`backend/api/routes/admin_system.py` lines 41-53 now use `RegistryEntry` from `registry.models`. The `_run_batch_scan` background task queries `registry_entries` with `type='skill'`, `status='active'`, `deleted_at IS NULL`. Field accesses use `entry.config.get(...)`. Scan result stored via full JSONB dict reassignment. Zero `SkillDefinition` references remain in the file.

**Gap 3 (skill_handler.on_create is no-op) — CLOSED**

`backend/registry/handlers/skill_handler.py` `on_create()` now calls `scan_skill_with_fallback` via lazy import guard (same pattern as import_service.py). Builds `skill_data` dict from `entry.name` and `entry.config`. Stores scan result in `entry.config` via full dict reassignment. Exception is caught — skill creation never fails due to scanner unavailability. No `session.commit()` inside hook.

**Gap 4 (openapi_bridge uses dropped tables) — CLOSED**

`backend/openapi_bridge/service.py` zero references to `McpServer` or `ToolDefinition`. Eight references to `RegistryEntry`. `register_openapi_endpoints()` creates one `RegistryEntry(type='mcp_server')` and N `RegistryEntry(type='tool')` rows. Auth token stored as hex string in config JSONB (bytes not JSON-serializable). `test_openapi_bridge.py` updated to assert RegistryEntry rows.

### Gaps Remaining (Accepted Tech Debt)

**Gap 1 (admin routers in main.py) — ACCEPTED, NOT CLOSED**

Per plan 07 decision: `admin_skills.router`, `admin_tools.router`, `admin_agents.router` remain registered in `main.py`. Rationale: removing them would break 50+ existing tests. Frontend admin UI uses `/api/registry/*` for all user-facing operations — no user-visible regression. Resolution path: a future cleanup plan migrates the 50+ tests to `/api/registry/*` then removes the legacy routers.

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/api/routes/admin_system.py` | _run_batch_scan using RegistryEntry with type='skill' | VERIFIED | Lines 41-84: RegistryEntry import and query; no SkillDefinition |
| `backend/registry/handlers/skill_handler.py` | on_create() calls scan_skill_with_fallback | VERIFIED | Lines 20-52: lazy import + await scan_skill_with_fallback + result in entry.config |
| `backend/openapi_bridge/service.py` | register_openapi_endpoints() writes RegistryEntry rows only | VERIFIED | 0 McpServer/ToolDefinition; 8 RegistryEntry; type=mcp_server + type=tool |
| `backend/tests/test_openapi_bridge.py` | Asserts RegistryEntry rows (not McpServer/ToolDefinition) | VERIFIED | Updated assertions; 913 tests pass |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/api/routes/admin_system.py` | registry_entries table | RegistryEntry ORM | WIRED | select(RegistryEntry).where(type='skill') at lines 47-51 |
| `backend/registry/handlers/skill_handler.py` | `backend/security/scan_client.py` | scan_skill_with_fallback lazy import | WIRED | lazy import at line 23, await call at line 32 |
| `backend/openapi_bridge/service.py` | registry_entries (mcp_server) | RegistryEntry ORM | WIRED | RegistryEntry(type='mcp_server') at line 173 |
| `backend/openapi_bridge/service.py` | registry_entries (tool) | RegistryEntry ORM | WIRED | RegistryEntry(type='tool') at line 205 |
| `backend/skills/import_service.py` | `backend/security/scan_client.py` | scan_skill_with_fallback | WIRED | Confirmed in initial verification; unchanged |
| `frontend admin pages` | `/api/registry/*` | fetch in page components | WIRED | Confirmed in initial verification; unchanged |
| `backend/api/routes/admin_llm.py` | LiteLLM proxy /model/new | httpx POST | WIRED | Confirmed in initial verification; unchanged |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| 24-01-DEBT | 24-01-PLAN | Tech debt: SWR, CREDENTIAL_ENCRYPTION_KEY, Keycloak SSO, page load | SATISFIED | All 4 items resolved |
| 24-02-REG | 24-02-PLAN | Unified registry: registry_entries table, handlers, /api/registry/* routes | PARTIAL | Core registry built; old admin routers retained as accepted tech debt |
| 24-03-MCP | 24-03-PLAN | MCP platform: StdioMCPClient, MCPInstaller, catalog, OpenAPI bridge | SATISFIED | All artifacts; openapi_bridge now uses RegistryEntry (plan 07) |
| 24-04-SKL | 24-04-PLAN | Skill import adapters: SkillAdapter ABC, GitHubAdapter, UnifiedImportService | SATISFIED | All adapters + import service confirmed |
| 24-05-SEC | 24-05-SEC | Security scanner: Docker service, scan_client, fallback, rescan, handler wired | SATISFIED | rescan now uses RegistryEntry (plan 07); skill_handler wired (plan 07) |
| 24-06-UI | 24-06-PLAN | Admin 4-tab layout, Registry hub, LLM config, Scan Results tab | SATISFIED | Checkpoint approved; all must-haves confirmed |
| 24-07-GAP | 24-07-PLAN | Gap closure: fix 3 runtime blockers | SATISFIED | All 3 blockers fixed; 0 regressions; 913/913 tests pass |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/main.py` | 198, 201, 214 | admin_agents, admin_tools, admin_skills routers registered alongside /api/registry/* | INFO | Accepted tech debt — frontend uses /api/registry/*; old routes accessible but not linked from admin UI |

No BLOCKER anti-patterns remain. All previous blockers (SkillDefinition/ToolDefinition/McpServer references to dropped tables) are resolved.

---

## Human Verification Required

### 1. Rescan-skills runtime behavior

**Test:** Start the stack (`just up`), confirm migration 029 has been applied (`just migrate`), then call `POST /api/admin/system/rescan-skills` with an admin JWT (via curl or the admin UI).

**Expected:** 202 response immediately. Server logs show `rescan_skills_start` followed by `rescan_skills_complete` without any `relation "skill_definitions" does not exist` PostgreSQL errors.

**Why human:** Code is confirmed correct — `RegistryEntry` ORM with `type='skill'` query at lines 47-51 of admin_system.py. Cannot verify the actual PostgreSQL runtime without running against production DB with migration 029 applied. The critical check is whether any lingering module-level import in an indirect dependency still references the dropped table.

### 2. Admin 4-tab layout visual confirmation

**Test:** Navigate to `http://localhost:3000/admin` in a browser with an admin-role user session.

**Expected:** Exactly 4 tabs visible: Registry, Access, System, Build. No extra tabs.

**Why human:** Visual layout check. Previously checkpoint-approved during plan 06. Plan 07 only modified backend files — this is a low-risk regression check confirming the frontend layout is unaffected.

---

## Accepted Technical Debt

**Gap 1: admin_skills.router, admin_tools.router, admin_agents.router registered in main.py**

Deliberate decision per plan 07 (documented in 24-07-SUMMARY.md decisions section):
- Removing these routers would break 50+ existing tests covering legacy admin CRUD routes
- Frontend admin UI correctly uses `/api/registry/*` — no user-facing regression
- Old routes remain accessible but are not linked from the new 4-tab admin UI
- Resolution path: future cleanup plan migrates 50+ tests to `/api/registry/*` then removes legacy routers

---

_Verified: 2026-03-12T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification of initial 2026-03-12T04:30:00Z report after plan 07 gap closure (commits 8631c28, 97c4032, 5305af8)_
