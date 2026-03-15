"""
UserNotification — per-user notification model for share and system events.

First consumer: file/folder share notifications (Phase 28, STOR-04).
Designed for reuse by: Phase 30+ notification bell, skill sharing alerts.

Visible only to the recipient user (user_id from JWT — no FK since users live in Keycloak).
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class UserNotification(Base):
    """
    A notification delivered to a specific user.

    notification_type: "file_shared", "folder_shared", "skill_available", etc.
    metadata_json: plain Text (JSON string) for extra data — avoids JSONB for SQLite test compat.
    No FK on user_id — users live in Keycloak, not PostgreSQL.
    """

    __tablename__ = "user_notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
