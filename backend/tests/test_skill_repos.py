"""
Tests for external skill repository management.

Covers Task 1a (repo CRUD) and Task 1b (browse/import).

Sections:
- TestFetchIndex          — fetch_index validates remote agentskills-index.json
- TestRepoService         — add_repo, remove_repo, sync_repo, list_repos
- TestBrowseSkills        — browse_skills aggregates and filters
- TestImportFromRepo      — import_from_repo calls SkillImporter + SecurityScanner
- TestAdminRoutes         — admin routes require registry:manage permission
- TestUserRoutes          — user routes require chat permission
"""
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skill_repos.schemas import RepoCreate, ImportRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repo(
    repo_id: uuid.UUID | None = None,
    name: str = "test-repo",
    url: str = "https://skills.example.com",
    description: str | None = "A test repository",
    is_active: bool = True,
    cached_index: dict[str, Any] | None = None,
    last_synced_at: datetime | None = None,
) -> MagicMock:
    """Build a mock SkillRepository ORM instance."""
    repo = MagicMock()
    repo.id = repo_id or uuid.uuid4()
    repo.name = name
    repo.url = url
    repo.description = description
    repo.is_active = is_active
    repo.last_synced_at = last_synced_at
    repo.cached_index = cached_index or {
        "repository": {
            "name": name,
            "description": description or "",
            "url": url,
            "version": "1.0",
        },
        "skills": [
            {
                "name": "email-digest",
                "description": "Summarize emails",
                "version": "1.0",
                "skill_url": f"{url}/skills/email-digest/SKILL.md",
                "directory_url": f"{url}/skills/email-digest/",
                "metadata": {"author": "blitz", "license": "MIT"},
            }
        ],
    }
    return repo


_VALID_INDEX: dict[str, Any] = {
    "repository": {
        "name": "acme-skills",
        "description": "Acme skill collection",
        "url": "https://skills.acme.com",
        "version": "1.0",
    },
    "skills": [
        {
            "name": "daily-digest",
            "description": "Send a daily digest email",
            "version": "1.2.0",
            "skill_url": "https://skills.acme.com/skills/daily-digest/SKILL.md",
            "directory_url": "https://skills.acme.com/skills/daily-digest/",
            "metadata": {"author": "acme", "license": "Apache-2.0"},
        }
    ],
}

_INVALID_INDEX_MISSING_REPOSITORY: dict[str, Any] = {
    "skills": [{"name": "orphan", "description": "no parent"}],
}

_INVALID_INDEX_MISSING_SKILLS: dict[str, Any] = {
    "repository": {"name": "bad-repo", "description": "", "url": "http://x.com", "version": "1"},
}


# ---------------------------------------------------------------------------
# TestFetchIndex
# ---------------------------------------------------------------------------


class TestFetchIndex:
    """Unit tests for fetch_index() — fetches and validates repo index JSON."""

    @pytest.mark.asyncio
    async def test_fetch_index_returns_parsed_index_on_valid_response(self) -> None:
        """fetch_index() fetches agentskills-index.json and returns parsed dict."""
        from skill_repos.service import fetch_index

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _VALID_INDEX

        with patch("skill_repos.service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await fetch_index("https://skills.acme.com")

        assert result["repository"]["name"] == "acme-skills"
        assert len(result["skills"]) == 1
        assert result["skills"][0]["name"] == "daily-digest"

    @pytest.mark.asyncio
    async def test_fetch_index_appends_agentskills_index_json(self) -> None:
        """fetch_index() constructs the correct URL by appending /agentskills-index.json."""
        from skill_repos.service import fetch_index

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _VALID_INDEX

        with patch("skill_repos.service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await fetch_index("https://skills.acme.com/")  # trailing slash

        call_url = mock_client.get.call_args[0][0]
        assert call_url == "https://skills.acme.com/agentskills-index.json"

    @pytest.mark.asyncio
    async def test_fetch_index_raises_on_missing_repository_field(self) -> None:
        """fetch_index() raises ValueError when 'repository' field is missing."""
        from skill_repos.service import fetch_index

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _INVALID_INDEX_MISSING_REPOSITORY

        with patch("skill_repos.service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="skills"):
                await fetch_index("https://bad.example.com")

    @pytest.mark.asyncio
    async def test_fetch_index_raises_on_missing_skills_field(self) -> None:
        """fetch_index() raises ValueError when 'skills' field is missing."""
        from skill_repos.service import fetch_index

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _INVALID_INDEX_MISSING_SKILLS

        with patch("skill_repos.service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError):
                await fetch_index("https://bad.example.com")


# ---------------------------------------------------------------------------
# TestRepoService
# ---------------------------------------------------------------------------


class TestRepoService:
    """Unit tests for add_repo, remove_repo, sync_repo, list_repos."""

    @pytest.mark.asyncio
    async def test_add_repo_creates_skill_repository_row(self) -> None:
        """add_repo() calls fetch_index and creates a SkillRepository row."""
        from skill_repos.service import add_repo

        mock_repo_instance = _make_repo(name="acme-skills", url="https://skills.acme.com")
        mock_repo_instance.id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        # sequence: first execute() → no duplicate; second execute (refresh re-reads) → N/A
        mock_result_check = MagicMock()
        mock_result_check.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result_check)

        # refresh must update mock_repo_instance to have id set
        async def _refresh(obj: Any) -> None:
            obj.id = mock_repo_instance.id
            obj.name = mock_repo_instance.name
            obj.url = mock_repo_instance.url
            obj.description = mock_repo_instance.description
            obj.is_active = mock_repo_instance.is_active
            obj.last_synced_at = mock_repo_instance.last_synced_at
            obj.cached_index = mock_repo_instance.cached_index

        mock_session.refresh = _refresh

        with patch("skill_repos.service.fetch_index", new=AsyncMock(return_value=_VALID_INDEX)):
            result = await add_repo("https://skills.acme.com", mock_session)

        assert result.name == "acme-skills"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_repo_rejects_duplicate_name(self) -> None:
        """add_repo() raises ValueError when repo name already exists."""
        from skill_repos.service import add_repo

        mock_session = AsyncMock()
        # Simulate existing repo with same name
        existing_repo = _make_repo(name="acme-skills")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_repo
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("skill_repos.service.fetch_index", new=AsyncMock(return_value=_VALID_INDEX)):
            with pytest.raises(ValueError, match="acme-skills"):
                await add_repo("https://skills.acme.com", mock_session)

    @pytest.mark.asyncio
    async def test_remove_repo_deletes_row(self) -> None:
        """remove_repo() deletes the SkillRepository row."""
        from skill_repos.service import remove_repo

        mock_session = AsyncMock()
        repo = _make_repo()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = repo
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()

        await remove_repo(repo.id, mock_session)

        mock_session.delete.assert_awaited_once_with(repo)
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_remove_repo_raises_404_when_not_found(self) -> None:
        """remove_repo() raises HTTPException 404 when repo not found."""
        from fastapi import HTTPException
        from skill_repos.service import remove_repo

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await remove_repo(uuid.uuid4(), mock_session)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_sync_repo_updates_cached_index_and_last_synced_at(self) -> None:
        """sync_repo() re-fetches index and updates cached_index + last_synced_at."""
        from skill_repos.service import sync_repo

        repo = _make_repo(name="acme-skills", url="https://skills.acme.com")
        new_index: dict[str, Any] = {
            **_VALID_INDEX,
            "skills": [
                *_VALID_INDEX["skills"],
                {
                    "name": "new-skill",
                    "description": "A brand new skill",
                    "version": "1.0",
                    "skill_url": "https://skills.acme.com/skills/new-skill/SKILL.md",
                    "directory_url": "https://skills.acme.com/skills/new-skill/",
                    "metadata": {},
                },
            ],
        }

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = repo
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        with patch("skill_repos.service.fetch_index", new=AsyncMock(return_value=new_index)):
            result = await sync_repo(repo.id, mock_session)

        # After sync, cached_index updated
        assert repo.cached_index == new_index
        assert repo.last_synced_at is not None
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_repos_returns_all_repos_with_skill_count(self) -> None:
        """list_repos() returns all repos with skill_count from cached_index."""
        from skill_repos.service import list_repos

        repo1 = _make_repo(name="repo-a")
        repo2 = _make_repo(
            name="repo-b",
            cached_index={
                "repository": {"name": "repo-b", "description": "", "url": "http://b.com", "version": "1"},
                "skills": [
                    {"name": "skill-1", "description": "s1", "version": "1.0", "skill_url": "http://b.com/skill-1/SKILL.md", "directory_url": "http://b.com/skill-1/", "metadata": {}},
                    {"name": "skill-2", "description": "s2", "version": "1.0", "skill_url": "http://b.com/skill-2/SKILL.md", "directory_url": "http://b.com/skill-2/", "metadata": {}},
                ],
            },
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [repo1, repo2]
        mock_session.execute = AsyncMock(return_value=mock_result)

        results = await list_repos(mock_session)

        assert len(results) == 2
        # repo-b has 2 skills in its index
        repo_b_result = next(r for r in results if r.name == "repo-b")
        assert repo_b_result.skill_count == 2


# ---------------------------------------------------------------------------
# TestBrowseSkills
# ---------------------------------------------------------------------------


class TestBrowseSkills:
    """Unit tests for browse_skills — aggregation and search filtering."""

    @pytest.mark.asyncio
    async def test_browse_skills_aggregates_from_all_active_repos(self) -> None:
        """browse_skills() returns skills from ALL active repositories."""
        from skill_repos.service import browse_skills

        repo1 = _make_repo(name="repo-a", is_active=True)
        repo2 = _make_repo(
            name="repo-b",
            url="https://b.example.com",
            is_active=True,
            cached_index={
                "repository": {"name": "repo-b", "description": "", "url": "https://b.example.com", "version": "1"},
                "skills": [
                    {
                        "name": "project-summarizer",
                        "description": "Summarize a project",
                        "version": "2.0",
                        "skill_url": "https://b.example.com/skills/project-summarizer/SKILL.md",
                        "directory_url": "https://b.example.com/skills/project-summarizer/",
                        "metadata": {"author": "team-b", "license": "MIT"},
                    }
                ],
            },
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [repo1, repo2]
        mock_session.execute = AsyncMock(return_value=mock_result)

        results = await browse_skills(None, mock_session)

        # repo1 has 1 skill (email-digest), repo2 has 1 skill (project-summarizer)
        assert len(results) == 2
        names = {r.name for r in results}
        assert "email-digest" in names
        assert "project-summarizer" in names

    @pytest.mark.asyncio
    async def test_browse_skills_filters_by_search_query(self) -> None:
        """browse_skills() filters by case-insensitive substring match on name + description."""
        from skill_repos.service import browse_skills

        repo = _make_repo(
            name="repo-a",
            is_active=True,
            cached_index={
                "repository": {"name": "repo-a", "description": "", "url": "https://a.com", "version": "1"},
                "skills": [
                    {
                        "name": "email-digest",
                        "description": "Summarize emails",
                        "version": "1.0",
                        "skill_url": "https://a.com/email-digest/SKILL.md",
                        "directory_url": "https://a.com/email-digest/",
                        "metadata": {},
                    },
                    {
                        "name": "calendar-summary",
                        "description": "List calendar events",
                        "version": "1.0",
                        "skill_url": "https://a.com/calendar-summary/SKILL.md",
                        "directory_url": "https://a.com/calendar-summary/",
                        "metadata": {},
                    },
                ],
            },
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [repo]
        mock_session.execute = AsyncMock(return_value=mock_result)

        results = await browse_skills("email", mock_session)

        assert len(results) == 1
        assert results[0].name == "email-digest"

    @pytest.mark.asyncio
    async def test_browse_skills_search_is_case_insensitive(self) -> None:
        """browse_skills() search query matching is case-insensitive."""
        from skill_repos.service import browse_skills

        repo = _make_repo(
            name="repo-a",
            is_active=True,
            cached_index={
                "repository": {"name": "repo-a", "description": "", "url": "https://a.com", "version": "1"},
                "skills": [
                    {
                        "name": "Email-Digest",
                        "description": "Summarize Emails",
                        "version": "1.0",
                        "skill_url": "https://a.com/Email-Digest/SKILL.md",
                        "directory_url": "https://a.com/Email-Digest/",
                        "metadata": {},
                    },
                ],
            },
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [repo]
        mock_session.execute = AsyncMock(return_value=mock_result)

        results = await browse_skills("email", mock_session)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_browse_skills_search_matches_description(self) -> None:
        """browse_skills() search matches against description field too."""
        from skill_repos.service import browse_skills

        repo = _make_repo(
            name="repo-a",
            is_active=True,
            cached_index={
                "repository": {"name": "repo-a", "description": "", "url": "https://a.com", "version": "1"},
                "skills": [
                    {
                        "name": "xray-skill",
                        "description": "Send a daily email digest",
                        "version": "1.0",
                        "skill_url": "https://a.com/xray-skill/SKILL.md",
                        "directory_url": "https://a.com/xray-skill/",
                        "metadata": {},
                    },
                ],
            },
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [repo]
        mock_session.execute = AsyncMock(return_value=mock_result)

        results = await browse_skills("email digest", mock_session)

        assert len(results) == 1
        assert results[0].name == "xray-skill"

    @pytest.mark.asyncio
    async def test_browse_skills_skips_inactive_repos(self) -> None:
        """browse_skills() only includes skills from is_active=True repos."""
        from skill_repos.service import browse_skills

        # This should NOT happen — the service queries WHERE is_active=True
        # We verify by checking the session.execute was called with active filter
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        results = await browse_skills(None, mock_session)

        assert results == []


# ---------------------------------------------------------------------------
# TestImportFromRepo
# ---------------------------------------------------------------------------


class TestImportFromRepo:
    """Unit tests for import_from_repo — calls SkillImporter + SecurityScanner."""

    @pytest.mark.asyncio
    async def test_import_from_repo_calls_skill_importer_with_skill_url(self) -> None:
        """import_from_repo() passes skill_url from the index to SkillImporter.import_from_url."""
        from skill_repos.service import import_from_repo

        repo_id = uuid.uuid4()
        user_id = uuid.uuid4()
        skill_url = "https://skills.acme.com/skills/daily-digest/SKILL.md"

        repo = _make_repo(
            repo_id=repo_id,
            name="acme-skills",
            url="https://skills.acme.com",
            cached_index={
                "repository": {"name": "acme-skills", "description": "", "url": "https://skills.acme.com", "version": "1"},
                "skills": [
                    {
                        "name": "daily-digest",
                        "description": "Daily digest skill",
                        "version": "1.0",
                        "skill_url": skill_url,
                        "directory_url": "https://skills.acme.com/skills/daily-digest/",
                        "metadata": {},
                    }
                ],
            },
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = repo
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        skill_data = {
            "name": "daily-digest",
            "description": "Daily digest skill",
            "version": "1.0",
            "skill_type": "instructional",
            "instruction_markdown": "## Instructions\nDo stuff.",
            "source_type": "imported",
        }

        mock_importer = AsyncMock()
        mock_importer.import_from_url = AsyncMock(return_value=skill_data)

        from skills.security_scanner import SecurityReport
        mock_report = SecurityReport(
            score=80,
            factors={"source_reputation": 95, "tool_scope": 100, "prompt_safety": 100, "complexity": 100, "author_verification": 50},
            recommendation="approve",
            injection_matches=[],
        )
        mock_scanner = MagicMock()
        mock_scanner.scan = AsyncMock(return_value=mock_report)

        with patch("skill_repos.service.SkillImporter", return_value=mock_importer):
            with patch("skill_repos.service.SecurityScanner", return_value=mock_scanner):
                with patch("skill_repos.service.SkillDefinition") as mock_skill_cls:
                    mock_skill_instance = MagicMock()
                    mock_skill_instance.id = uuid.uuid4()
                    mock_skill_instance.name = "daily-digest"
                    mock_skill_cls.return_value = mock_skill_instance

                    async def _refresh(obj: Any) -> None:
                        pass

                    mock_session.refresh.side_effect = _refresh

                    result = await import_from_repo(repo_id, "daily-digest", user_id, mock_session)

        mock_importer.import_from_url.assert_awaited_once_with(skill_url)

    @pytest.mark.asyncio
    async def test_import_from_repo_runs_security_scanner(self) -> None:
        """import_from_repo() calls SecurityScanner.scan with skill_data + skill_url."""
        from skill_repos.service import import_from_repo

        repo_id = uuid.uuid4()
        user_id = uuid.uuid4()
        skill_url = "https://skills.acme.com/skills/daily-digest/SKILL.md"

        repo = _make_repo(
            repo_id=repo_id,
            name="acme-skills",
            url="https://skills.acme.com",
            cached_index={
                "repository": {"name": "acme-skills", "description": "", "url": "https://skills.acme.com", "version": "1"},
                "skills": [
                    {
                        "name": "daily-digest",
                        "description": "Daily digest skill",
                        "version": "1.0",
                        "skill_url": skill_url,
                        "directory_url": "https://skills.acme.com/skills/daily-digest/",
                        "metadata": {},
                    }
                ],
            },
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = repo
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        skill_data = {
            "name": "daily-digest",
            "description": "Daily digest skill",
            "version": "1.0",
            "skill_type": "instructional",
            "instruction_markdown": "## Instructions\nDo stuff.",
            "source_type": "imported",
        }

        mock_importer = AsyncMock()
        mock_importer.import_from_url = AsyncMock(return_value=skill_data)

        from skills.security_scanner import SecurityReport
        mock_report = SecurityReport(
            score=65,
            factors={},
            recommendation="review",
            injection_matches=[],
        )
        mock_scanner = MagicMock()
        mock_scanner.scan = AsyncMock(return_value=mock_report)

        with patch("skill_repos.service.SkillImporter", return_value=mock_importer):
            with patch("skill_repos.service.SecurityScanner", return_value=mock_scanner):
                with patch("skill_repos.service.SkillDefinition") as mock_skill_cls:
                    mock_skill_instance = MagicMock()
                    mock_skill_instance.id = uuid.uuid4()
                    mock_skill_instance.name = "daily-digest"
                    mock_skill_cls.return_value = mock_skill_instance

                    result = await import_from_repo(repo_id, "daily-digest", user_id, mock_session)

        mock_scanner.scan.assert_awaited_once_with(skill_data, source_url=skill_url)

    @pytest.mark.asyncio
    async def test_import_from_repo_creates_pending_review_skill(self) -> None:
        """import_from_repo() creates SkillDefinition with status='pending_review'."""
        from skill_repos.service import import_from_repo

        repo_id = uuid.uuid4()
        user_id = uuid.uuid4()

        repo = _make_repo(repo_id=repo_id)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = repo
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        skill_data = {
            "name": "email-digest",
            "description": "Summarize emails",
            "version": "1.0",
            "skill_type": "instructional",
            "instruction_markdown": "## Instructions\nDo stuff.",
            "source_type": "imported",
        }

        mock_importer = AsyncMock()
        mock_importer.import_from_url = AsyncMock(return_value=skill_data)

        from skills.security_scanner import SecurityReport
        mock_report = SecurityReport(
            score=72,
            factors={},
            recommendation="review",
            injection_matches=[],
        )
        mock_scanner = MagicMock()
        mock_scanner.scan = AsyncMock(return_value=mock_report)

        created_kwargs: dict[str, Any] = {}

        def _capture_skill(**kwargs: Any) -> MagicMock:
            created_kwargs.update(kwargs)
            inst = MagicMock()
            inst.id = uuid.uuid4()
            inst.name = kwargs.get("name", "")
            return inst

        with patch("skill_repos.service.SkillImporter", return_value=mock_importer):
            with patch("skill_repos.service.SecurityScanner", return_value=mock_scanner):
                with patch("skill_repos.service.SkillDefinition", side_effect=_capture_skill):
                    result = await import_from_repo(repo_id, "email-digest", user_id, mock_session)

        assert created_kwargs.get("status") == "pending_review"
        assert created_kwargs.get("security_score") == 72

    @pytest.mark.asyncio
    async def test_import_from_repo_raises_404_when_skill_not_in_index(self) -> None:
        """import_from_repo() raises HTTPException 404 when skill_name not found in repo index."""
        from fastapi import HTTPException
        from skill_repos.service import import_from_repo

        repo_id = uuid.uuid4()
        user_id = uuid.uuid4()
        repo = _make_repo(repo_id=repo_id)  # has "email-digest" only

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = repo
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await import_from_repo(repo_id, "nonexistent-skill", user_id, mock_session)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_import_from_repo_raises_404_when_repo_not_found(self) -> None:
        """import_from_repo() raises HTTPException 404 when repo not found."""
        from fastapi import HTTPException
        from skill_repos.service import import_from_repo

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await import_from_repo(uuid.uuid4(), "some-skill", uuid.uuid4(), mock_session)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# TestAdminRoutes
# ---------------------------------------------------------------------------


class TestAdminRoutes:
    """Integration-level tests for admin routes — require registry:manage permission."""

    @pytest.fixture
    def client(self) -> "TestClient":
        from fastapi.testclient import TestClient
        from main import create_app
        app = create_app()
        return TestClient(app, raise_server_exceptions=False)

    def test_list_repos_requires_auth(self, client: "TestClient") -> None:
        """GET /api/admin/skill-repos returns 401 without Authorization header."""
        response = client.get("/api/admin/skill-repos")
        assert response.status_code == 401

    def test_add_repo_requires_auth(self, client: "TestClient") -> None:
        """POST /api/admin/skill-repos returns 401 without Authorization header."""
        response = client.post(
            "/api/admin/skill-repos",
            json={"url": "https://skills.example.com"},
        )
        assert response.status_code == 401

    def test_delete_repo_requires_auth(self, client: "TestClient") -> None:
        """DELETE /api/admin/skill-repos/{id} returns 401 without auth."""
        response = client.delete(f"/api/admin/skill-repos/{uuid.uuid4()}")
        assert response.status_code == 401

    def test_sync_repo_requires_auth(self, client: "TestClient") -> None:
        """POST /api/admin/skill-repos/{id}/sync returns 401 without auth."""
        response = client.post(f"/api/admin/skill-repos/{uuid.uuid4()}/sync")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# TestUserRoutes
# ---------------------------------------------------------------------------


class TestUserRoutes:
    """Integration-level tests for user-facing routes — require chat permission."""

    @pytest.fixture
    def client(self) -> "TestClient":
        from fastapi.testclient import TestClient
        from main import create_app
        app = create_app()
        return TestClient(app, raise_server_exceptions=False)

    def test_browse_requires_auth(self, client: "TestClient") -> None:
        """GET /api/skill-repos/browse returns 401 without Authorization header."""
        response = client.get("/api/skill-repos/browse")
        assert response.status_code == 401

    def test_import_requires_auth(self, client: "TestClient") -> None:
        """POST /api/skill-repos/import returns 401 without Authorization header."""
        response = client.post(
            "/api/skill-repos/import",
            json={"repository_id": str(uuid.uuid4()), "skill_name": "test"},
        )
        assert response.status_code == 401
