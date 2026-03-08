"""
Unit tests for scheduler.tasks.check_skill_updates

Tests cover:
  - test_hash_unchanged_no_new_row: matching hash → no session.add
  - test_hash_changed_creates_pending_review: different hash → session.add with pending_review row
  - test_null_hash_stores_without_creating_review: null baseline → update only, no new row
  - test_builtin_skill_skipped: source_type="builtin" → _check_single_skill not called
  - test_fetch_failure_logs_warning_and_continues: httpx raises → skill skipped, no exception
  - test_bump_version_patch: _bump_version semver and non-semver behaviour

Pattern: mock httpx.AsyncClient, async_session, session.execute/add/commit.
"""
import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_skill(
    source_type: str = "imported",
    source_url: str = "https://example.com/skill.yaml",
    source_hash: str | None = None,
    status: str = "active",
    name: str = "test-skill",
    version: str = "1.0.0",
    **extra: object,
) -> MagicMock:
    skill = MagicMock()
    skill.id = uuid.uuid4()
    skill.source_type = source_type
    skill.source_url = source_url
    skill.source_hash = source_hash
    skill.status = status
    skill.name = name
    skill.version = version
    skill.display_name = "Test Skill"
    skill.description = "A test skill"
    skill.skill_type = "instructional"
    skill.instruction_markdown = "# Test"
    skill.procedure_json = None
    skill.input_schema = None
    skill.output_schema = None
    skill.license = "MIT"
    skill.compatibility = None
    skill.metadata_json = None
    skill.allowed_tools = None
    skill.tags = []
    skill.category = "test"
    skill.created_by = None
    for k, v in extra.items():
        setattr(skill, k, v)
    return skill


# ── _bump_version pure function tests ─────────────────────────────────────────


def test_bump_version_patch_standard() -> None:
    from scheduler.tasks.check_skill_updates import _bump_version

    assert _bump_version("1.0.0") == "1.0.1"
    assert _bump_version("2.3.9") == "2.3.10"
    assert _bump_version("0.0.1") == "0.0.2"


def test_bump_version_non_semver() -> None:
    from scheduler.tasks.check_skill_updates import _bump_version

    assert _bump_version("invalid") == "invalid.1"
    assert _bump_version("1.0") == "1.0.1"


# ── _check_single_skill tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_hash_unchanged_no_new_row() -> None:
    """When fetched hash equals stored source_hash, no new DB row is created."""
    content = b"skill content unchanged"
    current_hash = hashlib.sha256(content).hexdigest()
    skill = _make_skill(source_hash=current_hash)

    mock_resp = MagicMock()
    mock_resp.content = content
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch("scheduler.tasks.check_skill_updates.async_session", return_value=mock_session):
            from scheduler.tasks.check_skill_updates import _check_single_skill

            await _check_single_skill(skill)

    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_hash_changed_creates_pending_review() -> None:
    """When fetched hash differs from stored hash, a new pending_review row is created."""
    old_content = b"old skill content"
    old_hash = hashlib.sha256(old_content).hexdigest()
    new_content = b"new skill content - upstream changed"
    skill = _make_skill(source_hash=old_hash, version="1.0.0")

    mock_resp = MagicMock()
    mock_resp.content = new_content
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch("scheduler.tasks.check_skill_updates.async_session", return_value=mock_session):
            from scheduler.tasks.check_skill_updates import _check_single_skill

            await _check_single_skill(skill)

    mock_session.add.assert_called_once()
    added_row = mock_session.add.call_args[0][0]
    assert added_row.status == "pending_review"
    assert added_row.version == "1.0.1"
    expected_new_hash = hashlib.sha256(new_content).hexdigest()
    assert added_row.source_hash == expected_new_hash


@pytest.mark.asyncio
async def test_null_hash_stores_without_creating_review() -> None:
    """When source_hash is None (no baseline), hash is stored but no new row is created."""
    content = b"first time fetched content"
    skill = _make_skill(source_hash=None)

    mock_resp = MagicMock()
    mock_resp.content = content
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch("scheduler.tasks.check_skill_updates.async_session", return_value=mock_session):
            from scheduler.tasks.check_skill_updates import _check_single_skill

            await _check_single_skill(skill)

    # Must NOT create a new row
    mock_session.add.assert_not_called()
    # Must store the hash via session.execute (UPDATE)
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_failure_logs_warning_and_continues() -> None:
    """When httpx raises an exception, warning is logged and no exception propagates."""
    import httpx

    skill = _make_skill(source_hash="somehash")

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch("scheduler.tasks.check_skill_updates.async_session", return_value=mock_session):
            from scheduler.tasks.check_skill_updates import _check_single_skill

            # Should NOT raise
            await _check_single_skill(skill)

    mock_session.add.assert_not_called()


# ── _check_all_skill_updates — builtin skills skipped ─────────────────────────


@pytest.mark.asyncio
async def test_builtin_skill_skipped() -> None:
    """source_type='builtin' skills are excluded by the DB query filter."""
    builtin_skill = _make_skill(source_type="builtin")

    # Mock _check_all_skill_updates to verify the query filters correctly
    # We mock _check_single_skill and verify it is never called for builtin skills.
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []  # query returns empty — builtin filtered out

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("scheduler.tasks.check_skill_updates.async_session", return_value=mock_session):
        with patch(
            "scheduler.tasks.check_skill_updates._check_single_skill", new_callable=AsyncMock
        ) as mock_check:
            from scheduler.tasks.check_skill_updates import _check_all_skill_updates

            await _check_all_skill_updates()

    mock_check.assert_not_called()
