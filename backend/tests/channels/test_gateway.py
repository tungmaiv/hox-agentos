"""Tests for ChannelGateway: identity mapping, session resolution, pairing."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from channels.gateway import ChannelGateway
from channels.models import InternalMessage
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


@pytest.fixture
def gateway():
    return ChannelGateway(
        sidecar_urls={
            "telegram": "http://telegram-gateway:9001",
            "whatsapp": "http://whatsapp-gateway:9002",
            "ms_teams": "http://teams-gateway:9003",
        }
    )


# -- Identity mapping -------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_paired_account(session: AsyncSession, gateway: ChannelGateway):
    user_id = uuid.uuid4()
    acct = ChannelAccount(
        id=uuid.uuid4(),
        user_id=user_id,
        channel="telegram",
        external_user_id="111",
        is_paired=True,
    )
    session.add(acct)
    await session.commit()

    msg = InternalMessage(
        direction="inbound",
        channel="telegram",
        external_user_id="111",
        text="Hello",
    )
    result = await gateway.resolve_account(msg, session)
    assert result is not None
    assert result.user_id == user_id
    assert result.is_paired is True


@pytest.mark.asyncio
async def test_resolve_unknown_account_returns_none(
    session: AsyncSession, gateway: ChannelGateway
):
    msg = InternalMessage(
        direction="inbound",
        channel="telegram",
        external_user_id="unknown",
        text="Hello",
    )
    result = await gateway.resolve_account(msg, session)
    assert result is None


# -- Session resolution -----------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_or_create_session(session: AsyncSession, gateway: ChannelGateway):
    acct = ChannelAccount(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        channel="telegram",
        external_user_id="222",
        is_paired=True,
    )
    session.add(acct)
    await session.commit()

    msg = InternalMessage(
        direction="inbound",
        channel="telegram",
        external_user_id="222",
        external_chat_id="chat-222",
        text="Hello",
    )
    sess1 = await gateway.resolve_or_create_session(acct, msg, session)
    assert sess1.conversation_id is not None

    # Second call with same chat_id returns same session
    sess2 = await gateway.resolve_or_create_session(acct, msg, session)
    assert sess2.id == sess1.id
    assert sess2.conversation_id == sess1.conversation_id


# -- Pairing flow -----------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_pairing_code(session: AsyncSession, gateway: ChannelGateway):
    user_id = uuid.uuid4()
    code = await gateway.generate_pairing_code(user_id, "telegram", session)
    assert len(code) == 6
    assert code.isalnum()

    # Verify record in DB
    result = await session.execute(
        select(ChannelAccount).where(ChannelAccount.pairing_code == code)
    )
    acct = result.scalar_one()
    assert acct.user_id == user_id
    assert acct.is_paired is False
    assert acct.pairing_expires is not None


@pytest.mark.asyncio
async def test_handle_pairing_success(session: AsyncSession, gateway: ChannelGateway):
    user_id = uuid.uuid4()
    code = await gateway.generate_pairing_code(user_id, "telegram", session)

    msg = InternalMessage(
        direction="inbound",
        channel="telegram",
        external_user_id="333",
        external_chat_id="333",
        text=f"/pair {code}",
    )
    response = await gateway.handle_pairing(msg, session)
    assert response is not None
    assert "linked" in response.text.lower() or "success" in response.text.lower()

    # Verify account is now paired
    result = await session.execute(
        select(ChannelAccount).where(ChannelAccount.user_id == user_id)
    )
    acct = result.scalar_one()
    assert acct.is_paired is True
    assert acct.external_user_id == "333"
    assert acct.pairing_code is None


@pytest.mark.asyncio
async def test_handle_pairing_expired_code(session: AsyncSession, gateway: ChannelGateway):
    user_id = uuid.uuid4()
    # Create account with expired pairing code
    acct = ChannelAccount(
        id=uuid.uuid4(),
        user_id=user_id,
        channel="telegram",
        external_user_id="",  # not paired yet
        pairing_code="EXPIRE",
        pairing_expires=datetime.now(timezone.utc) - timedelta(minutes=1),
        is_paired=False,
    )
    session.add(acct)
    await session.commit()

    msg = InternalMessage(
        direction="inbound",
        channel="telegram",
        external_user_id="444",
        text="/pair EXPIRE",
    )
    response = await gateway.handle_pairing(msg, session)
    assert "expired" in response.text.lower() or "invalid" in response.text.lower()


@pytest.mark.asyncio
async def test_is_pairing_command():
    gw = ChannelGateway(sidecar_urls={})
    assert gw.is_pairing_command(
        InternalMessage(direction="inbound", channel="telegram", external_user_id="1", text="/pair ABC123")
    )
    assert not gw.is_pairing_command(
        InternalMessage(direction="inbound", channel="telegram", external_user_id="1", text="Hello")
    )
    assert not gw.is_pairing_command(
        InternalMessage(direction="inbound", channel="telegram", external_user_id="1", text=None)
    )
