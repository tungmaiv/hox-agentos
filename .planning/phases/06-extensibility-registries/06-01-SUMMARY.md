---
phase: 06-extensibility-registries
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, pydantic, orm, permissions, registry]

# Dependency graph
requires:
  - phase: 05-scheduler-and-channels
    provides: "Channel tables, tool_acl, mcp_servers base table"
provides:
  - "AgentDefinition, ToolDefinition, SkillDefinition ORM models"
  - "ArtifactPermission and UserArtifactPermission models with staged status"
  - "RolePermission model replacing hardcoded ROLE_PERMISSIONS dict"
  - "McpServer evolved with version, display_name, status, last_seen_at"
  - "Alembic migration 014 with seed data and tool_acl data migration"
  - "Pydantic v2 schemas for all registry CRUD operations"
affects: [06-02-PLAN, 06-03-PLAN, 06-04-PLAN, 06-05-PLAN, 06-06-PLAN, 06-07-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "UNIQUE(name, version) constraint on all artifact tables for multi-version management"
    - "Staged permission model: status='pending' until admin confirms, then 'active'"
    - "_JSONB = JSON().with_variant(JSONB(), 'postgresql') pattern for SQLite test compat"
    - "No FK on polymorphic artifact_id columns -- polymorphic across tables"

key-files:
  created:
    - backend/core/models/agent_definition.py
    - backend/core/models/tool_definition.py
    - backend/core/models/skill_definition.py
    - backend/core/models/artifact_permission.py
    - backend/core/models/user_artifact_permission.py
    - backend/core/models/role_permission.py
    - backend/core/schemas/registry.py
    - backend/alembic/versions/014_extensibility_registries.py
    - backend/tests/test_registry_models.py
  modified:
    - backend/core/models/mcp_server.py
    - backend/core/models/__init__.py

key-decisions:
  - "UNIQUE(name, version) not UNIQUE(name) on all artifact tables -- enables multi-version with is_active flag"
  - "tool_acl rows migrated to user_artifact_permissions (not artifact_permissions) since tool_acl stored user_id not role"
  - "No FK on artifact_id columns -- polymorphic across agent/tool/skill/mcp_server tables"
  - "Skill slash_command is globally unique (not per-version) -- prevents command conflicts"
  - "McpServer.is_active retained for backward compat; status column added alongside"

patterns-established:
  - "Registry model pattern: id, name, display_name, description, version, is_active, status, last_seen_at + type-specific columns"
  - "Staged permission pattern: ArtifactPermission/UserArtifactPermission with status='pending'|'active'"

requirements-completed: [EXTD-01]

# Metrics
duration: 5min
completed: 2026-02-28
---

# Phase 6 Plan 01: Registry Models & Migration Summary

**6 ORM models (agent/tool/skill/artifact_perm/user_perm/role_perm) with UNIQUE(name,version), Alembic 014 migration with seed data + tool_acl migration, and Pydantic v2 CRUD schemas with cross-field validation**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-28T11:24:36Z
- **Completed:** 2026-02-28T11:29:30Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- 6 new ORM models covering all extensibility registry artifact types and permissions
- McpServer evolved with version, display_name, status, and last_seen_at columns
- Alembic migration 014 creates all tables, seeds role_permissions from ROLE_PERMISSIONS dict, seeds 4 built-in agents, migrates tool_acl rows
- Full Pydantic v2 schema coverage for CRUD operations including staged permissions and cross-field validation
- 28 new tests covering CRUD, unique constraints, is_active flag, staged status, and schema validation
- Full test suite: 337 passed, no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: ORM Models for All 6 New Tables + MCP Server Evolution** - `8a3746a` (feat)
2. **Task 2: Alembic Migration 014 + Tests + Pydantic Schemas** - `904ef9b` (feat)

## Files Created/Modified
- `backend/core/models/agent_definition.py` - AgentDefinition ORM with handler_module/function, routing_keywords
- `backend/core/models/tool_definition.py` - ToolDefinition ORM with handler_type (backend/mcp/sandbox), input/output schemas
- `backend/core/models/skill_definition.py` - SkillDefinition ORM with instructional/procedural types, slash_command, security review
- `backend/core/models/artifact_permission.py` - ArtifactPermission ORM with staged status for per-role access control
- `backend/core/models/user_artifact_permission.py` - UserArtifactPermission ORM for per-user overrides beyond role defaults
- `backend/core/models/role_permission.py` - RolePermission ORM replacing hardcoded ROLE_PERMISSIONS dict
- `backend/core/models/mcp_server.py` - Evolved with version, display_name, status, last_seen_at columns
- `backend/core/models/__init__.py` - Added imports for all 6 new models
- `backend/core/schemas/registry.py` - Pydantic v2 schemas for all CRUD operations (agent, tool, skill, permission)
- `backend/alembic/versions/014_extensibility_registries.py` - Migration creating 6 tables, evolving mcp_servers, seeding data
- `backend/tests/test_registry_models.py` - 28 tests covering all models and schema validation

## Decisions Made
- UNIQUE(name, version) not UNIQUE(name) on all artifact tables -- enables safe multi-version rollback with is_active flag
- tool_acl rows migrated to user_artifact_permissions (not artifact_permissions) because tool_acl stored per-user entries (user_id), not per-role
- No FK on artifact_id columns -- polymorphic references across agent/tool/skill/mcp_server tables
- Skill slash_command has global unique constraint (not per-version) -- prevents /command conflicts
- McpServer.is_active column retained for backward compat during migration; new status column added alongside
- Migration seeds role_permissions with exact values from ROLE_PERMISSIONS dict (5 roles, 12 unique permissions)
- Migration seeds agent_definitions with 4 built-in agents (master, email, calendar, project) using current handler paths

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. Migration 014 will need to be applied to production DB (`just migrate` or `docker exec`).

## Next Phase Readiness
- All 6 ORM models in place -- ready for CRUD API routes in 06-02 and 06-03
- Pydantic schemas complete -- route handlers can use them directly
- Migration 014 ready to apply -- seeds role_permissions and agent_definitions
- Full test suite green (337 tests) -- safe foundation for subsequent plans

## Self-Check: PASSED

- All 11 files verified present on disk
- Both task commits (8a3746a, 904ef9b) verified in git log
- 337 tests passing, 0 failures

---
*Phase: 06-extensibility-registries*
*Completed: 2026-02-28*
