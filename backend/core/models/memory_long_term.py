"""
Long-term memory ORM models: MemoryEpisode and MemoryFact.

MemoryEpisode: Summarized conversation snapshots with 1024-dim bge-m3 embeddings.
MemoryFact: Persistent user facts extracted from conversations.
  - superseded_at: soft-delete timestamp for conflict resolution (old fact not deleted,
    just marked superseded when a newer fact replaces it).

SECURITY INVARIANT:
All queries must be parameterized on user_id from JWT — never from user input.
Both tables have ix_*_user_id indexes to enforce isolation efficiently.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class MemoryEpisode(Base):
    """
    Summarized episode of a conversation, stored with its bge-m3 embedding.
    Created by the summarize_episode Celery task after a conversation ends.
    """

    __tablename__ = "memory_episodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MemoryFact(Base):
    """
    A durable fact about a user extracted from conversation context.

    Conflict resolution: when a new fact supersedes an old one (e.g. user changed
    their preference), the old row's superseded_at is set to now() rather than
    deleting it. This preserves history and enables rollback/audit.
    """

    __tablename__ = "memory_facts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
