"""
ArtifactPermission ORM model -- per-artifact per-role access control.

Replaces the old tool_acl table with a unified permission system that covers
all artifact types (agent, tool, skill, mcp_server). Supports a staged apply
model: permissions are written with status='pending' until admin confirms,
then set to status='active'.

Design:
- artifact_type: "agent" | "tool" | "skill" | "mcp_server"
- artifact_id: UUID of the artifact (no FK -- polymorphic across tables)
- role: Keycloak realm role name
- allowed: True = grant, False = deny
- status: "pending" (staged) | "active" (applied)
- UNIQUE(artifact_type, artifact_id, role): one permission per artifact+role
- Index on (artifact_type, artifact_id) for fast lookup
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class ArtifactPermission(Base):
    """Per-role permission for a registry artifact."""

    __tablename__ = "artifact_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    artifact_type: Mapped[str] = mapped_column(String(20), nullable=False)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False  # No FK -- polymorphic
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'active'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "artifact_type", "artifact_id", "role",
            name="uq_artifact_perm_type_id_role",
        ),
        Index("ix_artifact_perm_type_id", "artifact_type", "artifact_id"),
    )
