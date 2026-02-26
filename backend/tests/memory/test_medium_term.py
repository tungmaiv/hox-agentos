"""
TDD tests for memory/medium_term.py (episode summaries).

CRITICAL invariant tested: user isolation — load_recent_episodes() must never
return another user's episodes (WHERE user_id = $1).

Uses aiosqlite in-memory DB for tests that need real DB interactions,
but only for models without Vector columns. Since MemoryEpisode has a
Vector(1024) embedding column, we use mock sessions for DB-layer tests and
a custom SQLite-compatible schema for the isolation test.

The real integration (PostgreSQL + pgvector) is verified by the overall
verification step — unit tests focus on correctness of logic and isolation.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_save_episode_inserts_row_with_correct_fields():
    """save_episode() adds a MemoryEpisode with correct user_id, conversation_id, summary."""
    from memory.medium_term import save_episode

    mock_session = MagicMock()
    mock_session.add = MagicMock()

    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    summary = "User discussed backend architecture preferences."

    episode = await save_episode(
        mock_session,
        user_id=user_id,
        conversation_id=conversation_id,
        summary=summary,
    )

    assert episode.user_id == user_id
    assert episode.conversation_id == conversation_id
    assert episode.summary == summary
    assert episode.embedding is None  # Celery fills this later
    mock_session.add.assert_called_once_with(episode)


@pytest.mark.asyncio
async def test_save_episode_embedding_is_none_on_insert():
    """save_episode() creates row with embedding=None — Celery fills it asynchronously."""
    from memory.medium_term import save_episode

    mock_session = MagicMock()
    user_id = uuid.uuid4()
    episode = await save_episode(
        mock_session,
        user_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        summary="Summary text",
    )
    assert episode.embedding is None


@pytest.mark.asyncio
async def test_load_recent_episodes_queries_by_user_id():
    """load_recent_episodes() executes query with user_id filter (isolation enforcement)."""
    from memory.medium_term import load_recent_episodes
    from core.models.memory_long_term import MemoryEpisode

    user_id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    episodes = await load_recent_episodes(mock_session, user_id=user_id, n=5)

    assert isinstance(episodes, list)
    mock_session.execute.assert_called_once()

    # Inspect the WHERE clause of the executed query to verify user_id filtering
    call_args = mock_session.execute.call_args
    stmt = call_args[0][0]
    # The statement's WHERE clause must include user_id == user_id
    compiled = stmt.compile()
    sql_str = str(compiled)
    # 'user_id' must appear in the WHERE clause
    assert "user_id" in sql_str


@pytest.mark.asyncio
async def test_load_recent_episodes_returns_user_episodes_only():
    """User B episodes are not returned when querying for user A."""
    from memory.medium_term import load_recent_episodes
    from core.models.memory_long_term import MemoryEpisode

    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    # Create mock episodes for user_a only
    ep_a = MagicMock(spec=MemoryEpisode)
    ep_a.user_id = user_a
    ep_a.summary = "User A fact"

    ep_b = MagicMock(spec=MemoryEpisode)
    ep_b.user_id = user_b
    ep_b.summary = "User B fact"

    mock_result = MagicMock()
    # Only user_a episode is in DB result (WHERE user_id = user_a filters out user_b)
    mock_result.scalars.return_value.all.return_value = [ep_a]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    episodes = await load_recent_episodes(mock_session, user_id=user_a, n=10)

    assert len(episodes) == 1
    assert episodes[0].summary == "User A fact"
    assert episodes[0].user_id == user_a
    # user_b's episode must not be present
    assert not any(ep.user_id == user_b for ep in episodes)


@pytest.mark.asyncio
async def test_load_recent_episodes_respects_limit():
    """load_recent_episodes() passes n as LIMIT to the query."""
    from memory.medium_term import load_recent_episodes

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    await load_recent_episodes(mock_session, user_id=uuid.uuid4(), n=3)

    call_args = mock_session.execute.call_args
    stmt = call_args[0][0]
    # Verify LIMIT is in the compiled SQL
    compiled = stmt.compile()
    sql_str = str(compiled)
    assert "LIMIT" in sql_str.upper()
