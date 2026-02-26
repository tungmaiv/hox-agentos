"""
SystemConfig ORM model — admin-scoped key/JSONB value store.

Used by GET /api/admin/config and PUT /api/admin/config/{key} to persist
system-wide feature flags and configuration (e.g. agent enable toggles,
embedding model selection, memory thresholds).

Design:
- key is the primary key (text) — e.g. "agent.email.enabled"
- value is JSONB — supports any JSON type (bool, int, str, dict)
- updated_at is set by the application on every write (via onupdate=func.now())
"""

from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class SystemConfig(Base):
    """Key/JSONB value store for admin-managed system configuration."""

    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
