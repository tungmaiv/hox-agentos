"""
AgentDefinition ORM model -- registry entry for an agent type.

Stores metadata for each registered agent (master, email, calendar, project, etc.)
including handler module/function for dispatch, routing keywords for intent matching,
and version/status tracking for multi-version management.

Design:
- id: UUID primary key
- name: machine-readable identifier (e.g. "email_agent")
- display_name: human-readable label (e.g. "Email Agent")
- version: semver string, default "1.0.0"
- is_active: only one version per name should be active at a time
- last_seen_at: updated on each successful invocation (stale detection)
- UNIQUE(name, version): allows multiple versions of the same agent
- handler_module + handler_function: Python import path for dispatch
- routing_keywords: JSON list of keywords for intent-based routing
- config_json: arbitrary JSONB for type-specific settings
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, JSON, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base

# JSON type compatible with both SQLite (tests) and PostgreSQL (production)
_JSONB = JSON().with_variant(JSONB(), "postgresql")


class AgentDefinition(Base):
    """Registry entry for a single agent type."""

    __tablename__ = "agent_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'1.0.0'")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'active'")
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    handler_module: Mapped[str | None] = mapped_column(Text, nullable=True)
    handler_function: Mapped[str | None] = mapped_column(Text, nullable=True)
    routing_keywords: Mapped[list[Any] | None] = mapped_column(
        _JSONB, nullable=True
    )
    config_json: Mapped[dict[str, Any] | None] = mapped_column(
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

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_agent_name_version"),
    )
