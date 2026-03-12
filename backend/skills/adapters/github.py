"""
GitHubAdapter — fetches skill files from public GitHub repositories.

Handles:
- GitHub repo browse URLs: https://github.com/user/repo
- NOT direct .md file URLs (those go to SkillRepoAdapter)

Uses the GitHub API (no auth for public repos) to list files, then fetches
each SKILL.md or skill.yaml via raw.githubusercontent.com.
"""
import re
from typing import Any

import httpx
import structlog

from skills.adapters.base import NormalizedSkill, SkillAdapter
from skills.adapters.skill_repo import _dict_to_normalized
from skills.importer import SkillImporter

logger = structlog.get_logger(__name__)

_GITHUB_URL_RE = re.compile(r"https?://github\.com/([^/]+)/([^/]+)(?:/.*)?$")

_SKILL_EXTENSIONS = ("SKILL.md", "skill.yaml", "skill.yml")


def _parse_owner_repo(url: str) -> tuple[str, str] | None:
    """Extract (owner, repo) from a github.com URL.

    Returns None if the URL doesn't match the expected pattern.
    """
    match = _GITHUB_URL_RE.match(url)
    if not match:
        return None
    owner = match.group(1)
    repo = match.group(2)
    # Strip trailing .git suffix if present
    repo = repo.removesuffix(".git")
    return owner, repo


class GitHubAdapter(SkillAdapter):
    """Adapter for importing skills from public GitHub repositories.

    Uses GitHub Trees API to discover skill files without downloading
    the entire repository.
    """

    def can_handle(self, source: str, **kwargs: object) -> bool:
        """Return True for GitHub repo URLs that are not direct .md file links."""
        if "github.com/" not in source:
            return False
        # Direct .md file URL → SkillRepoAdapter handles it
        if source.endswith(".md"):
            return False
        return True

    async def validate_source(self, source: str, **kwargs: object) -> dict:
        """HEAD request to github.com/{owner}/{repo} to verify existence."""
        parsed = _parse_owner_repo(source)
        if not parsed:
            return {"valid": False, "reason": "Could not parse owner/repo from URL"}
        owner, repo = parsed
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.head(f"https://github.com/{owner}/{repo}")
                if response.status_code == 200:
                    return {"valid": True, "reason": None}
                if response.status_code == 404:
                    return {"valid": False, "reason": "Repository not found"}
                return {"valid": True, "reason": None}  # Non-404 errors — proceed
        except httpx.HTTPError as exc:
            return {"valid": False, "reason": str(exc)}

    async def get_skill_list(self, source: str, **kwargs: object) -> list[dict]:
        """List skill files in a GitHub repository using the Trees API.

        Args:
            source: GitHub repo URL (e.g., https://github.com/user/repo)

        Returns:
            List of dicts with name, url, description for each discovered skill file.
        """
        parsed = _parse_owner_repo(source)
        if not parsed:
            raise ValueError(f"Cannot parse GitHub repo URL: {source}")
        owner, repo = parsed

        api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                api_url,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            response.raise_for_status()
            tree_data = response.json()

        skill_files: list[dict] = []
        for item in tree_data.get("tree", []):
            path: str = item.get("path", "")
            if item.get("type") != "blob":
                continue
            # Check if the file name ends with any skill extension
            filename = path.split("/")[-1]
            if not any(filename == ext for ext in _SKILL_EXTENSIONS):
                continue

            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}"
            # Use parent directory name as skill name, or the filename without extension
            parts = path.rsplit("/", 1)
            if len(parts) > 1 and parts[0]:
                name = parts[0].split("/")[-1]
            else:
                name = filename.replace(".md", "").replace(".yaml", "").replace(".yml", "")

            skill_files.append({
                "name": name,
                "url": raw_url,
                "description": None,
            })

        logger.info(
            "github_skill_list_fetched",
            owner=owner,
            repo=repo,
            count=len(skill_files),
        )
        return skill_files

    async def fetch_and_normalize(self, source: str, **kwargs: object) -> NormalizedSkill:
        """Fetch a skill file and return a NormalizedSkill.

        Accepts either:
        - A raw.githubusercontent.com URL (direct raw content)
        - A github.com blob URL (converted to raw URL internally)
        - A github.com repo URL (fetches first skill found)

        Args:
            source: URL to the skill file.

        Returns:
            NormalizedSkill with source_type="github".
        """
        # Determine the raw content URL
        raw_url = _to_raw_url(source)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(raw_url)
            response.raise_for_status()
            content = response.text

        importer = SkillImporter()
        # Detect format by extension
        if raw_url.endswith((".yaml", ".yml")):
            skill_dict: dict[str, Any] = importer.import_from_claude_code_yaml(content)
        else:
            skill_dict = importer.parse_skill_md(content)

        return _dict_to_normalized(skill_dict, source=raw_url, source_type="github")


def _to_raw_url(url: str) -> str:
    """Convert a GitHub blob URL to raw.githubusercontent.com.

    raw.githubusercontent.com URLs and non-GitHub URLs are returned unchanged.
    """
    if "raw.githubusercontent.com" in url:
        return url
    return SkillImporter._github_to_raw_url(url)
