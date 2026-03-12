"""
AgentHandler — type-specific handler for registry entries with type='agent'.

validate_config: agents have no mandatory config fields at MVP — only logs a
warning when no handler_function is present (agents may be externally dispatched).

on_create / on_delete: no-ops for MVP (agents are discovered at startup,
not dynamically loaded during runtime).
"""
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from registry.handlers.base import RegistryHandler

logger = structlog.get_logger(__name__)


class AgentHandler(RegistryHandler):
    """Handler for agent registry entries."""

    async def on_create(self, entry: object, session: AsyncSession) -> None:
        """Log creation — no side effects for MVP."""
        logger.info(
            "registry_agent_created",
            name=getattr(entry, "name", None),
        )

    async def on_delete(self, entry: object, session: AsyncSession) -> None:
        """Log deletion — no side effects for MVP."""
        logger.info(
            "registry_agent_deleted",
            name=getattr(entry, "name", None),
        )

    def validate_config(self, config: dict) -> None:
        """Agents have no required config fields at MVP."""
        if not config.get("handler_function") and not config.get("handler_module"):
            logger.debug(
                "agent_config_no_handler",
                hint="agent may be externally dispatched",
            )
        # No mandatory fields — external agents don't need handler_function
