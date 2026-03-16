"""StorageShare ORM model — access grants for files and folders."""
import datetime
import uuid

from datetime import timezone as _tz

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from core.db import Base


class StorageShare(Base):
    """An access grant that allows shared_with_user_id to access a file or folder.

    Either ``file_id`` or ``folder_id`` must be set (but not necessarily both).
    - ``permission``: one of ``"READ"``, ``"WRITE"``, or ``"ADMIN"``
    """

    __tablename__ = "storage_shares"

    id: uuid.UUID = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    file_id: uuid.UUID | None = Column(
        PGUUID(as_uuid=True),
        ForeignKey("storage_files.id", ondelete="CASCADE"),
        nullable=True,
    )
    folder_id: uuid.UUID | None = Column(
        PGUUID(as_uuid=True),
        ForeignKey("storage_folders.id", ondelete="CASCADE"),
        nullable=True,
    )
    shared_with_user_id: uuid.UUID = Column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    shared_by_user_id: uuid.UUID = Column(
        PGUUID(as_uuid=True),
        nullable=False,
    )
    permission: str = Column(String(20), nullable=False)  # "READ" | "WRITE" | "ADMIN"
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
