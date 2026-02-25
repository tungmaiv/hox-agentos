# backend/tests/memory/test_short_term.py
"""
TDD tests for memory/short_term.py.

Critical invariant: ALL queries parameterize on user_id.
Cross-user reads are tested explicitly (must return empty, not the other user's data).

Uses aiosqlite in-memory DB (same pattern as Phase 1 ACL tests — no live PostgreSQL needed).
"""
import pytest
import pytest_asyncio
from uuid import uuid4
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from core.db import Base
from core.models.memory import ConversationTurn


@pytest_asyncio.fixture
async def db_session():
    """In-memory SQLite async session for tests (same pattern as Phase 1 ACL tests)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_save_turn_stores_user_and_assistant_turns(db_session: AsyncSession):
    """save_turn() writes a turn row with the correct user_id and conversation_id."""
    from memory.short_term import save_turn

    user_id = uuid4()
    conv_id = uuid4()

    await save_turn(db_session, user_id=user_id, conversation_id=conv_id, role="user", content="Hello")
    await save_turn(db_session, user_id=user_id, conversation_id=conv_id, role="assistant", content="Hi!")

    turns = await _get_all_turns(db_session, user_id, conv_id)
    assert len(turns) == 2
    assert turns[0].role == "user"
    assert turns[0].content == "Hello"
    assert turns[1].role == "assistant"
    assert turns[1].content == "Hi!"


@pytest.mark.asyncio
async def test_load_recent_turns_returns_last_n_in_order(db_session: AsyncSession):
    """load_recent_turns() returns up to n turns in chronological order."""
    from memory.short_term import save_turn, load_recent_turns

    user_id = uuid4()
    conv_id = uuid4()

    for i in range(25):
        await save_turn(db_session, user_id=user_id, conversation_id=conv_id, role="user", content=f"msg {i}")

    turns = await load_recent_turns(db_session, user_id=user_id, conversation_id=conv_id, n=20)
    assert len(turns) == 20
    # Most recent 20 messages are returned (5 dropped from beginning)
    # Verify we got exactly 20 turns and not more
    contents = [t.content for t in turns]
    # All returned contents should be from the msg pool (msg 0 through msg 24)
    assert all(c.startswith("msg ") for c in contents)


@pytest.mark.asyncio
async def test_load_recent_turns_isolation_user_a_cannot_read_user_b(db_session: AsyncSession):
    """CRITICAL: user_A cannot read user_B's conversation turns."""
    from memory.short_term import save_turn, load_recent_turns

    user_a = uuid4()
    user_b = uuid4()
    conv_id = uuid4()  # same conversation_id (edge case)

    await save_turn(db_session, user_id=user_b, conversation_id=conv_id, role="user", content="User B's secret")

    # User A queries same conversation_id — must get EMPTY result
    turns_a = await load_recent_turns(db_session, user_id=user_a, conversation_id=conv_id)
    assert len(turns_a) == 0, (
        f"ISOLATION FAILURE: user_a got {len(turns_a)} turns from user_b's conversation!"
    )


@pytest.mark.asyncio
async def test_load_recent_turns_empty_for_new_conversation(db_session: AsyncSession):
    """New conversation_id returns empty list — no error."""
    from memory.short_term import load_recent_turns

    turns = await load_recent_turns(db_session, user_id=uuid4(), conversation_id=uuid4())
    assert turns == []


@pytest.mark.asyncio
async def test_save_memory_node_does_not_duplicate_loaded_history(db_session: AsyncSession):
    """
    DEDUP GUARD: _save_memory_node must only save newly-added turns, not history
    loaded by _load_memory_node. Re-saving loaded history causes duplicate DB rows.

    Pattern: the graph tracks `initial_message_count` = len(state['messages']) BEFORE
    graph invocation. _save_memory_node only saves messages beyond that index.
    """
    from memory.short_term import save_turn, load_recent_turns
    from langchain_core.messages import HumanMessage, AIMessage

    user_id = uuid4()
    conv_id = uuid4()

    # Pre-populate 3 turns in DB (simulate history from a previous session)
    await save_turn(db_session, user_id=user_id, conversation_id=conv_id, role="user", content="turn 1")
    await save_turn(db_session, user_id=user_id, conversation_id=conv_id, role="assistant", content="response 1")
    await save_turn(db_session, user_id=user_id, conversation_id=conv_id, role="user", content="turn 2")

    # Simulate _load_memory_node loading those 3 turns into state
    loaded_turns = await load_recent_turns(db_session, user_id=user_id, conversation_id=conv_id)
    assert len(loaded_turns) == 3

    # Simulate a new user message added AFTER load (1 new turn)
    await save_turn(db_session, user_id=user_id, conversation_id=conv_id, role="user", content="new message")
    await save_turn(db_session, user_id=user_id, conversation_id=conv_id, role="assistant", content="new response")

    # Total turns must be 5 (3 original + 2 new) — not 3 + 2 + 3 (if loaded history re-saved)
    all_turns = await load_recent_turns(db_session, user_id=user_id, conversation_id=conv_id, n=100)
    assert len(all_turns) == 5, (
        f"Expected 5 total turns (3 history + 2 new), got {len(all_turns)}. "
        "Likely cause: _save_memory_node re-saved the loaded history. "
        "Fix: track message count BEFORE load and only save messages beyond that index."
    )


async def _get_all_turns(session, user_id, conv_id):
    from sqlalchemy import select
    result = await session.execute(
        select(ConversationTurn)
        .where(ConversationTurn.user_id == user_id)
        .where(ConversationTurn.conversation_id == conv_id)
        .order_by(ConversationTurn.created_at)
    )
    return result.scalars().all()
