"""
Cross-user memory and credential isolation pen tests.

Verifies application-level user_id isolation — User A cannot read User B's data.
These tests use in-memory SQLite (no live PostgreSQL or RLS enforcement).
They verify the application-layer WHERE user_id = $1 clauses.

RLS is the PostgreSQL defense-in-depth layer (migration 016); application isolation
is the primary control verified here.

Test Coverage:
  1. Conversation turns (short-term memory) — User A cannot read User B's turns
  2. Credentials — User A cannot read User B's credentials
  3. Long-term memory facts — SKIPPED (MemoryFact uses pgvector Vector(1024),
     incompatible with SQLite; isolation verified at query-level code review)
  4. Workflow runs — User A cannot read User B's workflow runs via ORM query
  5. Credential upsert — Upsert does not leak tokens across users (same provider)
"""
import os

import pytest
import pytest_asyncio
from uuid import uuid4, UUID
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

from core.db import Base
import core.models  # noqa: F401 — registers all ORM models in Base.metadata before db_session fixture

# Ensure CREDENTIAL_ENCRYPTION_KEY is set for crypto tests.
# test_credentials.py sets this too; setdefault() is idempotent.
_TEST_KEY = b"test_encryption_key_32bytes_here"
assert len(_TEST_KEY) == 32, "Test key must be exactly 32 bytes for AES-256"
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", _TEST_KEY.hex())


@pytest_asyncio.fixture
async def db_session():
    """
    In-memory SQLite async session — no PostgreSQL required.

    Uses StaticPool so all connections share the same in-memory DB instance.
    This prevents "no such table" errors from aiosqlite's connection isolation.
    """
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


@pytest.fixture
def user_a_id() -> UUID:
    return uuid4()


@pytest.fixture
def user_b_id() -> UUID:
    return uuid4()


# ---------------------------------------------------------------------------
# Test 1: Short-term memory isolation (conversation turns)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_a_cannot_read_user_b_conversation_turns(
    db_session, user_a_id: UUID, user_b_id: UUID
) -> None:
    """
    ISOLATION TEST: User A cannot read User B's conversation turns.

    Saves 2 turns for User B, then loads turns for User A with a fresh
    conversation_id. Result must be an empty list — User A sees no data.
    """
    from memory.short_term import save_turn, load_recent_turns

    conversation_b = uuid4()

    # Save 2 turns for User B
    await save_turn(
        db_session,
        user_id=user_b_id,
        conversation_id=conversation_b,
        role="user",
        content="User B's private message 1",
    )
    await save_turn(
        db_session,
        user_id=user_b_id,
        conversation_id=conversation_b,
        role="assistant",
        content="User B's private response",
    )
    await db_session.commit()

    # User A tries to read with their own (different) conversation_id
    user_a_conversation = uuid4()
    turns = await load_recent_turns(
        db_session,
        user_id=user_a_id,
        conversation_id=user_a_conversation,
    )

    assert turns == [], (
        f"ISOLATION FAILURE: User A read {len(turns)} of User B's turns! "
        "WHERE user_id filter is broken."
    )


@pytest.mark.asyncio
async def test_user_a_cannot_read_user_b_conversation_turns_even_with_same_conversation_id(
    db_session, user_a_id: UUID, user_b_id: UUID
) -> None:
    """
    EDGE CASE: Even if User A somehow knows User B's conversation_id,
    the user_id filter must prevent cross-user reads.

    This is a more aggressive attack scenario — the query uses BOTH
    user_id AND conversation_id, so both must match.
    """
    from memory.short_term import save_turn, load_recent_turns

    # Both users share the same conversation_id (adversarial scenario)
    shared_conversation_id = uuid4()

    await save_turn(
        db_session,
        user_id=user_b_id,
        conversation_id=shared_conversation_id,
        role="user",
        content="User B's secret content",
    )
    await db_session.commit()

    # User A queries with User B's conversation_id but User A's user_id
    turns = await load_recent_turns(
        db_session,
        user_id=user_a_id,
        conversation_id=shared_conversation_id,
    )

    assert turns == [], (
        "ISOLATION FAILURE: User A read User B's turn by guessing conversation_id! "
        "user_id AND conversation_id must both match."
    )


# ---------------------------------------------------------------------------
# Test 2: Credential isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_a_cannot_read_user_b_credentials(
    db_session, user_a_id: UUID, user_b_id: UUID
) -> None:
    """
    ISOLATION TEST: User A cannot read User B's OAuth credentials.

    Stores a credential for User B (provider: gmail), then User A queries
    the same provider. Result must be None.
    """
    from security.credentials import store_credential, get_credential

    # Store User B's credential
    await store_credential(
        db_session,
        user_id=user_b_id,
        provider="gmail",
        token="user_b_secret_gmail_token",
    )

    # User A queries same provider
    result = await get_credential(db_session, user_id=user_a_id, provider="gmail")

    assert result is None, (
        f"ISOLATION FAILURE: User A retrieved '{result}' from User B's credential! "
        "WHERE user_id filter is broken in get_credential()."
    )


# ---------------------------------------------------------------------------
# Test 3: Long-term memory facts
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason=(
        "MemoryFact uses pgvector Vector(1024) which cannot be created in SQLite "
        "(aiosqlite DDL error: unknown type 'VECTOR'). "
        "Isolation is enforced by WHERE user_id = $1 in search_facts() — "
        "verified at code review level. RLS migration 016 adds DB-level defense-in-depth "
        "for this table on PostgreSQL."
    )
)
@pytest.mark.asyncio
async def test_memory_facts_isolated_by_user_id(
    db_session, user_a_id: UUID, user_b_id: UUID
) -> None:
    """
    SKIPPED: Long-term memory fact isolation via search_facts().

    Would test: save fact for User B, search_facts(user_id=user_a_id) returns [].
    Skipped because MemoryFact.embedding is Vector(1024) — pgvector type,
    not supported by SQLite used in unit test fixtures.
    """
    from memory.long_term import save_fact, search_facts

    await save_fact(
        db_session,
        user_id=user_b_id,
        content="User B's private fact",
        source="conversation",
    )
    await db_session.commit()

    # search_facts requires a query_embedding (list of 1024 floats) — pgvector only
    results = await search_facts(
        db_session,
        user_id=user_a_id,
        query_embedding=[0.0] * 1024,
        k=5,
    )
    assert results == [], "ISOLATION FAILURE: User A read User B's memory fact!"


# ---------------------------------------------------------------------------
# Test 4: Workflow run isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_cannot_read_another_users_workflow_runs(
    db_session, user_a_id: UUID, user_b_id: UUID
) -> None:
    """
    ISOLATION TEST: User A cannot read User B's workflow runs.

    Directly inserts a WorkflowRun for User B, then queries WorkflowRun
    with User A's owner_user_id — must return empty.
    """
    from core.models.workflow import Workflow, WorkflowRun

    # Create a workflow owned by User B
    workflow = Workflow(
        owner_user_id=user_b_id,
        name="User B's Workflow",
        definition_json={"schema_version": "1.0", "nodes": [], "edges": []},
    )
    db_session.add(workflow)
    await db_session.flush()  # flush to get workflow.id without committing

    # Create a workflow run for User B
    run = WorkflowRun(
        workflow_id=workflow.id,
        owner_user_id=user_b_id,
        trigger_type="manual",
        status="completed",
        owner_roles_json=["employee"],
    )
    db_session.add(run)
    await db_session.commit()

    # User A queries workflow runs with their own user_id
    result = await db_session.execute(
        select(WorkflowRun).where(WorkflowRun.owner_user_id == user_a_id)
    )
    runs = result.scalars().all()

    assert len(runs) == 0, (
        f"ISOLATION FAILURE: User A found {len(runs)} of User B's workflow runs! "
        "WHERE owner_user_id filter is broken."
    )


# ---------------------------------------------------------------------------
# Test 5: Credential upsert does not leak across users
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_credential_store_upsert_does_not_leak_across_users(
    db_session, user_a_id: UUID, user_b_id: UUID
) -> None:
    """
    ISOLATION TEST: Credential upsert for same provider does not mix tokens.

    Both users store credentials for "gmail". Each user must retrieve their
    own token — not the other's. This verifies that upsert (select-then-update)
    correctly scopes to user_id and does not accidentally overwrite.
    """
    from security.credentials import store_credential, get_credential

    # Store different tokens for same provider — both users
    await store_credential(db_session, user_id=user_a_id, provider="gmail", token="token_for_user_a")
    await store_credential(db_session, user_id=user_b_id, provider="gmail", token="token_for_user_b")

    # Each user retrieves their own token
    token_a = await get_credential(db_session, user_id=user_a_id, provider="gmail")
    token_b = await get_credential(db_session, user_id=user_b_id, provider="gmail")

    assert token_a == "token_for_user_a", (
        f"ISOLATION FAILURE: User A got '{token_a}' instead of 'token_for_user_a'! "
        "Upsert leaked User B's token to User A."
    )
    assert token_b == "token_for_user_b", (
        f"ISOLATION FAILURE: User B got '{token_b}' instead of 'token_for_user_b'! "
        "Upsert leaked User A's token to User B."
    )
    assert token_a != token_b, (
        "ISOLATION FAILURE: Both users retrieved the same token! "
        "Credential isolation is completely broken."
    )
