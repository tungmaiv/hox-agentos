# backend/core/models/user_instructions.py
"""SQLAlchemy ORM model for per-user custom agent instructions."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class UserInstructions(Base):
    """
    Per-user custom instructions appended to the agent system prompt.

    One row per user (unique constraint on user_id).
    The `instructions` field contains free-text instructions the user enters
    in settings, e.g. "Always respond in Vietnamese" or "I'm a backend engineer."
    """

    __tablename__ = "user_instructions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, index=True
    )
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
