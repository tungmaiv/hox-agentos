---
phase: 16-navigation-user-experience
plan: "01"
subsystem: backend-preferences
tags: [user-preferences, api, sqlalchemy, alembic, fastapi, tdd]
dependency_graph:
  requires: []
  provides: [user-preferences-api, user-preferences-model, migration-020]
  affects: [16-03-profile-page]
tech_stack:
  added: []
  patterns: [jsonb-sqlite-variant, upsert-partial-update, tdd-red-green]
key_files:
  created:
    - backend/core/models/user_preferences.py
    - backend/alembic/versions/020_add_user_preferences.py
    - backend/api/routes/user_preferences.py
    - backend/tests/api/test_user_preferences.py
  modified:
    - backend/core/models/__init__.py
    - backend/main.py
key_decisions:
  - "JSONB column uses JSON().with_variant(JSONB(), 'postgresql') for SQLite test compat"
  - "No FK on user_id — users live in Keycloak, not PostgreSQL"
  - "Partial update via None-check on each field — omitted fields retain current values or defaults"
  - "get_user_preference_values() helper exported for agent prompt injection in Plan 03"
  - "Router prefix /users/me/preferences (plural, RESTful) distinct from /user/instructions (legacy)"
metrics:
  duration_seconds: 162
  completed_date: "2026-03-05"
  tasks_completed: 2
  files_created: 4
  files_modified: 2
  tests_added: 7
  test_suite_before: 718
  test_suite_after: 725
---

# Phase 16 Plan 01: User Preferences Backend Summary

**One-liner:** User preferences REST API (GET/PUT /api/users/me/preferences) with JSONB model and Alembic migration 020 for thinking_mode and response_style settings.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create UserPreferences model and migration | 3e4b732 | user_preferences.py, __init__.py, 020_add_user_preferences.py |
| 2 | Create preference API endpoints and tests | 534e712 | api/routes/user_preferences.py, main.py, tests/api/test_user_preferences.py |

## What Was Built

### UserPreferences ORM Model (`backend/core/models/user_preferences.py`)
- `id`: UUID primary key with default uuid4
- `user_id`: UUID, unique=True, index=True, no FK (Keycloak users)
- `preferences`: JSONB with SQLite variant (`JSON().with_variant(JSONB(), 'postgresql')`)
- `created_at`, `updated_at`: DateTime with server_default and onupdate
- Default preferences: `{"thinking_mode": False, "response_style": "concise"}`

### Alembic Migration 020 (`backend/alembic/versions/020_add_user_preferences.py`)
- Creates `user_preferences` table
- `down_revision = "019"` — linear chain, single head confirmed
- Manual migration (not autogenerate) to ensure clean JSONB/SQLite variant handling

### Preference API (`backend/api/routes/user_preferences.py`)
- `GET /api/users/me/preferences` — returns stored preferences or defaults
- `PUT /api/users/me/preferences` — upsert with partial update (only fields provided are updated)
- `UserPreferencesResponse`: validated Pydantic model with `thinking_mode: bool` and `response_style: Literal[...]`
- `UserPreferencesUpdate`: partial update schema (both fields optional)
- `get_user_preference_values(user_id, session)` — internal helper for Plan 03 agent prompt injection
- Registered in `main.py` under `/api` prefix

### Tests (`backend/tests/api/test_user_preferences.py`)
7 tests covering all behaviors:
- `test_get_preferences_requires_jwt` — 401 without auth
- `test_get_preferences_default` — returns defaults when no row exists
- `test_get_preferences_returns_stored` — returns stored values after PUT
- `test_put_preferences_creates_row` — upsert creates new row
- `test_put_preferences_updates_existing` — upsert updates existing row
- `test_put_preferences_partial_update` — only sent fields change; others preserved
- `test_put_invalid_response_style` — 422 for invalid enum value

## Verification Results

- `alembic heads`: single head at `020`
- `pytest tests/api/test_user_preferences.py -v`: 7 passed
- `pytest tests/ -q`: 725 passed, 1 skipped (up from 718 — 7 new tests, no regressions)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Files created:
- FOUND: backend/core/models/user_preferences.py
- FOUND: backend/alembic/versions/020_add_user_preferences.py
- FOUND: backend/api/routes/user_preferences.py
- FOUND: backend/tests/api/test_user_preferences.py

Commits:
- FOUND: 3e4b732 (feat(16-01): add UserPreferences model and migration 020)
- FOUND: 534e712 (feat(16-01): add user preferences API endpoints and tests)
