---
phase: 28-storage-service
plan: "01"
subsystem: storage
tags:
  - minio
  - s3
  - object-storage
  - orm
  - alembic
  - text-extraction
dependency_graph:
  requires: []
  provides:
    - MinIO Docker services (minio + minio-init)
    - storage/client.py singleton (get_aioboto3_session)
    - storage/service.py (StorageService presigned URLs + byte upload/download)
    - storage/text_extractor.py (extract_text_from_file + EXTRACTABLE_MIME_TYPES)
    - core/models/storage_file.py (StorageFile ORM)
    - core/models/storage_folder.py (StorageFolder ORM)
    - core/models/storage_share.py (StorageShare ORM)
    - alembic/versions/032_storage_tables.py (DB migration)
  affects:
    - docker-compose.yml (added minio services and volume)
    - backend/core/config.py (added 6 MinIO settings fields)
    - backend/pyproject.toml (added aioboto3, pdfminer-six, python-docx)
tech_stack:
  added:
    - aioboto3>=15.5.0 (async S3 client for MinIO)
    - pdfminer-six>=20260107 (PDF text extraction)
    - python-docx>=1.2.0 (DOCX text extraction)
    - minio/minio:latest Docker image (object storage)
    - minio/mc:latest Docker image (bucket init)
  patterns:
    - aioboto3 async context manager per operation (no singleton S3 client)
    - Module-level aioboto3.Session singleton via get_aioboto3_session()
    - SQLAlchemy ORM with PGUUID columns; no FK to users (Keycloak architecture)
    - JSONB-compatible migration using sa.Column patterns
key_files:
  created:
    - backend/storage/__init__.py
    - backend/storage/client.py
    - backend/storage/service.py
    - backend/storage/text_extractor.py
    - backend/core/models/storage_file.py
    - backend/core/models/storage_folder.py
    - backend/core/models/storage_share.py
    - backend/alembic/versions/032_storage_tables.py
  modified:
    - docker-compose.yml (minio + minio-init services, minio_data volume)
    - backend/core/config.py (6 MinIO settings fields)
    - backend/pyproject.toml (3 new dependencies)
    - backend/uv.lock (updated)
decisions:
  - "[28-01]: S3 client created per-operation with async context manager — never as module singleton (boto3/aioboto3 clients are not thread-safe)"
  - "[28-01]: aioboto3.Session is the singleton (safe to share); s3 client is created fresh per call"
  - "[28-01]: minio_internal_url used for upload presigned URLs — backend signs with internal Docker URL"
  - "[28-01]: minio_public_url used for download presigned URLs — browser fetches from localhost:9000"
  - "[28-01]: EXTRACTABLE_MIME_TYPES is frozenset — immutable constant for membership checks"
  - "[28-01]: pdfminer and docx imports are lazy (inside function) — avoids import cost on startup"
metrics:
  duration: "25min"
  completed_date: "2026-03-16"
  tasks_completed: 2
  files_created: 8
  files_modified: 3
---

# Phase 28 Plan 01: MinIO Infrastructure and Storage Foundation Summary

MinIO Docker services with async aioboto3 client, presigned URL generation, text extraction from PDF/DOCX/plain text, and three PostgreSQL storage tables via migration 032.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | MinIO Docker service, config settings, and storage module skeleton | d823ebc | docker-compose.yml, core/config.py, storage/__init__.py, storage/client.py, storage/service.py, pyproject.toml |
| 2 | ORM models, Alembic migration 032, and text extractor | 9776f64 | core/models/storage_file.py, storage_folder.py, storage_share.py, alembic/versions/032_storage_tables.py, storage/text_extractor.py |

## What Was Built

### MinIO Docker Services

Added two services to `docker-compose.yml`:
- `minio`: MinIO server with healthcheck at `localhost:9000/minio/health/live`, ports 9000 (API) and 9001 (console)
- `minio-init`: One-shot container that creates the `blitz-files` bucket on startup
- `minio_data` volume for persistent storage

### Storage Module (`backend/storage/`)

- **`client.py`**: `get_aioboto3_session()` returns a module-level `aioboto3.Session` singleton. The session is safe to share; S3 clients are created per-operation via `async with`.
- **`service.py`**: `StorageService` with `make_object_key()`, `generate_upload_url()` (uses internal URL), `generate_download_url()` (uses public URL), `upload_bytes()`, `download_bytes()`, `delete_object()`.
- **`text_extractor.py`**: `extract_text_from_file(content, mime_type)` with lazy imports for pdfminer and python-docx. Returns `""` for unsupported MIME types (images, video, etc).

### Config Settings

Six new fields in `Settings`:
```
minio_internal_url = "http://minio:9000"
minio_public_url   = "http://localhost:9000"
minio_access_key   = ""
minio_secret_key   = ""
minio_bucket       = "blitz-files"
storage_max_file_size_mb = 100
```

### ORM Models

- **`StorageFolder`**: `storage_folders` table, self-referencing `parent_folder_id` FK, indexed on `owner_user_id`
- **`StorageFile`**: `storage_files` table, `content_hash` (SHA-256), `in_memory` flag, indexed on `owner_user_id` and `content_hash`
- **`StorageShare`**: `storage_shares` table, nullable `file_id` and `folder_id` FKs, `permission` column (READ/WRITE/ADMIN), indexed on `shared_with_user_id`

### Alembic Migration 032

`032_storage_tables.py` with `down_revision = "a1b2c3d4e5f6"` (chaining from migration 031). Creates tables in dependency order (folders → files → shares) with appropriate indexes.

## Test Results

All 19 plan-scope tests pass:
- `tests/storage/test_file_service.py` — 4 tests (StorageService + singleton)
- `tests/storage/test_folder_service.py` — 6 tests (ORM model columns)
- `tests/storage/test_text_extractor.py` — 9 tests (text extraction + MIME constants)

Tests for future plans (`test_share_service.py`, `test_storage_embedding.py`, `tests/api/test_storage_routes.py`) remain RED as expected — they test `api.routes.storage` and `scheduler.tasks.storage_embedding` implemented in plans 28-02+.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

```
FOUND: /home/tungmv/Projects/hox-agentos/backend/storage/client.py
FOUND: /home/tungmv/Projects/hox-agentos/backend/storage/service.py
FOUND: /home/tungmv/Projects/hox-agentos/backend/storage/text_extractor.py
FOUND: /home/tungmv/Projects/hox-agentos/backend/core/models/storage_file.py
FOUND: /home/tungmv/Projects/hox-agentos/backend/core/models/storage_folder.py
FOUND: /home/tungmv/Projects/hox-agentos/backend/core/models/storage_share.py
FOUND: /home/tungmv/Projects/hox-agentos/backend/alembic/versions/032_storage_tables.py
FOUND commit d823ebc (Task 1)
FOUND commit 9776f64 (Task 2)
```

## Self-Check: PASSED
