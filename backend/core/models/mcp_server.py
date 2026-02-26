"""
McpServer ORM model — MCP server registry.

Stores the URL, name, and AES-256 encrypted auth_token for each MCP server
registered in the system. Used by the MCP client to resolve server endpoints
and by 03-03 CRUD admin routes.

Design:
- id: UUID primary key (gen_random_uuid() in DB)
- name: unique display name (e.g. "crm", "docs")
- url: HTTP SSE endpoint URL (e.g. "http://mcp-crm:8001")
- auth_token: AES-256-GCM encrypted blob (bytes) — decrypted only inside tool executor
- is_active: feature flag — inactive servers are skipped during tool routing
- created_at: immutable timestamp set on insert
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, LargeBinary, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class McpServer(Base):
    """Registry entry for a single MCP server connection."""

    __tablename__ = "mcp_servers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    auth_token: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,  # AES-256-GCM encrypted; None = no auth required
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
