---
created: 2026-03-15T06:51:58.504Z
title: "Implement Storage Service (Topic #19)"
area: infrastructure
priority: high
target: v1.4-infrastructure
effort: 9 weeks
existing_code: 0%
depends_on: []
blocks: ["topic-20-projects-spaces", "topic-13-avatar-upload"]
design_doc: docs/enhancement/topics/19-storage-service/00-specification.md
---

## Problem

No file storage system exists in AgentOS. Files are only stored as embeddings in pgvector. No MinIO deployment, no file/folder models, no upload/download APIs, no storage provider abstraction.

## What Exists (0%)

Zero code — specification only.

## What's Needed

- **MinIO deployment** — self-hosted S3-compatible storage in docker-compose.yml
- **Storage service API** (port 8001) — unified interface for upload, download, list, delete, share
- **Storage Provider Adapter pattern:**
  - `StorageProvider` abstract base class
  - MinIO/S3 adapter (Phase 1 MVP)
  - Future: Filesystem, OneDrive, Google Drive adapters
- **Database tables:** `files`, `folders`, `file_folder_links`, `file_shares`, `memory_file_links`
- **File permissions** — ACL system working across all providers
- **Avatar upload integration** — user profile avatar storage
- **Memory file linking** — connect files to memory entries (NotebookLM-style sources)
- **Per-folder provider configuration** — mix storage types by use case
- **Local caching** — hot files cached locally regardless of source provider

## Solution

Follow specification at `docs/enhancement/topics/19-storage-service/00-specification.md`. Start with single MinIO instance — no distributed setup for 100-user scale (YAGNI).
