"""
Tests for normalize_repo_url() and fetch_index() GitHub fallback behavior.

All 8 behavior cases from the plan:
1. normalize_repo_url("HKUDS/CLI-Anything") -> "https://github.com/HKUDS/CLI-Anything"
2. normalize_repo_url("owner/repo") -> "https://github.com/owner/repo"
3. normalize_repo_url("https://github.com/owner/repo") -> passthrough
4. normalize_repo_url("https://skills.example.com") -> passthrough (non-GitHub)
5. fetch_index on github.com URL with 404: calls GitHub API, returns synthetic index
6. fetch_index on non-github.com URL with 404: raises httpx.HTTPStatusError
7. fetch_index on github.com URL with valid agentskills-index.json: returns real index
8. fetch_index on non-404 HTTP error (500) for github.com URL: raises httpx.HTTPStatusError
"""
import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ---------------------------------------------------------------------------
# TestNormalizeRepoUrl
# ---------------------------------------------------------------------------


class TestNormalizeRepoUrl:
    """Unit tests for normalize_repo_url() shorthand detection and expansion."""

    def test_owner_repo_shorthand_is_expanded_to_github_url(self) -> None:
        """normalize_repo_url("HKUDS/CLI-Anything") -> "https://github.com/HKUDS/CLI-Anything"."""
        from skill_repos.service import normalize_repo_url

        result = normalize_repo_url("HKUDS/CLI-Anything")
        assert result == "https://github.com/HKUDS/CLI-Anything"

    def test_lowercase_owner_repo_shorthand_is_expanded(self) -> None:
        """normalize_repo_url("owner/repo") -> "https://github.com/owner/repo"."""
        from skill_repos.service import normalize_repo_url

        result = normalize_repo_url("owner/repo")
        assert result == "https://github.com/owner/repo"

    def test_full_github_url_is_passed_through_unchanged(self) -> None:
        """normalize_repo_url("https://github.com/owner/repo") -> passthrough."""
        from skill_repos.service import normalize_repo_url

        url = "https://github.com/owner/repo"
        result = normalize_repo_url(url)
        assert result == url

    def test_non_github_full_url_is_passed_through_unchanged(self) -> None:
        """normalize_repo_url("https://skills.example.com") -> passthrough."""
        from skill_repos.service import normalize_repo_url

        url = "https://skills.example.com"
        result = normalize_repo_url(url)
        assert result == url

    def test_shorthand_with_dots_and_dashes_is_expanded(self) -> None:
        """normalize_repo_url("my.org/my-repo") -> "https://github.com/my.org/my-repo"."""
        from skill_repos.service import normalize_repo_url

        result = normalize_repo_url("my.org/my-repo")
        assert result == "https://github.com/my.org/my-repo"

    def test_triple_segment_path_is_not_expanded(self) -> None:
        """normalize_repo_url with extra path segments (3+) returns unchanged — not a simple owner/repo."""
        from skill_repos.service import normalize_repo_url

        url = "https://github.com/owner/repo/tree/main"
        result = normalize_repo_url(url)
        assert result == url


# ---------------------------------------------------------------------------
# TestFetchIndexGithubFallback
# ---------------------------------------------------------------------------


def _make_http_status_error(status_code: int, url: str) -> httpx.HTTPStatusError:
    """Build a real httpx.HTTPStatusError for mocking."""
    request = httpx.Request("GET", url)
    response = httpx.Response(status_code=status_code, request=request)
    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=request,
        response=response,
    )


_VALID_INDEX: dict[str, Any] = {
    "repository": {
        "name": "my-skills",
        "description": "A collection of skills",
        "url": "https://github.com/myorg/my-skills",
        "version": "1.0",
    },
    "skills": [
        {
            "name": "demo-skill",
            "description": "A demo skill",
            "version": "1.0",
            "skill_url": "https://github.com/myorg/my-skills/skills/demo-skill/SKILL.md",
            "directory_url": "https://github.com/myorg/my-skills/skills/demo-skill/",
            "metadata": {},
        }
    ],
}


class TestFetchIndexGithubFallback:
    """Tests for fetch_index() GitHub fallback and non-GitHub 404 behavior."""

    @pytest.mark.asyncio
    async def test_github_url_404_calls_github_api_and_returns_synthetic_index(self) -> None:
        """fetch_index on github.com URL with 404 returns synthetic index from GitHub API."""
        from skill_repos.service import fetch_index

        index_404_error = _make_http_status_error(404, "https://github.com/HKUDS/CLI-Anything/agentskills-index.json")
        github_api_response = MagicMock()
        github_api_response.status_code = 200
        github_api_response.json.return_value = {
            "name": "CLI-Anything",
            "description": "A CLI tool skill collection",
            "html_url": "https://github.com/HKUDS/CLI-Anything",
        }

        mock_index_response = MagicMock()
        mock_index_response.raise_for_status.side_effect = index_404_error

        with patch("skill_repos.service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            # First call: index fetch (returns 404), second call: GitHub API (returns 200)
            mock_client.get = AsyncMock(side_effect=[mock_index_response, github_api_response])
            mock_client_cls.return_value = mock_client

            result = await fetch_index("https://github.com/HKUDS/CLI-Anything")

        assert result["repository"]["name"] == "CLI-Anything"
        assert result["repository"]["description"] == "A CLI tool skill collection"
        assert result["repository"]["url"] == "https://github.com/HKUDS/CLI-Anything"
        assert result["repository"]["version"] == "0.0.0"
        assert result["skills"] == []

    @pytest.mark.asyncio
    async def test_non_github_url_404_raises_http_status_error(self) -> None:
        """fetch_index on non-github.com URL with 404 raises httpx.HTTPStatusError."""
        from skill_repos.service import fetch_index

        error = _make_http_status_error(404, "https://skills.example.com/agentskills-index.json")
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = error

        with patch("skill_repos.service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await fetch_index("https://skills.example.com")

    @pytest.mark.asyncio
    async def test_github_url_with_valid_index_returns_real_index(self) -> None:
        """fetch_index on github.com URL with valid agentskills-index.json returns real index (no fallback)."""
        from skill_repos.service import fetch_index

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()  # no error
        mock_response.json.return_value = _VALID_INDEX

        with patch("skill_repos.service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await fetch_index("https://github.com/myorg/my-skills")

        # Returns the real index, not a synthetic one
        assert result["repository"]["name"] == "my-skills"
        assert len(result["skills"]) == 1
        assert result["skills"][0]["name"] == "demo-skill"
        # Only one HTTP call was made (no GitHub API fallback)
        assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_github_url_500_error_raises_http_status_error(self) -> None:
        """fetch_index on github.com URL with 500 (non-404) error raises httpx.HTTPStatusError."""
        from skill_repos.service import fetch_index

        error = _make_http_status_error(500, "https://github.com/HKUDS/CLI-Anything/agentskills-index.json")
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = error

        with patch("skill_repos.service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await fetch_index("https://github.com/HKUDS/CLI-Anything")

        # Must be the 500 error, not a GitHub API call
        assert exc_info.value.response.status_code == 500

    @pytest.mark.asyncio
    async def test_github_api_returns_non_200_raises_value_error(self) -> None:
        """When GitHub API returns non-200 after index 404, raises ValueError."""
        from skill_repos.service import fetch_index

        index_404_error = _make_http_status_error(404, "https://github.com/HKUDS/CLI-Anything/agentskills-index.json")
        github_api_response = MagicMock()
        github_api_response.status_code = 404  # GitHub API also says not found

        mock_index_response = MagicMock()
        mock_index_response.raise_for_status.side_effect = index_404_error

        with patch("skill_repos.service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=[mock_index_response, github_api_response])
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="GitHub repo not found"):
                await fetch_index("https://github.com/HKUDS/CLI-Anything")
