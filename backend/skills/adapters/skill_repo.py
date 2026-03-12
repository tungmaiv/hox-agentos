"""
SkillRepoAdapter — wraps existing SkillImporter for agentskills-index.json and direct URL imports.

Handles:
- Direct SKILL.md URLs: https://example.com/skill.md
- agentskills-index.json protocol: https://agentskills.io/index.json
- ZIP bundle URLs: https://example.com/skill.zip

Does NOT handle github.com repo browse URLs (those go to GitHubAdapter).
"""
from typing import Any

import httpx
import structlog

from skills.adapters.base import NormalizedSkill, SkillAdapter
from skills.importer import SkillImporter

logger = structlog.get_logger(__name__)


class SkillRepoAdapter(SkillAdapter):
    """Adapter for agentskills-index.json protocol and direct URL imports.

    Wraps the existing SkillImporter — does NOT rewrite import logic.
    """

    def can_handle(self, source: str, **kwargs: object) -> bool:
        """Return True for http/https URLs that are not github.com repo browse URLs.

        GitHub direct raw URLs (raw.githubusercontent.com or .md ending) are
        handled here too — SkillImporter.import_from_url() already converts them.
        GitHub repo browse URLs (github.com/user/repo without .md) go to GitHubAdapter.
        """
        if not source.startswith(("http://", "https://")):
            return False
        # GitHub repo browse URL (not a direct file URL) → GitHubAdapter handles
        if "github.com/" in source and not source.endswith(".md"):
            return False
        return True

    async def validate_source(self, source: str, **kwargs: object) -> dict:
        """Perform a HEAD request to verify the URL is reachable."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.head(source)
                if response.status_code < 400:
                    return {"valid": True, "reason": None}
                return {
                    "valid": False,
                    "reason": f"HTTP {response.status_code} from {source}",
                }
        except httpx.HTTPError as exc:
            return {"valid": False, "reason": str(exc)}

    async def fetch_and_normalize(self, source: str, **kwargs: object) -> NormalizedSkill:
        """Delegate to SkillImporter.import_from_url() and map result to NormalizedSkill."""
        importer = SkillImporter()
        skill_dict: dict[str, Any] = await importer.import_from_url(source)
        return _dict_to_normalized(skill_dict, source=source, source_type="direct_url")

    async def get_skill_list(self, source: str, **kwargs: object) -> list[dict]:
        """For agentskills-index.json URLs, fetch the index and return entries.

        For direct SKILL.md URLs, returns a single-item list.
        """
        # Try fetching as agentskills-index.json
        if source.endswith(".json") or "index" in source.lower():
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.get(source)
                    response.raise_for_status()
                    index = response.json()
                    if isinstance(index, list):
                        return [
                            {
                                "name": entry.get("name", ""),
                                "url": entry.get("url", ""),
                                "description": entry.get("description"),
                            }
                            for entry in index
                            if isinstance(entry, dict) and entry.get("url")
                        ]
            except Exception as exc:
                logger.warning("skill_index_fetch_failed", source=source, error=str(exc))

        # Fallback: treat source as a direct single-skill URL
        # Attempt to get skill name without full fetch
        return [{"name": source.split("/")[-1].replace(".md", ""), "url": source, "description": None}]


def _dict_to_normalized(
    skill_dict: dict[str, Any],
    source: str,
    source_type: str,
) -> NormalizedSkill:
    """Map a SkillImporter result dict to a NormalizedSkill dataclass."""
    return NormalizedSkill(
        name=skill_dict["name"],
        description=skill_dict["description"],
        version=skill_dict.get("version", "1.0.0"),
        instruction_markdown=skill_dict.get("instruction_markdown"),
        procedure_json=skill_dict.get("procedure_json"),
        allowed_tools=skill_dict.get("allowed_tools"),
        tags=skill_dict.get("tags"),
        category=skill_dict.get("category"),
        source_url=skill_dict.get("source_url") or source,
        source_type=source_type,
        author=skill_dict.get("author") or (
            skill_dict.get("metadata_json", {}) or {}
        ).get("author"),
        license=skill_dict.get("license"),
        skill_type=skill_dict.get("skill_type", "instructional"),
    )
