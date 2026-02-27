"""Tests for channel_accounts and channel_sessions ORM models."""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db import Base
from core.models.channel import ChannelAccount, ChannelSession


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_sess = async_sessionmaker(engine, expire_on_commit=False)
    async with async_sess() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_channel_account(session: AsyncSession):
    acct = ChannelAccount(
        id=uuid.uuid4(),
        channel="telegram",
        external_user_id="12345678",
        display_name="Test User",
        is_paired=False,
    )
    session.add(acct)
    await session.commit()

    result = await session.execute(
        select(ChannelAccount).where(ChannelAccount.channel == "telegram")
    )
    row = result.scalar_one()
    assert row.external_user_id == "12345678"
    assert row.is_paired is False
    assert row.user_id is None


@pytest.mark.asyncio
async def test_create_channel_session(session: AsyncSession):
    acct = ChannelAccount(
        id=uuid.uuid4(),
        channel="whatsapp",
        external_user_id="+84912345678",
        is_paired=True,
        user_id=uuid.uuid4(),
    )
    session.add(acct)
    await session.flush()

    sess = ChannelSession(
        id=uuid.uuid4(),
        channel_account_id=acct.id,
        external_chat_id="+84912345678",
        conversation_id=uuid.uuid4(),
    )
    session.add(sess)
    await session.commit()

    result = await session.execute(
        select(ChannelSession).where(ChannelSession.channel_account_id == acct.id)
    )
    row = result.scalar_one()
    assert row.is_active is True
    assert row.external_chat_id == "+84912345678"


@pytest.mark.asyncio
async def test_channel_account_unique_constraint(session: AsyncSession):
    """Same (channel, external_user_id) pair cannot be inserted twice."""
    kwargs = dict(channel="telegram", external_user_id="99999", is_paired=False)
    session.add(ChannelAccount(id=uuid.uuid4(), **kwargs))
    await session.commit()

    from sqlalchemy.exc import IntegrityError

    session.add(ChannelAccount(id=uuid.uuid4(), **kwargs))
    with pytest.raises(IntegrityError):
        await session.commit()
