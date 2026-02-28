"""
ToolDefinition ORM model -- registry entry for a tool.

Stores metadata for each registered tool (backend functions, MCP-backed, sandboxed)
including handler type, dispatch info, schema definitions, and version tracking.

Design:
- handler_type: "backend" | "mcp" | "sandbox" -- determines dispatch path
- mcp_server_id / mcp_tool_name: populated for MCP-backed tools (no FK for SQLite compat)
- sandbox_required: routes to Docker sandbox executor when True
- input_schema / output_schema: JSON Schema for tool I/O validation
- UNIQUE(name, version): allows multiple versions of the same tool
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, JSON, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base

_JSONB = JSON().with_variant(JSONB(), "postgresql")


class ToolDefinition(Base):
    """Registry entry for a single tool."""

    __tablename__ = "tool_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'1.0.0'")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'active'")
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    handler_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'backend'")
    )
    handler_module: Mapped[str | None] = mapped_column(Text, nullable=True)
    handler_function: Mapped[str | None] = mapped_column(Text, nullable=True)
    mcp_server_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True  # No FK -- polymorphic, SQLite compat
    )
    mcp_tool_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    sandbox_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    input_schema: Mapped[dict[str, Any] | None] = mapped_column(
        _JSONB, nullable=True
    )
    output_schema: Mapped[dict[str, Any] | None] = mapped_column(
        _JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_tool_name_version"),
    )
