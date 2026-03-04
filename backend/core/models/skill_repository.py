"""
SkillRepository ORM model -- registry entry for a remote skill repository.

Stores the URL and metadata for each external skill repository
(e.g., a Skill Store, a team repository, or a company-internal collection).
The cached_index column stores the last fetched skill index as JSONB.

Design:
- id: UUID primary key
- name: unique machine-readable identifier (e.g. "blitz-official")
- url: URL to the skill repository index (JSON endpoint)
- description: human-readable description (nullable)
- is_active: feature flag -- inactive repositories are not synced
- last_synced_at: timestamp of last successful sync (nullable until first sync)
- cached_index: JSONB blob of the fetched skill index (nullable until first sync)
- created_at: immutable timestamp set on insert
- updated_at: auto-maintained via DB trigger or onupdate
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, JSON, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base

_JSONB = JSON().with_variant(JSONB(), "postgresql")


class SkillRepository(Base):
    """Registry entry for a remote skill repository."""

    __tablename__ = "skill_repositories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cached_index: Mapped[dict[str, Any] | None] = mapped_column(
        _JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
