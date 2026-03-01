"""
Tests for the get_user_db FastAPI dependency.

Verifies that the dependency sets app.user_id for RLS policy evaluation before
yielding the session to user-scoped route handlers.

RLS context: migration 016 adds FORCE ROW LEVEL SECURITY on memory_facts,
memory_conversations, user_credentials, workflow_runs, memory_episodes, and
conversation_titles. Without set_rls_user_id() being called, the blitz DB role
uses BYPASSRLS and returns all rows — isolation is silently broken.
"""
import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db import Base, get_db
from core.models.user import UserContext
from main import app
from security.deps import get_current_user

_USER_ID = uuid4()


def _make_user() -> UserContext:
    return UserContext(
        user_id=_USER_ID,
        email="alice@blitz.local",
        username="alice",
        roles=["employee"],
        groups=[],
    )


@pytest.fixture()
def sqlite_override():
    """Replace get_db with an in-memory SQLite session; restore after test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def _init() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_init())

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def fake_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = fake_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    loop.run_until_complete(engine.dispose())
    loop.close()


def test_get_user_db_calls_set_rls_user_id(sqlite_override) -> None:
    """
    A route using get_user_db must call set_rls_user_id with the JWT user_id.

    This is the critical invariant for RLS enforcement: migration 016 enables
    FORCE ROW LEVEL SECURITY but the policy only filters rows when app.user_id
    is set via SET LOCAL. Without this call, all queries bypass RLS silently.
    """
    from security import deps as deps_mod  # imported here to enable patching

    called: list[UUID] = []

    async def spy_set_rls(session: AsyncSession, user_id: UUID) -> None:
        called.append(user_id)

    app.dependency_overrides[get_current_user] = _make_user
    try:
        with patch.object(deps_mod, "set_rls_user_id", spy_set_rls):
            client = TestClient(app, raise_server_exceptions=True)
            client.get("/api/conversations/")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert _USER_ID in called, (
        "set_rls_user_id was not called with the authenticated user's user_id. "
        "The conversations route must use get_user_db instead of get_db so that "
        "RLS migration 016 is activated before any query."
    )


def test_conversations_route_returns_200_with_get_user_db(sqlite_override) -> None:
    """
    Switching conversations to get_user_db must not break the route.

    get_user_db calls set_rls_user_id then yields the same session. On SQLite
    (used in tests), set_rls_user_id is a no-op. The route must still return 200.
    """
    app.dependency_overrides[get_current_user] = _make_user
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get("/api/conversations/")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_set_rls_user_id_is_noop_on_sqlite(sqlite_override) -> None:
    """
    set_rls_user_id must not raise on non-PostgreSQL engines.

    SQLite does not support SET LOCAL. The function must silently skip on
    non-PostgreSQL dialects so that unit tests that use SQLite continue to pass
    after all user-scoped routes switch to get_user_db.
    """
    from core.db import set_rls_user_id

    user_id = uuid4()

    async def _run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            # Must not raise OperationalError or any other exception
            await set_rls_user_id(session, user_id)
        await engine.dispose()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()
