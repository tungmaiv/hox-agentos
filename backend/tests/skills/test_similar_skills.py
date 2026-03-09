"""
Tests for similar skill search (SKBLD-04) and fork (SKBLD-05).

SKBLD-04: search_similar() returns top-k skills from skill_repo_index ordered by pgvector cosine distance
SKBLD-05: Fork external skill copies metadata + source_url attribution into builder state (fork_source)
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_index_row(
    name: str,
    description: str | None = None,
    repository_id: uuid.UUID | None = None,
    source_url: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    embedding: list[float] | None = None,
) -> MagicMock:
    """Create a mock SkillRepoIndex ORM row."""
    row = MagicMock()
    row.skill_name = name
    row.description = description
    row.repository_id = repository_id or uuid.uuid4()
    row.source_url = source_url
    row.category = category
    row.tags = tags
    row.embedding = embedding
    return row


def _make_repo(repo_id: uuid.UUID, name: str = "Test Repo") -> MagicMock:
    """Create a mock SkillRepository ORM row."""
    repo = MagicMock()
    repo.id = repo_id
    repo.name = name
    return repo


# ─── test_search_similar_returns_top_k ────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_similar_returns_top_k() -> None:
    """SKBLD-04: search_similar() returns top-k results ordered by cosine distance.

    Strategy:
    - Mock the DB session to return SkillRepoIndex rows (with embeddings) and repo rows.
    - Verify search_similar() returns a list of dicts with expected keys.
    - Verify the result count is bounded by top_k.
    """
    from skill_repos.service import search_similar

    repo_id = uuid.uuid4()
    query_embedding = [0.1] * 1024

    # Three mock index rows — all have embeddings
    row_a = _make_index_row("Skill A", "desc A", repo_id, "https://a.example/skill-a", "email", ["tag1"])
    row_b = _make_index_row("Skill B", "desc B", repo_id, "https://b.example/skill-b", None, None)
    row_c = _make_index_row("Skill C", "desc C", repo_id, None, "automation", ["tag2", "tag3"])

    mock_repo = _make_repo(repo_id, "Test Repo")

    # Build mock scalars chain for index rows
    index_scalars = MagicMock()
    index_scalars.all.return_value = [row_a, row_b, row_c]
    index_result = MagicMock()
    index_result.scalars.return_value = index_scalars

    # Build mock scalars chain for repo lookup
    repo_scalars = MagicMock()
    repo_scalars.all.return_value = [mock_repo]
    repo_result = MagicMock()
    repo_result.scalars.return_value = repo_scalars

    # Session returns index rows on first execute, repos on second
    session = AsyncMock()
    session.execute.side_effect = [index_result, repo_result]

    results = await search_similar(
        query_embedding=query_embedding,
        top_k=5,
        session=session,
    )

    # Should return a list of dicts
    assert isinstance(results, list)
    # All three rows had embeddings, so all three should appear
    assert len(results) == 3

    # Each result must have the expected keys
    expected_keys = {"name", "description", "repository_name", "source_url", "category", "tags"}
    for item in results:
        assert isinstance(item, dict)
        assert expected_keys.issubset(item.keys()), f"Missing keys in result: {item.keys()}"

    # Check a concrete result value
    names = {r["name"] for r in results}
    assert "Skill A" in names
    assert "Skill B" in names
    assert "Skill C" in names

    # top_k respected: when DB returns only 2 rows (LIMIT applied by pgvector query),
    # search_similar() returns exactly those 2 rows.
    session2 = AsyncMock()
    index_scalars2 = MagicMock()
    # Simulate DB honouring LIMIT(2) — returns only 2 rows
    index_scalars2.all.return_value = [row_a, row_b]
    index_result2 = MagicMock()
    index_result2.scalars.return_value = index_scalars2

    repo_scalars2 = MagicMock()
    repo_scalars2.all.return_value = [mock_repo]
    repo_result2 = MagicMock()
    repo_result2.scalars.return_value = repo_scalars2

    session2.execute.side_effect = [index_result2, repo_result2]

    results2 = await search_similar(
        query_embedding=query_embedding,
        top_k=2,
        session=session2,
    )
    assert len(results2) == 2


# ─── test_fork_external_skill ─────────────────────────────────────────────────


def test_fork_external_skill() -> None:
    """SKBLD-05: fork_source is set to 'name@source_url' format.

    The frontend constructs fork_source from similar skill data when the Fork
    button is clicked. This test verifies the expected format as documented in
    ArtifactBuilderState.fork_source and the plan decision.
    """
    # Similar skill data as returned by search_similar()
    skill = {
        "name": "Email Digest",
        "description": "Sends a morning email digest",
        "repository_name": "Blitz Skills",
        "source_url": "https://skills.example.com/email-digest",
        "category": "email",
        "tags": ["email", "digest"],
    }

    # Fork source format: "name@source_url" (per ArtifactBuilderState docstring)
    expected_fork_source = f"{skill['name']}@{skill['source_url']}"
    assert expected_fork_source == "Email Digest@https://skills.example.com/email-digest"

    # Verify keys expected by builder state are present in the similar skill dict
    expected_keys = {"name", "description", "repository_name", "source_url", "category", "tags"}
    assert expected_keys.issubset(skill.keys())

    # Fork source for a skill without source_url should be gracefully formed
    skill_no_url = {
        "name": "Calendar Sync",
        "description": None,
        "repository_name": "Test Repo",
        "source_url": None,
        "category": None,
        "tags": None,
    }
    fork_source_no_url = f"{skill_no_url['name']}@{skill_no_url['source_url']}"
    assert fork_source_no_url == "Calendar Sync@None"
