"""StorageFile ORM model — metadata record for files stored in MinIO."""
import datetime
import uuid

from datetime import timezone as _tz

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from core.db import Base


class StorageFile(Base):
    """Metadata for a user-owned file stored in MinIO.

    - ``object_key``: MinIO path, generated as ``users/{owner_user_id}/{id}``
    - ``content_hash``: SHA-256 hex digest — used for deduplication (STOR-03)
    - ``in_memory``: True when file content is indexed in pgvector memory (STOR-05)
    """

    __tablename__ = "storage_files"

    id: uuid.UUID = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_user_id: uuid.UUID = Column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    folder_id: uuid.UUID | None = Column(
        PGUUID(as_uuid=True),
        ForeignKey("storage_folders.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: str = Column(String(255), nullable=False)
    object_key: str = Column(String(500), nullable=False)
    content_hash: str = Column(String(64), nullable=False, index=True)
    mime_type: str = Column(String(200), nullable=False)
    size_bytes: int = Column(BigInteger, nullable=False)
    in_memory: bool = Column(Boolean, nullable=False, default=False)
    created_at: datetime.datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(_tz.utc),
        nullable=False,
    )
    updated_at: datetime.datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(_tz.utc),
        onupdate=lambda: datetime.datetime.now(_tz.utc),
        nullable=False,
    )
