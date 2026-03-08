---
phase: 21-skill-platform-c-dependency-security-hardening
plan: "03"
subsystem: scheduler / skill-platform
tags: [skill-platform, security, celery, migration, tdd, sksec-03]
dependency_graph:
  requires: [21-01, 21-02, 19-xx, 20-xx]
  provides: [SKSEC-03, source_hash column, daily upstream change detection]
  affects: [backend/core/models/skill_definition.py, backend/scheduler/celery_app.py]
tech_stack:
  added: [httpx async fetch, hashlib SHA-256, celery crontab schedule]
  patterns: [asyncio.run() in Celery task, pending_review version row pattern, null-baseline first-run guard]
key_files:
  created:
    - backend/alembic/versions/024_skill_source_hash.py
    - backend/scheduler/tasks/check_skill_updates.py
    - backend/tests/scheduler/test_check_skill_updates.py
  modified:
    - backend/core/models/skill_definition.py
    - backend/scheduler/celery_app.py
decisions:
  - "[21-03]: null baseline guard — source_hash=None stores hash without pending_review row, avoids spurious first-run review flood"
  - "[21-03]: _bump_version handles both semver (1.0.0 -> 1.0.1) and non-semver (invalid -> invalid.1) gracefully"
  - "[21-03]: _check_single_skill uses separate async_session() contexts for read and write — avoids holding sessions across slow HTTP fetches"
metrics:
  duration: "~15 minutes"
  completed: "2026-03-08"
  tasks_completed: 2
  files_created: 3
  files_modified: 2
---

# Phase 21 Plan 03: Skill Source Hash and Daily Update Checker Summary

**One-liner:** Migration 024 adds `source_hash TEXT` to skill_definitions; daily Celery task compares SHA-256 hashes to detect upstream changes and creates `pending_review` version rows for admin review.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add source_hash column — ORM model and migration 024 | 06fd4c7 | skill_definition.py, 024_skill_source_hash.py |
| 2 | Implement check_skill_updates Celery task (TDD) | a44355d | check_skill_updates.py, celery_app.py, test_check_skill_updates.py |

## What Was Built

### Migration 024 (`024_skill_source_hash.py`)
- Adds `source_hash TEXT NULL` column to `skill_definitions` table
- Revision chain: 024 → down_revision=023 (confirmed via `alembic heads`)
- Downgrade: `op.drop_column("skill_definitions", "source_hash")`

### ORM Model (`skill_definition.py`)
- Added `source_hash: Mapped[str | None] = mapped_column(Text, nullable=True)` after `source_url`
- Plain `Text` column — no JSONB variant needed (plain string)

### Daily Celery Task (`check_skill_updates.py`)
Implements SKSEC-03 — daily upstream change detection for imported skills:

1. **Query**: Fetches only skills with `source_type='imported'`, non-null `source_url`, `status='active'`
2. **Fetch**: HTTP GET via `httpx.AsyncClient(timeout=30.0)` with `raise_for_status()`
3. **Hash comparison**:
   - `source_hash=None` (first run): stores hash via UPDATE, no new row created
   - Hash unchanged: no-op
   - Hash changed: creates new `SkillDefinition` row with `status='pending_review'` and patch-bumped version
4. **Error handling**: Fetch failures log warning and continue — task never propagates individual skill errors
5. **Beat schedule**: `crontab(hour=2, minute=0)` — 2:00 AM UTC daily

### Updated `celery_app.py`
- Added `"scheduler.tasks.check_skill_updates"` to `include` list
- Added task route to `task_routes` dict
- Added `"check-skill-updates-daily"` entry to `beat_schedule` with `crontab(hour=2, minute=0)`
- Added `from celery.schedules import crontab` import

## Test Coverage

7 unit tests — all passing (816 total in suite, no regressions):

| Test | Covers |
|------|--------|
| `test_bump_version_patch_standard` | 1.0.0→1.0.1, 2.3.9→2.3.10 |
| `test_bump_version_non_semver` | "invalid"→"invalid.1", "1.0"→"1.0.1" |
| `test_hash_unchanged_no_new_row` | Matching hash → session.add not called |
| `test_hash_changed_creates_pending_review` | Different hash → session.add with status=pending_review, version=1.0.1 |
| `test_null_hash_stores_without_creating_review` | None baseline → session.execute UPDATE, session.add NOT called |
| `test_fetch_failure_logs_warning_and_continues` | httpx.ConnectError → no exception propagated |
| `test_builtin_skill_skipped` | DB query returns empty (builtin filtered) → _check_single_skill not called |

## Decisions Made

1. **Null baseline guard**: First-run behavior stores the hash baseline without triggering admin reviews. Without this, every imported skill would appear as "Update available" the first time the task runs after migration — flooding the admin queue.

2. **Separate session contexts**: `_check_single_skill` uses separate `async_session()` for read (outer caller) and write (per-skill). This avoids holding a DB session open during slow HTTP fetches.

3. **_bump_version graceful fallback**: Non-semver versions get `.1` appended (`"invalid" → "invalid.1"`) rather than raising. This ensures the task never fails due to unusual version strings.

4. **pending_review row pattern**: Consistent with the existing skill import flow — new versions of skills are flagged as `pending_review` for admin review before going live. The existing admin badge on the skill catalog automatically shows these.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- FOUND: backend/alembic/versions/024_skill_source_hash.py
- FOUND: backend/scheduler/tasks/check_skill_updates.py
- FOUND: backend/tests/scheduler/test_check_skill_updates.py
- FOUND commit 06fd4c7 (Task 1 — ORM + migration)
- FOUND commit a44355d (Task 2 — Celery task + tests)
