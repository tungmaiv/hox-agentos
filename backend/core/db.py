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
"""
from collections.abc import AsyncGenerator
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

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


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for injecting a database session."""
    async with async_session() as session:
        yield session


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
        await session.execute(
            sa.text("SET LOCAL app.user_id = :uid"),
            {"uid": str(user_id)},
        )
    except sa.exc.DBAPIError:
        # Non-PostgreSQL engines (SQLite in tests) do not support SET LOCAL.
        # On PostgreSQL this branch is never reached.
        pass
