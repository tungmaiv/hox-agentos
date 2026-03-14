# Storage Service Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a scalable, dedicated storage service for AgentOS with MinIO integration, file/folder management, sharing, and long-term memory synchronization.

**Architecture:** architect-01 - Dedicated storage microservice (port 8001) + MCP-inspired storage adapter pattern (MinIO default, S3/Azure future) + shared PostgreSQL database for file/folder/metadata.

**Tech Stack:**
- FastAPI 0.115+ (Python 3.10+)
- MinIO (latest) - S3-compatible object storage
- PostgreSQL 16+ with pgvector (shared with backend)
- SQLAlchemy 2.0+ async ORM
- Pydantic v2 for validation
- Python 3.10+ with type hints
- bge-m3 (1024-dim) for memory embedding
- Next.js 15+ for frontend UI

---

## Phase 1: Foundation (Week 1)

### Task 1: Create storage service directory structure

**Files:**
- Create: `backend/storage-service/__init__.py`
- Create: `backend/storage-service/models.py`
- Create: `backend/storage-service/schemas.py`
- Create: `backend/storage-service/config.py`
- Create: `backend/storage-service/main.py`
- Create: `backend/storage-service/routes.py`
- Create: `backend/storage-service/adapters/__init__.py`
- Create: `backend/storage-service/adapters/base.py`
- Create: `backend/storage-service/adapters/factory.py`

**Step 1: Write directory structure**

```python
# backend/storage-service/__init__.py
from .main import app

# backend/storage-service/config.py
from pydantic_settings import BaseSettings

class StorageServiceSettings(BaseSettings):
    STORAGE_ADAPTER: str = "minio"
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str = "agentos-storage"
    DATABASE_URL: str

settings = StorageServiceSettings()
```

**Step 2: Run test to verify directory created**

```bash
ls backend/storage-service/
```

Expected: List of created files

**Step 3: Commit**

```bash
git add backend/storage-service/
git commit -m "feat(19-01): create storage service directory structure"
```

---

### Task 2: Implement database models

**Files:**
- Modify: `backend/storage-service/models.py`

**Step 1: Write failing test for File model**

```python
# backend/storage-service/tests/test_models.py
import pytest
from sqlalchemy import select
from backend.storage_service.models import File, FileStatus, FileShare, SharePermission, Folder, FolderType

def test_file_model_creation():
    """Test File model can be instantiated"""
    file = File(
        bucket_path="registry/test/file.txt",
        owner_type="user",
        owner_id="test-uuid",
        original_name="test.txt",
        mime_type="text/plain",
        size=100,
        hash="abc123",
        status=FileStatus.ACTIVE,
    )
    assert file.bucket_path == "registry/test/file.txt"
    assert file.owner_type == "user"
```

**Step 2: Run test to verify it fails**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_models.py::test_file_model_creation -v
```

Expected: PASS (models can be imported)

**Step 3: Write full database models**

```python
# backend/storage-service/models.py
from sqlalchemy import Column, String, BigInteger, DateTime, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from enum import Enum
import uuid
from datetime import datetime

class FileStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"

class FolderType(str, Enum):
    PERSONAL = "personal"
    SHARED = "shared"
    PROJECT = "project"

class SharePermission(str, Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"

from backend.core.db import Base

class File(Base):
    __tablename__ = "files"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bucket_path = Column(String, nullable=False, unique=True)
    owner_type = Column(String, nullable=False)
    owner_id = Column(UUID(as_uuid=True), nullable=False)
    original_name = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size = Column(BigInteger, nullable=False)
    hash = Column(String, nullable=False, index=True)
    status = Column(SQLEnum(FileStatus), default=FileStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    folder_links = relationship("FileFolderLink", back_populates="file", cascade="all, delete-orphan")
    shares = relationship("FileShare", back_populates="file", cascade="all, delete-orphan")
    memory_links = relationship("MemoryFileLink", back_populates="file", cascade="all, delete-orphan")
    __table_args__ = (
        Index("ix_files_owner", "owner_type", "owner_id"),
        Index("ix_files_status", "status"),
        Index("ix_files_created_at", "created_at"),
    )

class Folder(Base):
    __tablename__ = "folders"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("folders.id"), nullable=True)
    parent = relationship("Folder", remote_side=[id], backref="children")
    owner_type = Column(String, nullable=False)
    owner_id = Column(UUID(as_uuid=True), nullable=False)
    name = Column(String, nullable=False)
    folder_type = Column(SQLEnum(FolderType), default=FolderType.PERSONAL, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    file_links = relationship("FileFolderLink", back_populates="folder", cascade="all, delete-orphan")
    __table_args__ = (
        Index("ix_folders_owner", "owner_type", "owner_id"),
        Index("ix_folders_parent", "parent_id"),
        Index("ix_folders_type", "folder_type"),
    )

class FileFolderLink(Base):
    __tablename__ = "file_folder_links"
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    folder_id = Column(UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    file = relationship("File", back_populates="folder_links")
    folder = relationship("Folder", back_populates="file_links")

class FileShare(Base):
    __tablename__ = "file_shares"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    owner_type = Column(String, nullable=False)
    owner_id = Column(UUID(as_uuid=True), nullable=False)
    recipient_type = Column(String, nullable=False)
    recipient_id = Column(UUID(as_uuid=True), nullable=False)
    permission = Column(SQLEnum(SharePermission), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    file = relationship("File", back_populates="shares")
    __table_args__ = (
        Index("ix_file_shares_file", "file_id"),
        Index("ix_file_shares_recipient", "recipient_type", "recipient_id"),
        Index("ix_file_shares_owner", "owner_type", "owner_id"),
    )

class MemoryFileLink(Base):
    __tablename__ = "memory_file_links"
    memory_record_id = Column(UUID(as_uuid=True), ForeignKey("memory_records.id", ondelete="CASCADE"), primary_key=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    file = relationship("File", back_populates="memory_links")
    __table_args__ = (
        Index("ix_memory_file_links_memory", "memory_record_id"),
        Index("ix_memory_file_links_file", "file_id"),
    )
```

**Step 4: Run test to verify it passes**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_models.py::test_file_model_creation -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/storage-service/models.py
git commit -m "feat(19-02): implement storage database models"
```

---

### Task 3: Create Alembic migration

**Files:**
- Create: `backend/storage-service/alembic/versions/001_create_storage_tables.py`

**Step 1: Write migration file**

```python
# backend/storage-service/alembic/versions/001_create_storage_tables.py
"""create storage tables

Revision ID: 001_create_storage_tables
Revises: 
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_create_storage_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'files',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('bucket_path', sa.String(), nullable=False, unique=True),
        sa.Column('owner_type', sa.String(), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('original_name', sa.String(), nullable=False),
        sa.Column('mime_type', sa.String(), nullable=False),
        sa.Column('size', sa.BigInteger(), nullable=False),
        sa.Column('hash', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    
    # Create indexes for files
    op.create_index('ix_files_owner', 'files', ['owner_type', 'owner_id'])
    op.create_index('ix_files_status', 'files', ['status'])
    op.create_index('ix_files_created_at', 'files', ['created_at'])
    
    # Create folders table
    op.create_table(
        'folders',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('owner_type', sa.String(), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('folder_type', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    
    # Create indexes for folders
    op.create_index('ix_folders_owner', 'folders', ['owner_type', 'owner_id'])
    op.create_index('ix_folders_parent', 'folders', ['parent_id'])
    op.create_index('ix_folders_type', 'folders', ['folder_type'])
    
    # Create file_folder_links table
    op.create_table(
        'file_folder_links',
        sa.Column('file_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('folder_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    
    # Create file_shares table
    op.create_table(
        'file_shares',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_type', sa.String(), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('recipient_type', sa.String(), nullable=False),
        sa.Column('recipient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('permission', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    
    # Create indexes for file_shares
    op.create_index('ix_file_shares_file', 'file_shares', ['file_id'])
    op.create_index('ix_file_shares_recipient', 'file_shares', ['recipient_type', 'recipient_id'])
    op.create_index('ix_file_shares_owner', 'file_shares', ['owner_type', 'owner_id'])
    
    # Create memory_file_links table
    op.create_table(
        'memory_file_links',
        sa.Column('memory_record_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('file_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    
    # Create indexes for memory_file_links
    op.create_index('ix_memory_file_links_memory', 'memory_file_links', ['memory_record_id'])
    op.create_index('ix_memory_file_links_file', 'memory_file_links', ['file_id'])


def downgrade():
    op.drop_table('memory_file_links')
    op.drop_table('file_shares')
    op.drop_table('file_folder_links')
    op.drop_table('folders')
    op.drop_table('files')
```

**Step 2: Apply migration**

```bash
cd backend
PYTHONPATH=. .venv/bin/alembic upgrade head
```

Expected: SUCCESS message

**Step 3: Commit**

```bash
git add backend/storage-service/alembic/versions/001_create_storage_tables.py
git commit -m "feat(19-03): create alembic migration for storage tables"
```

---

### Task 4: Set up FastAPI app skeleton

**Files:**
- Modify: `backend/storage-service/main.py`
- Modify: `backend/storage-service/routes.py`

**Step 1: Write failing test for health endpoint**

```python
# backend/storage-service/tests/test_main.py
import pytest
from fastapi.testclient import TestClient
from backend.storage_service.main import app

def test_health_endpoint():
    """Test health endpoint returns 200"""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "storage-service"}
```

**Step 2: Run test to verify it fails**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_main.py::test_health_endpoint -v
```

Expected: FAIL with "module not found"

**Step 3: Write FastAPI app skeleton**

```python
# backend/storage-service/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

logger = structlog.get_logger(__name__)

app = FastAPI(
    title="AgentOS Storage Service",
    version="1.0.0",
    description="Dedicated storage service for AgentOS",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "service": "storage-service"}


@app.on_event("startup")
async def startup_event():
    logger.info("Storage service starting up")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Storage service shutting down")
```

**Step 4: Run test to verify it passes**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_main.py::test_health_endpoint -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/storage-service/main.py
git commit -m "feat(19-04): set up FastAPI app skeleton"
```

---

### Task 5: Add storage service configuration

**Files:**
- Modify: `backend/storage-service/config.py`

**Step 1: Write failing test for configuration**

```python
# backend/storage-service/tests/test_config.py
import pytest
from backend.storage_service.config import settings

def test_configuration_defaults():
    """Test default configuration values"""
    assert settings.STORAGE_ADAPTER == "minio"
    assert settings.MINIO_BUCKET == "agentos-storage"
    assert settings.MINIO_ENDPOINT == "minio:9000"
```

**Step 2: Run test to verify it fails**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_config.py::test_configuration_defaults -v
```

Expected: FAIL with "module not found"

**Step 3: Write configuration module**

```python
# backend/storage-service/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class StorageServiceSettings(BaseSettings):
    """Storage service configuration"""
    
    # Storage adapter selection
    STORAGE_ADAPTER: str = "minio"
    
    # MinIO config
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str = "agentos-storage"
    MINIO_USE_SSL: bool = False
    
    # AWS S3 config (future)
    AWS_REGION: Optional[str] = None
    AWS_ACCESS_KEY: Optional[str] = None
    AWS_SECRET_KEY: Optional[str] = None
    S3_BUCKET: Optional[str] = None
    
    # Azure Blob Storage config (future)
    AZURE_CONNECTION_STRING: Optional[str] = None
    AZURE_CONTAINER: Optional[str] = None
    
    # Database config (shared with backend)
    DATABASE_URL: str = "postgresql+asyncpg://blitz:password@postgres/blitz"
    
    # Backend service URL (for memory sync)
    BACKEND_URL: str = "http://backend:8000"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = StorageServiceSettings()
```

**Step 4: Run test to verify it passes**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_config.py::test_configuration_defaults -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/storage-service/config.py
git commit -m "feat(19-05): add storage service configuration"
```

---

### Task 6: Create base StorageAdapter protocol

**Files:**
- Modify: `backend/storage-service/adapters/base.py`

**Step 1: Write failing test for adapter protocol**

```python
# backend/storage-service/tests/test_adapters.py
import pytest
from backend.storage_service.adapters.base import StorageAdapter

def test_adapter_protocol_exists():
    """Test StorageAdapter protocol exists"""
    assert hasattr(StorageAdapter, '__protocol__')
```

**Step 2: Run test to verify it fails**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_adapters.py::test_adapter_protocol_exists -v
```

Expected: FAIL with "module not found"

**Step 3: Write adapter protocol**

```python
# backend/storage-service/adapters/base.py
from typing import Protocol, Optional, Dict
from io import BytesIO


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
        metadata: Optional[Dict[str, str]] = None,
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
    
    async def get_metadata(self, object_key: str) -> Dict[str, str]:
        """Get file metadata (size, etag, last_modified)"""
        ...
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        ...
```

**Step 4: Run test to verify it passes**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_adapters.py::test_adapter_protocol_exists -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/storage-service/adapters/base.py
git commit -m "feat(19-06): create base storage adapter protocol"
```

---

### Task 7: Set up database session factory

**Files:**
- Modify: `backend/storage-service/main.py`

**Step 1: Write failing test for database session**

```python
# backend/storage-service/tests/test_main.py
import pytest
from fastapi.testclient import TestClient
from backend.storage_service.main import app
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

def test_database_connection():
    """Test database connection works"""
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_main.py::test_database_connection -v
```

Expected: PASS

**Step 3: Add database session factory to main.py**

```python
# backend/storage-service/main.py (add to existing)
from backend.core.db import async_session_maker

# Import models
from backend.storage_service.models import File, Folder, FileFolderLink, FileShare, MemoryFileLink

# Add routes placeholder
from backend.storage_service import routes

app.include_router(routes.router, prefix="/api/storage")
```

**Step 4: Run test to verify it passes**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_main.py::test_database_connection -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/storage-service/main.py
git commit -m "feat(19-07): set up database session factory"
```

---

## Phase 2: MinIO Integration (Week 1)

### Task 8: Implement MinIO adapter

**Files:**
- Create: `backend/storage-service/adapters/minio.py`

**Step 1: Write failing test for MinIO adapter**

```python
# backend/storage-service/tests/test_minio_adapter.py
import pytest
from backend.storage_service.adapters.minio import MinIOStorageAdapter
from io import BytesIO

def test_minio_adapter_initialization():
    """Test MinIO adapter can be initialized"""
    adapter = MinIOStorageAdapter(
        endpoint="http://localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="test-bucket",
    )
    assert adapter.adapter_name == "minio"
    assert "upload" in adapter.supported_operations
```

**Step 2: Run test to verify it fails**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_minio_adapter.py::test_minio_adapter_initialization -v
```

Expected: FAIL with "module not found"

**Step 3: Write MinIO adapter implementation**

```python
# backend/storage-service/adapters/minio.py
from minio import Minio, MinioException
from datetime import timedelta
from io import BytesIO
from typing import Optional, Dict
from backend.storage_service.adapters.base import StorageAdapter


class MinIOStorageAdapter:
    """MinIO storage adapter (default for AgentOS)"""
    
    adapter_name = "minio"
    supported_operations = ["upload", "download", "delete", "exists", "get_url", "get_metadata"]
    
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, use_ssl: bool = False):
        self.client = Minio(endpoint, access_key, secret_key, secure=use_ssl)
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
        metadata: Optional[Dict[str, str]] = None,
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
    
    async def download(self, object_key: str) -> BytesIO:
        """Download file from MinIO"""
        try:
            response = self.client.get_object(self.bucket, object_key)
            content = BytesIO(response.read())
            content.seek(0)
            return content
        except MinioException as e:
            raise RuntimeError(f"MinIO download failed: {e}")
    
    async def delete(self, object_key: str) -> None:
        """Delete file from MinIO"""
        try:
            self.client.remove_object(self.bucket, object_key)
        except MinioException as e:
            raise RuntimeError(f"MinIO delete failed: {e}")
    
    async def exists(self, object_key: str) -> bool:
        """Check if file exists in MinIO"""
        try:
            self.client.stat_object(self.bucket, object_key)
            return True
        except MinioException:
            return False
    
    async def get_url(self, object_key: str, expires: int = 3600) -> str:
        """Generate presigned URL (expires in seconds)"""
        try:
            url = self.client.presigned_get_object(
                bucket_name=self.bucket,
                object_name=object_key,
                expires=timedelta(seconds=expires),
            )
            return url
        except MinioException as e:
            raise RuntimeError(f"MinIO URL generation failed: {e}")
    
    async def get_metadata(self, object_key: str) -> Dict[str, str]:
        """Get file metadata from MinIO"""
        try:
            stat = self.client.stat_object(self.bucket, object_key)
            return {
                "size": stat.size,
                "etag": stat.etag,
                "last_modified": stat.last_modified.isoformat(),
                "content_type": stat.content_type,
                "metadata": stat.metadata or {},
            }
        except MinioException as e:
            raise RuntimeError(f"MinIO metadata fetch failed: {e}")
    
    async def cleanup(self) -> None:
        """MinIO client doesn't need cleanup"""
        pass
    
    async def _bucket_exists(self) -> bool:
        """Check if bucket exists"""
        try:
            self.client.bucket_exists(self.bucket)
            return True
        except MinioException:
            return False
```

**Step 4: Run test to verify it passes**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_minio_adapter.py::test_minio_adapter_initialization -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/storage-service/adapters/minio.py
git commit -m "feat(19-08): implement MinIO storage adapter"
```

---

### Task 9: Create adapter factory

**Files:**
- Modify: `backend/storage-service/adapters/factory.py`

**Step 1: Write failing test for adapter factory**

```python
# backend/storage-service/tests/test_factory.py
import pytest
from backend.storage_service.adapters.factory import get_storage_adapter, list_storage_adapters

def test_list_storage_adapters():
    """Test storage adapters can be listed"""
    adapters = list_storage_adapters()
    assert "minio" in adapters
    assert isinstance(adapters, list)
```

**Step 2: Run test to verify it fails**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_factory.py::test_list_storage_adapters -v
```

Expected: FAIL with "module not found"

**Step 3: Write adapter factory implementation**

```python
# backend/storage-service/adapters/factory.py
from typing import Dict, Type
from backend.storage_service.adapters.base import StorageAdapter
from backend.storage_service.adapters.minio import MinIOStorageAdapter
from backend.storage_service.config import settings


# Adapter registry
_STORAGE_ADAPTERS: Dict[str, Type[StorageAdapter]] = {
    "minio": MinIOStorageAdapter,
}


def get_storage_adapter(name: str, config: Dict[str, str]) -> StorageAdapter:
    """Get storage adapter instance by name"""
    if name not in _STORAGE_ADAPTERS:
        raise ValueError(f"Unknown storage adapter: {name}")
    
    adapter_class = _STORAGE_ADAPTERS[name]
    return adapter_class(**config)


def list_storage_adapters() -> list[str]:
    """List all registered storage adapters"""
    return list(_STORAGE_ADAPTERS.keys())
```

**Step 4: Run test to verify it passes**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_factory.py::test_list_storage_adapters -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/storage-service/adapters/factory.py
git commit -m "feat(19-09): create storage adapter factory"
```

---

### Task 10: Set up MinIO Docker service

**Files:**
- Modify: `docker-compose.yml`
- Create: `infra/minio/policies/registry-read.json`
- Create: `infra/minio/policies/registry-write.json`

**Step 1: Write MinIO policies**

```json
// infra/minio/policies/registry-read.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": ["arn:aws:s3:::agentos-storage"],
      "Condition": {
        "StringLike": {
          "s3:prefix": ["registry/file-*"]
        }
      }
    }
  ]
}
```

```json
// infra/minio/policies/registry-write.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:DeleteObject"],
      "Resource": ["arn:aws:s3:::agentos-storage/registry/file-*"]
    }
  ]
}
```

**Step 2: Update docker-compose.yml**

```yaml
# docker-compose.yml (add MinIO service)
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY}
    volumes:
      - minio-data:/data
      - ./infra/minio/policies:/policies:readonly
    networks:
      - agentos
```

**Step 3: Test MinIO starts**

```bash
docker-compose up minio -d
docker ps | grep minio
```

Expected: MinIO container running

**Step 4: Commit**

```bash
git add docker-compose.yml infra/minio/
git commit -m "feat(19-10): add MinIO service to docker-compose"
```

---

### Task 11: Implement file download endpoint

**Files:**
- Modify: `backend/storage-service/routes.py`

**Step 1: Write failing test for download endpoint**

```python
# backend/storage-service/tests/test_routes.py
import pytest
from fastapi.testclient import TestClient
from backend.storage_service.main import app

def test_file_download_redirects():
    """Test file download returns redirect"""
    with TestClient(app) as client:
        response = client.get("/api/storage/files/test-id/download")
        assert response.status_code == 307  # Temporary redirect
```

**Step 2: Run test to verify it fails**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_routes.py::test_file_download_redirects -v
```

Expected: FAIL with "404 Not Found"

**Step 3: Implement download endpoint**

```python
# backend/storage-service/routes.py
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/storage")


# Storage dependency
def get_storage():
    """FastAPI dependency to get storage adapter instance"""
    from backend.storage_service.adapters.factory import get_storage_adapter
    from backend.storage_service.config import settings
    
    config = {
        "endpoint": settings.MINIO_ENDPOINT,
        "access_key": settings.MINIO_ACCESS_KEY,
        "secret_key": settings.MINIO_SECRET_KEY,
        "bucket": settings.MINIO_BUCKET,
    }
    
    adapter = get_storage_adapter(settings.STORAGE_ADAPTER, config)
    
    # Initialize adapter if not already initialized
    import asyncio
    asyncio.run(adapter.initialize())
    
    return adapter


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: str,
    storage = Depends(get_storage),
    db: AsyncSession = Depends(async_session_maker),
):
    """Download file (redirect to presigned MinIO URL)"""
    from backend.storage_service.models import File
    from backend.security.deps import get_current_user_id
    
    user_id = await get_current_user_id()
    
    # Get file record
    file_uuid = file_id
    result = await db.execute(select(File).where(File.id == file_uuid))
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Generate presigned URL
    url = await storage.get_url(object_key=file.bucket_path, expires=3600)
    
    logger.info("File downloaded", file_id=file_id, user_id=str(user_id))
    
    return Response(status_code=307, headers={"Location": url})
```

**Step 4: Run test to verify it passes**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_routes.py::test_file_download_redirects -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/storage-service/routes.py
git commit -m "feat(19-11): implement file download endpoint"
```

---

### Task 12: Implement file upload endpoint

**Files:**
- Modify: `backend/storage-service/routes.py`
- Modify: `backend/storage-service/schemas.py`

**Step 1: Write failing test for upload endpoint**

```python
# backend/storage-service/tests/test_routes.py
def test_file_upload_requires_auth():
    """Test file upload requires authentication"""
    with TestClient(app) as client:
        from io import BytesIO
        files = {"file": ("test.txt", BytesIO(b"content"), "text/plain")}
        response = client.post("/api/storage/files/upload", files=files)
        assert response.status_code == 401
```

**Step 2: Run test to verify it fails**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_routes.py::test_file_upload_requires_auth -v
```

Expected: FAIL with "404 Not Found"

**Step 3: Write upload schemas**

```python
# backend/storage-service/schemas.py
from pydantic import BaseModel
from typing import Optional


class FileUploadResponse(BaseModel):
    file_id: str
    bucket_path: str
    original_name: str
    size: int
    mime_type: str
    created_at: str


class FileListResponse(BaseModel):
    files: list[FileUploadResponse]
    total: int
    page: int
    page_size: int
```

**Step 4: Implement upload endpoint**

```python
# backend/storage-service/routes.py (add to existing)
from fastapi import UploadFile
import hashlib
import uuid
from datetime import datetime

from backend.storage_service.schemas import FileUploadResponse
from backend.storage_service.models import File, FileFolderLink


@router.post("/files/upload", response_model=FileUploadResponse, status_code=201)
async def upload_file(
    file: UploadFile,
    folder_id: Optional[str] = None,
    storage = Depends(get_storage),
    db: AsyncSession = Depends(async_session_maker),
):
    """Upload file to personal storage or specific folder"""
    from backend.security.deps import get_current_user_id
    
    user_id = await get_current_user_id()
    
    # Validate folder ownership if specified
    if folder_id:
        from backend.storage_service.models import Folder
        result = await db.execute(select(Folder).where(Folder.id == folder_id))
        folder = result.scalar_one_or_none()
        if not folder or folder.owner_id != user_id:
            raise HTTPException(status_code=404, detail="Folder not found")
    
    # Calculate file hash (SHA-256 for deduplication)
    file_content = await file.read()
    file_hash = hashlib.sha256(file_content).hexdigest()
    
    # Check for duplicate (optional: skip or create new reference)
    result = await db.execute(
        select(File).where(File.hash == file_hash, File.status == "active")
    )
    existing_file = result.scalar_one_or_none()
    
    if existing_file:
        logger.info("Duplicate file detected, creating reference", file_hash=file_hash)
        file_record = existing_file
        file_id = str(existing_file.id)
    else:
        # Upload to MinIO
        object_key = f"registry/file-{uuid.uuid4()}/{file.filename}"
        url = await storage.upload(
            object_key=object_key,
            content=file_content,
            content_type=file.content_type or "application/octet-stream",
            metadata={"original_name": file.filename, "user_id": str(user_id)},
        )
        
        # Create File record
        from backend.storage_service.models import FileStatus
        file_record = File(
            bucket_path=object_key,
            owner_type="user",
            owner_id=user_id,
            original_name=file.filename,
            mime_type=file.content_type or "application/octet-stream",
            size=len(file_content),
            hash=file_hash,
            status=FileStatus.ACTIVE,
        )
        db.add(file_record)
        await db.commit()
        await db.refresh(file_record)
        file_id = str(file_record.id)
        
        # Link to folder (if specified)
        if folder_id:
            link = FileFolderLink(file_id=file_record.id, folder_id=folder_id)
            db.add(link)
            await db.commit()
    
    logger.info("File uploaded", file_id=file_id, user_id=str(user_id))
    
    return FileUploadResponse(
        file_id=file_id,
        bucket_path=file_record.bucket_path,
        original_name=file_record.original_name,
        size=file_record.size,
        mime_type=file_record.mime_type,
        created_at=file_record.created_at.isoformat(),
    )
```

**Step 5: Run test to verify it passes**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/test_routes.py::test_file_upload_requires_auth -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/storage-service/routes.py backend/storage-service/schemas.py
git commit -m "feat(19-12): implement file upload endpoint"
```

---

### Task 13: Add file upload/download E2E tests

**Files:**
- Create: `backend/storage-service/tests/e2e/test_file_operations.py`

**Step 1: Write failing test for file upload/download**

```python
# backend/storage-service/tests/e2e/test_file_operations.py
import pytest
import httpx
from io import BytesIO

def test_e2e_file_upload_and_download():
    """Test file upload and download end-to-end"""
    # This test requires MinIO to be running
    pass
```

**Step 2: Run test to verify it fails**

```bash
cd backend/storage-service
PYTHONPATH=. .venv/bin/pytest tests/e2e/test_file_operations.py::test_e2e_file_upload_and_download -v
```

Expected: PASS (skipped if MinIO not running)

**Step 3: Write E2E test implementation**

```python
# backend/storage-service/tests/e2e/test_file_operations.py
import pytest
import httpx
from io import BytesIO
import hashlib


@pytest.mark.e2e
@pytest.mark.skipif("not os.getenv('MINIO_URL')", reason="MinIO not configured")
def test_e2e_file_upload_and_download():
    """Test file upload and download end-to-end"""
    
    # Upload file
    minio_url = os.getenv('MINIO_URL', 'http://localhost:9000')
    minio_access_key = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
    minio_secret_key = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
    bucket = os.getenv('MINIO_BUCKET', 'agentos-storage')
    
    test_content = b"test file content"
    test_filename = "test.txt"
    test_hash = hashlib.sha256(test_content).hexdigest()
    object_key = f"registry/e2e/{test_filename}"
    
    # Upload to MinIO
    upload_url = f"{minio_url}/{bucket}/{object_key}"
    with httpx.Client() as client:
        response = client.put(
            upload_url,
            content=test_content,
            headers={
                "Content-Type": "text/plain",
                "x-amz-meta-original-name": test_filename,
            },
        )
        response.raise_for_status()
    
    # Download from MinIO
    with httpx.Client() as client:
        download_response = client.get(upload_url)
        download_response.raise_for_status()
        downloaded_content = download_response.content
    
    # Verify content
    assert downloaded_content == test_content
```

**Step 4: Run test to verify it passes**

```bash
cd backend/storage-service
MINIO_URL=http://localhost:9000 MINIO_ACCESS_KEY=minioadmin MINIO_SECRET_KEY=minioadmin MINIO_BUCKET=agentos-storage PYTHONPATH=. .venv/bin/pytest tests/e2e/test_file_operations.py::test_e2e_file_upload_and_download -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/storage-service/tests/e2e/
git commit -m "test(19-13): add file upload/download E2E tests"
```

---

## Remaining Phases Summary

**Phases 3-9 will follow the same TDD pattern:**

Each phase consists of:
- 3-5 bite-sized tasks
- Each task: failing test → verify fail → implement → verify pass → commit
- Target: 95%+ test pass rate
- Timeline: 7 weeks (Phase 3-9)

**Next Steps After Phase 2:**

1. **Phase 3 (Week 2):** Folder Management
   - Create/Read/Update/Delete folder endpoints
   - Folder hierarchy navigation
   - CASCADE delete validation

2. **Phase 4 (Week 2):** File Operations
   - List files endpoint
   - File metadata CRUD
   - Deduplication logic

3. **Phase 5 (Week 3):** Memory Synchronization
   - MemorySyncService class
   - Backend HTTP client
   - File embedding flow

4. **Phase 6 (Week 3):** Sharing System
   - Share CRUD endpoints
   - Access control checks
   - Share permission validation

5. **Phase 7 (Week 4):** Security & Access Control
   - SecurityMiddleware class
   - Three-gate security model
   - Audit logging

6. **Phase 8 (Week 5):** Frontend UI
   - Storage page component
   - FileList component
   - FolderTree component
   - FileUpload component
   - ShareDialog component
   - MemoryToggle component

7. **Phase 9 (Week 6):** Testing & Deployment
   - Unit tests (models, adapters, routes, security)
   - E2E tests (upload/download, sharing, memory, folders)
   - Performance tests
   - Docker Compose configuration
   - Staging deployment
   - Load testing (100 concurrent users)

**Implementation Guidelines:**

- **DRY:** Extract shared logic to utilities
- **YAGNI:** Don't add features beyond spec
- **TDD:** Write failing tests first, then implement
- **Frequent Commits:** Commit after each task
- **Atomic Commits:** One logical change per commit
- **Type Safety:** Full type annotations on all functions
- **Logging:** Use structlog for all operations
- **Error Handling:** Raise HTTPException with meaningful status codes

---

**Plan complete and saved to `docs/plans/2026-03-14-storage-service.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
