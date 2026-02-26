---
phase: 02.1-tech-debt-cleanup
plan: "01"
subsystem: frontend-routes, backend-models, planning-docs
tags: [tech-debt, env-var, migration, documentation]
dependency_graph:
  requires: [Phase 2 complete]
  provides: [consistent env var usage, updated_at trigger, accurate planning docs]
  affects: [frontend/src/app/api/**, backend/core/models/user_instructions.py, alembic/versions/006]
tech_stack:
  added: []
  patterns: [NEXT_PUBLIC_API_URL for all server-side backend URL references, PostgreSQL BEFORE UPDATE trigger for timestamp management]
key_files:
  created:
    - backend/alembic/versions/006_fix_user_instructions_updated_at.py
  modified:
    - frontend/src/app/api/conversations/route.ts
    - frontend/src/app/api/conversations/[id]/route.ts
    - frontend/src/app/api/conversations/[id]/messages/route.ts
    - frontend/src/app/api/conversations/[id]/title/route.ts
    - frontend/src/app/api/copilotkit/route.ts
    - frontend/src/app/api/copilotkit/[...path]/route.ts
    - backend/core/models/user_instructions.py
decisions:
  - "Use revision 006 (not 005) for updated_at trigger migration — 005 was already taken by conversation_titles migration"
  - "Rename BACKEND_URL constant to API_URL in copilotkit routes for clarity while switching to NEXT_PUBLIC_API_URL"
  - "REQUIREMENTS.md and ROADMAP.md were already accurate — no file changes needed for Task 3"
metrics:
  duration: "97 seconds"
  completed: "2026-02-26T08:33:03Z"
  tasks_completed: 3
  files_changed: 8
---

# Phase 2.1 Plan 01: Tech Debt Cleanup Summary

**One-liner:** Closed all v1.0 tech debt: unified 6 frontend server routes to NEXT_PUBLIC_API_URL, added PostgreSQL BEFORE UPDATE trigger for user_instructions.updated_at, confirmed planning docs already accurate.

## Tasks Completed

### Task 1: Standardize backend URL env var (6 routes)

Changed `process.env.BACKEND_URL` to `process.env.NEXT_PUBLIC_API_URL` in all 6 affected routes:

- `frontend/src/app/api/conversations/route.ts` — inline `apiUrl` variable
- `frontend/src/app/api/conversations/[id]/route.ts` — module-level `API_URL` constant
- `frontend/src/app/api/conversations/[id]/messages/route.ts` — inline `apiUrl` variable
- `frontend/src/app/api/conversations/[id]/title/route.ts` — module-level `API_URL` constant
- `frontend/src/app/api/copilotkit/route.ts` — renamed `BACKEND_URL` -> `API_URL`, switched env var
- `frontend/src/app/api/copilotkit/[...path]/route.ts` — same rename and env var switch

All 6 routes now consistent with the pattern already used in `user/instructions/route.ts`. Zero `process.env.BACKEND_URL` references remain in `frontend/src/app/api/`.

**Commit:** a3449d8

### Task 2: Fix user_instructions.updated_at

Two changes:

**A. ORM model** (`backend/core/models/user_instructions.py`): Added `onupdate=func.now()` to the `updated_at` column so SQLAlchemy triggers an UPDATE SET on every row update.

**B. Migration 006** (`backend/alembic/versions/006_fix_user_instructions_updated_at.py`): Created PostgreSQL BEFORE UPDATE trigger `user_instructions_set_updated_at` that calls `set_updated_at()` trigger function. The trigger function sets `NEW.updated_at = now()`.

**IMPORTANT:** Migration 006 must be applied before the fix takes effect in production. Run:
```bash
just migrate
# or if justfile unavailable:
docker exec -it <postgres_container> psql -U blitz -d blitz
```

Note: Migration was numbered 006 (not 005) because `005_conversation_titles.py` already exists in the chain.

**Commit:** 72fd1f8

### Task 3: Verify REQUIREMENTS.md and ROADMAP.md checkboxes

Inspected both files. Both were already accurate — no changes required:

- REQUIREMENTS.md: All 12 completed requirements (AUTH-01 to AUTH-06, AGNT-01, AGNT-02, AGNT-07, MEMO-01, MEMO-05, INTG-04) already show `[x]`
- ROADMAP.md: `01-04-PLAN.md` already shows `[x]`; all Phase 2 plans (02-01 through 02-05) already show `[x]`

No commit needed for Task 3.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Discovery] Migration numbered 006 instead of 005**
- **Found during:** Task 2
- **Issue:** Plan specified `005_fix_user_instructions_updated_at.py` but `005_conversation_titles.py` already exists in the migration chain
- **Fix:** Created `006_fix_user_instructions_updated_at.py` with `revision = "006"` and `down_revision = "005"`
- **Files modified:** `backend/alembic/versions/006_fix_user_instructions_updated_at.py`
- **Commit:** 72fd1f8

**2. [Rule 1 - Discovery] Task 3 docs already accurate**
- **Found during:** Task 3
- **Issue:** Plan expected stale checkboxes in REQUIREMENTS.md and ROADMAP.md, but both files were already updated correctly (likely updated during the v1.0 audit phase)
- **Fix:** Verified accuracy via grep checks — no changes needed
- **Impact:** Zero diff for Task 3; all verification checks still pass

## Verification Results

| Check | Command | Result |
|-------|---------|--------|
| No BACKEND_URL in routes | `grep -rn "process.env.BACKEND_URL" .../app/api/ \| wc -l` | 0 |
| onupdate in ORM model | `grep -n "onupdate" user_instructions.py` | line 38: onupdate=func.now() |
| Migration 006 exists | `ls backend/alembic/versions/006_*.py` | file exists |
| 12 checked requirements | `grep -c "\[x\]" REQUIREMENTS.md` | 12 |
| 01-04-PLAN.md checked | `grep "\[x\].*01-04" ROADMAP.md` | matches |

## Self-Check: PASSED

All created/modified files verified present:
- `frontend/src/app/api/conversations/route.ts` — FOUND
- `frontend/src/app/api/conversations/[id]/route.ts` — FOUND
- `frontend/src/app/api/conversations/[id]/messages/route.ts` — FOUND
- `frontend/src/app/api/conversations/[id]/title/route.ts` — FOUND
- `frontend/src/app/api/copilotkit/route.ts` — FOUND
- `frontend/src/app/api/copilotkit/[...path]/route.ts` — FOUND
- `backend/core/models/user_instructions.py` — FOUND
- `backend/alembic/versions/006_fix_user_instructions_updated_at.py` — FOUND

Commits: a3449d8, 72fd1f8 — both verified in git log.
