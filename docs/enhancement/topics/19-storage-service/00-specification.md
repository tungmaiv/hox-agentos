# Storage Service

**Topic #19**
**Status:** ✅ Design Complete
**Priority:** High
**Target:** v1.7+
**Estimated Effort:** 1 Phase (9 weeks)
**Created:** 2026-03-14
**Architecture Label:** architect-01

---

## Problem Statement

AgentOS currently lacks a unified file storage system. Users cannot:
1. Store and share documents/files within AgentOS
2. Organize files in folder structures (personal, projects)
3. Share files between users and workspaces
4. Add files to long-term memory for semantic search
5. Sync file changes with memory records (re-embedding on update)
6. Access files from multiple devices (upload/download)

**Current State:**
- No file storage infrastructure
- Files stored in memory as embeddings only (no original file access)
- No folder structure or file management
- No sharing capabilities
- No file-to-memory integration
- No UI for file management

**Impact:**
- Users cannot store documents within AgentOS (must use external cloud storage)
- No file organization (personal storage vs project folders)
- Cannot share files with team members
- Files cannot be added to long-term memory
- No central file repository for agents to reference

---

## Target State (To-Be)

Build a **scalable storage service** for AgentOS with:

### Core Capabilities

1. **Dedicated Personal Storage** (per user)
   - Each user gets root folder (`/`): personal documents, projects
   - Projects map to subfolders under personal storage
   - Future: Workspaces get dedicated storage (`/workspace-id/`)

2. **Universal Storage Backend**
   - MinIO (default, self-hosted S3-compatible)
   - Future: S3, Azure Blob Storage (via adapter pattern)
   - MCP-inspired adapter interface for easy backend swapping

3. **Folder-Based Organization**
   - Virtual folder structure (database-backed, not in MinIO)
   - Create/rename/delete folders
   - Navigate folder hierarchy (breadcrumb, tree view)
   - Folder types: personal, shared, project

4. **File Upload/Download**
   - Drag-and-drop file upload
   - File metadata storage (name, mime type, size, hash)
   - Download via presigned URLs (secure, time-limited)
   - File deduplication (SHA-256 hash)

5. **File Sharing System**
   - Share files with other users (READ, WRITE, ADMIN permissions)
   - Share files with workspaces (future)
   - Revoke shares
   - "Shared with Me" folder for incoming shares

6. **Memory Integration**
   - Add files to long-term memory (bge-m3 embedding)
   - Memory icon indicator on files in memory
   - Automatic re-embedding on file update (hash comparison)
   - Remove files from memory (cascades to memory record)

7. **File Manager UI**
   - Grid and list view for files
   - Folder tree navigation (left sidebar)
   - Breadcrumb navigation
   - Search functionality
   - Bulk selection and actions
   - Memory toggle button
   - Share dialog

8. **Security & Access Control**
   - Three-gate security (JWT + RBAC + storage ACL)
   - Database-level access control (ownership + share permissions)
   - Audit logging for all operations
   - No per-user MinIO policies (scales to 2000-3000 users)

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          Frontend (Next.js)                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Storage Page (File Manager UI)                        │   │
│  │  - File upload/download                                │   │
│  │  - Folder navigation                                   │   │
│  │  - Sharing permissions                                   │   │
│  │  - Memory-linked file indicators                         │   │
│  └────────────────────┬─────────────────────────────────────┘   │
│                       │ REST API                                 │
└───────────────────────┼─────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                    API Gateway (FastAPI)                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  /api/storage/* (proxied to storage-service)          │   │
│  └────────────────┬─────────────────────────────────────┘   │
│                   │                                          │
┌───────────────────┼──────────────────────────────────────┐
│         │         │                                          │
│   ┌─────▼────────┴────────────────────────┐             │
│   │  Backend Service (Existing)           │             │
│   │  - Master agent                      │             │
│   │  - Tools                           │             │
│   │  - Memory service                   │             │
│   │  - Scheduler                      │             │
│   └─────┬────────────────────────────────┘             │
│         │                                        │
│         │ Direct DB access                        │
│         │                                        │
│         │                                        │
│         │        ┌──────────────────────────▼────────┐
│         │        │         PostgreSQL (Shared Database)      │
│         │        │  ┌─────────────────────────────────┐    │
│         │        │  │ Backend tables:              │    │
│         │        │  │  - agents, tools, workflows    │    │
│         │        │  │  - memory_records             │    │
│         │        │  │                             │    │
│         │        │  │ Storage tables:              │    │
│         │        │  │  - File                     │    │
│         │        │  │  - Folder                   │    │
│         │        │  │  - FileFolderLink           │    │
│         │        │  │  - FileShare                │    │
│         │        │  │  - MemoryFileLink           │    │
│         │        │  └─────────────────────────────────┘    │
│         │        └──────────────────────────▲────────┘
│         │                   │
└─────────┼───────────────────┴──────────────────────────────┐
          │ REST API                                         │
          │                                                  │
┌─────────▼─────────────────────────────────────────────┐
│  Storage Service (NEW - Dedicated Microservice)              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  FastAPI app (port 8003)                          │  │
│  │  # Port 8003 — port 8001 is reserved for MCP CRM Server, port 8002 for MCP Docs Server
│  │                                                      │  │
│  │  /api/storage/files/* Routes:                         │  │
│  │  - POST /upload (upload file)                           │  │
│  │  - GET / (list files)                                 │  │
│  │  - GET /{file_id}/download (download)                   │  │
│  │  - DELETE /{file_id} (delete)                            │  │
│  │                                                      │  │
│  │  /api/storage/folders/* Routes:                               │  │
│  │  - POST / (create folder)                              │  │
│  │  - GET / (list folders)                                │  │
│  │  - PUT /{folder_id} (rename)                           │  │
│  │  - DELETE /{folder_id} (delete)                         │  │
│  │                                                      │  │
│  │  /api/storage/shares/* Routes:                                 │  │
│  │  - POST /{file_id} (share)                            │  │
│  │  - GET / (list shared with me)                          │  │
│  │  - DELETE /{share_id} (revoke)                          │  │
│  │                                                      │  │
│  │  /api/storage/memory/* Routes:                                  │  │
│  │  - POST /{file_id}/add-to-memory (embed)               │  │
│  │  - DELETE /{file_id}/remove-from-memory               │  │
│  │  - GET /in-memory (list files in memory)               │  │
│  │                                                      │  │
│  │  Storage Adapters (MCP-inspired):                      │  │
│  │  - MinIOAdapter (default)                             │  │
│  │  - S3Adapter (future)                                 │  │
│  │  - AzureAdapter (future)                               │  │
│  └────────────────┬─────────────────────────────────────┘  │
│                   │                                          │
└───────────────────┼──────────────────────────────────────────┘
                    │
                    │ Direct SDK calls (via adapter)
                    │
┌───────────────────▼──────────────────────────────────────────┐
│              MinIO Storage (S3-compatible)                  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  Bucket: agentos-storage                             │   │
│  │  Policies:                                         │   │
│  │  - registry-read: GetObject, ListObject               │   │
│  │  - registry-write: PutObject, DeleteObject             │   │
│  │                                                      │   │
│  │  Structure:                                         │   │
│  │  registry/file-{uuid}/{original_name}                    │   │
│  └────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────┘
```

### Key Architectural Decisions

| Decision | Rationale |
|-----------|------------|
| **Dedicated storage service** (microservice) | Scales independently, clear separation of concerns, can run multiple instances |
| **MCP-inspired adapter pattern** | Consistent with AgentOS architecture, easy to swap backends (MinIO → S3/Azure) |
| **DB-only folder structure** | No per-user MinIO policies (scales to 2000+ users), single source of truth |
| **Shared PostgreSQL database** | Simplifies memory record joins, no cross-service DB replication |
| **Universal storage abstraction** | Future-ready for cloud migration, no code changes needed |
| **Soft delete for files** | Enables recovery, audit trail, eventual consistency with memory |

---

## Database Schema

### File Table

```python
class File(Base):
    """File metadata (actual content stored in MinIO)"""
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # MinIO storage reference
    bucket_path = Column(String, nullable=False, unique=True)  # "registry/file-{id}/{original_name}"

    # Ownership
    owner_type = Column(String, nullable=False)  # "user" | "workspace"
    owner_id = Column(UUID(as_uuid=True), nullable=False)

    # File metadata
    original_name = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size = Column(BigInteger, nullable=False)
    hash = Column(String, nullable=False, index=True)  # SHA-256 for deduplication

    # Status
    status = Column(SQLEnum(FileStatus), default=FileStatus.ACTIVE, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    folder_links = relationship("FileFolderLink", back_populates="file", cascade="all, delete-orphan")
    shares = relationship("FileShare", back_populates="file", cascade="all, delete-orphan")
    memory_links = relationship("MemoryFileLink", back_populates="file", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("ix_files_owner", "owner_type", "owner_id"),
        Index("ix_files_status", "status"),
        Index("ix_files_created_at", "created_at"),
    )
```

### Folder Table

```python
class Folder(Base):
    """Folder structure (hierarchical, virtual in DB only)"""
    __tablename__ = "folders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Hierarchy
    parent_id = Column(UUID(as_uuid=True), ForeignKey("folders.id"), nullable=True)
    parent = relationship("Folder", remote_side=[id], backref="children")

    # Ownership
    owner_type = Column(String, nullable=False)  # "user" | "workspace"
    owner_id = Column(UUID(as_uuid=True), nullable=False)

    # Folder metadata
    name = Column(String, nullable=False)
    folder_type = Column(SQLEnum(FolderType), default=FolderType.PERSONAL, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    file_links = relationship("FileFolderLink", back_populates="folder", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("ix_folders_owner", "owner_type", "owner_id"),
        Index("ix_folders_parent", "parent_id"),
        Index("ix_folders_type", "folder_type"),
    )
```

### FileFolderLink Table

```python
class FileFolderLink(Base):
    """Many-to-many relationship between files and folders"""
    __tablename__ = "file_folder_links"

    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    folder_id = Column(UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    file = relationship("File", back_populates="folder_links")
    folder = relationship("Folder", back_populates="file_links")
```

### FileShare Table

```python
class FileShare(Base):
    """File sharing permissions"""
    __tablename__ = "file_shares"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)

    # Who is sharing
    owner_type = Column(String, nullable=False)
    owner_id = Column(UUID(as_uuid=True), nullable=False)

    # Who is receiving
    recipient_type = Column(String, nullable=False)
    recipient_id = Column(UUID(as_uuid=True), nullable=False)

    # Permission
    permission = Column(SQLEnum(SharePermission), nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    file = relationship("File", back_populates="shares")

    # Indexes
    __table_args__ = (
        Index("ix_file_shares_file", "file_id"),
        Index("ix_file_shares_recipient", "recipient_type", "recipient_id"),
        Index("ix_file_shares_owner", "owner_type", "owner_id"),
    )
```

### MemoryFileLink Table

```python
class MemoryFileLink(Base):
    """Link between memory records and files"""
    __tablename__ = "memory_file_links"

    memory_record_id = Column(UUID(as_uuid=True), ForeignKey("memory_records.id", ondelete="CASCADE"), primary_key=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    file = relationship("File", back_populates="memory_links")

    # Indexes
    __table_args__ = (
        Index("ix_memory_file_links_memory", "memory_record_id"),
        Index("ix_memory_file_links_file", "file_id"),
    )
```

### Database Size Estimates (2000-3000 Users)

| Table | Avg Rows per User | Total Rows (3000 users) | Row Size | Total DB Size |
|--------|-------------------|--------------------------|-----------|---------------|
| File | 100 | 300,000 | 500 bytes | 150 MB |
| Folder | 50 | 150,000 | 300 bytes | 45 MB |
| FileFolderLink | 200 | 600,000 | 100 bytes | 60 MB |
| FileShare | 10 | 30,000 | 150 bytes | 5 MB |
| MemoryFileLink | 50 | 150,000 | 100 bytes | 15 MB |
| **Total** | - | **1,230,000** | - | **275 MB** |

**PostgreSQL handles 275 MB easily** (typical production databases are 10-100 GB).

---

## Storage Adapters (MCP-Inspired Pattern)

### Base Adapter Protocol

```python
class StorageAdapter(Protocol):
    """Universal storage adapter interface"""

    adapter_name: str
    supported_operations: list[str]

    async def initialize(self) -> None:
        """Initialize adapter (connection, auth)"""
        ...

    async def health_check(self) -> bool:
        """Check if adapter is healthy"""
        ...

    async def upload(
        self,
        object_key: str,
        content: BytesIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Upload file and return URL"""
        ...

    async def download(self, object_key: str) -> BytesIO:
        """Download file content"""
        ...

    async def delete(self, object_key: str) -> None:
        """Delete file"""
        ...

    async def exists(self, object_key: str) -> bool:
        """Check if file exists"""
        ...

    async def get_url(self, object_key: str, expires: int = 3600) -> str:
        """Get presigned or public URL"""
        ...

    async def get_metadata(self, object_key: str) -> dict[str, str]:
        """Get file metadata (size, etag, last_modified)"""
        ...

    async def cleanup(self) -> None:
        """Cleanup resources"""
        ...
```

### MinIO Adapter (Default)

```python
class MinIOStorageAdapter:
    """MinIO storage adapter (default for AgentOS)"""

    adapter_name = "minio"
    supported_operations = ["upload", "download", "delete", "exists", "get_url", "get_metadata"]

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str):
        self.client = Minio(endpoint, access_key, secret_key, secure=False)
        self.bucket = bucket

    async def initialize(self) -> None:
        """Ensure bucket exists"""
        try:
            if not await self._bucket_exists():
                self.client.make_bucket(self.bucket)
        except MinioException as e:
            raise RuntimeError(f"Failed to initialize MinIO: {e}")

    async def health_check(self) -> bool:
        """Check if MinIO is accessible"""
        try:
            self.client.list_buckets()
            return True
        except MinioException:
            return False

    async def upload(
        self,
        object_key: str,
        content: BytesIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Upload file to MinIO"""
        try:
            self.client.put_object(
                bucket_name=self.bucket,
                object_name=object_key,
                data=content,
                length=-1,
                part_size=5 * 1024 * 1024,
                content_type=content_type,
                metadata=metadata or {},
            )
            return f"{self.client._endpoint_url}/{self.bucket}/{object_key}"
        except MinioException as e:
            raise RuntimeError(f"MinIO upload failed: {e}")

    # ... (download, delete, exists, get_url, get_metadata methods)
```

### S3 Adapter (Future)

```python
class S3StorageAdapter:
    """AWS S3 storage adapter (future support)"""

    adapter_name = "s3"
    supported_operations = ["upload", "download", "delete", "exists", "get_url", "get_metadata"]

    def __init__(self, region: str, access_key: str, secret_key: str, bucket: str):
        self.client = boto3.client(
            's3',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        self.bucket = bucket

    # ... (similar implementation to MinIO, using boto3)
```

### Adapter Factory

```python
_STORAGE_ADAPTERS: dict[str, Type[StorageAdapter]] = {
    "minio": MinIOStorageAdapter,
    "s3": S3StorageAdapter,
}

def get_storage_adapter(name: str, config: dict[str, str]) -> StorageAdapter:
    """Get storage adapter instance by name"""
    if name not in _STORAGE_ADAPTERS:
        raise ValueError(f"Unknown storage adapter: {name}")

    adapter_class = _STORAGE_ADAPTERS[name]
    return adapter_class(**config)

def list_storage_adapters() -> list[str]:
    """List all registered storage adapters"""
    return list(_STORAGE_ADAPTERS.keys())
```

---

## API Routes

### File Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|---------|-------------|----------------|
| `/api/storage/files/upload` | POST | Upload file | ✅ |
| `/api/storage/files` | GET | List files | ✅ |
| `/api/storage/files/{id}` | GET | Get file metadata | ✅ |
| `/api/storage/files/{id}/download` | GET | Download file (redirect) | ✅ |
| `/api/storage/files/{id}` | PUT | Update file metadata | ✅ |
| `/api/storage/files/{id}` | DELETE | Delete file (soft) | ✅ |

### Folder Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|---------|-------------|----------------|
| `/api/storage/folders` | POST | Create folder | ✅ |
| `/api/storage/folders` | GET | List folders | ✅ |
| `/api/storage/folders/{id}` | GET | Get folder metadata | ✅ |
| `/api/storage/folders/{id}` | PUT | Rename folder | ✅ |
| `/api/storage/folders/{id}` | DELETE | Delete folder | ✅ |

### Sharing Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|---------|-------------|----------------|
| `/api/storage/files/{id}/share` | POST | Share file | ✅ |
| `/api/storage/files/shared` | GET | List shared files | ✅ |
| `/api/storage/files/share/{id}` | DELETE | Revoke share | ✅ |

### Memory Integration Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|---------|-------------|----------------|
| `/api/storage/files/{id}/memory` | POST | Add to memory | ✅ |
| `/api/storage/files/{id}/memory` | DELETE | Remove from memory | ✅ |
| `/api/storage/files/in-memory` | GET | List memory files | ✅ |

---

## Memory Synchronization

### File-to-Memory Flow

```
User uploads "report.pdf" → Storage Service
                                  │
                                  ▼
                          File uploaded to MinIO
                                  │
                                  ▼
                          File record created
                                  │
                                  ▼
                    User clicks "Add to Memory"
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                  Storage Service (Memory Sync)                │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 1. Download file content from MinIO                        │  │
│  │ 2. Send to backend memory service for embedding             │  │
│  │ 3. Create MemoryFileLink record (storage DB)              │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                         │
└───────────────────────┼───────────────────────────────────────────┘
                        │ HTTP call
                        │
┌───────────────────────▼───────────────────────────────────────────┐
│                  Backend Service (Memory)                        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ 3. Embed file content via bge-m3                      │ │
│  │ 4. Create memory_record (backend DB)                      │ │
│  │ 5. Return memory_record_id                                │ │
│  └────────────────────┬─────────────────────────────────────┘ │
│                       │                                         │
└───────────────────────┼───────────────────────────────────────────┘
                        │ HTTP response
                        │
┌───────────────────────▼───────────────────────────────────────────┐
│                  Storage Service (Memory Sync)                │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ 6. Update MemoryFileLink with memory_record_id             │ │
│  └────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────┘

User sees memory icon on "report.pdf" ✓
```

### File Update Sync

```
User updates "report.pdf" → Storage Service
                                  │
                                  ▼
                          New content uploaded to MinIO
                                  │
                                  ▼
                          File hash updated (SHA-256)
                                  │
                                  ▼
                    Background task: "sync_file_update"
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                  Storage Service (Memory Sync)                │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ 1. Download new content from MinIO                          │  │
│  │ 2. Compare new hash vs stored hash                         │  │
│  │ 3. If changed:                                            │  │
│  │    a. Call backend to re-embed                            │  │
│  │    b. Update memory_record with new hash                     │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **REST Communication (Not Direct DB Access)**
   - Storage service calls backend via HTTP for embedding
   - Clear service boundary
   - Backend can embed in separate Celery workers

2. **File Hash Comparison**
   - SHA-256 hash detects content changes
   - Only re-embed if hash changes
   - Saves CPU time (bge-m3 embedding is expensive)

3. **CASCADE Delete**
   - Deleting file removes MemoryFileLink automatically
   - Backend memory_record is orphaned (garbage collection needed)
   - Or implement: storage calls backend DELETE on memory record

4. **Background Tasks**
   - File upload → sync after upload (fast response)
   - File update → sync via Celery task (eventual consistency)
   - Memory add → sync immediately (user action)

---

## Security & Access Control

### Three-Gate Security Model

```
File Download Request:
├── Gate 1: JWT Validation (AgentOS standard)
│   └── Verify signature, expiry, issuer, audience
├── Gate 2: RBAC Permission Check (AgentOS standard)
│   └── Map Keycloak roles → permissions
└── Gate 3: Storage Access Check (NEW)
    └── Check READ access (owner or share)
```

### Access Control Matrix

| Operation | Owner | Recipient (READ) | Recipient (WRITE) | Recipient (ADMIN) |
|----------|--------|-------------------|---------------------|----------------------|
| Upload | ✅ | ❌ | ❌ | ❌ |
| Download | ✅ | ✅ | ✅ | ✅ |
| Update Metadata | ✅ | ❌ | ✅ | ✅ |
| Rename | ✅ | ❌ | ✅ | ✅ |
| Delete | ✅ | ❌ | ❌ | ✅ |
| Share | ✅ | ❌ | ❌ | ❌ |
| Revoke Share | ✅ | ❌ | ❌ | ✅ |

**Legend:**
- **Owner:** User who created the file
- **Recipient (READ):** User with READ permission share
- **Recipient (WRITE):** User with WRITE permission share
- **Recipient (ADMIN):** User with ADMIN permission share

### Audit Logging

```python
def log_file_operation(
    operation: str,
    file_id: UUID,
    user_id: UUID,
    success: bool,
    error: Optional[str] = None,
    metadata: dict[str, Any] | None = None,
):
    """Log file operation to audit trail"""

    log_entry = {
        "operation": operation,
        "file_id": str(file_id),
        "user_id": str(user_id),
        "success": success,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if error:
        log_entry["error"] = error

    if metadata:
        log_entry["metadata"] = metadata

    if success:
        audit_logger.info("file_operation", **log_entry)
    else:
        audit_logger.warning("file_operation_denied", **log_entry)
```

### MinIO Security

```yaml
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::agentos-storage"
      ],
      "Condition": {
        "StringLike": {
          "s3:prefix": ["registry/file-*"]
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::agentos-storage/registry/file-*"
      ]
    }
  ]
}
```

**MinIO Policy Strategy:**
- **No per-user policies** (exceeds 1000 policy limit at 2000+ users)
- **Role-based policies:** `registry-read` and `registry-write`
- **Prefix-based access:** All files under `registry/`
- **Application-level ACL:** Storage service enforces access control via database

---

## Frontend UI (File Manager)

### Main Components

| Component | Description | Props |
|----------|-------------|--------|
| `StoragePage` | Main storage page with toolbar, file list, folder tree | - folders, files, loading, error |
| `FileList` | Grid/list view of files with selection, actions | - files, selectedFiles, viewMode, callbacks |
| `FolderTree` | Hierarchical folder navigation tree | - folders, currentFolder, callbacks |
| `FileUpload` | Drag-and-drop file upload component | - onUpload callback |
| `MemoryToggle` | Toggle button for adding/removing files from memory | - fileId, isInMemory, onToggle |
| `ShareDialog` | Modal dialog for sharing files with users/workspaces | - files, onClose, onShare |

### User Experience Flow

**1. Initial Load**
- User opens `/storage` page
- Folder tree loads on left sidebar
- Root folder files load in main area
- Loading state shown during fetch

**2. Navigation**
- User clicks folder in tree → expands folder, loads files
- Breadcrumb navigation shows path: `Storage > Personal > Projects > Project Alpha`
- User can navigate back to parent folders

**3. File Upload**
- User clicks "+ New Folder" or drags files to upload area
- Upload dialog shows progress bar
- File appears in list after upload (no page refresh)
- File hash calculated, duplicate detected if exists

**4. File Operations**
- Single-click: Select file (highlighted)
- Double-click: Download/open file
- Right-click: Context menu (share, delete, add to memory)
- Bulk selection: Shift+click or checkbox selection

**5. Memory Integration**
- Memory icon shown on files in long-term memory (brain icon)
- Click memory icon to toggle (add/remove)
- File automatically re-embedded if content changes
- Memory status persisted across sessions

**6. Sharing**
- Click "Share" button → opens share dialog
- Select recipient (user/workspace) + permission level
- Share appears in recipient's "Shared with Me" folder
- Revoke share from share dialog or context menu

---

## Implementation Phases

### Phase 1: Foundation (Week 1)

**Goal:** Create storage service skeleton with database models

**Tasks:**
- [ ] Create `backend/storage-service/` directory structure
- [ ] Implement database models (File, Folder, FileFolderLink, FileShare, MemoryFileLink)
- [ ] Create Alembic migration for storage tables
- [ ] Set up FastAPI app skeleton (`main.py`, `routes.py`)
- [ ] Add storage service configuration (`config.py`)
- [ ] Create base StorageAdapter protocol
- [ ] Set up database session factory
- [ ] Add `/health` endpoint for monitoring

**Success Criteria:**
- ✅ Storage service starts on port 8003
- ✅ All tables created in PostgreSQL
- ✅ `/health` endpoint returns 200
- ✅ No database connection errors

---

### Phase 2: MinIO Integration (Week 1)

**Goal:** Integrate MinIO adapter and basic storage operations

**Tasks:**
- [ ] Implement MinIOStorageAdapter class
- [ ] Create adapter factory (`adapters/factory.py`)
- [ ] Set up MinIO Docker service in `docker-compose.yml`
- [ ] Configure MinIO policies (registry-read, registry-write)
- [ ] Implement `/api/storage/files/{id}/download` endpoint
- [ ] Implement `/api/storage/files/upload` endpoint
- [ ] Add file upload/download tests (unit + E2E)
- [ ] Test MinIO connection and bucket creation

**Success Criteria:**
- ✅ File uploads to MinIO successfully
- ✅ File downloads from MinIO via presigned URL
- ✅ MinIO bucket exists with correct policies
- ✅ Upload/download E2E tests pass (100%)

---

### Phase 3: Folder Management (Week 2)

**Goal:** Implement folder hierarchy and CRUD operations

**Tasks:**
- [ ] Implement `/api/storage/folders` endpoints (GET, POST)
- [ ] Implement `/api/storage/folders/{id}` endpoints (GET, PUT, DELETE)
- [ ] Add folder validation (parent existence, ownership check)
- [ ] Implement folder hierarchy queries (parent/children navigation)
- [ ] Add folder type filtering (personal, shared, project)
- [ ] Create folder unit tests
- [ ] Test folder CRUD operations
- [ ] Verify CASCADE delete works (parent deletes children)

**Success Criteria:**
- ✅ User can create folders
- ✅ User can navigate folder hierarchy
- ✅ Deleting parent folder CASCADE deletes children
- ✅ Folder ownership enforced (users can't access others' folders)

---

### Phase 4: File Operations (Week 2)

**Goal:** Implement core file CRUD operations

**Tasks:**
- [ ] Implement `/api/storage/files` list endpoint
- [ ] Implement `/api/storage/files/{id}` get endpoint
- [ ] Implement `/api/storage/files/{id}` put endpoint
- [ ] Implement `/api/storage/files/{id}` delete endpoint (soft delete)
- [ ] Add file hash calculation (SHA-256)
- [ ] Add deduplication logic (check hash before upload)
- [ ] Implement file metadata queries
- [ ] Add file operation unit tests
- [ ] Test file upload/download/update/delete

**Success Criteria:**
- ✅ User can list files
- ✅ User can upload files
- ✅ User can download files
- ✅ User can delete files (soft delete)
- ✅ Duplicate files detected via hash

---

### Phase 5: Memory Synchronization (Week 3)

**Goal:** Integrate file storage with long-term memory

**Tasks:**
- [ ] Implement MemorySyncService class
- [ ] Create `/api/storage/files/{id}/memory` POST endpoint
- [ ] Create `/api/storage/files/{id}/memory` DELETE endpoint
- [ ] Create `/api/storage/files/in-memory` GET endpoint
- [ ] Implement backend HTTP client for memory service calls
- [ ] Add file embedding flow (download → embed → create link)
- [ ] Implement memory sync background task (file update detection)
- [ ] Add memory integration unit tests
- [ ] Test file → memory workflow

**Success Criteria:**
- ✅ User can add files to memory
- ✅ User can remove files from memory
- ✅ Memory icon shown on files in memory
- ✅ File updates trigger re-embedding

---

### Phase 6: Sharing System (Week 3)

**Goal:** Implement file sharing between users/workspaces

**Tasks:**
- [ ] Implement `/api/storage/files/{id}/share` POST endpoint
- [ ] Implement `/api/storage/files/shared` GET endpoint
- [ ] Implement `/api/storage/files/share/{id}` DELETE endpoint
- [ ] Add share permission validation (READ, WRITE, ADMIN)
- [ ] Implement access control checks (ownership + share lookup)
- [ ] Add share validation (recipient exists, permission levels)
- [ ] Create sharing unit tests
- [ ] Test user-to-user sharing
- [ ] Test share revocation

**Success Criteria:**
- ✅ User can share files with other users
- ✅ Shared files appear in recipient's "Shared with Me" folder
- ✅ Share permissions enforced (READ can't edit, etc.)
- ✅ Users can revoke shares

---

### Phase 7: Security & Access Control (Week 4)

**Goal:** Implement security gates and audit logging

**Tasks:**
- [ ] Implement SecurityMiddleware class
- [ ] Add access control functions (`check_file_access`, `check_folder_access`)
- [ ] Implement operation validation (`validate_file_operation`)
- [ ] Add JWT authentication to all endpoints
- [ ] Add RBAC permission checks (Gate 2)
- [ ] Implement audit logging (file operations, shares, memory sync)
- [ ] Create structured JSON audit logs
- [ ] Add security tests (access denied, unauthorized, etc.)

**Success Criteria:**
- ✅ All endpoints require authentication
- ✅ Unauthorized access returns 401/403
- ✅ Audit logs capture all operations
- ✅ Security tests pass (100%)

---

### Phase 8: Frontend UI (Week 5)

**Goal:** Build file manager interface in Next.js

**Tasks:**
- [ ] Create `/storage` page (`page.tsx`)
- [ ] Implement `useStorage` hook (API calls)
- [ ] Build FileList component (grid/list views)
- [ ] Build FolderTree component (hierarchical navigation)
- [ ] Build FileUpload component (drag-and-drop)
- [ ] Build ShareDialog component (sharing modal)
- [ ] Build MemoryToggle component (memory icon button)
- [ ] Add file selection and bulk actions
- [ ] Implement search functionality
- [ ] Add loading states and error handling
- [ ] Create UI unit tests (React Testing Library)

**Success Criteria:**
- ✅ File manager UI loads and displays files
- ✅ User can navigate folders
- ✅ User can upload/download/delete files
- ✅ User can share files
- ✅ Memory icons shown correctly
- ✅ Grid/list view toggle works

---

### Phase 9: Testing & Deployment (Week 6)

**Goal:** Comprehensive testing and production deployment

**Tasks:**
- [ ] Write unit tests for all models (File, Folder, etc.)
- [ ] Write unit tests for all adapters (MinIO)
- [ ] Write unit tests for all API endpoints
- [ ] Write E2E tests (upload → download → verify)
- [ ] Write E2E tests for sharing workflow
- [ ] Write E2E tests for memory integration
- [ ] Add performance tests (upload/download benchmarks)
- [ ] Create docker-compose configuration for storage service
- [ ] Add MinIO service to docker-compose.yml
- [ ] Update API Gateway to proxy `/api/storage/*` to storage-service
- [ ] Create deployment documentation
- [ ] Run full test suite (target: 95%+ pass rate)
- [ ] Deploy to staging environment
- [ ] Verify health checks pass
- [ ] Load test with 100 concurrent users

**Success Criteria:**
- ✅ 95%+ test pass rate (target: 100%)
- ✅ All E2E scenarios pass
- ✅ Storage service deployed and healthy
- ✅ MinIO bucket created with policies
- ✅ No critical bugs in production

---

### Implementation Timeline

| Phase | Duration | Dependencies | Success Rate Target |
|--------|-----------|--------------|-------------------|
| 1: Foundation | 5 days | 1 | 100% (no complex logic) |
| 2: MinIO Integration | 5 days | 1 | 100% (simple CRUD) |
| 3: Folder Management | 5 days | 1, 2 | 100% (standard CRUD) |
| 4: File Operations | 5 days | 2, 3 | 100% (standard CRUD) |
| 5: Memory Synchronization | 5 days | 4 | 95% (backend integration) |
| 6: Sharing System | 5 days | 4, 5, 6 | 95% (access control complexity) |
| 7: Security & Access Control | 5 days | 4, 5, 6 | 100% (middleware pattern) |
| 8: Frontend UI | 5 days | 1-7 | 95% (React complexity) |
| 9: Testing & Deployment | 5 days | 1-8 | 95% (comprehensive testing) |
| **Total** | **9 weeks** | - | **95%+ overall** |

---

## Test Coverage Targets

| Test Type | Target |
|----------|---------|
| Unit Tests (Models) | 100% |
| Unit Tests (Adapters) | 100% |
| Unit Tests (API Routes) | 100% |
| Unit Tests (Security) | 100% |
| E2E Tests (Upload/Download) | 100% |
| E2E Tests (Sharing) | 100% |
| E2E Tests (Memory Integration) | 100% |
| E2E Tests (Folder Navigation) | 100% |
| **Total Target** | **100%** |

---

## Open Questions & Future Work

### Questions for Implementation Planning

1. **Workspace Storage:** How should workspace storage integrate with user personal storage? (Topic #20 will address this)
2. **File Versioning:** Should we implement file versioning (backup versions on edit) or overwrite?
3. **Thumbnail Generation:** Should we generate thumbnails for images/documents (background task)?
4. **Quota Enforcement:** Should we enforce storage quotas per user (e.g., 10GB per user)?
5. **Compression:** Should we compress files before upload to save storage space?

### Deferred to Future Topics

- **Topic #20 (Projects/Spaces):** Workspace storage and project folder structure
- **Topic #21 (Universal Integration):** CLI-Anything wrapper for external software integration
- **Topic #24 (Third-Party Apps UI):** Dynamic UI generation using CopilotKit/AG-UI/A2UI

---

## Success Criteria

Storage Service is complete when:

- [ ] Users can upload/download files via file manager UI
- [ ] Users can create/navigate/delete folders
- [ ] Users can share files with other users
- [ ] Files can be added to/removed from long-term memory
- [ ] Memory icons shown correctly on files in memory
- [ ] File re-embedded automatically when content changes
- [ ] All security gates enforced (JWT + RBAC + storage ACL)
- [ ] Audit logs capture all file operations
- [ ] MinIO storage backend operational with correct policies
- [ ] 95%+ test pass rate (100% target)
- [ ] Storage service deployed to production
- [ ] Scalable to 2000-3000 users (275 MB database, 2TB MinIO)

---

**Last Updated:** 2026-03-14
