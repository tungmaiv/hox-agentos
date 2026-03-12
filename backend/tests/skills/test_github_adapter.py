"""Tests for GitHubAdapter — fetch repo file tree and convert SKILL.md to NormalizedSkill."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skills.adapters.github import GitHubAdapter
from skills.adapters.base import NormalizedSkill


_VALID_SKILL_MD = """---
name: test-skill
description: A test skill from GitHub
version: 1.2.0
---
These are the instructions for the skill.
"""

_GITHUB_TREE_RESPONSE = {
    "tree": [
        {"path": "README.md", "type": "blob"},
        {"path": "skills/SKILL.md", "type": "blob"},
        {"path": "src/main.py", "type": "blob"},
    ]
}


@pytest.fixture
def adapter() -> GitHubAdapter:
    return GitHubAdapter()


class TestGitHubAdapterCanHandle:
    def test_can_handle_github_repo_url(self, adapter: GitHubAdapter) -> None:
        """GitHub repo URL (no .md extension) is handled by GitHubAdapter."""
        assert adapter.can_handle("https://github.com/user/repo") is True

    def test_can_handle_non_github_returns_false(self, adapter: GitHubAdapter) -> None:
        """Non-GitHub URL is NOT handled by GitHubAdapter."""
        assert adapter.can_handle("https://example.com/skill.md") is False


class TestGitHubAdapterGetSkillList:
    @pytest.mark.asyncio
    async def test_get_skill_list_returns_skill_files(self, adapter: GitHubAdapter) -> None:
        """Mock GitHub API response with tree containing 'skills/SKILL.md' and 'README.md'.
        get_skill_list() returns list with 1 entry (SKILL.md only)."""
        mock_response = MagicMock()
        mock_response.json.return_value = _GITHUB_TREE_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_skill_list("https://github.com/user/repo")

        assert len(result) == 1
        assert result[0]["name"] is not None
        assert "SKILL.md" in result[0]["url"] or "raw.githubusercontent.com" in result[0]["url"]


class TestGitHubAdapterFetchAndNormalize:
    @pytest.mark.asyncio
    async def test_fetch_and_normalize_parses_skill_md(self, adapter: GitHubAdapter) -> None:
        """Mock raw content fetch returning valid SKILL.md.
        fetch_and_normalize() returns NormalizedSkill with correct name and description."""
        mock_response = MagicMock()
        mock_response.text = _VALID_SKILL_MD
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await adapter.fetch_and_normalize(
                "https://raw.githubusercontent.com/user/repo/HEAD/skills/SKILL.md"
            )

        assert isinstance(result, NormalizedSkill)
        assert result.name == "test-skill"
        assert result.description == "A test skill from GitHub"
        assert result.source_type == "github"
