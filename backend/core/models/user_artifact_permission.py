"""
UserArtifactPermission ORM model -- per-user overrides beyond role defaults.

Allows individual users to be granted or denied access to specific artifacts
beyond what their role-level permissions dictate. Supports the same staged
apply model as ArtifactPermission.

Design:
- artifact_type: "agent" | "tool" | "skill" | "mcp_server"
- artifact_id: UUID of the artifact (no FK -- polymorphic)
- user_id: UUID from Keycloak JWT (no FK -- users in Keycloak, not PostgreSQL)
- allowed: True = grant override, False = deny override
- status: "pending" (staged) | "active" (applied)
- UNIQUE(artifact_type, artifact_id, user_id): one override per artifact+user
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class UserArtifactPermission(Base):
    """Per-user permission override for a registry artifact."""

    __tablename__ = "user_artifact_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    artifact_type: Mapped[str] = mapped_column(String(20), nullable=False)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False  # No FK -- polymorphic
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False  # No FK -- Keycloak
    )
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
            "artifact_type", "artifact_id", "user_id",
            name="uq_user_artifact_perm_type_id_user",
        ),
        Index("ix_user_artifact_perm_type_id", "artifact_type", "artifact_id"),
    )
