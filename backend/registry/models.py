"""
Registry ORM models.

RegistryEntry — unified registry for agents, skills, tools, and MCP servers.

Design:
- type: "agent" | "skill" | "tool" | "mcp_server"
- config: JSONB — type-specific fields (replaces old type-specific columns)
- status: "draft" | "active" | "archived"
- owner_id: UUID of owning user (from Keycloak — no FK)
- deleted_at: soft delete timestamp (NULL = not deleted)
- UNIQUE(type, name): enforces one entry per type+name combination

McpServerCatalog — pre-built MCP server catalog (not yet installed).
Installation creates a registry_entries row.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.types import JSON

from core.db import Base

# JSON type compatible with both SQLite (tests) and PostgreSQL (production)
_JSONB = JSON().with_variant(JSONB(), "postgresql")


class RegistryEntry(Base):
    """Unified registry entry for agents, skills, tools, and MCP servers."""

    __tablename__ = "registry_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    config = Column(_JSONB, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default="draft")
    owner_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("type", "name", name="uq_registry_type_name"),
    )


class McpServerCatalog(Base):
    """Pre-built MCP server catalog entry.

    Represents a known, installable MCP server package. Not yet installed.
    Installing one creates a corresponding registry_entries row.
    """

    __tablename__ = "mcp_server_catalog"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    package_manager = Column(String(10), nullable=False)
    package_name = Column(String(200), nullable=False)
    command = Column(String(200), nullable=False)
    args = Column(_JSONB, nullable=False, default=list)
    env_vars = Column(_JSONB, nullable=False, default=dict)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )
