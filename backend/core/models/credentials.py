# backend/core/models/credentials.py
"""SQLAlchemy ORM model for AES-256 encrypted user credentials."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class UserCredential(Base):
    """
    Per-user encrypted OAuth token store.

    Each row stores ONE provider token per user (upsert pattern).
    Tokens are AES-256-GCM encrypted — ciphertext + iv stored separately.
    The encryption key comes from settings.credential_encryption_key (AES-256 = 32 bytes).

    Security:
    - user_id always from JWT — never from request body
    - ciphertext is meaningless without the encryption key
    - iv is random per encryption (same plaintext -> different ciphertext each time)
    - Credentials are NEVER logged, returned to frontend, or passed to LLMs
    """

    __tablename__ = "user_credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    iv: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_credentials_user_provider"),
    )
