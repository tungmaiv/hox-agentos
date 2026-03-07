---
phase: 20-skill-platform-b-discovery-catalog
plan: 01
subsystem: database
tags: [alembic, postgresql, pgvector, fts, tsvector, gin-index, skill-catalog]

# Dependency graph
requires:
  - phase: 19-skill-standards-compliance
    provides: skill_definitions table with 022 migration (name, description, category, source_url, etc.)

provides:
  - usage_count INTEGER NOT NULL DEFAULT 0 column on skill_definitions table (ORM + migration 023)
  - tsvector GIN index ix_skill_definitions_fts on skill_definitions for FTS queries
  - Alembic migration 023 (down_revision=022) ready to apply via docker exec

affects:
  - 20-02 (FTS query endpoints will use ix_skill_definitions_fts)
  - 20-03 (catalog UI sort-by-usage will read usage_count)
  - 20-04 (skill invocation logic will increment usage_count)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - GIN index on tsvector expression via op.execute() raw SQL (not op.create_index) for tsvector index type
    - 'simple' language config for tsvector — no stop-word stripping, required for Vietnamese support

key-files:
  created:
    - backend/alembic/versions/023_skill_catalog_fts.py
  modified:
    - backend/core/models/skill_definition.py

key-decisions:
  - "Non-CONCURRENTLY GIN index — dev DB is small, avoids autocommit isolation_level complexity"
  - "'simple' tsvector config chosen over 'english' — required for Vietnamese text support (SKCAT-02)"
  - "No tsvector ORM column — GIN index managed purely in SQL, invisible to SQLAlchemy model layer"

patterns-established:
  - "Pattern: Raw SQL GIN index creation uses op.execute() in Alembic, not op.create_index()"
  - "Pattern: server_default=text('0') for integer counters with NOT NULL constraint"

requirements-completed: [SKCAT-01, SKCAT-02]

# Metrics
duration: 8min
completed: 2026-03-07
---

# Phase 20 Plan 01: Skill Catalog FTS Schema Migration Summary

**Alembic migration 023 adds usage_count column and tsvector GIN index ix_skill_definitions_fts to skill_definitions using 'simple' language config for Vietnamese FTS support**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-07T00:00:00Z
- **Completed:** 2026-03-07T00:08:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `usage_count` INTEGER NOT NULL DEFAULT 0 to SkillDefinition ORM model (after source_url, before security_score)
- Created Alembic migration 023 with correct chain: down_revision="022", revision="023"
- GIN index `ix_skill_definitions_fts` on `to_tsvector('simple', coalesce(name,'') || ' ' || coalesce(description,''))` ready to apply
- Full test suite maintained at 794 passing, 1 skipped — no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add usage_count to SkillDefinition ORM model** - `731d2a5` (feat)
2. **Task 2: Create Alembic migration 023 — usage_count + FTS GIN index** - `d387e46` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `backend/core/models/skill_definition.py` - Added usage_count: Mapped[int] with server_default=text("0")
- `backend/alembic/versions/023_skill_catalog_fts.py` - Migration 023: usage_count column + GIN FTS index

## Decisions Made

- Non-CONCURRENTLY index creation chosen over CONCURRENTLY — avoids autocommit isolation_level complexity; dev DB is small and this runs once at migration time
- `'simple'` tsvector language config (not `'english'`) — no stop-word stripping, required for Vietnamese text support per SKCAT-02
- No tsvector column in ORM — the GIN index is a functional index on an expression, invisible to SQLAlchemy; ORM model stays clean
- Migration applied separately via docker exec (not `just migrate` from host) — consistent with Phase 19 pattern

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

The migration 023 must be applied to the running PostgreSQL container:

```bash
# Copy migration file into running container (if not volume-mounted)
docker cp backend/alembic/versions/023_skill_catalog_fts.py blitz-backend:/app/alembic/versions/

# Apply migration inside container
docker exec blitz-backend .venv/bin/alembic upgrade head
```

Or via `just migrate` if the backend service has the file mounted.

## Next Phase Readiness

- DB schema prerequisites for skill catalog FTS are complete
- Plan 20-02 (FTS query endpoints) can proceed — ix_skill_definitions_fts is ready
- Plan 20-03 (catalog UI) can proceed — usage_count column is available for sort-by-usage
- Migration 023 is the new head; plan 20-02 migration (if any) will use down_revision="023"

---
*Phase: 20-skill-platform-b-discovery-catalog*
*Completed: 2026-03-07*

## Self-Check: PASSED

- FOUND: backend/core/models/skill_definition.py
- FOUND: backend/alembic/versions/023_skill_catalog_fts.py
- FOUND: .planning/phases/20-skill-platform-b-discovery-catalog/20-01-SUMMARY.md
- FOUND: commit 731d2a5 (Task 1)
- FOUND: commit d387e46 (Task 2)
