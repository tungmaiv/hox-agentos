"""
AdminNotification — generic notification model for admin users.

First consumer: SSO health state transitions (Phase 26).
Designed for reuse by: skill activation (Phase 30), email system (Phase 33).

Visible to ALL admins (no user_id FK). Notifications are system-wide alerts.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class AdminNotification(Base):
    """
    System-wide notification for admin users.

    category: "sso_health", "skill_activation", "permission_request", etc.
    severity: "info", "warning", "critical"
    metadata_json: JSON string for extra data (plain Text — avoids JSONB for SQLite test compat).
    """

    __tablename__ = "admin_notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
