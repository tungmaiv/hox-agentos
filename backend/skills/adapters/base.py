"""
SkillAdapter ABC and NormalizedSkill dataclass.

All skill import adapters must implement SkillAdapter and return NormalizedSkill
from fetch_and_normalize(). This decouples the import pipeline from any specific
source format (agentskills-index.json, GitHub, claude-market://, ZIP).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NormalizedSkill:
    """Canonical normalized representation of an imported skill.

    All adapters return this dataclass from fetch_and_normalize().
    Field names mirror SkillDefinitionCreate where possible.
    """

    name: str
    description: str
    version: str = "1.0.0"
    instruction_markdown: Optional[str] = None
    procedure_json: Optional[list] = None
    allowed_tools: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    category: Optional[str] = None
    source_url: Optional[str] = None
    source_type: str = "direct_url"  # "direct_url" | "github" | "claude_market" | "zip"
    author: Optional[str] = None
    license: Optional[str] = None
    skill_type: str = "instructional"  # "instructional" | "procedural"


class SkillAdapter(ABC):
    """Abstract base class for all skill import adapters.

    Adapters are responsible for:
    1. Detecting if they can handle a given source (can_handle)
    2. Validating the source is reachable/valid (validate_source)
    3. Fetching and normalizing a single skill (fetch_and_normalize)
    4. Listing all skills available at a source (get_skill_list)
    """

    @abstractmethod
    def can_handle(self, source: str, **kwargs: object) -> bool:
        """Return True if this adapter can handle the given source string.

        This method is synchronous for use in detect_adapter() without
        the overhead of creating an event loop.

        Args:
            source: URL, URI, or identifier string for the skill source.
            **kwargs: Optional adapter-specific hints.

        Returns:
            True if this adapter should handle the source.
        """
        ...

    @abstractmethod
    async def validate_source(self, source: str, **kwargs: object) -> dict:
        """Validate that the source is reachable and has the expected format.

        Args:
            source: URL, URI, or identifier string.
            **kwargs: Optional adapter-specific hints.

        Returns:
            Dict with keys: "valid" (bool), "reason" (str | None).
        """
        ...

    @abstractmethod
    async def fetch_and_normalize(self, source: str, **kwargs: object) -> NormalizedSkill:
        """Fetch skill content from source and return a NormalizedSkill.

        Args:
            source: URL, URI, or identifier string.
            **kwargs: Optional adapter-specific hints.

        Returns:
            NormalizedSkill dataclass with all available fields populated.

        Raises:
            SkillImportError: If fetch fails or content is invalid.
        """
        ...

    @abstractmethod
    async def get_skill_list(self, source: str, **kwargs: object) -> list[dict]:
        """Return a list of available skills at the source.

        For single-skill URLs, returns a list with one entry.
        For index/repo sources, returns all discovered skills.

        Args:
            source: URL, URI, or identifier string.
            **kwargs: Optional adapter-specific hints.

        Returns:
            List of dicts with keys: "name" (str), "url" (str),
            "description" (str | None).
        """
        ...
