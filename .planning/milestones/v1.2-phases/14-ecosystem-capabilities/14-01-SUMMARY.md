---
phase: 14-ecosystem-capabilities
plan: "01"
subsystem: capabilities
tags: [capabilities, migration, a2ui, routing]
dependency_graph:
  requires: []
  provides:
    - "Migration 019: skill_repositories table, mcp_servers.openapi_spec_url, tool_definitions.config_json"
    - "SkillRepository SQLAlchemy model"
    - "capabilities module: system_capabilities() tool + CapabilitiesResponse schema"
    - "CapabilitiesCard A2UI component with collapsed sections and count badges"
    - "Master agent keyword routing for capabilities intent"
  affects:
    - backend/agents/master_agent.py
    - backend/core/models/tool_definition.py
    - backend/core/models/mcp_server.py
    - frontend/src/components/a2ui/A2UIMessageRenderer.tsx
tech_stack:
  added:
    - "capabilities/ package (new backend module)"
    - "CapabilitiesCard.tsx (new A2UI frontend component)"
    - "Migration 019 with skill_repositories table"
  patterns:
    - "SQLAlchemy async with session.begin() for read-only queries"
    - "batch_check_artifact_permissions() for permission-filtered listing"
    - "A2UI JSON card envelope pattern (agent='capabilities')"
    - "TDD: tests written alongside implementation"
key_files:
  created:
    - backend/alembic/versions/019_ecosystem_capabilities.py
    - backend/core/models/skill_repository.py
    - backend/capabilities/__init__.py
    - backend/capabilities/schemas.py
    - backend/capabilities/tool.py
    - backend/tests/test_capabilities.py
    - frontend/src/components/a2ui/CapabilitiesCard.tsx
  modified:
    - backend/core/models/__init__.py
    - backend/core/models/tool_definition.py
    - backend/core/models/mcp_server.py
    - backend/agents/master_agent.py
    - frontend/src/lib/a2ui-types.ts
    - frontend/src/components/a2ui/A2UIMessageRenderer.tsx
    - frontend/src/components/a2ui/index.ts
decisions:
  - "[14-01]: CapabilitiesCard uses collapsed sections with count badges — sections collapsed by default per CONTEXT.md locked decision"
  - "[14-01]: system.capabilities seeded into tool_definitions in migration 019 — single authoritative source"
  - "[14-01]: Capabilities routing handled in _classify_by_keywords() before agent routing — returns 'capabilities' intent"
  - "[14-01]: _capabilities_node routes through delivery_router like all other nodes — consistent graph topology"
  - "[14-01]: Agents and MCP servers use default-allow; tools and skills use batch_check_artifact_permissions() filtering"
metrics:
  duration: "~10 minutes"
  completed: "2026-03-04"
  tasks_completed: 3
  tasks_total: 3
  files_created: 7
  files_modified: 7
---

# Phase 14 Plan 01: Ecosystem Capabilities Foundation Summary

**One-liner:** Migration 019 with skill_repositories table + system_capabilities() tool with four-registry introspection + CapabilitiesCard A2UI component with collapsible sections.

## What Was Built

### Task 1: Migration 019, SkillRepository model, model updates (commit 2bcca92)

- Created `backend/core/models/skill_repository.py` — SkillRepository ORM model with id, name, url, description, is_active, last_synced_at, cached_index (JSONB), created_at, updated_at
- Added `config_json` (JSONB nullable) to ToolDefinition model — stores OpenAPI proxy tool config
- Added `openapi_spec_url` (Text nullable) to McpServer model — links MCP server to its OpenAPI spec
- Updated `core/models/__init__.py` to import SkillRepository
- Created `backend/alembic/versions/019_ecosystem_capabilities.py` — creates skill_repositories table, adds both columns, seeds system.capabilities tool definition

### Task 2: capabilities module + master agent routing (commit 6390908)

- Created `backend/capabilities/__init__.py`, `schemas.py`, `tool.py`
- `CapabilitiesResponse` Pydantic schema bundles AgentInfo, ToolInfo, SkillInfo, McpServerInfo
- `system_capabilities()` queries all four active artifact registries, filters tools+skills via `batch_check_artifact_permissions()`, counts MCP tools per server
- Updated `_classify_by_keywords()` in master_agent.py to detect 9 capabilities-intent phrases (case-insensitive)
- Added `_capabilities_node` graph node that invokes system_capabilities() and returns A2UI JSON card
- Wired `capabilities_node` into StateGraph with route_map and delivery_router edge
- 14 tests: all capabilities tool behaviors, permission filtering, empty registries, keyword routing

### Task 3: CapabilitiesCard A2UI frontend component (commit 5dd6f31)

- Created `frontend/src/components/a2ui/CapabilitiesCard.tsx` — "use client" component with four collapsible sections (Agents, Tools, Skills, MCP Servers)
- Each section has a count badge, collapsed by default, expands on click via useState
- Items show display_name (or name) + one-line description; static, not clickable
- Added Zod schemas (AgentInfoSchema, ToolInfoSchema, SkillInfoSchema, McpServerInfoSchema, CapabilitiesOutputSchema) to `a2ui-types.ts`
- Updated `A2UIMessageRenderer.tsx` to route `agent="capabilities"` to CapabilitiesCard
- Exported CapabilitiesCard from `a2ui/index.ts`

## Verification Results

- `PYTHONPATH=. .venv/bin/pytest tests/test_capabilities.py -v` — **14/14 passed**
- `PYTHONPATH=. .venv/bin/pytest tests/ -q` — **653 passed, 1 skipped** (no regression)
- `pnpm run build` — **succeeded with zero TypeScript errors** (only pre-existing warnings)
- All model imports verified: SkillRepository, ToolDefinition.config_json, McpServer.openapi_spec_url

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical feature] CapabilitiesCard renders unicode emoji using HTML entities**
- **Found during:** Task 3
- **Issue:** Emoji characters in JSX (🤖, ⭐) can cause build warnings or encoding issues
- **Fix:** Used HTML entities (e.g., `&#129302;`, `&#127775;`) for unicode symbols instead of raw emoji in JSX
- **Files modified:** `frontend/src/components/a2ui/CapabilitiesCard.tsx`
- **Commit:** 5dd6f31

**2. [Rule 2 - Missing input] `batch_check_artifact_permissions` call updated to match actual signature**
- **Found during:** Task 2 implementation
- **Issue:** Plan spec showed function signature as `(user_roles, artifact_ids, artifact_type, session)` but actual function takes `(user: UserContext, artifact_type, artifact_ids, session)`
- **Fix:** Read `security/rbac.py` to confirm actual signature, implemented with correct `user: UserContext` argument
- **Files modified:** `backend/capabilities/tool.py`
- **Commit:** 6390908

## Self-Check

**Files exist:**
- backend/alembic/versions/019_ecosystem_capabilities.py: FOUND
- backend/core/models/skill_repository.py: FOUND
- backend/capabilities/tool.py: FOUND
- backend/capabilities/schemas.py: FOUND
- backend/tests/test_capabilities.py: FOUND
- frontend/src/components/a2ui/CapabilitiesCard.tsx: FOUND

**Commits exist:**
- 2bcca92: FOUND (Task 1)
- 6390908: FOUND (Task 2)
- 5dd6f31: FOUND (Task 3)

## Self-Check: PASSED
