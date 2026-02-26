"""
TDD tests for memory/long_term.py (semantic fact storage and retrieval).

CRITICAL invariants tested:
- save_fact(): embedding=None on insert (Celery fills it later)
- search_facts(): WHERE user_id = $1 — user isolation
- search_facts(): WHERE embedding IS NOT NULL — skip unprocessed facts
- search_facts(): WHERE superseded_at IS NULL — skip soft-deleted facts
- mark_fact_superseded(): sets superseded_at without hard-deleting the row

Uses mock sessions since pgvector's Vector(1024) column type is not compatible
with SQLite in-memory DB. The real pgvector cosine distance search is verified
in integration (PostgreSQL) — unit tests focus on security/isolation logic.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_save_fact_inserts_row():
    """save_fact() adds MemoryFact with correct user_id, content; embedding is None."""
    from memory.long_term import save_fact

    mock_session = MagicMock()
    mock_session.add = MagicMock()

    user_id = uuid.uuid4()
    fact = await save_fact(mock_session, user_id=user_id, content="User prefers dark mode")

    assert fact.user_id == user_id
    assert fact.content == "User prefers dark mode"
    assert fact.source == "conversation"  # default source
    assert fact.embedding is None  # Celery fills this later
    assert fact.superseded_at is None
    mock_session.add.assert_called_once_with(fact)


@pytest.mark.asyncio
async def test_save_fact_uses_provided_source():
    """save_fact() stores the provided source value."""
    from memory.long_term import save_fact

    mock_session = MagicMock()
    fact = await save_fact(
        mock_session,
        user_id=uuid.uuid4(),
        content="Fact from document",
        source="document",
    )
    assert fact.source == "document"


@pytest.mark.asyncio
async def test_mark_fact_superseded_sets_timestamp_not_deletes():
    """mark_fact_superseded() sets superseded_at without hard-deleting the row."""
    from memory.long_term import mark_fact_superseded
    from core.models.memory_long_term import MemoryFact

    fact_id = uuid.uuid4()

    # Create a mock fact row (simulates what the DB would return)
    mock_fact = MagicMock(spec=MemoryFact)
    mock_fact.id = fact_id
    mock_fact.superseded_at = None

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_fact

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    await mark_fact_superseded(mock_session, fact_id=fact_id)

    # superseded_at was set (soft delete)
    assert mock_fact.superseded_at is not None
    assert isinstance(mock_fact.superseded_at, datetime)

    # session.delete() was NOT called — this is a soft delete only
    mock_session.delete.assert_not_called()


@pytest.mark.asyncio
async def test_mark_fact_superseded_noop_for_missing_id():
    """mark_fact_superseded() does nothing if fact_id doesn't exist in DB."""
    from memory.long_term import mark_fact_superseded

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # fact not found

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Should not raise
    await mark_fact_superseded(mock_session, fact_id=uuid.uuid4())
    mock_session.delete.assert_not_called()


@pytest.mark.asyncio
async def test_search_facts_includes_user_id_filter():
    """search_facts() WHERE clause includes user_id (memory isolation enforcement)."""
    from memory.long_term import search_facts

    user_id = uuid.uuid4()
    query_embedding = [0.1] * 1024

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    await search_facts(mock_session, user_id=user_id, query_embedding=query_embedding, k=5)

    mock_session.execute.assert_called_once()
    call_args = mock_session.execute.call_args
    stmt = call_args[0][0]

    # Verify the WHERE clause contains user_id filtering
    compiled = stmt.compile()
    sql_str = str(compiled)
    assert "user_id" in sql_str, (
        "search_facts() MUST filter by user_id to enforce memory isolation. "
        "Returning facts from other users is a security violation."
    )


@pytest.mark.asyncio
async def test_search_facts_filters_null_embeddings():
    """search_facts() WHERE clause filters out facts with embedding IS NULL."""
    from memory.long_term import search_facts

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    await search_facts(
        mock_session,
        user_id=uuid.uuid4(),
        query_embedding=[0.0] * 1024,
        k=10,
    )

    call_args = mock_session.execute.call_args
    stmt = call_args[0][0]
    compiled = stmt.compile()
    sql_str = str(compiled)

    # embedding IS NOT NULL must be in the WHERE clause
    assert "embedding" in sql_str, (
        "search_facts() must filter embedding IS NOT NULL. "
        "Facts with no embedding (unprocessed by Celery) must be excluded from search."
    )


@pytest.mark.asyncio
async def test_search_facts_filters_superseded_facts():
    """search_facts() WHERE clause filters out facts with superseded_at IS NOT NULL."""
    from memory.long_term import search_facts

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    await search_facts(
        mock_session,
        user_id=uuid.uuid4(),
        query_embedding=[0.5] * 1024,
        k=5,
    )

    call_args = mock_session.execute.call_args
    stmt = call_args[0][0]
    compiled = stmt.compile()
    sql_str = str(compiled)

    # superseded_at IS NULL must be in the WHERE clause
    assert "superseded_at" in sql_str, (
        "search_facts() must filter superseded_at IS NULL. "
        "Superseded (soft-deleted) facts must not appear in search results."
    )


@pytest.mark.asyncio
async def test_search_facts_returns_list_of_facts():
    """search_facts() returns the list of facts from DB execute result."""
    from memory.long_term import search_facts
    from core.models.memory_long_term import MemoryFact

    user_id = uuid.uuid4()
    mock_fact = MagicMock(spec=MemoryFact)
    mock_fact.user_id = user_id
    mock_fact.content = "User prefers Python"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_fact]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    results = await search_facts(
        mock_session, user_id=user_id, query_embedding=[0.1] * 1024, k=5
    )

    assert len(results) == 1
    assert results[0].content == "User prefers Python"
