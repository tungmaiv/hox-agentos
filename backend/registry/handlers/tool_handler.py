"""
ToolHandler — type-specific handler for registry entries with type='tool'.

validate_config: requires 'handler_function' key for backend tools.
MCP tools require 'mcp_tool_name' instead.

on_create / on_delete: no-ops for MVP (tool cache refresh happens at request time).
"""
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from registry.handlers.base import RegistryHandler

logger = structlog.get_logger(__name__)


class ToolHandler(RegistryHandler):
    """Handler for tool registry entries."""

    async def on_create(self, entry: object, session: AsyncSession) -> None:
        """Log creation — no side effects for MVP."""
        logger.info(
            "registry_tool_created",
            name=getattr(entry, "name", None),
        )

    async def on_delete(self, entry: object, session: AsyncSession) -> None:
        """Log deletion — no side effects for MVP."""
        logger.info(
            "registry_tool_deleted",
            name=getattr(entry, "name", None),
        )

    def validate_config(self, config: dict) -> None:
        """
        Validate tool config.

        Backend tools require 'handler_function'.
        MCP tools require 'mcp_tool_name'.
        Sandbox tools require 'handler_function' or 'handler_code'.
        """
        handler_type = config.get("handler_type", "backend")

        if handler_type == "mcp":
            if not config.get("mcp_tool_name"):
                raise ValueError(
                    "mcp tool config must include 'mcp_tool_name'"
                )
        else:
            # backend or sandbox — require handler_function (or handler_code for sandbox)
            if not config.get("handler_function") and not config.get("handler_code"):
                raise ValueError(
                    "tool config must include 'handler_function'"
                )
