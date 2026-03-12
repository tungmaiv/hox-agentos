"""
SkillHandler — type-specific handler for registry entries with type='skill'.

validate_config: requires 'skill_type' key. Instructional skills must have
'instruction_markdown'; procedural skills must have 'procedure_json'.

on_create / on_delete: no-ops for MVP.
"""
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from registry.handlers.base import RegistryHandler

logger = structlog.get_logger(__name__)


class SkillHandler(RegistryHandler):
    """Handler for skill registry entries."""

    async def on_create(self, entry: object, session: AsyncSession) -> None:
        """Log creation — no side effects for MVP."""
        logger.info(
            "registry_skill_created",
            name=getattr(entry, "name", None),
        )

    async def on_delete(self, entry: object, session: AsyncSession) -> None:
        """Log deletion — no side effects for MVP."""
        logger.info(
            "registry_skill_deleted",
            name=getattr(entry, "name", None),
        )

    def validate_config(self, config: dict) -> None:
        """
        Validate skill config.

        Raises ValueError if skill_type is missing or if required content
        for the skill_type is absent.
        """
        skill_type = config.get("skill_type")
        if not skill_type:
            raise ValueError("skill config must include 'skill_type'")

        if skill_type == "instructional" and not config.get("instruction_markdown"):
            raise ValueError(
                "instructional skill config must include 'instruction_markdown'"
            )
        if skill_type == "procedural" and not config.get("procedure_json"):
            raise ValueError(
                "procedural skill config must include 'procedure_json'"
            )
