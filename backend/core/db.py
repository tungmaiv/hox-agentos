"""
Async SQLAlchemy database engine and session factory.

Usage:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))

FastAPI dependency:
    async def endpoint(db: AsyncSession = Depends(get_db)):
        ...

RLS helper:
    await set_rls_user_id(session, user_id)
    # Call before any user-scoped query to populate app.user_id for RLS policies.

Single-session-per-request:
    Use get_session() instead of async_session() in route handlers and agents.
    RequestSessionMiddleware opens one session per HTTP request and stores it in
    _request_session_ctx. get_session() returns that session when set, or opens
    a new one (for Celery tasks, startup code, and test contexts).
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
)

# Single-session-per-request contextvar.
# Set by RequestSessionMiddleware at the start of each HTTP request.
# get_session() returns this session when set, or opens a new one.
_request_session_ctx: ContextVar[AsyncSession | None] = ContextVar(
    "_request_session_ctx", default=None
)


@asynccontextmanager
async def get_session():
    """
    Return the request-scoped DB session if available, else open a new one.

    Use this instead of `async with async_session()` in route handlers and
    business logic called from route handlers. Celery tasks and startup code
    that don't run inside an HTTP request will fall through to open a new session.

    Lifecycle contract:
    - Request context: yields the shared middleware session. Commit/rollback is
      handled by RequestSessionMiddleware after the response returns. Callers
      MUST NOT call session.commit() or session.rollback() on this session.
    - Standalone context (Celery, startup, tests): opens a new session, commits
      on clean exit, and rolls back on exception. Callers do not need to manage
      the transaction lifecycle.

    Usage:
        async with get_session() as session:
            result = await session.execute(...)
    """
    existing = _request_session_ctx.get()
    if existing is not None:
        yield existing
    else:
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


class RequestSessionMiddleware(BaseHTTPMiddleware):
    """
    Opens one AsyncSession per HTTP request and stores it in _request_session_ctx.

    All code within that request can call get_session() to retrieve the shared
    session — eliminating 6-9 separate session opens per agent invocation.

    The session is committed on success or rolled back on exception, then closed
    in the finally block regardless of outcome.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        async with async_session() as session:
            token = _request_session_ctx.set(session)
            try:
                response = await call_next(request)
                await session.commit()
                return response
            except Exception:
                await session.rollback()
                raise
            finally:
                _request_session_ctx.reset(token)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for injecting a database session."""
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def set_rls_user_id(session: AsyncSession, user_id: UUID) -> None:
    """
    Set the PostgreSQL session-local variable app.user_id for RLS policy evaluation.

    MUST be called before any user-scoped DB query in route handlers and Celery tasks.
    This populates the app.user_id context variable that RLS policies read via:
        current_setting('app.user_id', true)::uuid

    Uses SET LOCAL so the setting is scoped to the current transaction and does not
    leak across connection pool reuse.

    No-op on non-PostgreSQL engines (e.g., SQLite used in tests).

    Args:
        session: The active async DB session.
        user_id: The authenticated user's UUID from the JWT (Gate 1).

    Example:
        async with async_session() as session:
            await set_rls_user_id(session, current_user.id)
            result = await session.execute(select(MemoryFact).where(...))
    """
    try:
        # Use a literal UUID string (no bind params) so asyncpg sends SET LOCAL via the
        # Simple Query Protocol instead of Extended Query Protocol (PARSE + BIND + EXECUTE).
        # PostgreSQL rejects PARSE for SET statements, which aborts the transaction.
        # user_id is already a UUID type from JWT validation — str() only produces
        # hex digits and dashes, so there is no SQL injection risk here.
        await session.execute(
            sa.text(f"SET LOCAL app.user_id = '{user_id!s}'"),
        )
    except sa.exc.OperationalError:
        # Non-PostgreSQL engines (SQLite in tests) do not support SET LOCAL.
        # Narrowed from DBAPIError: PostgreSQL errors (InFailedSQLTransactionError etc.)
        # are not OperationalError and should not be silently swallowed.
        pass
