# Phase 28: Storage Service - Research

**Researched:** 2026-03-16
**Domain:** MinIO S3-compatible object storage, file management UI, text extraction for memory integration
**Confidence:** HIGH

## Summary

Phase 28 introduces personal file storage backed by MinIO (S3-compatible, self-hosted). Users upload, organize in virtual folders, share with other users, and optionally add text files to long-term memory. The architecture divides cleanly into four concerns: (1) MinIO infrastructure, (2) backend storage module with presigned URLs, (3) PostgreSQL metadata (files, folders, shares), and (4) a File Manager UI at `/files`.

The key design choice is **aioboto3** for the async Python S3 client — it provides native async/await patterns consistent with the rest of the codebase (FastAPI, asyncpg, SQLAlchemy async). Text extraction (PDF/DOCX) runs in Celery workers on the existing `embedding` queue, following the same `asyncio.run(_async_body())` pattern as `embed_and_store`. MinIO integrates into docker-compose.yml with a one-shot `mc` init container that creates the `blitz-files` bucket automatically.

Migration numbering: the current Alembic head is `a1b2c3d4e5f6` (031). New migrations for this phase are `032_storage_tables` and any subsequent additions.

**Primary recommendation:** Use aioboto3 (async S3 client) for presigned URLs and object storage; pdfminer.six for PDF extraction; python-docx for DOCX extraction; all extraction in Celery embedding queue workers.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**File Manager layout:**
- New top-level nav tab at `/files`, alongside /chat, /workflows, /skills
- Sidebar + main area layout: left sidebar with collapsible folder tree, right main area for file browsing
- Sidebar sections: "My Files" (expandable folder tree) and "Shared with me"
- Grid view: file icon + filename only (visual, scannable)
- List view: name + size + modified date + owner columns (metadata-rich)
- Breadcrumb navigation in the main area header
- Folder creation via "New Folder" button / '+' menu in the toolbar (inline editable name field)

**Upload behavior:**
- Drag-and-drop onto the main area + explicit "Upload" toolbar button (both supported)
- Upload progress shown as a per-file collapsible tray in the bottom-right (like Google Drive's upload panel) — dismissible when all uploads complete
- SHA-256 deduplication: when a duplicate is detected, prompt user with three choices: "Keep both (rename)" / "Replace" / "Skip" — per-file decision
- File size limit: 100MB per file (default, enforced backend)
- File type: configurable by admin (admin panel setting); default allowlist is all document and image types (PDF, DOCX, DOC, XLS, XLSX, PPT, PPTX, TXT, MD, CSV, PNG, JPG, GIF, SVG, etc.)
- Admin can adjust both the size limit and allowed MIME types from the admin panel

**Sharing UX:**
- Share initiated via "Share" option in the file/folder "..." actions menu (right-click also works)
- Share dialog: typeahead search by name or email against local user DB
- Permission levels: READ / WRITE / ADMIN (as per STOR-04)
- Recipients receive both in-app notification (bell badge) and email notification on new share
- Share dialog shows current shares with edit/revoke capability — owner can change permission level or remove access without re-creating the share
- Folders can also be shared (sharing a folder grants permission on all contents)

**Memory integration:**
- "Add to Memory" option in the "..." actions menu per file (same menu as Share)
- Eligible types: PDF, DOCX, TXT, MD — text-extractable only
- "Add to Memory" is greyed out (with tooltip) for non-text-extractable types
- Files already in memory show a small brain icon badge overlaid on the file icon in both grid and list view; tooltip: "In your long-term memory"
- When a file in memory is updated (new version uploaded), re-embedding triggers automatically in background via Celery worker — no user action required; a toast confirms when re-indexing completes
- Memory embedding runs in Celery worker (never in FastAPI request handler — consistent with existing embedding pattern)

### Claude's Discretion

- Exact multi-select bulk action UX (whether to support multi-select for upload/memory in addition to per-file actions)
- MinIO bucket naming and per-user prefix convention (e.g., `blitz-files/users/{user_id}/`)
- Python storage client choice: boto3 (sync, thread pool) vs aiobotocore (async) — pick based on async pattern consistency
- Toast notification implementation for share/memory events (reuse existing pattern or new)
- Exact drag-and-drop drop zone visual (highlight overlay style)
- How to handle sharing of files the user received (READ recipients cannot re-share)
- Pagination strategy for file lists (infinite scroll vs page numbers — align with existing admin pattern)

### Deferred Ideas (OUT OF SCOPE)

- File versioning / version history — future phase
- Trash / recycle bin — future phase
- Real-time sync / WebSocket notifications for file changes — future phase
- Virus/malware scanning on upload — future phase
- CDN or external storage backend — post-MVP
- Bulk "Add to Memory" for multiple selected files — could be added if time permits, but per-file is baseline
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STOR-01 | MinIO deployed as Docker Compose service with S3-compatible API | MinIO `minio/minio` image; `mc` init container for bucket creation; port 9000 (API) + 9001 (console) |
| STOR-02 | Per-user personal storage with virtual folder hierarchy (database-backed) | `file_folders` table with `parent_folder_id` self-FK; `files` table with `folder_id` + `owner_user_id`; virtual paths stored in DB, not object key structure |
| STOR-03 | File upload/download with presigned URLs, metadata storage, SHA-256 deduplication | aioboto3 `generate_presigned_url`; SHA-256 computed in FastAPI before upload; dedup via `content_hash` lookup in `files` table |
| STOR-04 | File sharing between users with READ/WRITE/ADMIN permissions | `file_shares` table; enum `permission` column; JWT-based ownership check before share creation |
| STOR-05 | Memory integration — add files to long-term memory with auto re-embedding on update | New Celery task `extract_and_embed_file`; reuses `embed_and_store` pattern; pdfminer.six for PDF, python-docx for DOCX; `file_memory_links` join table |
| STOR-06 | File manager UI with grid/list view, folder tree, breadcrumb navigation, search | Next.js route at `(authenticated)/files/`; reuses `DualPagination`, `NotificationBell` patterns; `react-dropzone` for drag-and-drop |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aioboto3 | 15.5.0 | Async S3/MinIO client for presigned URLs, upload, download | Native async/await; matches FastAPI async-first pattern; wraps aiobotocore |
| minio/minio | RELEASE.2025-03-12+ (latest) | Docker Compose S3-compatible object storage service | Official image; S3-compatible API works with aioboto3 |
| pdfminer.six | 20231228+ | Extract text from PDF files for memory indexing | Actively maintained fork; pure Python; high accuracy; handles layout |
| python-docx | 1.1.2+ | Extract text from DOCX files for memory indexing | Official python-docx; simple paragraph iteration API |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-multipart | already installed (0.0.22+) | Multipart form data for file upload endpoint | Already in pyproject.toml — no additional install needed |
| react-dropzone | 14.x | Drag-and-drop file upload zone in Next.js | Industry standard; headless; zero styling opinions |
| lucide-react | already in project | File type icons (FolderOpen, File, FileText, etc.) | Already installed; use for file/folder icons |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| aioboto3 | boto3 (sync) in thread pool | boto3 is sync; using run_in_executor adds complexity and doesn't integrate with async sessions cleanly |
| aioboto3 | minio-py (official MinIO Python SDK) | minio-py is sync-only; async support requires threading; aioboto3 is cleaner for this codebase |
| pdfminer.six | pypdf | pypdf simpler but less accurate on complex layouts; pdfminer.six better for office documents |
| pdfminer.six | PyMuPDF (fitz) | PyMuPDF is faster and more capable but has AGPL license — avoid for enterprise on-prem |

**Installation:**
```bash
# Backend
cd /home/tungmv/Projects/hox-agentos/backend
uv add aioboto3 pdfminer.six python-docx

# Frontend
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm add react-dropzone
```

---

## Architecture Patterns

### Recommended Project Structure

```
backend/
├── storage/
│   ├── __init__.py
│   ├── client.py          # get_storage_client() — aioboto3 session singleton
│   ├── service.py         # StorageService: upload_file, delete_file, generate_presigned_url
│   └── text_extractor.py  # extract_text_from_file(content: bytes, mime_type: str) -> str

scheduler/tasks/
└── storage_embedding.py   # embed_file_content(file_id_str, user_id_str) task

api/routes/
└── storage.py             # GET/POST /api/storage/files, /folders, /shares

core/models/
├── storage_file.py        # StorageFile ORM model
├── storage_folder.py      # StorageFolder ORM model
└── storage_share.py       # StorageShare ORM model

frontend/src/app/(authenticated)/files/
├── page.tsx               # Server component shell
├── layout.tsx             # Optional layout wrapper
└── _components/
    ├── file-manager.tsx   # "use client" — main stateful component
    ├── folder-tree.tsx    # Sidebar collapsible folder tree
    ├── file-grid.tsx      # Grid view: icon + filename
    ├── file-list.tsx      # List view: name, size, date, owner
    ├── breadcrumb.tsx     # Header breadcrumb navigation
    ├── upload-tray.tsx    # Bottom-right upload progress tray
    ├── share-dialog.tsx   # Modal: typeahead + permission picker
    └── toolbar.tsx        # Upload button, New Folder, view toggle
```

### Pattern 1: MinIO Docker Compose Service

**What:** Add MinIO as a new service in docker-compose.yml with a one-shot `mc` (MinIO Client) init container that creates the `blitz-files` bucket.
**When to use:** All object storage operations route through this service from within the Docker network.

```yaml
# Source: verified pattern from MinIO community docs + pliutau.com article
minio:
  image: minio/minio:latest
  ports:
    - "9000:9000"   # S3 API — accessed by backend as http://minio:9000
    - "9001:9001"   # Web console — accessed from host at http://localhost:9001
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
  volumes:
    - minio_data:/data
  command: server /data --console-address ":9001"
  healthcheck:
    test: ["CMD-SHELL", "curl -f http://localhost:9000/minio/health/live || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 5
  networks:
    - blitz-net

minio-init:
  image: minio/mc:latest
  depends_on:
    minio:
      condition: service_healthy
  entrypoint: >
    /bin/sh -c "
    mc alias set blitz http://minio:9000 $$MINIO_ROOT_USER $$MINIO_ROOT_PASSWORD &&
    mc mb --ignore-existing blitz/blitz-files &&
    exit 0;
    "
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
  networks:
    - blitz-net
```

Add to volumes section: `minio_data:`

### Pattern 2: aioboto3 Storage Client Singleton

**What:** Module-level aioboto3 session; create fresh client per operation (aioboto3 clients are async context managers — NOT singletons).
**When to use:** All upload, download, delete, presigned URL operations.

```python
# backend/storage/client.py
# Source: aioboto3 PyPI docs + aiobotocore usage patterns (MEDIUM confidence)
import aioboto3
from core.config import get_settings

_session: aioboto3.Session | None = None

def get_aioboto3_session() -> aioboto3.Session:
    global _session
    if _session is None:
        _session = aioboto3.Session()
    return _session

# Usage pattern — client is an async context manager:
# async with get_aioboto3_session().client(
#     "s3",
#     endpoint_url=settings.minio_url,         # "http://minio:9000"
#     aws_access_key_id=settings.minio_access_key,
#     aws_secret_access_key=settings.minio_secret_key,
#     region_name="us-east-1",                 # MinIO requires a region even if unused
# ) as s3:
#     url = await s3.generate_presigned_url(
#         "get_object",
#         Params={"Bucket": "blitz-files", "Key": object_key},
#         ExpiresIn=3600,
#     )
```

### Pattern 3: Per-User Object Key Prefix

**What:** All objects stored under `users/{user_id}/{file_id}` in the single `blitz-files` bucket. Virtual folder hierarchy is database-only (not reflected in object keys).
**When to use:** Every upload resolves to this key scheme.

```python
# Object key format (Claude's Discretion resolved to this pattern)
def make_object_key(user_id: UUID, file_id: UUID) -> str:
    return f"users/{user_id}/{file_id}"
# Example: "users/550e8400-e29b-41d4-a716-446655440000/f47ac10b-58cc-4372-a567-0e02b2c3d479"
```

**Why this pattern:**
- Simple and collision-proof (file_id is UUIDs)
- Virtual folder structure lives in DB only (no complex S3 prefix operations)
- Presigned URL uses the object key directly — no folder path needed
- User isolation is enforced by the `owner_user_id` check in queries (not by key prefix)

### Pattern 4: SHA-256 Deduplication on Upload

**What:** Compute SHA-256 hash of file content before issuing a PUT presigned URL. Check if hash exists in `files` table for this user. If duplicate found, return dedup info to frontend.
**When to use:** Every upload request.

```python
# In the upload initiation endpoint (POST /api/storage/files/initiate-upload)
import hashlib

async def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

# Check for existing file with same hash owned by user:
# SELECT * FROM files WHERE owner_user_id = $1 AND content_hash = $2 LIMIT 1
# If found: return {"duplicate": true, "existing_file_id": ..., "existing_file_name": ...}
# Frontend shows: "Keep both (rename)" / "Replace" / "Skip" dialog
```

### Pattern 5: Celery Task for File Embedding

**What:** New Celery task `embed_file_content` on the `embedding` queue. Extracts text from file bytes, then calls `embed_and_store` to persist the vector. Follows exact same pattern as existing `summarize_episode`.
**When to use:** Triggered by "Add to Memory" action, or automatically when a file-in-memory is updated.

```python
# backend/scheduler/tasks/storage_embedding.py
# Source: mirrors existing embed_and_store pattern in scheduler/tasks/embedding.py
import asyncio
from uuid import UUID
from scheduler.celery_app import celery_app
import structlog

logger = structlog.get_logger(__name__)

@celery_app.task(
    queue="embedding",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="scheduler.tasks.storage_embedding.embed_file_content",
)
def embed_file_content(self, file_id_str: str, user_id_str: str) -> None:
    """
    Extract text from a stored file and embed it into long-term memory.

    Reads file bytes from MinIO, extracts text based on MIME type,
    then calls embed_and_store to persist vector in memory_facts.

    Args:
        file_id_str: File UUID as string
        user_id_str: User UUID from JWT context — never from user input
    """
    from core.db import async_session
    from storage.text_extractor import extract_text_from_file
    from storage.service import StorageService
    from core.models.storage_file import StorageFile
    from sqlalchemy import select

    async def _run() -> None:
        file_id = UUID(file_id_str)
        user_id = UUID(user_id_str)

        async with async_session() as session:
            result = await session.execute(
                select(StorageFile).where(StorageFile.id == file_id)
            )
            file_record = result.scalar_one_or_none()
            if file_record is None:
                logger.error("embed_file_content_file_not_found", file_id=file_id_str)
                return

        # Download file bytes from MinIO
        service = StorageService()
        content_bytes = await service.download_bytes(file_record.object_key)

        # Extract text based on MIME type
        text = extract_text_from_file(content_bytes, file_record.mime_type)
        if not text.strip():
            logger.warning("embed_file_content_no_text", file_id=file_id_str)
            return

        # Dispatch to existing embed_and_store task
        from scheduler.tasks.embedding import embed_and_store
        embed_and_store.delay(text, user_id_str, "fact")

        logger.info("embed_file_content_dispatched", file_id=file_id_str)

    try:
        asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
```

### Pattern 6: Text Extraction by MIME Type

**What:** Centralized `extract_text_from_file(content: bytes, mime_type: str) -> str` function in `backend/storage/text_extractor.py`. Routes to correct library by MIME type.

```python
# backend/storage/text_extractor.py
# Source: pdfminer.six docs (HIGH) + python-docx docs (HIGH)
from io import BytesIO

EXTRACTABLE_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
}

def extract_text_from_file(content: bytes, mime_type: str) -> str:
    if mime_type == "application/pdf":
        from pdfminer.high_level import extract_text
        return extract_text(BytesIO(content))

    elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        from docx import Document
        doc = Document(BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    elif mime_type in ("text/plain", "text/markdown"):
        return content.decode("utf-8", errors="replace")

    return ""
```

### Pattern 7: Database Schema for Storage

**What:** Three new tables in the `032` migration: `storage_files`, `storage_folders`, `storage_shares`.

```python
# Key columns — full migration in 032_storage_tables.py
# Source: derived from existing codebase patterns (models/workflow.py, models/memory_long_term.py)

# storage_folders
# - id: UUID PK
# - owner_user_id: UUID NOT NULL (no FK — users live in Keycloak)
# - name: String(255) NOT NULL
# - parent_folder_id: UUID nullable FK -> storage_folders.id (self-referential)
# - created_at, updated_at: DateTime(timezone=True)

# storage_files
# - id: UUID PK
# - owner_user_id: UUID NOT NULL
# - folder_id: UUID nullable FK -> storage_folders.id
# - name: String(255) NOT NULL
# - object_key: String(500) NOT NULL  # "users/{user_id}/{file_id}"
# - content_hash: String(64) NOT NULL  # SHA-256 hex
# - mime_type: String(200) NOT NULL
# - size_bytes: BigInteger NOT NULL
# - in_memory: Boolean NOT NULL default False  # "Add to Memory" flag
# - created_at, updated_at: DateTime(timezone=True)

# storage_shares
# - id: UUID PK
# - file_id: UUID nullable FK -> storage_files.id
# - folder_id: UUID nullable FK -> storage_folders.id
# - shared_with_user_id: UUID NOT NULL
# - shared_by_user_id: UUID NOT NULL
# - permission: String(20) NOT NULL  # "READ" | "WRITE" | "ADMIN"
# - created_at, updated_at: DateTime(timezone=True)
# - CHECK: exactly one of file_id / folder_id is NOT NULL
```

### Anti-Patterns to Avoid

- **Storing folder paths as S3 prefixes:** Virtual folders must be database-only. Object keys use `users/{user_id}/{file_id}` flat scheme. Never encode folder hierarchy into S3 key paths.
- **Sync S3 client inside async FastAPI handlers:** Never `import boto3` and use synchronously in route handlers. Always use `aioboto3` with `async with session.client()`.
- **Running text extraction in FastAPI handler:** Text extraction (pdfminer.six, python-docx) is CPU-bound. Always dispatch to `embed_file_content` Celery task on the `embedding` queue.
- **Accepting user_id from request body for file queries:** Security invariant — `user_id` comes from `get_current_user()` JWT dependency, never request body.
- **Checking share permissions by object key prefix:** All permission checks happen via DB queries on `storage_shares` table, not MinIO ACL policies.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async S3 operations | Custom httpx-based S3 client | aioboto3 | Presigned URL signing, multipart, retries all handled; S3 signing is nontrivial |
| PDF text extraction | Custom PDF parser | pdfminer.six | PDF format is enormously complex; encoding, fonts, page objects — don't touch |
| DOCX text extraction | XML parsing of .docx zip | python-docx | DOCX is a ZIP of XML; edge cases in headers, tables, embedded objects |
| Drag-and-drop upload zone | Custom HTML5 drag events | react-dropzone | Browser API surface is large; mobile, accessibility, event bubbling handled |
| File type icon mapping | Custom SVG icon library | lucide-react (already installed) | File, Folder, FileText, Image icons all present; zero additional install |
| SHA-256 hashing | Third-party hash library | Python stdlib `hashlib.sha256` | Already in stdlib; no additional dependency needed |

**Key insight:** The entire S3 signing protocol (SigV4) is cryptographically complex. Never attempt to hand-roll presigned URL generation. Always use aioboto3.

---

## Common Pitfalls

### Pitfall 1: MinIO presigned URL endpoint mismatch

**What goes wrong:** Backend generates presigned URL using `endpoint_url=http://minio:9000` (Docker internal). Frontend receives this URL and tries to download from `http://minio:9000/...` — fails because Docker service names do not resolve from the user's browser.
**Why it happens:** Presigned URLs embed the endpoint hostname in the URL itself. The backend's `endpoint_url` for signing must match what the browser can reach.
**How to avoid:** Generate presigned URLs with `endpoint_url=http://localhost:9000` (or a configurable `MINIO_PUBLIC_URL` env var). Keep two separate env vars: `MINIO_INTERNAL_URL=http://minio:9000` (for server-side upload/download operations) and `MINIO_PUBLIC_URL=http://localhost:9000` (baked into presigned URLs returned to clients).
**Warning signs:** Download URLs contain `minio:9000` in the hostname visible to the browser.

### Pitfall 2: aioboto3 client as singleton (context manager misuse)

**What goes wrong:** Creating an aioboto3 client once at module level and reusing it across requests. aioboto3 clients are async context managers and must be opened/closed per usage.
**Why it happens:** Looks like boto3 where you call `boto3.client("s3")` once and reuse.
**How to avoid:** Always use `async with session.client("s3", ...) as s3:` — create a new context per operation, or use a dependency-injected service that opens/closes the context per request.
**Warning signs:** `RuntimeError: Session is closed` or connection pool exhaustion errors.

### Pitfall 3: MinIO `region_name` is required

**What goes wrong:** aioboto3 fails with signature errors or `NoRegionError` when connecting to MinIO.
**Why it happens:** MinIO is S3-compatible but requires `region_name` to be set (even though it doesn't actually enforce region). Without it, SigV4 signing produces incorrect signatures.
**How to avoid:** Always pass `region_name="us-east-1"` (or any arbitrary string) in the S3 client constructor.
**Warning signs:** `botocore.exceptions.NoRegionError` or 403 Forbidden from MinIO on presigned URL access.

### Pitfall 4: Folder share permissions not applied recursively at query time

**What goes wrong:** User A shares Folder X with User B at READ. User B can see the folder but cannot access individual files inside because the file_shares check looks only at `file_id`, not parent folder shares.
**Why it happens:** Naive implementation queries `storage_shares WHERE file_id = $1` without checking ancestor folder shares.
**How to avoid:** File access check must be: (1) user is owner, OR (2) there is a direct `file_id` share for this user, OR (3) there is a `folder_id` share for this user that covers the file's `folder_id`. Implement this as a single DB query with UNION or EXISTS subquery.
**Warning signs:** Shared folder shows 0 files to recipients.

### Pitfall 5: SHA-256 dedup for large files — compute in chunks

**What goes wrong:** Reading a 100MB file into memory entirely to compute SHA-256 in a FastAPI handler causes memory pressure.
**Why it happens:** `hashlib.sha256(content).hexdigest()` requires the full content in memory.
**How to avoid:** For the upload endpoint, receive the file as a streaming multipart upload. Compute SHA-256 incrementally using `sha256_obj.update(chunk)` as chunks arrive. Only buffer to compute hash, then stream to MinIO.
**Warning signs:** Backend OOM errors on large file uploads.

### Pitfall 6: Migration numbering — current head is `a1b2c3d4e5f6` (031)

**What goes wrong:** New migration created with wrong `down_revision`, breaking the chain.
**Why it happens:** Multiple heads existed earlier in the project; developers sometimes create branches.
**How to avoid:** New migration for this phase uses `down_revision = "a1b2c3d4e5f6"`. Confirmed via `alembic heads` — single head as of 2026-03-16. Next migration number: `032`.
**Warning signs:** `alembic heads` shows multiple heads after migration creation.

---

## Code Examples

Verified patterns from project codebase and library docs:

### MinIO Docker Compose Service (verified pattern)
```yaml
# Add to docker-compose.yml services:
minio:
  image: minio/minio:latest
  ports:
    - "9000:9000"
    - "9001:9001"
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
  volumes:
    - minio_data:/data
  command: server /data --console-address ":9001"
  healthcheck:
    test: ["CMD-SHELL", "curl -f http://localhost:9000/minio/health/live || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 5
  networks:
    - blitz-net

minio-init:
  image: minio/mc:latest
  depends_on:
    minio:
      condition: service_healthy
  entrypoint: >
    /bin/sh -c "
    mc alias set blitz http://minio:9000 $$MINIO_ROOT_USER $$MINIO_ROOT_PASSWORD &&
    mc mb --ignore-existing blitz/blitz-files &&
    exit 0;
    "
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
  networks:
    - blitz-net
```

### aioboto3 Presigned URL Generation
```python
# Source: aioboto3 async context manager pattern (MEDIUM confidence — verified from PyPI docs)
import aioboto3
from core.config import get_settings

async def generate_download_url(object_key: str, expires_in: int = 3600) -> str:
    settings = get_settings()
    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=settings.minio_public_url,    # http://localhost:9000 — browser-accessible
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        region_name="us-east-1",                   # required by SigV4 even for MinIO
    ) as s3:
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": "blitz-files", "Key": object_key},
            ExpiresIn=expires_in,
        )
    return url

async def generate_upload_url(object_key: str, expires_in: int = 600) -> str:
    settings = get_settings()
    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=settings.minio_internal_url,  # http://minio:9000 for server-side ops
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        region_name="us-east-1",
    ) as s3:
        url = await s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": "blitz-files", "Key": object_key},
            ExpiresIn=expires_in,
        )
    return url
```

### Settings Extension for MinIO
```python
# Add to backend/core/config.py Settings class
minio_internal_url: str = "http://minio:9000"    # server-to-server (Docker network)
minio_public_url: str = "http://localhost:9000"  # browser-accessible presigned URLs
minio_access_key: str = ""
minio_secret_key: str = ""
minio_bucket: str = "blitz-files"
# Storage limits (admin-configurable via system_config keys "storage.max_file_size_mb" etc.)
storage_max_file_size_mb: int = 100              # default 100MB, enforced by FastAPI before upload
```

### Alembic Migration 032 Structure
```python
# backend/alembic/versions/032_storage_tables.py
revision: str = "032_storage_tables"
down_revision: str = "a1b2c3d4e5f6"  # 031_sso_circuit_breaker_and_notifications

# Tables to create:
# - storage_folders (self-referential parent_folder_id)
# - storage_files (owner_user_id, folder_id FK, content_hash, object_key, in_memory)
# - storage_shares (file_id OR folder_id, shared_with_user_id, permission)
```

### Navigation Rail Extension
```typescript
// Add to frontend/src/components/nav-rail.tsx top group:
import { HardDrive } from "lucide-react";  // or FolderOpen

// In top group, after Skills:
<NavItem
  href="/files"
  icon={<HardDrive size={20} />}
  label="Files"
  active={isActive("/files")}
/>
```

### File Upload Endpoint (FastAPI pattern)
```python
# Source: mirrors existing route patterns in api/routes/
from fastapi import APIRouter, Depends, UploadFile, File
from security.deps import get_current_user

router = APIRouter(prefix="/api/storage", tags=["storage"])

@router.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    folder_id: str | None = None,
    current_user = Depends(get_current_user),
) -> dict:
    content = await file.read()
    # 1. Validate MIME type against system_config allowlist
    # 2. Validate size <= system_config max_file_size_mb
    # 3. Compute SHA-256 hash
    # 4. Check for duplicate (same hash + owner_user_id)
    # 5. If no duplicate: generate object_key, upload to MinIO, save DB record
    # 6. Return file metadata + dedup_status
    ...
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| boto3 (sync) with `run_in_executor` | aioboto3 (native async) | aioboto3 v1.x+ | Clean async without thread pool overhead |
| PyPDF2 (deprecated) | pdfminer.six + pypdf (maintained) | 2022 | PyPDF2 archived; use pdfminer.six for extraction |
| MinIO's own Python SDK (sync) | aioboto3 with S3-compatible endpoint | 2023+ | Consistent library across cloud + self-hosted S3 |
| Object key = folder path | Flat object keys + DB virtual folders | Standard pattern | Avoids S3 prefix complexity; folder renames are DB-only |

**Deprecated/outdated:**
- `PyPDF2`: Archived on GitHub, not actively maintained. Use `pdfminer.six`.
- `minio-py`: Official MinIO Python SDK is synchronous only — incompatible with async-first codebase pattern.

---

## Open Questions

1. **Email notification for shares (STOR-04 requirement)**
   - What we know: Context.md says "recipients receive both in-app notification and email notification on new share"
   - What's unclear: EMAIL phase (Phase 33) hasn't been built yet. No SMTP infrastructure exists.
   - Recommendation: Implement in-app notification (via existing `AdminNotification` bell or a new per-user notification table) in this phase. Stub out email notification with a no-op function `send_share_email()` that logs instead of sending. Wire up properly in Phase 33.

2. **Per-user notification bell vs admin-only notification bell**
   - What we know: Existing `notification-bell.tsx` is admin-only; located in `admin/` component folder. Share notifications must go to regular users (`employee` role).
   - What's unclear: Does Phase 28 need to introduce a new per-user notification infrastructure?
   - Recommendation: Add a new `user_notifications` table (separate from `admin_notifications`) and a new `UserNotificationBell` component for the nav rail. Keep admin and user notifications separate as the existing Phase 26 decision established.

3. **Frontend upload pattern: presigned PUT vs direct multipart**
   - What we know: aioboto3 supports both PUT presigned URL (browser uploads directly to MinIO) and server-side multipart through backend.
   - What's unclear: For 100MB files, direct browser-to-MinIO PUT avoids double-bandwidth through backend, but requires exposing MinIO port to user's browser.
   - Recommendation: Use server-side upload (browser POSTs to FastAPI, FastAPI streams to MinIO). Simpler security model — MinIO port 9000 doesn't need to be accessible from browsers. Revisit if performance is a problem.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.0 |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/storage/ -q` |
| Full suite command | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STOR-01 | MinIO service responds to health check | integration/smoke | Manual via `curl http://localhost:9000/minio/health/live` | ❌ Wave 0 |
| STOR-02 | Create/list/delete virtual folders per user | unit | `pytest tests/storage/test_folder_service.py -x` | ❌ Wave 0 |
| STOR-03 | Upload file, get presigned URL, check dedup detection | unit (mocked S3) | `pytest tests/storage/test_file_service.py -x` | ❌ Wave 0 |
| STOR-04 | Share file with READ/WRITE/ADMIN; verify permission check | unit | `pytest tests/storage/test_share_service.py -x` | ❌ Wave 0 |
| STOR-05 | extract_text_from_file returns text for PDF/DOCX/TXT | unit | `pytest tests/storage/test_text_extractor.py -x` | ❌ Wave 0 |
| STOR-05 | embed_file_content Celery task dispatches embed_and_store | unit (mocked) | `pytest tests/storage/test_storage_embedding.py -x` | ❌ Wave 0 |
| STOR-06 | /api/storage/files returns paginated list for current user | unit (API) | `pytest tests/api/test_storage_routes.py -x` | ❌ Wave 0 |
| STOR-06 | File sharing search endpoint returns user matches | unit (API) | `pytest tests/api/test_storage_routes.py::test_user_search -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/storage/ -q`
- **Per wave merge:** `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/storage/__init__.py` — package init
- [ ] `tests/storage/test_folder_service.py` — covers STOR-02
- [ ] `tests/storage/test_file_service.py` — covers STOR-03 (mock aioboto3 with `pytest-mock`)
- [ ] `tests/storage/test_share_service.py` — covers STOR-04
- [ ] `tests/storage/test_text_extractor.py` — covers STOR-05 text extraction
- [ ] `tests/storage/test_storage_embedding.py` — covers STOR-05 Celery task
- [ ] `tests/api/test_storage_routes.py` — covers STOR-06 API endpoints
- [ ] `backend/storage/__init__.py` — storage module package
- [ ] Framework install: `uv add aioboto3 pdfminer.six python-docx` — not yet in pyproject.toml

---

## Sources

### Primary (HIGH confidence)

- Existing codebase — `backend/scheduler/tasks/embedding.py`, `backend/core/config.py`, `backend/memory/long_term.py`, `backend/alembic/versions/031_*.py` — architecture patterns, migration chain, Celery task patterns
- Existing codebase — `docker-compose.yml` — Docker Compose service structure, network names, volume naming, env var patterns
- Existing codebase — `frontend/src/components/nav-rail.tsx`, `admin/dual-pagination.tsx` — frontend component patterns
- pdfminer.six PyPI + official docs — text extraction API
- aioboto3 PyPI (v15.5.0) — async S3 client, context manager pattern

### Secondary (MEDIUM confidence)

- aioboto3 readthedocs.io — async context manager pattern, `async with session.client()` confirmed
- MinIO community docs (pliutau.com + banach.net.pl 2025) — `mc` init container pattern for bucket auto-creation
- aiobotocore GitHub discussions — presigned URL async support confirmed as of v1.0.1+

### Tertiary (LOW confidence)

- WebSearch results on aioboto3 + MinIO presigned URL: specific `endpoint_url` + `generate_presigned_url` combination not found in official docs sample code — inferred from S3-compatible API contract and aioboto3 async pattern

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — aioboto3/MinIO/pdfminer.six all verified via PyPI and official sources
- Architecture: HIGH — derived directly from existing codebase patterns (Celery tasks, models, routes)
- Pitfalls: MEDIUM — presigned URL hostname mismatch and aioboto3 context manager misuse verified from GitHub issues; MinIO region requirement from community sources
- Migration chain: HIGH — confirmed via `alembic heads` on live repo

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (stable libraries; MinIO image tag may change but pattern is stable)
