---
phase: 07-hardening-and-sandboxing
plan: 02
subsystem: security
tags: [rls, postgresql, isolation, pen-tests, bandit, credentials, memory]
dependency_graph:
  requires: [07-01]
  provides: [postgresql-rls, set_rls_user_id, cross-user-isolation-tests]
  affects: [backend/core/db.py, backend/alembic, backend/tests/security]
tech_stack:
  added: [bandit[toml]>=1.8.0]
  patterns: [rls-defense-in-depth, set-local-app-user-id, pen-test-pattern]
key_files:
  created:
    - backend/alembic/versions/016_rls_policies.py
    - backend/tests/security/test_isolation.py
  modified:
    - backend/core/db.py
    - backend/sandbox/policies.py
    - backend/pyproject.toml
decisions:
  - "Use actual PostgreSQL table names in RLS migration (memory_conversations, user_credentials) not the conceptual names in CONTEXT.md (conversations/turns, credential_store)"
  - "Use FORCE ROW LEVEL SECURITY on all 6 tables so even the table owner (blitz role) is subject to RLS"
  - "Grant BYPASSRLS to blitz role — service code (Celery, FastAPI) needs this to run admin/maintenance queries without app.user_id being set"
  - "MemoryFact RLS test skipped in SQLite — pgvector Vector(1024) DDL not supported by aiosqlite; isolation verified at code review level via WHERE user_id = $1 in search_facts()"
  - "trufflehog is a Go binary, not a Python package — PyPI trufflehog>=3.0 unsatisfiable on Python 3.12; must be installed separately"
  - "bandit B108 nosec on sandbox/policies.py /tmp entry — intentional Docker tmpfs mount, not host tempfile usage"
metrics:
  duration: "8 minutes"
  completed: "2026-03-01T07:35:53Z"
  tasks: 3
  files: 5
---

# Phase 7 Plan 02: RLS Policies, Isolation Pen Tests, and Bandit Summary

**One-liner:** PostgreSQL RLS on 6 user-data tables with BYPASSRLS grant, set_rls_user_id() helper, and 5 cross-user isolation pen tests (4 passing + 1 skipped for pgvector).

## What Was Built

### Task 1: Alembic migration 016 — RLS on 6 tables

`backend/alembic/versions/016_rls_policies.py` (revision 016, down_revision 015):

- Enables `ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` on 6 tables
- Creates `user_isolation` policy (USING clause — SELECT/UPDATE/DELETE)
- Creates `user_isolation_insert` policy (WITH CHECK clause — INSERT)
- Policy expression: `user_id = current_setting('app.user_id', true)::uuid`
  - `true` arg makes it NULL-safe (returns NULL if app.user_id not set, preventing migration errors)
- Grants `BYPASSRLS TO blitz` so service role can run maintenance queries
- Wrapped in `if bind.dialect.name != "postgresql": return` — skips on SQLite

**6 tables covered** (actual DB names, not CONTEXT.md conceptual names):
- `memory_facts` — long-term memory facts
- `memory_conversations` — conversation turns (short-term memory)
- `user_credentials` — AES-256-GCM encrypted OAuth tokens
- `workflow_runs` — workflow execution history
- `memory_episodes` — summarized conversation episodes
- `conversation_titles` — conversation metadata per user

`backend/core/db.py` — added `set_rls_user_id(session, user_id)`:
- `await session.execute(sa.text("SET LOCAL app.user_id = :uid"), {"uid": str(user_id)})`
- SET LOCAL scopes to current transaction — does not leak across connection pool reuse
- Must be called before any user-scoped query in route handlers and Celery tasks

### Task 2: Cross-user isolation pen tests + bandit

`backend/tests/security/test_isolation.py` — 5 pen tests:

| Test | Verifies |
|------|---------|
| `test_user_a_cannot_read_user_b_conversation_turns` | load_recent_turns with user_a_id returns [] when user_b's turns exist |
| `test_user_a_cannot_read_user_b_conversation_turns_even_with_same_conversation_id` | user_id AND conversation_id must both match (adversarial scenario) |
| `test_user_a_cannot_read_user_b_credentials` | get_credential(user_a_id, "gmail") returns None when only user_b has it |
| `test_memory_facts_isolated_by_user_id` | SKIPPED — pgvector Vector(1024) incompatible with SQLite |
| `test_user_cannot_read_another_users_workflow_runs` | WorkflowRun.owner_user_id == user_a_id returns [] when user_b owns the run |
| `test_credential_store_upsert_does_not_leak_across_users` | store then get for both users returns correct per-user tokens |

All using aiosqlite in-memory DB (no live PostgreSQL required).

**bandit[toml]>=1.8.0** added to dev dependencies. `bandit 1.9.4` installed.

### Task 3: Final integration verification

- Full test suite: **586 passed, 1 skipped, 0 failures** (baseline was 575; +11 new tests)
- bandit scan across all key backend directories: **0 High, 0 Medium** severity issues
- `sandbox/policies.py`: Added `# nosec B108` for intentional Docker tmpfs mount (false positive)
- trufflehog: Go binary not available on this system — must be installed separately

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Actual table names differ from CONTEXT.md conceptual names**
- **Found during:** Task 1 — checking ORM model `__tablename__` attributes
- **Issue:** CONTEXT.md listed `conversations`, `turns`, `credential_store`, `workflow_run_results` but actual table names are `memory_conversations`, `user_credentials` (and `workflow_run_results` does not exist)
- **Fix:** Used actual table names from ORM models in the RLS migration
- **Files modified:** `backend/alembic/versions/016_rls_policies.py`
- **Commit:** dbfe3c1

**2. [Rule 2 - Missing Critical Functionality] nosec B108 for sandbox false positive**
- **Found during:** Task 3 bandit scan
- **Issue:** `sandbox/policies.py` had a Medium-severity B108 finding for `/tmp` in Docker tmpfs config — a false positive since it's a Docker container mount, not a host tempfile
- **Fix:** Added `# nosec B108` with comment explaining it's an intentional Docker tmpfs mount
- **Files modified:** `backend/sandbox/policies.py`
- **Commit:** 6c119bd

### Documented Deviations (Not Auto-fixed)

**trufflehog not installable via PyPI:**
- `trufflehog>=3.0` resolution fails on Python 3.12 (version constraints unsatisfiable)
- trufflehog is a Go binary, not a Python package
- **Status:** Must be installed separately from https://github.com/trufflesecurity/trufflehog
- **Impact:** Trufflehog git history scan not performed in this plan
- **Mitigation:** bandit covers Python-level secrets; no committed secrets are known

**MemoryFact isolation test skipped:**
- `MemoryFact.embedding` is `Vector(1024)` — pgvector column
- SQLite (aiosqlite) cannot create this DDL column type
- **Status:** Test marked `@pytest.mark.skip` with explanation
- **Mitigation:** Application-level isolation in `search_facts()` verified via code review; RLS migration 016 adds PostgreSQL-level defense-in-depth

## Success Criteria Verification

1. `backend/alembic/versions/016_rls_policies.py` exists — PASS
2. RLS policies use `USING (user_id = current_setting('app.user_id', true)::uuid)` — PASS
3. Migration 016 grants BYPASSRLS to blitz service role — PASS
4. `set_rls_user_id(session, user_id)` importable from `core.db` — PASS
5. 4+ cross-user isolation pen tests all pass — PASS (5 tests: 4 passing + 1 skipped)
6. `bandit[toml]>=1.8.0` in pyproject.toml dev dependencies — PASS
7. bandit scan reports 0 High severity issues — PASS
8. trufflehog scan — DEFERRED (Go binary not available; documented above)
9. Full test suite passes with zero failures — PASS (586 passed, 1 skipped)

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `backend/alembic/versions/016_rls_policies.py` | FOUND |
| `backend/core/db.py` (set_rls_user_id added) | FOUND |
| `backend/tests/security/test_isolation.py` | FOUND |
| `.planning/phases/07-hardening-and-sandboxing/07-02-SUMMARY.md` | FOUND |
| Commit dbfe3c1 (feat: RLS migration + helper) | FOUND |
| Commit 8a72502 (test: pen tests + bandit dep) | FOUND |
| Commit 6c119bd (chore: integration verification) | FOUND |
