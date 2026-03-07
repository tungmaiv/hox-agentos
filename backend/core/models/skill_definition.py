"""
SkillDefinition ORM model -- registry entry for a skill.

Stores metadata for each registered skill (instructional or procedural).
Instructional skills provide markdown instructions; procedural skills define
multi-step JSON procedures with input/output schemas.

Design:
- skill_type: "instructional" | "procedural" (String, not enum for SQLite compat)
- slash_command: unique nullable -- enables /command invocation from chat
- source_type: "builtin" | "imported" | "user_created"
- instruction_markdown: populated for instructional skills
- procedure_json: populated for procedural skills
- security_score / security_report: populated after security review
- UNIQUE(name, version): allows multiple versions of the same skill
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base

_JSONB = JSON().with_variant(JSONB(), "postgresql")


class SkillDefinition(Base):
    """Registry entry for a single skill (instructional or procedural)."""

    __tablename__ = "skill_definitions"

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
    skill_type: Mapped[str] = mapped_column(
        String(20), nullable=False  # "instructional" | "procedural"
    )
    slash_command: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'builtin'")
    )
    instruction_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    procedure_json: Mapped[dict[str, Any] | None] = mapped_column(
        _JSONB, nullable=True
    )
    input_schema: Mapped[dict[str, Any] | None] = mapped_column(
        _JSONB, nullable=True
    )
    output_schema: Mapped[dict[str, Any] | None] = mapped_column(
        _JSONB, nullable=True
    )
    # ── agentskills.io standard metadata fields ──────────────────────────────
    license: Mapped[str | None] = mapped_column(Text, nullable=True)
    compatibility: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        _JSONB, nullable=True
    )
    allowed_tools: Mapped[list[str] | None] = mapped_column(
        _JSONB, nullable=True
    )
    tags: Mapped[list[str] | None] = mapped_column(_JSONB, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    security_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    security_report: Mapped[dict[str, Any] | None] = mapped_column(
        _JSONB, nullable=True
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
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
        UniqueConstraint("name", "version", name="uq_skill_name_version"),
    )
