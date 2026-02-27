"""
SQLAlchemy ORM models for the multi-channel integration subsystem.

Two tables:
  - channel_accounts: maps external platform user -> Blitz user (via pairing code)
  - channel_sessions: maps external conversation -> internal conversation

Isolation rule: channel_accounts queries MUST include WHERE user_id=$1 from JWT
for authenticated endpoints. The /api/channels/incoming route looks up by
(channel, external_user_id) since it receives traffic from unauthenticated sidecars.

CRITICAL: No FK on user_id -- users live in Keycloak, not PostgreSQL.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base

# JSON type compatible with SQLite (tests) and PostgreSQL (production).
_JSONB = JSON().with_variant(JSONB(), "postgresql")


class ChannelAccount(Base):
    """
    Maps an external platform user to a Blitz user.

    user_id is NULLABLE -- unpaired accounts (awaiting /pair command) have no user yet.
    Once paired, user_id is set and is_paired=True.

    No FK on user_id -- users live in Keycloak, not PostgreSQL.
    """

    __tablename__ = "channel_accounts"
    __table_args__ = (
        UniqueConstraint("channel", "external_user_id", name="uq_channel_external_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    external_user_id: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    pairing_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    pairing_expires: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_paired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict] = mapped_column(
        _JSONB, nullable=False, server_default="{}", default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChannelSession(Base):
    """
    Maps an external chat/conversation to an internal Blitz conversation.

    Each (channel_account, external_chat_id) pair gets a unique conversation_id
    so sessions can be tracked per-chat (important for group chats).
    """

    __tablename__ = "channel_sessions"
    __table_args__ = (
        UniqueConstraint(
            "channel_account_id", "external_chat_id", name="uq_account_chat"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    channel_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channel_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_chat_id: Mapped[str] = mapped_column(String(256), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
