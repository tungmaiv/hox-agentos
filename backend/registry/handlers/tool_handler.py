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
        """Log creation and auto-resolve matching gaps in draft skills."""
        tool_name: str = getattr(entry, "name", "") or ""
        logger.info("registry_tool_created", name=tool_name)

        # Convert tool name to slug for gap matching
        # e.g. "slack.send-message" → "slack-send-message"
        tool_slug = tool_name.replace(".", "-").replace("_", "-").lower()

        try:
            from sqlalchemy import select
            from registry.models import RegistryEntry

            result = await session.execute(
                select(RegistryEntry).where(
                    RegistryEntry.type == "skill",
                    RegistryEntry.status == "draft",
                    RegistryEntry.deleted_at.is_(None),
                )
            )
            draft_skills = result.scalars().all()

            for skill in draft_skills:
                config = skill.config or {}
                gaps: list[dict] = config.get("tool_gaps", [])
                if not gaps:
                    continue

                # Remove gaps whose MISSING slug matches the new tool slug
                remaining = [
                    g for g in gaps
                    if tool_slug not in g.get("tool", "").replace("MISSING:", "").lower()
                ]

                if len(remaining) == len(gaps):
                    continue  # no match — skip

                updated_config = {**config, "tool_gaps": remaining}

                if not remaining:
                    skill.status = "pending_activation"
                    logger.info(
                        "skill_gaps_resolved",
                        skill_id=str(getattr(skill, "id", "?")),
                        skill_name=getattr(skill, "name", "?"),
                        triggered_by_tool=tool_name,
                    )
                else:
                    logger.info(
                        "skill_gap_partially_resolved",
                        skill_id=str(getattr(skill, "id", "?")),
                        remaining_gaps=len(remaining),
                        triggered_by_tool=tool_name,
                    )

                skill.config = updated_config
                session.add(skill)

        except Exception as exc:
            logger.warning("tool_gap_resolution_failed", error=str(exc), tool_name=tool_name)

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
