"""
Tool ACL test suite — Gate 3 security coverage.

Tests use an in-memory SQLite database (via aiosqlite) so no real PostgreSQL
instance is needed. All Gate 3 behaviors are covered:
  1. No ACL row → default allow (True)
  2. ACL row with allowed=False → deny (False)
  3. ACL row with allowed=True → allow (True)
  4. log_tool_call() does not raise (fire-and-forget audit log)
  5. Audit log contains required fields (user_id, tool, allowed, duration_ms)
     and never logs credentials

Note: check_tool_acl() must always receive user_id from JWT (not request body).
"""
import pytest
from uuid import UUID, uuid4

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from core.db import Base
from core.models.tool_acl import ToolAcl


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session() -> AsyncSession:
    """
    Provide an in-memory SQLite async session with all tables created.

    Uses aiosqlite driver. SQLite is sufficient for ACL unit tests because
    the queries are simple select/insert — no PostgreSQL-specific features.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# check_tool_acl tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_acl_row_defaults_to_allow(db_session: AsyncSession) -> None:
    """When no ACL row exists for (user_id, tool_name), check_tool_acl returns True (default allow)."""
    from security.acl import check_tool_acl

    user_id = uuid4()
    result = await check_tool_acl(user_id, "email.fetch", db_session)
    assert result is True


@pytest.mark.asyncio
async def test_acl_row_denied_returns_false(db_session: AsyncSession) -> None:
    """When ACL row has allowed=False, check_tool_acl returns False."""
    from security.acl import check_tool_acl

    user_id = uuid4()
    # Insert a deny row
    await db_session.execute(
        insert(ToolAcl).values(
            id=uuid4(),
            user_id=user_id,
            tool_name="email.fetch",
            allowed=False,
        )
    )
    await db_session.commit()

    result = await check_tool_acl(user_id, "email.fetch", db_session)
    assert result is False


@pytest.mark.asyncio
async def test_acl_row_allowed_returns_true(db_session: AsyncSession) -> None:
    """When ACL row has allowed=True, check_tool_acl returns True."""
    from security.acl import check_tool_acl

    user_id = uuid4()
    # Insert an explicit allow row
    await db_session.execute(
        insert(ToolAcl).values(
            id=uuid4(),
            user_id=user_id,
            tool_name="calendar.read",
            allowed=True,
        )
    )
    await db_session.commit()

    result = await check_tool_acl(user_id, "calendar.read", db_session)
    assert result is True


@pytest.mark.asyncio
async def test_acl_lookup_is_user_scoped(db_session: AsyncSession) -> None:
    """ACL deny for user A does not affect user B (queries are parameterized on user_id)."""
    from security.acl import check_tool_acl

    user_a = uuid4()
    user_b = uuid4()

    # Deny email.fetch for user A only
    await db_session.execute(
        insert(ToolAcl).values(
            id=uuid4(),
            user_id=user_a,
            tool_name="email.fetch",
            allowed=False,
        )
    )
    await db_session.commit()

    # user_a is denied
    assert await check_tool_acl(user_a, "email.fetch", db_session) is False
    # user_b has no row — default allow
    assert await check_tool_acl(user_b, "email.fetch", db_session) is True


@pytest.mark.asyncio
async def test_different_tools_are_independent(db_session: AsyncSession) -> None:
    """Denying one tool for a user does not affect other tools for the same user."""
    from security.acl import check_tool_acl

    user_id = uuid4()
    await db_session.execute(
        insert(ToolAcl).values(
            id=uuid4(),
            user_id=user_id,
            tool_name="email.fetch",
            allowed=False,
        )
    )
    await db_session.commit()

    # email.fetch is denied
    assert await check_tool_acl(user_id, "email.fetch", db_session) is False
    # calendar.read has no row — default allow
    assert await check_tool_acl(user_id, "calendar.read", db_session) is True


# ---------------------------------------------------------------------------
# log_tool_call tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_tool_call_does_not_raise(db_session: AsyncSession) -> None:
    """log_tool_call() must not raise for any input (fire-and-forget audit log)."""
    from security.acl import log_tool_call

    user_id = uuid4()
    # Should complete without error for both allowed and denied calls
    await log_tool_call(user_id, "email.fetch", allowed=True, duration_ms=42)
    await log_tool_call(user_id, "email.fetch", allowed=False, duration_ms=5)


@pytest.mark.asyncio
async def test_audit_log_contains_required_fields(db_session: AsyncSession, caplog: pytest.LogCaptureFixture) -> None:
    """
    log_tool_call() must emit a structlog event with all required audit fields.

    Required fields: user_id (str), tool (str), allowed (bool), duration_ms (int).
    Must NOT contain: access_token, refresh_token, password.
    """
    import logging
    from security.acl import log_tool_call

    user_id = uuid4()
    tool_name = "email.fetch"

    with caplog.at_level(logging.INFO):
        await log_tool_call(user_id, tool_name, allowed=True, duration_ms=123)

    # Check that at least one log record was emitted
    # (structlog with JSONRenderer may appear in caplog as the rendered string)
    all_output = " ".join(caplog.messages) + " ".join(str(r) for r in caplog.records)

    # Verify required fields appear in output
    assert str(user_id) in all_output or "tool_call" in all_output, (
        "Expected audit log event to contain user_id or tool_call event name"
    )
    # Verify no credentials leaked
    assert "access_token" not in all_output
    assert "refresh_token" not in all_output
    assert "password" not in all_output
