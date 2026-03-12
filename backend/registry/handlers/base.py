"""
Abstract base class for registry entry type handlers.

Each entry type (agent, skill, tool, mcp_server) has a corresponding handler
that implements type-specific lifecycle hooks and config validation.

Design:
- on_create: called after entry is inserted (e.g., trigger MCP discovery, seed tool cache)
- on_delete: called before entry is soft-deleted (e.g., evict client cache)
- validate_config: called before create/update (e.g., require handler_function for tools)
"""
from abc import ABC, abstractmethod

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class RegistryHandler(ABC):
    """Abstract base for type-specific registry entry handlers."""

    @abstractmethod
    async def on_create(self, entry: object, session: AsyncSession) -> None:
        """Called after a new entry is committed to the database."""
        ...

    @abstractmethod
    async def on_delete(self, entry: object, session: AsyncSession) -> None:
        """Called before an entry is soft-deleted."""
        ...

    @abstractmethod
    def validate_config(self, config: dict) -> None:
        """Validate type-specific config fields. Raise ValueError on invalid config."""
        ...
