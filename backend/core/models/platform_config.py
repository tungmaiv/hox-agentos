"""
PlatformConfig — single-row table for runtime identity provider configuration.

Decision (IDCFG-06): Use a typed-column table rather than system_config key/value store.
This enables type safety, simpler queries, and explicit schema evolution via migrations.

Single-row invariant: always upsert id=1. No multi-row support in v1.2.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class PlatformConfig(Base):
    """
    Single-row table storing Keycloak identity provider configuration.

    All Keycloak fields are nullable — NULL means "not configured".
    client_secret_encrypted stores the AES-256-GCM ciphertext as JSON:
      {"iv_b64": "...", "ct_b64": "..."}
    Plain string column (not JSONB) to keep the migration simple and
    avoid JSONB variant issues across SQLite test + PostgreSQL prod.
    """

    __tablename__ = "platform_config"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    keycloak_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    keycloak_realm: Mapped[str | None] = mapped_column(String(200), nullable=True)
    keycloak_client_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # AES-256-GCM encrypted; JSON string {"iv_b64": "...", "ct_b64": "..."}
    keycloak_client_secret_encrypted: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    keycloak_ca_cert: Mapped[str | None] = mapped_column(String(500), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
