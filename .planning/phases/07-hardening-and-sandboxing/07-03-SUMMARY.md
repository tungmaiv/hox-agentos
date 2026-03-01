---
phase: 07-hardening-and-sandboxing
plan: 03
subsystem: security-tests
tags: [isolation, pen-tests, orm-models, fix]
dependency_graph:
  requires:
    - 07-02 (RLS migration, isolation pen test suite)
  provides:
    - Deterministic isolation pen tests — no implicit test-collection side effects
  affects:
    - backend/tests/security/test_isolation.py
tech_stack:
  added: []
  patterns:
    - "import core.models at test module top-level ensures Base.metadata fully populated before db_session fixture"
key_files:
  modified:
    - backend/tests/security/test_isolation.py
decisions:
  - "[07-03]: import core.models at module top-level in test_isolation.py — ConversationTurn (memory_conversations table) not registered in Base.metadata when test file loaded in isolation; lazy import inside test body executes after db_session.create_all(), causing 'no such table' error"
metrics:
  duration: 62s
  completed: 2026-03-01
  tasks_completed: 1
  files_modified: 1
---

# Phase 7 Plan 03: Fix Lazy Import Defect in test_isolation.py Summary

One-liner: Added `import core.models` at module top-level so all ORM models register in Base.metadata before the db_session fixture calls create_all(), making isolation pen tests deterministic regardless of run order.

## What Changed

A single import line was added to `backend/tests/security/test_isolation.py` (line 29, after `from core.db import Base`):

```python
import core.models  # noqa: F401 — registers all ORM models in Base.metadata before db_session fixture
```

### Root Cause

The `db_session` pytest-asyncio fixture creates an in-memory SQLite engine and calls `Base.metadata.create_all()` before any test body runs. When `test_isolation.py` was run in isolation (not as part of the full suite), `ConversationTurn` (which registers the `memory_conversations` table) had not yet been imported — the imports were lazy, inside the test function bodies:

```python
# These lazy imports inside test bodies execute AFTER create_all():
from memory.short_term import save_turn, load_recent_turns
```

When the full suite ran, other test files imported `ConversationTurn` first (via collection side effects), so `create_all()` found the table registered. Running `test_isolation.py` in isolation caused `create_all()` to silently omit the `memory_conversations` table, causing a "no such table: memory_conversations" error.

### Fix

`core/models/__init__.py` imports all ORM models including `ConversationTurn`, `UserCredential`, `Workflow`, `WorkflowRun`, and all others. Importing it at module top-level ensures `Base.metadata` is fully populated before any fixture executes — identical to how Alembic's `env.py` ensures models are registered before autogenerate runs.

## Verification Output

### Standalone (isolated) run — the critical test:

```
$ cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/security/test_isolation.py -v --tb=short

============================= test session starts ==============================
platform linux -- Python 3.12.12, pytest-8.3.0, pluggy-1.6.0
asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=function
collected 6 items

tests/security/test_isolation.py::test_user_a_cannot_read_user_b_conversation_turns PASSED [ 16%]
tests/security/test_isolation.py::test_user_a_cannot_read_user_b_conversation_turns_even_with_same_conversation_id PASSED [ 33%]
tests/security/test_isolation.py::test_user_a_cannot_read_user_b_credentials PASSED [ 50%]
tests/security/test_isolation.py::test_memory_facts_isolated_by_user_id SKIPPED [ 66%]
tests/security/test_isolation.py::test_user_cannot_read_another_users_workflow_runs PASSED [ 83%]
tests/security/test_isolation.py::test_credential_store_upsert_does_not_leak_across_users PASSED [100%]

========================= 5 passed, 1 skipped in 2.15s =========================
```

4 passed + 1 skipped (pgvector skip is intentional — MemoryFact.embedding uses Vector(1024), not supported in SQLite).

### Full suite — regression check:

```
586 passed, 1 skipped, 16 warnings in 7.46s
```

Same count as before — no regressions.

## Commit

- `97957bf` — fix(07-03): add import core.models to test_isolation.py

## Deviations from Plan

None — plan executed exactly as written. The fix was a single import line addition as specified.

## Self-Check: PASSED

- File modified: `backend/tests/security/test_isolation.py` — FOUND
- `grep "import core.models" backend/tests/security/test_isolation.py` — MATCH
- Commit `97957bf` — FOUND
- Isolation tests standalone: 5 passed, 1 skipped — PASSED
- Full suite: 586 passed, 1 skipped — NO REGRESSIONS
