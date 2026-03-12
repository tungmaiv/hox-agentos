---
phase: 24
plan: "07"
subsystem: registry
tags: [gap-closure, runtime-fix, registry, openapi-bridge, security-scanner]
dependency_graph:
  requires: [24-05, 24-02]
  provides: [registry-runtime-correctness]
  affects: [admin_system, skill_handler, openapi_bridge]
tech_stack:
  added: []
  patterns: [RegistryEntry-JSONB-config, lazy-import-guard, dirty-tracking-reassign]
key_files:
  created: []
  modified:
    - backend/api/routes/admin_system.py
    - backend/registry/handlers/skill_handler.py
    - backend/openapi_bridge/service.py
    - backend/tests/test_openapi_bridge.py
decisions:
  - "[24-07]: astext JSONB accessor skipped in SQLite tests — Python-level filter used instead for handler_type check (SQLite JSON lacks PostgreSQL JSONB operators)"
  - "[24-07]: skill_handler.on_create() uses lazy import guard for scan_client — avoids circular import and matches import_service.py pattern"
  - "[24-07]: openapi_bridge auth_token stored as hex string in config — bytes not JSON-serializable in JSONB column"
  - "[24-07]: Gap 1 (admin_skills/admin_tools routers) accepted as technical debt — removing those routers would break 50+ tests; frontend correctly uses /api/registry/*"
metrics:
  duration: 285s
  completed_date: "2026-03-12"
  tasks_completed: 3
  files_modified: 4
---

# Phase 24 Plan 07: Runtime Gap Closure (RegistryEntry Migration) Summary

**One-liner:** Fixed three production-runtime blockers: admin batch rescan now queries registry_entries (not dropped skill_definitions), skill_handler.on_create() calls Docker security scanner, and openapi_bridge writes RegistryEntry rows (not dropped McpServer/ToolDefinition rows).

## What Was Built

Three targeted fixes to close production-runtime blockers found in Phase 24 verification. These code paths passed unit tests only because SQLite test mode recreates all tables from ORM models — any production Postgres deployment with migration 029 applied would fail on all three paths.

### Task 1: Fix admin_system.py batch rescan
**File:** `backend/api/routes/admin_system.py` (lines 38-80)

- Replaced `from core.models.skill_definition import SkillDefinition` with `from registry.models import RegistryEntry`
- Changed query from `select(SkillDefinition).where(status='active', is_active=True)` to `select(RegistryEntry).where(type='skill', status='active', deleted_at IS NULL)`
- Field accesses changed from `skill.instruction_markdown` to `entry.config.get('instruction_markdown', '')`
- Scan result stored via full dict reassignment: `entry.config = {**config, 'security_score': ..., 'security_report': ...}` (SQLAlchemy JSONB dirty-tracking requires full reassign)

### Task 2: Wire skill_handler.on_create() to Docker security scanner
**File:** `backend/registry/handlers/skill_handler.py` (lines 20-50)

- Added `scan_skill_with_fallback` call inside `on_create()` via lazy import guard
- Builds `skill_data` dict from `entry.name` and `entry.config` fields
- Stores scan result into `entry.config` (full dict reassignment for dirty-tracking)
- Exception caught and logged — skill creation never fails due to scanner unavailability
- No `session.commit()` inside `on_create()` — caller owns the transaction

### Task 3: Migrate openapi_bridge/service.py to RegistryEntry
**Files:** `backend/openapi_bridge/service.py`, `backend/tests/test_openapi_bridge.py`

- Removed `McpServer`, `ToolDefinition` lazy imports and `invalidate_tool_cache()` call
- Added `from registry.models import RegistryEntry` and `import uuid` at module level
- `register_openapi_endpoints()` now creates:
  - One `RegistryEntry(type='mcp_server')` with url/spec_url/auth in config JSONB
  - N `RegistryEntry(type='tool')` rows with handler_type/routing in config JSONB
- Auth token stored as hex string in config (bytes not JSON-serializable in JSONB)
- Updated `test_openapi_bridge.py`: removed McpServer/ToolDefinition imports, added RegistryEntry import, replaced assertions on McpServer.url/ToolDefinition.config_json with assertions on RegistryEntry.config dict

## Test Results

| Metric | Before | After |
|--------|--------|-------|
| Test count | 913 passed, 7 skipped | 913 passed, 7 skipped |
| Regressions | N/A | 0 |
| New failures | N/A | 0 |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQLite JSONB .astext incompatibility in test**
- **Found during:** Task 3
- **Issue:** Plan suggested `RegistryEntry.config["handler_type"].astext == "openapi_proxy"` for SQL WHERE clause but `.astext` is a PostgreSQL-only JSONB accessor; SQLite JSON throws `AttributeError`
- **Fix:** Query all `type='tool'` entries then filter in Python: `[t for t in tools if t.config.get("handler_type") == "openapi_proxy"]`
- **Files modified:** `backend/tests/test_openapi_bridge.py`
- **Commit:** 5305af8

## Accepted Technical Debt

**Gap 1: admin_skills.py and admin_tools.py routers still registered**

The `/api/admin/skills/*` and `/api/admin/tools/*` routes still exist alongside the new `/api/registry/*` routes. This was identified in the 24-VERIFICATION.md as Gap 1 but is explicitly out of scope for this plan:

- Removing those routers would break 50+ tests that cover the old admin_skills and admin_tools routes
- The frontend admin UI correctly uses `/api/registry/*` endpoints for all new operations
- User-facing behavior is correct; the old routes are accessible but not linked from the new UI
- Resolution: remove old routes in a dedicated cleanup plan with test updates

## Self-Check: PASSED

Files verified to exist:
- `backend/api/routes/admin_system.py` — FOUND
- `backend/registry/handlers/skill_handler.py` — FOUND
- `backend/openapi_bridge/service.py` — FOUND
- `backend/tests/test_openapi_bridge.py` — FOUND

Commits verified:
- `8631c28` fix(24-07): fix admin_system batch rescan to use RegistryEntry — FOUND
- `97c4032` feat(24-07): wire skill_handler.on_create() to call scan_skill_with_fallback — FOUND
- `5305af8` feat(24-07): migrate openapi_bridge to use RegistryEntry rows — FOUND
