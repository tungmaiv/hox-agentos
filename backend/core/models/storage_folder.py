"""StorageFolder ORM model — virtual folder hierarchy for user files."""
import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from core.db import Base


class StorageFolder(Base):
    """A named folder that groups StorageFile records.

    Folders are per-user (owner_user_id — no FK, users live in Keycloak).
    Supports arbitrary nesting via parent_folder_id self-reference.
    """

    __tablename__ = "storage_folders"

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
    name: str = Column(String(255), nullable=False)
    parent_folder_id: uuid.UUID | None = Column(
        PGUUID(as_uuid=True),
        ForeignKey("storage_folders.id", ondelete="CASCADE"),
        nullable=True,
    )
    created_at: datetime.datetime = Column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        nullable=False,
    )
    updated_at: datetime.datetime = Column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )
