# Phase 28: Storage Service - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Users get personal file storage: upload files, organize in virtual folders, download via presigned URLs, share with other users at READ/WRITE/ADMIN levels, and add text-extractable files to long-term memory. Backed by MinIO as a new Docker Compose service. Includes a full File Manager UI at `/files`.

Out of scope: file versioning, trash/recycle bin, real-time sync, virus scanning, CDN.

</domain>

<decisions>
## Implementation Decisions

### File Manager layout
- New top-level nav tab at `/files`, alongside /chat, /workflows, /skills
- Sidebar + main area layout: left sidebar with collapsible folder tree, right main area for file browsing
- Sidebar sections: "My Files" (expandable folder tree) and "Shared with me"
- Grid view: file icon + filename only (visual, scannable)
- List view: name + size + modified date + owner columns (metadata-rich)
- Breadcrumb navigation in the main area header
- Folder creation via "New Folder" button / '+' menu in the toolbar (inline editable name field)

### Upload behavior
- Drag-and-drop onto the main area + explicit "Upload" toolbar button (both supported)
- Upload progress shown as a per-file collapsible tray in the bottom-right (like Google Drive's upload panel) — dismissible when all uploads complete
- SHA-256 deduplication: when a duplicate is detected, prompt user with three choices: "Keep both (rename)" / "Replace" / "Skip" — per-file decision
- File size limit: 100MB per file (default, enforced backend)
- File type: configurable by admin (admin panel setting); default allowlist is all document and image types (PDF, DOCX, DOC, XLS, XLSX, PPT, PPTX, TXT, MD, CSV, PNG, JPG, GIF, SVG, etc.)
- Admin can adjust both the size limit and allowed MIME types from the admin panel

### Sharing UX
- Share initiated via "Share" option in the file/folder "..." actions menu (right-click also works)
- Share dialog: typeahead search by name or email against local user DB
- Permission levels: READ / WRITE / ADMIN (as per STOR-04)
- Recipients receive both in-app notification (bell badge) and email notification on new share
- Share dialog shows current shares with edit/revoke capability — owner can change permission level or remove access without re-creating the share
- Folders can also be shared (sharing a folder grants permission on all contents)

### Memory integration
- "Add to Memory" option in the "..." actions menu per file (same menu as Share)
- Eligible types: PDF, DOCX, TXT, MD — text-extractable only
- "Add to Memory" is greyed out (with tooltip) for non-text-extractable types
- Files already in memory show a small brain icon badge (🧠) overlaid on the file icon in both grid and list view; tooltip: "In your long-term memory"
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

</decisions>

<specifics>
## Specific Ideas

- File Manager sidebar + main area should feel like a standard Files app (Finder/Google Drive-style), not an admin data table
- Upload tray in bottom-right mirrors Google Drive's behavior — shows each file individually with progress, collapsible, stays until dismissed

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `dual-pagination.tsx`: reusable pagination component for file list views
- `sticky-save-bar.tsx`: could be reused for share dialog unsaved state
- `notification-bell.tsx`: existing notification bell — new share notifications should flow through this
- `registry-detail-layout.tsx`: consistent layout pattern for full-page routes — adapt for file detail if needed
- Celery worker infrastructure: already in place for embedding jobs (bge-m3 via FlagEmbedding in `memory/embeddings.py`)
- `memory/indexer`: existing long-term memory indexer — STOR-05 plugs into this

### Established Patterns
- All LLM/embedding workloads run in Celery workers, never in FastAPI handlers — re-embedding follows this
- `async with async_session()` for all DB operations
- JWT-based `get_current_user()` dependency injected in all routes — file routes use this for per-user isolation
- JSONB columns use `.with_variant(JSON(), 'sqlite')` for test compatibility
- Full type annotations + Pydantic v2 BaseModel for all route I/O

### Integration Points
- `/files` page: new route under `frontend/src/app/(authenticated)/files/`
- Nav rail (`nav-rail.tsx`): add Files tab — role `employee` and above
- Backend: new `backend/storage/` module (MinIO client, file service, presigned URL generation)
- New DB tables: `files`, `file_folders`, `file_shares` (migrations 031+)
- Celery: new task for re-embedding triggered on file update
- `memory/indexer`: called from storage service when "Add to Memory" is triggered
- Admin panel: new settings for allowed MIME types and max file size (reuse existing platform config pattern)
- Email notification: share notification email (coordinate with EMAIL phase scope — may use a simple SMTP send or defer to EMAIL phase)

</code_context>

<deferred>
## Deferred Ideas

- File versioning / version history — future phase
- Trash / recycle bin — future phase
- Real-time sync / WebSocket notifications for file changes — future phase
- Virus/malware scanning on upload — future phase
- CDN or external storage backend — post-MVP
- Bulk "Add to Memory" for multiple selected files — could be added if time permits, but per-file is baseline

</deferred>

---

*Phase: 28-storage-service*
*Context gathered: 2026-03-16*
