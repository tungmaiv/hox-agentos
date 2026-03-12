"""
ClaudeMarketAdapter — MVP stub for Claude Marketplace skill imports.

Handles sources with the claude-market:// URI scheme.
The actual Claude Market API is not yet implemented — this adapter
correctly routes the source type but raises NotImplementedError.
"""
import structlog

from skills.adapters.base import NormalizedSkill, SkillAdapter

logger = structlog.get_logger(__name__)


class ClaudeMarketAdapter(SkillAdapter):
    """Stub adapter for Claude Marketplace URIs (claude-market://).

    This adapter detects the correct source type but raises NotImplementedError
    for all operations that require network access to the marketplace API.
    The stub exists so that source detection works correctly — the ValueError
    "No adapter found" is not raised for claude-market:// sources.
    """

    def can_handle(self, source: str, **kwargs: object) -> bool:
        """Return True for claude-market:// URIs."""
        return source.startswith("claude-market://")

    async def validate_source(self, source: str, **kwargs: object) -> dict:
        """Always returns valid — no remote validation possible for MVP stub."""
        return {"valid": True, "reason": None}

    async def fetch_and_normalize(self, source: str, **kwargs: object) -> NormalizedSkill:
        """Not implemented — Claude Market API not yet wired.

        Raises:
            NotImplementedError: Always. Use direct URL import instead.
        """
        raise NotImplementedError(
            "Claude Market adapter not yet implemented — use direct URL import"
        )

    async def get_skill_list(self, source: str, **kwargs: object) -> list[dict]:
        """Not implemented — Claude Market API not yet wired.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(
            "Claude Market adapter not yet implemented — use direct URL import"
        )
