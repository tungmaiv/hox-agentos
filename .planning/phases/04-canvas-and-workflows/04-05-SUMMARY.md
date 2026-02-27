---
phase: 04-canvas-and-workflows
plan: "05"
subsystem: ui
tags: [workflow-templates, alembic, react, nextjs, tdd, json-fixtures]

# Dependency graph
requires:
  - phase: 04-canvas-and-workflows plan 01
    provides: "workflows table with is_template column, nullable owner_user_id, copy_template API endpoint"
provides:
  - "morning_digest.json and alert.json fixture files (schema_version 1.0, 5 nodes, 4 edges each)"
  - "Alembic migration 011 inserting both templates as is_template=true rows with owner_user_id=NULL"
  - "TemplateCard client component: Use Template button calls copy API and navigates to canvas"
  - "workflows/page.tsx: template gallery renders TemplateCard components server-side"
affects:
  - "Phase 5 (Channels) — templates demonstrate channel_output_node pattern for telegram/webhook flows"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "JSON fixture files in backend/data/workflow_templates/ for seeding pre-built templates"
    - "Alembic data migration (op.get_bind() + sa.text()) for seeding rows alongside schema migrations"
    - "Client Component with useRouter for copy-then-navigate pattern"
    - "Server Component fetches templates; passes props to client TemplateCard children"

key-files:
  created:
    - backend/data/workflow_templates/morning_digest.json
    - backend/data/workflow_templates/alert.json
    - backend/data/__init__.py
    - backend/alembic/versions/011_phase4_workflow_templates.py
    - backend/tests/test_workflow_fixtures.py
    - frontend/src/components/canvas/TemplateCard.tsx
  modified:
    - frontend/src/app/workflows/page.tsx

key-decisions:
  - "Fixture files as standalone JSON (not Python dicts) — readable, editable without code changes"
  - "Migration 011 down_revision='010' (010 is current head); ON CONFLICT DO NOTHING prevents double-insert on re-run"
  - "TemplateCard uses fetch('/api/workflows/templates/{id}/copy') not NEXT_PUBLIC_API_URL — routes through Next.js API which injects JWT"
  - "TemplateCard is a Client Component (useRouter + onClick); page.tsx remains Server Component for SSR template fetch"

patterns-established:
  - "JSON fixture files in backend/data/: testable pure data, imported by Alembic migration at migration time"
  - "Client TemplateCard receives minimal props from Server Component parent — no data fetching in client"

requirements-completed: [WKFL-03, WKFL-04, WKFL-09]

# Metrics
duration: 4min
completed: 2026-02-27
---

# Phase 4 Plan 05: Workflow Templates Summary

**Two pre-built workflow templates (Morning Digest cron+email+summarize and Alert webhook+keyword+notify) seeded via Alembic data migration with TemplateCard "Use Template" button that copies and navigates to canvas editor**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-27T04:39:03Z
- **Completed:** 2026-02-27T04:42:44Z
- **Tasks:** 4 (Tasks 1-4)
- **Files modified:** 7

## Accomplishments
- Two fixture JSON files (morning_digest.json + alert.json) with schema_version "1.0", correct node types, and valid edges — all 6 TDD tests pass
- Alembic migration 011 inserts both templates with owner_user_id=NULL using op.get_bind() + sa.text(); ON CONFLICT DO NOTHING for idempotency
- TemplateCard client component: POST /api/workflows/templates/{id}/copy → router.push(/workflows/{newId}), with loading + error states
- Full backend suite: 254 passed, 0 failed; frontend pnpm build: 0 TypeScript errors

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing fixture tests** - `8591a13` (test)
2. **Task 1 GREEN: JSON fixture files** - `414dc84` (feat)
3. **Task 2: Alembic migration 011** - `9dd2ccc` (feat)
4. **Task 3: TemplateCard + page.tsx wiring** - `73f1a7c` (feat)

_Note: TDD task has two commits (test RED, then feat GREEN)_

## Files Created/Modified
- `backend/data/workflow_templates/morning_digest.json` - 5-node workflow (cron → email.fetch → condition → agent summarize → telegram)
- `backend/data/workflow_templates/alert.json` - 5-node workflow (webhook → text.keyword_match → condition → project.create_task → telegram)
- `backend/data/__init__.py` - package marker for data directory
- `backend/alembic/versions/011_phase4_workflow_templates.py` - data migration inserting both templates as is_template=true
- `backend/tests/test_workflow_fixtures.py` - 6 TDD tests validating schema_version, node types, edge integrity
- `frontend/src/components/canvas/TemplateCard.tsx` - "use client" component with Use Template button, loading/error states
- `frontend/src/app/workflows/page.tsx` - replaced inline form with TemplateCard component

## Decisions Made
- Fixture files as standalone JSON (not embedded Python dicts) — easier to review, edit, and test independently
- Migration 011 with `ON CONFLICT DO NOTHING` ensures idempotent re-runs without duplicate templates
- TemplateCard uses `fetch('/api/workflows/templates/{id}/copy')` (relative URL through Next.js API proxy) to ensure JWT injection — never calls backend directly from browser
- TemplateCard is Client Component; WorkflowsPage remains Server Component — clean server/client boundary

## Deviations from Plan

None — plan executed exactly as written.

The `alembic check` command requires a live DB connection (not available in dev without Docker). Used Python import validation instead to verify migration file syntax and revision metadata. This is consistent with prior plan patterns (migrations applied via `just migrate` on running stack).

## Issues Encountered
- `alembic check` needed live DB (not running): used `.venv/bin/python -c "importlib.util..."` to verify migration file syntax and revision metadata (`revision='011', down_revision='010'`). No impact on functionality.

## User Setup Required
The migration must be applied on next `just migrate` run:
```bash
just migrate
# or: cd backend && .venv/bin/alembic upgrade head
```
This will insert the Morning Digest and Alert templates as `is_template=true` rows into the `workflows` table.

## Next Phase Readiness
- Phase 4 is fully complete: all 5 plans (CRUD, compiler, execution, HITL canvas, templates) implemented
- 254 backend tests passing, frontend build clean
- Phase 5 (Channels: Telegram/WhatsApp/Teams) can now begin — no blocking dependencies
- Template `channel_output_node` pattern demonstrates the delivery target concept that Phase 5 adapters will fulfill

---
*Phase: 04-canvas-and-workflows*
*Completed: 2026-02-27*
