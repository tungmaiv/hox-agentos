---
phase: 28-storage-service
plan: "02"
subsystem: storage
tags:
  - storage
  - api-routes
  - fastapi
  - celery
  - minio
  - user-notifications
  - alembic
  - deduplication
  - memory-indexing
dependency_graph:
  requires:
    - 28-01 (MinIO infrastructure, StorageFile/Folder/Share ORM models, text extractor)
  provides:
    - /api/storage/* router with 14 endpoints (upload, list, share, folders, memory indexing)
    - UserNotification ORM model + alembic migration 033
    - embed_file_content Celery task (queue=embedding)
    - check_file_access helper (owner + file share + folder share propagation)
  affects:
    - backend/main.py (storage_router registered)
tech_stack:
  added: []
  patterns:
    - JSONResponse(status_code=200) to override route-default 201 for dedup responses
    - Module-level import of embed_file_content for test patching
    - _embed_file_content_body exposed as __wrapped__ for Celery retry testing
    - StaticPool + check_same_thread=False for cross-request SQLite visibility in tests
    - action=replace matches by filename when SHA-256 differs (file replacement semantics)
key_files:
  created:
    - backend/api/routes/storage.py
    - backend/core/models/user_notification.py
    - backend/alembic/versions/033_user_notifications.py
    - backend/scheduler/tasks/storage_embedding.py
  modified:
    - backend/main.py (storage_router registration)
    - backend/tests/api/test_storage_routes.py (StaticPool, TypedDict dict access, seed fix)
    - backend/tests/storage/test_share_service.py (module-level model imports for create_all)
decisions:
  - "[28-02]: JSONResponse(status_code=200) used for dedup response — route decorator default is 201 and cannot be overridden otherwise"
  - "[28-02]: embed_file_content imported at module level in storage.py — required for patch('api.routes.storage.embed_file_content') test patching"
  - "[28-02]: _embed_file_content_body exposed as embed_file_content.__wrapped__ — Celery's __wrapped__ is a bound method; tests need unbound function with self param"
  - "[28-02]: action=replace also matches by filename (not just SHA-256) — test replaces file with new content, old hash doesn't match"
  - "[28-02]: Storage model imports added at test module level — Base.metadata.create_all must see all models before schema creation"
metrics:
  duration: "21min"
  completed_date: "2026-03-16"
  tasks_completed: 2
  files_created: 4
  files_modified: 3
---

# Phase 28 Plan 02: Storage API Routes, User Notification Model, and Memory Embedding Task Summary

Full storage backend feature surface: JWT-gated /api/storage/* endpoints for file upload/dedup, folder CRUD, share management, memory indexing, user notifications, and an async Celery task for file-to-memory embedding.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | User notification model, migration 033, and storage API routes | 3baef56 | user_notification.py, 033_user_notifications.py, storage.py (routes), main.py, test_storage_routes.py |
| 2 | Celery task for file memory embedding and share/embedding integration tests | 96b3da6 | storage_embedding.py, test_share_service.py |

## What Was Built

### UserNotification ORM Model

`backend/core/models/user_notification.py`:
- `user_notifications` table with `user_id` (indexed, no FK — Keycloak architecture), `title`, `message`, `notification_type`, `is_read`, `metadata_json` (plain Text for SQLite compat), `created_at`
- Used by share endpoint to notify recipients when files/folders are shared with them

### Alembic Migration 033

`backend/alembic/versions/033_user_notifications.py`:
- `down_revision = "032_storage_tables"` — chained correctly from plan 01
- Creates `user_notifications` table with index on `user_id`

### Storage API Router (`/api/storage/*`)

14 endpoints covering the complete Phase 28 feature surface:

**File endpoints:**
- `POST /files/upload` — SHA-256 dedup (200 + duplicate info for same-user hash match); replace action matches by filename when hash differs; replace of `in_memory=True` file auto-dispatches `embed_file_content.delay`
- `GET /files` — paginated, JWT-scoped, optional `folder_id` filter
- `GET /files/{file_id}` — presigned download URL; ownership or share access required
- `DELETE /files/{file_id}` — owner only
- `POST /files/{file_id}/add-to-memory` — EXTRACTABLE_MIME_TYPES only; sets `in_memory=True`, dispatches Celery task

**Folder endpoints:**
- `POST /folders`, `GET /folders`, `DELETE /folders/{folder_id}`

**Share endpoints:**
- `POST /shares` — creates StorageShare + UserNotification for recipient; stub `_send_share_email()` logs (email infra Phase 33)
- `GET /shares/{file_id}` — owner only
- `PATCH /shares/{share_id}` — permission update, owner only
- `DELETE /shares/{share_id}` — 403 for non-owner
- `GET /shared-with-me`

**User search:**
- `GET /users/search?q=` — queries `local_users` (email/username ILIKE), limit 10

**Access control helper:**
```python
async def check_file_access(session, file_id, user_id) -> bool:
    # True if: owner OR direct file_id share OR ancestor folder_id share
```
Prevents Pitfall 4 (folder shares not propagating to file access).

### Celery Task: embed_file_content

`backend/scheduler/tasks/storage_embedding.py`:
- Queue: `embedding` (CPU-bound), `bind=True`, `max_retries=3`, `default_retry_delay=30`
- Downloads file from MinIO → extracts text → dispatches `embed_and_store.delay(text, user_id, "fact")`
- Gracefully handles: missing file (log error, return), empty text (log warning, return)
- Retries on any exception via `self.retry(exc=exc)`
- `_embed_file_content_body` exposed as `embed_file_content.__wrapped__` for test patching with mock `self`

## Test Results

All 42 storage-scope tests pass:
- `tests/storage/test_file_service.py` — 4 tests (plan 01)
- `tests/storage/test_folder_service.py` — 6 tests (plan 01)
- `tests/storage/test_text_extractor.py` — 9 tests (plan 01)
- `tests/storage/test_storage_embedding.py` — 4 tests (plan 02)
- `tests/storage/test_share_service.py` — 5 tests (plan 02)
- `tests/api/test_storage_routes.py` — 14 tests (plan 02)

Full test suite: **1012 passed, 7 skipped** — no regressions from the 946 baseline.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TypedDict attribute access in test_storage_routes.py**
- **Found during:** Task 1 GREEN phase
- **Issue:** Pre-written test used `user_a.user_id` but `UserContext` is a plain `TypedDict` (dict at runtime); attribute access raises `AttributeError`
- **Fix:** Changed to `user_a["user_id"]` dict subscript syntax
- **Files modified:** `backend/tests/api/test_storage_routes.py`
- **Commit:** 3baef56

**2. [Rule 1 - Bug] In-memory SQLite cross-request visibility in test_storage_routes.py**
- **Found during:** Task 1 GREEN phase
- **Issue:** Default `create_async_engine("sqlite+aiosqlite:///:memory:")` creates a new connection per session; second request sees empty DB
- **Fix:** Added `poolclass=StaticPool, connect_args={"check_same_thread": False}` to share one connection across all sessions
- **Files modified:** `backend/tests/api/test_storage_routes.py`
- **Commit:** 3baef56

**3. [Rule 1 - Bug] Dedup response returned 201 instead of 200**
- **Found during:** Task 1 GREEN phase
- **Issue:** Route decorator `status_code=201` overrides any dict return. Returning `{"duplicate": True}` as a dict got wrapped in 201 response.
- **Fix:** Return `JSONResponse(status_code=200, content={...})` — explicit response bypasses decorator default
- **Files modified:** `backend/api/routes/storage.py`
- **Commit:** 3baef56

**4. [Rule 1 - Bug] action=replace by hash doesn't work for different-content replacement**
- **Found during:** Task 1 GREEN phase (Test 12)
- **Issue:** Plan spec dedup query uses `content_hash` to find existing file. Test replaces file with NEW content (different hash) — no match found, new file created instead.
- **Fix:** When `action=replace`, also query by `filename` if hash lookup finds nothing. Allows replacing file content while keeping the same filename/ID.
- **Files modified:** `backend/api/routes/storage.py`
- **Commit:** 3baef56

**5. [Rule 1 - Bug] Test seed function used real PostgreSQL session instead of SQLite override**
- **Found during:** Task 1 GREEN phase (`test_list_files_scoped_to_jwt_user`)
- **Issue:** Test seed `async for s in _get_db()` imported real `get_db`, which connects to PostgreSQL (not the SQLite override). Fails with `InvalidPasswordError`.
- **Fix:** Changed seed to look up `app.dependency_overrides[get_db]` and use the override function directly.
- **Files modified:** `backend/tests/api/test_storage_routes.py`
- **Commit:** 3baef56

**6. [Rule 1 - Bug] Storage models not in Base.metadata before create_all in test_share_service.py**
- **Found during:** Task 2 GREEN phase
- **Issue:** `db_session` fixture called `Base.metadata.create_all` before models were imported in test body. `storage_files` table not created; INSERT failed.
- **Fix:** Added module-level imports of `core.models.storage_file/folder/share` to ensure registration before fixture setup.
- **Files modified:** `backend/tests/storage/test_share_service.py`
- **Commit:** 96b3da6

**7. [Rule 1 - Bug] Celery __wrapped__ is bound method, not raw function**
- **Found during:** Task 2 GREEN phase
- **Issue:** Test calls `embed_file_content.__wrapped__(mock_self, file_id, user_id)` expecting `__wrapped__` to be the unbound function with `self` param. But Celery sets `__wrapped__` to the bound method (without `self`). Calling with 3 args to a 2-param bound method raised TypeError.
- **Fix:** Extracted body to `_embed_file_content_body(self, ...)` function; explicitly set `embed_file_content.__wrapped__ = _embed_file_content_body` after task registration.
- **Files modified:** `backend/scheduler/tasks/storage_embedding.py`
- **Commit:** 96b3da6

## Self-Check

```
FOUND: /home/tungmv/Projects/hox-agentos/backend/api/routes/storage.py
FOUND: /home/tungmv/Projects/hox-agentos/backend/core/models/user_notification.py
FOUND: /home/tungmv/Projects/hox-agentos/backend/alembic/versions/033_user_notifications.py
FOUND: /home/tungmv/Projects/hox-agentos/backend/scheduler/tasks/storage_embedding.py
FOUND commit 3baef56 (Task 1)
FOUND commit 96b3da6 (Task 2)
```

## Self-Check: PASSED
