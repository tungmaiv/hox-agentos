# backend/core/models/user_preferences.py
"""SQLAlchemy ORM model for per-user LLM interaction preferences."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, JSON, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


# JSON type compatible with both SQLite (tests) and PostgreSQL (production)
_JSONB_type = JSON().with_variant(JSONB(), "postgresql")

# Default preferences applied when no row exists for a user
DEFAULT_PREFERENCES: dict = {
    "thinking_mode": False,
    "response_style": "concise",
}


class UserPreferences(Base):
    """
    Per-user LLM interaction preferences.

    One row per user (unique constraint on user_id).
    The `preferences` JSONB column stores:
      - thinking_mode (bool): enable/disable extended reasoning mode
      - response_style (str): "concise" | "detailed" | "conversational"

    No FK on user_id — users live in Keycloak, not PostgreSQL.
    """

    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, index=True
    )
    preferences: Mapped[dict] = mapped_column(
        _JSONB_type,
        nullable=False,
        default=lambda: dict(DEFAULT_PREFERENCES),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
