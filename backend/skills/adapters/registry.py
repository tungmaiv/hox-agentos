"""
AdapterRegistry — detects the appropriate SkillAdapter for a given source string.

Detection priority:
1. claude-market:// sources → ClaudeMarketAdapter (most specific, checked first)
2. github.com repo browse URLs → GitHubAdapter
3. http/https URLs (not GitHub repo browse) → SkillRepoAdapter
4. Unknown → raises ValueError
"""
import structlog

from skills.adapters.base import SkillAdapter
from skills.adapters.claude_market import ClaudeMarketAdapter
from skills.adapters.github import GitHubAdapter
from skills.adapters.skill_repo import SkillRepoAdapter

logger = structlog.get_logger(__name__)


class AdapterRegistry:
    """Registry that maps skill source strings to the appropriate adapter.

    Adapters are checked in priority order using their can_handle() method.
    The first adapter that returns True is selected.
    """

    _adapters: list[SkillAdapter] = [
        ClaudeMarketAdapter(),   # checked first — most specific (URI scheme prefix)
        GitHubAdapter(),          # second — repo browse URLs
        SkillRepoAdapter(),       # third — direct http/https URLs
    ]

    def detect_adapter(self, source: str) -> SkillAdapter:
        """Return the first adapter that can handle the given source.

        Args:
            source: URL, URI, or identifier string for the skill source.

        Returns:
            The appropriate SkillAdapter instance.

        Raises:
            ValueError: If no adapter can handle the source.
        """
        for adapter in self._adapters:
            if adapter.can_handle(source):
                logger.debug(
                    "adapter_detected",
                    source=source,
                    adapter=type(adapter).__name__,
                )
                return adapter

        raise ValueError(f"No adapter found for source: {source}")
