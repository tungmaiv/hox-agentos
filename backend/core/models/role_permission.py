"""
RolePermission ORM model -- replaces hardcoded ROLE_PERMISSIONS dict.

Stores the role-to-permission mapping in the database so it can be managed
via the admin API. Seeded with the exact values from security/rbac.py
ROLE_PERMISSIONS dict during migration 014.

Design:
- role: Keycloak realm role name (e.g. "employee", "it-admin")
- permission: permission string (e.g. "tool:email", "sandbox:execute")
- UNIQUE(role, permission): one entry per role+permission pair
- Index on role for fast lookup
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class RolePermission(Base):
    """Database-backed role-to-permission mapping."""

    __tablename__ = "role_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    permission: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("role", "permission", name="uq_role_permission"),
        Index("ix_role_permissions_role", "role"),
    )
