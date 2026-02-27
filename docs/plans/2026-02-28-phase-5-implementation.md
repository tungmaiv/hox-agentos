# Phase 5: Multi-Channel Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable Telegram, WhatsApp, and MS Teams channels via sidecar Docker services with shared identity pairing and a unified ChannelGateway in the backend.

**Architecture:** Each channel is a standalone FastAPI sidecar with `/webhook` (inbound) and `/send` (outbound). All sidecars forward `InternalMessage` JSON to the backend's `/api/channels/incoming`. The backend `ChannelGateway` handles identity mapping (pairing codes), session resolution, and agent invocation — then calls the sidecar's `/send` for outbound delivery.

**Tech Stack:** FastAPI, SQLAlchemy async, httpx, python-telegram-bot (types only), WhatsApp Cloud API, botbuilder-core (Teams), Pydantic v2, structlog, Next.js 15 (settings UI).

**Design doc:** `docs/plans/2026-02-28-phase-5-channels-design.md`

**Canonical test command:** `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q`
**Frontend build command:** `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm run build`
**Current Alembic head:** 012 — next migration is 013
**Current test baseline:** 258 tests passing

---

## Plan 05-01: Core — DB Models, InternalMessage, ChannelGateway, Pairing, Backend Routes

**Goal:** Build the shared foundation that all three channel sidecars depend on: database tables, Pydantic models, gateway logic, pairing flow, and API routes.

**Depends on:** Nothing (first plan)
**Depended on by:** Plans 05-02, 05-03, 05-04, 05-05

---

### Task 1: Channel ORM Models (ChannelAccount, ChannelSession)

**Files:**
- Create: `backend/core/models/channel.py`
- Modify: `backend/core/models/__init__.py` (line 16 — add imports)
- Test: `backend/tests/models/test_channel_models.py`

**Step 1: Write the failing test**

```python
# backend/tests/models/test_channel_models.py
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
```

**Step 2: Run test to verify it fails**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/models/test_channel_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'core.models.channel'`

**Step 3: Write the ORM models**

```python
# backend/core/models/channel.py
"""
SQLAlchemy ORM models for the multi-channel integration subsystem.

Two tables:
  - channel_accounts: maps external platform user → Blitz user (via pairing code)
  - channel_sessions: maps external conversation → internal conversation

Isolation rule: channel_accounts queries MUST include WHERE user_id=$1 from JWT
for authenticated endpoints. The /api/channels/incoming route looks up by
(channel, external_user_id) since it receives traffic from unauthenticated sidecars.

CRITICAL: No FK on user_id — users live in Keycloak, not PostgreSQL.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base

# JSON type compatible with SQLite (tests) and PostgreSQL (production).
_JSONB = JSON().with_variant(JSONB(), "postgresql")


class ChannelAccount(Base):
    __tablename__ = "channel_accounts"
    __table_args__ = (
        UniqueConstraint("channel", "external_user_id", name="uq_channel_external_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    external_user_id: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    pairing_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    pairing_expires: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_paired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict] = mapped_column(
        _JSONB, nullable=False, server_default="{}", default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChannelSession(Base):
    __tablename__ = "channel_sessions"
    __table_args__ = (
        UniqueConstraint(
            "channel_account_id", "external_chat_id", name="uq_account_chat"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    channel_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channel_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_chat_id: Mapped[str] = mapped_column(String(256), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

**Step 4: Register models in `__init__.py`**

Add at end of `backend/core/models/__init__.py` (after line 16):

```python
from core.models.channel import ChannelAccount, ChannelSession  # noqa: F401
```

**Step 5: Run tests to verify they pass**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/models/test_channel_models.py -v
```

Expected: 3 passed

**Step 6: Create Alembic migration**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
.venv/bin/alembic revision --autogenerate -m "add channel_accounts and channel_sessions tables"
```

Verify the generated migration creates both tables with correct columns, constraints, and indexes. Rename to `013_channel_tables.py` if needed.

**Step 7: Commit**

```bash
git add backend/core/models/channel.py backend/core/models/__init__.py \
  backend/tests/models/test_channel_models.py backend/alembic/versions/*channel*
git commit -m "feat(05-01): add ChannelAccount and ChannelSession ORM models + migration 013"
```

---

### Task 2: InternalMessage Pydantic Models

**Files:**
- Create: `backend/channels/__init__.py`
- Create: `backend/channels/models.py`
- Test: `backend/tests/channels/test_models.py`

**Step 1: Write the failing test**

```python
# backend/tests/channels/__init__.py
# (empty — make it a package)
```

```python
# backend/tests/channels/test_models.py
"""Tests for InternalMessage and related Pydantic models."""
import uuid

import pytest

from channels.models import Attachment, InternalMessage, MessageAction


def test_inbound_message_minimal():
    msg = InternalMessage(
        direction="inbound",
        channel="telegram",
        external_user_id="12345",
        text="Hello",
    )
    assert msg.direction == "inbound"
    assert msg.channel == "telegram"
    assert msg.user_id is None
    assert msg.actions == []
    assert msg.attachments == []
    assert msg.is_group is False


def test_outbound_message_with_actions():
    msg = InternalMessage(
        direction="outbound",
        channel="whatsapp",
        external_user_id="+84912345678",
        external_chat_id="+84912345678",
        user_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        text="Do you approve this task?",
        actions=[
            MessageAction(label="Approve", action_id="approve_123", style="primary"),
            MessageAction(label="Reject", action_id="reject_123", style="danger"),
        ],
    )
    assert len(msg.actions) == 2
    assert msg.actions[0].label == "Approve"
    assert msg.actions[1].style == "danger"


def test_message_with_attachment():
    msg = InternalMessage(
        direction="inbound",
        channel="telegram",
        external_user_id="99999",
        attachments=[
            Attachment(type="image", url="https://example.com/photo.jpg", mime_type="image/jpeg"),
        ],
    )
    assert len(msg.attachments) == 1
    assert msg.attachments[0].type == "image"


def test_json_roundtrip():
    original = InternalMessage(
        direction="outbound",
        channel="ms_teams",
        external_user_id="teams-user-id",
        text="Summary report",
        actions=[MessageAction(label="View", action_id="view_1")],
    )
    json_str = original.model_dump_json()
    restored = InternalMessage.model_validate_json(json_str)
    assert restored.channel == "ms_teams"
    assert restored.actions[0].label == "View"


def test_invalid_channel_rejected():
    with pytest.raises(Exception):
        InternalMessage(
            direction="inbound",
            channel="discord",  # not in Literal
            external_user_id="123",
        )


def test_invalid_direction_rejected():
    with pytest.raises(Exception):
        InternalMessage(
            direction="sideways",  # not in Literal
            channel="telegram",
            external_user_id="123",
        )
```

**Step 2: Run test to verify it fails**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/channels/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'channels'`

**Step 3: Write the Pydantic models**

```python
# backend/channels/__init__.py
"""Multi-channel integration: gateway, adapters, and models."""
```

```python
# backend/channels/models.py
"""
Platform-agnostic message models for the multi-channel integration layer.

InternalMessage is the canonical format shared between:
  - Channel sidecars (Telegram, WhatsApp, Teams)
  - Backend ChannelGateway
  - Agent invocation and response delivery

All sidecars translate platform-specific events INTO InternalMessage (inbound)
and FROM InternalMessage (outbound). The backend never sees platform-specific payloads.
"""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class MessageAction(BaseModel):
    """An inline button attached to an outbound message."""

    label: str
    action_id: str
    style: Literal["primary", "secondary", "danger"] = "primary"


class Attachment(BaseModel):
    """A file or media item attached to a message."""

    type: Literal["image", "file", "audio", "video"]
    url: str | None = None
    file_path: str | None = None
    mime_type: str | None = None


class InternalMessage(BaseModel):
    """
    Canonical message format for all channels.

    Inbound: sidecar → backend (user_id and conversation_id filled by gateway)
    Outbound: backend → sidecar (all fields filled)
    """

    direction: Literal["inbound", "outbound"]
    channel: Literal["telegram", "whatsapp", "ms_teams", "web"]
    external_user_id: str
    external_chat_id: str | None = None
    user_id: UUID | None = None
    conversation_id: UUID | None = None
    text: str | None = None
    attachments: list[Attachment] = []
    actions: list[MessageAction] = []
    is_group: bool = False
    metadata: dict = {}
```

**Step 4: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/channels/test_models.py -v
```

Expected: 6 passed

**Step 5: Commit**

```bash
git add backend/channels/__init__.py backend/channels/models.py \
  backend/tests/channels/__init__.py backend/tests/channels/test_models.py
git commit -m "feat(05-01): add InternalMessage, MessageAction, Attachment Pydantic models"
```

---

### Task 3: ChannelGateway — Identity Mapping, Session Resolution, Pairing

**Files:**
- Create: `backend/channels/gateway.py`
- Test: `backend/tests/channels/test_gateway.py`

**Step 1: Write the failing test**

```python
# backend/tests/channels/test_gateway.py
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


# ── Identity mapping ──────────────────────────────────────────


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


# ── Session resolution ─────────────────────────────────────────


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


# ── Pairing flow ───────────────────────────────────────────────


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
```

**Step 2: Run test to verify it fails**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/channels/test_gateway.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'channels.gateway'`

**Step 3: Implement ChannelGateway**

```python
# backend/channels/gateway.py
"""
ChannelGateway — central dispatcher for all channel inbound/outbound traffic.

Responsibilities:
  1. Pairing command detection and processing (/pair <code>)
  2. Identity mapping: (channel, external_user_id) → ChannelAccount → user_id
  3. Session resolution: (channel_account, external_chat_id) → ChannelSession → conversation_id
  4. Agent invocation: reuse master agent's run_conversation (same as web chat)
  5. Outbound delivery: POST to the appropriate sidecar's /send endpoint

Security: /api/channels/incoming is internal-only (Docker network isolation).
All agent invocations pass through the same 3-gate security (user_id from channel_account).
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from channels.models import InternalMessage
from core.models.channel import ChannelAccount, ChannelSession

logger = structlog.get_logger(__name__)

_PAIRING_CODE_LENGTH = 6
_PAIRING_EXPIRY_MINUTES = 10


class ChannelGateway:
    def __init__(self, sidecar_urls: dict[str, str]) -> None:
        self.sidecar_urls = sidecar_urls

    # ── Public API ─────────────────────────────────────────────

    def is_pairing_command(self, msg: InternalMessage) -> bool:
        """Check if the message is a /pair command."""
        return bool(msg.text and msg.text.strip().startswith("/pair "))

    async def resolve_account(
        self, msg: InternalMessage, db: AsyncSession
    ) -> ChannelAccount | None:
        """Look up a ChannelAccount by (channel, external_user_id)."""
        result = await db.execute(
            select(ChannelAccount).where(
                and_(
                    ChannelAccount.channel == msg.channel,
                    ChannelAccount.external_user_id == msg.external_user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def resolve_or_create_session(
        self,
        account: ChannelAccount,
        msg: InternalMessage,
        db: AsyncSession,
    ) -> ChannelSession:
        """Find or create a ChannelSession for this chat."""
        chat_id = msg.external_chat_id or msg.external_user_id
        result = await db.execute(
            select(ChannelSession).where(
                and_(
                    ChannelSession.channel_account_id == account.id,
                    ChannelSession.external_chat_id == chat_id,
                )
            )
        )
        session = result.scalar_one_or_none()
        if session:
            session.last_activity_at = datetime.now(timezone.utc)
            await db.commit()
            return session

        new_session = ChannelSession(
            id=uuid.uuid4(),
            channel_account_id=account.id,
            external_chat_id=chat_id,
            conversation_id=uuid.uuid4(),
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        return new_session

    async def generate_pairing_code(
        self, user_id: uuid.UUID, channel: str, db: AsyncSession
    ) -> str:
        """Generate a 6-character alphanumeric pairing code for the user."""
        code = secrets.token_hex(3).upper()[:_PAIRING_CODE_LENGTH]
        expires = datetime.now(timezone.utc) + timedelta(minutes=_PAIRING_EXPIRY_MINUTES)

        # Upsert: if a pending (unpaired) account for this user+channel exists, update it
        result = await db.execute(
            select(ChannelAccount).where(
                and_(
                    ChannelAccount.user_id == user_id,
                    ChannelAccount.channel == channel,
                    ChannelAccount.is_paired == False,  # noqa: E712
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.pairing_code = code
            existing.pairing_expires = expires
        else:
            acct = ChannelAccount(
                id=uuid.uuid4(),
                user_id=user_id,
                channel=channel,
                external_user_id="",  # filled on pairing
                pairing_code=code,
                pairing_expires=expires,
                is_paired=False,
            )
            db.add(acct)
        await db.commit()

        logger.info("pairing_code_generated", user_id=str(user_id), channel=channel)
        return code

    async def handle_pairing(
        self, msg: InternalMessage, db: AsyncSession
    ) -> InternalMessage:
        """Process a /pair <code> command. Returns an outbound response message."""
        parts = (msg.text or "").strip().split()
        code = parts[1] if len(parts) >= 2 else ""

        result = await db.execute(
            select(ChannelAccount).where(
                and_(
                    ChannelAccount.pairing_code == code,
                    ChannelAccount.channel == msg.channel,
                    ChannelAccount.is_paired == False,  # noqa: E712
                )
            )
        )
        acct = result.scalar_one_or_none()

        if not acct:
            return self._make_reply(
                msg, "Invalid or expired pairing code. Please generate a new code in Settings."
            )

        now = datetime.now(timezone.utc)
        if acct.pairing_expires and acct.pairing_expires < now:
            return self._make_reply(
                msg, "Pairing code has expired. Please generate a new code in Settings."
            )

        # Link the account
        acct.external_user_id = msg.external_user_id
        acct.is_paired = True
        acct.pairing_code = None
        acct.pairing_expires = None
        acct.display_name = msg.metadata.get("display_name")
        await db.commit()

        logger.info(
            "channel_paired",
            user_id=str(acct.user_id),
            channel=msg.channel,
            external_user_id=msg.external_user_id,
        )
        return self._make_reply(
            msg,
            "Account linked successfully! You can now chat with Blitz here.",
        )

    async def handle_inbound(
        self, msg: InternalMessage, db: AsyncSession
    ) -> InternalMessage:
        """
        Main entry point for all inbound channel messages.

        1. Check for pairing command
        2. Resolve identity
        3. Resolve session
        4. Invoke agent (placeholder — wired in 05-05)
        5. Send outbound response
        """
        if self.is_pairing_command(msg):
            response = await self.handle_pairing(msg, db)
            await self.send_outbound(response)
            return response

        account = await self.resolve_account(msg, db)
        if not account or not account.is_paired:
            response = self._make_reply(
                msg,
                "Please link your account first. Visit Settings > Channel Linking in the Blitz web app.",
            )
            await self.send_outbound(response)
            return response

        msg.user_id = account.user_id
        session = await self.resolve_or_create_session(account, msg, db)
        msg.conversation_id = session.conversation_id

        # Agent invocation — placeholder, wired in 05-05
        response = await self._invoke_agent(msg)
        await self.send_outbound(response)
        return response

    async def send_outbound(self, msg: InternalMessage) -> None:
        """Send an outbound message to the appropriate channel sidecar."""
        if msg.channel == "web":
            logger.debug("outbound_web_skip", note="Web delivery handled by AG-UI")
            return

        url = self.sidecar_urls.get(msg.channel)
        if not url:
            logger.warning("outbound_no_sidecar", channel=msg.channel)
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{url}/send",
                    json=msg.model_dump(mode="json"),
                )
                resp.raise_for_status()
            logger.info(
                "outbound_sent",
                channel=msg.channel,
                external_user_id=msg.external_user_id,
            )
        except httpx.HTTPError as exc:
            logger.error(
                "outbound_send_failed",
                channel=msg.channel,
                error=str(exc),
            )

    # ── Private helpers ────────────────────────────────────────

    async def _invoke_agent(self, msg: InternalMessage) -> InternalMessage:
        """
        Invoke the master agent for a channel message.

        Placeholder for 05-01. Wired to real agent in 05-05.
        Returns a simple echo response for now.
        """
        logger.info(
            "channel_agent_invoke_stub",
            channel=msg.channel,
            user_id=str(msg.user_id),
        )
        return self._make_reply(msg, f"[Blitz] Received: {msg.text}")

    def _make_reply(self, original: InternalMessage, text: str) -> InternalMessage:
        """Create an outbound reply to an inbound message."""
        return InternalMessage(
            direction="outbound",
            channel=original.channel,
            external_user_id=original.external_user_id,
            external_chat_id=original.external_chat_id,
            user_id=original.user_id,
            conversation_id=original.conversation_id,
            text=text,
        )
```

**Step 4: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/channels/test_gateway.py -v
```

Expected: 7 passed

**Step 5: Commit**

```bash
git add backend/channels/gateway.py backend/tests/channels/test_gateway.py
git commit -m "feat(05-01): add ChannelGateway with identity mapping, session resolution, and pairing"
```

---

### Task 4: Backend API Routes for Channels

**Files:**
- Create: `backend/api/routes/channels.py`
- Modify: `backend/main.py` (add router registration)
- Test: `backend/tests/api/test_channel_routes.py`

**Step 1: Write the failing test**

```python
# backend/tests/api/test_channel_routes.py
"""Tests for channel API routes."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_user():
    return {
        "user_id": uuid.uuid4(),
        "email": "test@blitz.com",
        "username": "testuser",
        "roles": ["employee"],
        "groups": [],
    }


def _override_auth(mock_user):
    """Return a dependency override for get_current_user."""
    from security.deps import get_current_user

    async def _fake():
        return mock_user

    return {get_current_user: _fake}


# ── POST /api/channels/incoming ─────────────────────────────


def test_incoming_forwards_to_gateway(client: TestClient):
    with patch("api.routes.channels.get_channel_gateway") as mock_gw_fn:
        mock_gw = AsyncMock()
        mock_gw.handle_inbound.return_value = None
        mock_gw_fn.return_value = mock_gw

        resp = client.post(
            "/api/channels/incoming",
            json={
                "direction": "inbound",
                "channel": "telegram",
                "external_user_id": "12345",
                "text": "Hello",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_gw.handle_inbound.assert_called_once()


# ── POST /api/channels/pair ──────────────────────────────────


def test_pair_requires_auth(client: TestClient):
    resp = client.post("/api/channels/pair", json={"channel": "telegram"})
    assert resp.status_code == 401


def test_pair_generates_code(client: TestClient, mock_user):
    app = client.app
    app.dependency_overrides = _override_auth(mock_user)

    with patch("api.routes.channels.get_channel_gateway") as mock_gw_fn:
        mock_gw = AsyncMock()
        mock_gw.generate_pairing_code.return_value = "ABC123"
        mock_gw_fn.return_value = mock_gw

        resp = client.post("/api/channels/pair", json={"channel": "telegram"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "ABC123"
        assert data["expires_in"] == 600

    app.dependency_overrides = {}


# ── GET /api/channels/accounts ────────────────────────────────


def test_list_accounts_requires_auth(client: TestClient):
    resp = client.get("/api/channels/accounts")
    assert resp.status_code == 401
```

**Step 2: Run test to verify it fails**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/api/test_channel_routes.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'api.routes.channels'`

**Step 3: Implement the routes**

```python
# backend/api/routes/channels.py
"""
Channel integration API routes.

POST /api/channels/incoming  — receives InternalMessage from sidecars (no auth)
POST /api/channels/pair      — generate pairing code (requires JWT)
GET  /api/channels/accounts  — list user's linked channel accounts (requires JWT)
DELETE /api/channels/accounts/{account_id} — unlink a channel account (requires JWT)

Security notes:
  - /incoming is internal-only (Docker network isolation, no JWT)
  - /pair, /accounts require JWT via get_current_user dependency
"""
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from channels.gateway import ChannelGateway
from channels.models import InternalMessage
from core.db import get_db
from core.models.channel import ChannelAccount
from core.models.user import UserContext
from security.deps import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/channels", tags=["channels"])

# ── Gateway singleton ──────────────────────────────────────────

_gateway: ChannelGateway | None = None


def get_channel_gateway() -> ChannelGateway:
    """Return the singleton ChannelGateway. Initialized on first call."""
    global _gateway
    if _gateway is None:
        from core.config import settings

        sidecar_urls = {
            "telegram": getattr(settings, "telegram_gateway_url", "http://telegram-gateway:9001"),
            "whatsapp": getattr(settings, "whatsapp_gateway_url", "http://whatsapp-gateway:9002"),
            "ms_teams": getattr(settings, "teams_gateway_url", "http://teams-gateway:9003"),
        }
        _gateway = ChannelGateway(sidecar_urls=sidecar_urls)
    return _gateway


# ── Schemas ────────────────────────────────────────────────────


class PairRequest(BaseModel):
    channel: str


class PairResponse(BaseModel):
    code: str
    expires_in: int


class ChannelAccountResponse(BaseModel):
    id: UUID
    channel: str
    external_user_id: str
    display_name: str | None
    is_paired: bool


# ── Routes ─────────────────────────────────────────────────────


@router.post("/incoming")
async def channel_incoming(
    msg: InternalMessage,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Receive an InternalMessage from a channel sidecar.

    No JWT auth — this endpoint is internal-only (Docker network isolation).
    """
    gateway = get_channel_gateway()
    await gateway.handle_inbound(msg, db)
    return {"ok": True}


@router.post("/pair", response_model=PairResponse)
async def generate_pair_code(
    body: PairRequest,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PairResponse:
    """Generate a 6-digit pairing code for linking a channel account."""
    gateway = get_channel_gateway()
    code = await gateway.generate_pairing_code(user["user_id"], body.channel, db)
    return PairResponse(code=code, expires_in=600)


@router.get("/accounts", response_model=list[ChannelAccountResponse])
async def list_accounts(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChannelAccountResponse]:
    """List the authenticated user's linked channel accounts."""
    result = await db.execute(
        select(ChannelAccount).where(
            and_(
                ChannelAccount.user_id == user["user_id"],
                ChannelAccount.is_paired == True,  # noqa: E712
            )
        )
    )
    accounts = result.scalars().all()
    return [
        ChannelAccountResponse(
            id=a.id,
            channel=a.channel,
            external_user_id=a.external_user_id,
            display_name=a.display_name,
            is_paired=a.is_paired,
        )
        for a in accounts
    ]


@router.delete("/accounts/{account_id}", status_code=204)
async def unlink_account(
    account_id: UUID,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Unlink a channel account. Only the owning user can unlink."""
    result = await db.execute(
        select(ChannelAccount).where(
            and_(
                ChannelAccount.id == account_id,
                ChannelAccount.user_id == user["user_id"],
            )
        )
    )
    acct = result.scalar_one_or_none()
    if not acct:
        raise HTTPException(status_code=404, detail="Channel account not found")

    await db.delete(acct)
    await db.commit()
    logger.info(
        "channel_unlinked",
        user_id=str(user["user_id"]),
        channel=acct.channel,
    )
```

**Step 4: Register the router in `backend/main.py`**

Add import at line 24 (after `webhooks_router` import):

```python
from api.routes.channels import router as channels_router
```

Add registration before `return app` (before line 120):

```python
    # Channel integration routes — incoming (no auth), pair/accounts (JWT)
    app.include_router(channels_router)
```

**Step 5: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/api/test_channel_routes.py -v
```

Expected: 3 passed

**Step 6: Run full test suite**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: 258 + new tests passed (no regressions)

**Step 7: Commit**

```bash
git add backend/api/routes/channels.py backend/main.py \
  backend/tests/api/test_channel_routes.py
git commit -m "feat(05-01): add channel API routes — incoming, pair, accounts, unlink"
```

---

## Plan 05-02: Telegram Sidecar

**Goal:** Build the Telegram channel gateway as a standalone FastAPI Docker service.

**Depends on:** Plan 05-01 (InternalMessage model)

---

### Task 1: Telegram Sidecar — Project Setup and Webhook Handler

**Files:**
- Create: `channel-gateways/telegram/pyproject.toml`
- Create: `channel-gateways/telegram/main.py`
- Create: `channel-gateways/telegram/telegram_api.py`
- Create: `channel-gateways/telegram/Dockerfile`
- Create: `channel-gateways/telegram/tests/test_webhook.py`
- Create: `channel-gateways/telegram/tests/test_send.py`

**Step 1: Create `pyproject.toml`**

```toml
# channel-gateways/telegram/pyproject.toml
[project]
name = "blitz-telegram-gateway"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.34",
    "httpx>=0.28",
    "pydantic>=2.10",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "httpx",  # for TestClient
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

**Step 2: Create `telegram_api.py`**

```python
# channel-gateways/telegram/telegram_api.py
"""Thin wrapper around the Telegram Bot API (HTTP calls only)."""
import httpx
import structlog

logger = structlog.get_logger(__name__)


class TelegramAPI:
    def __init__(self, bot_token: str) -> None:
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "MarkdownV2",
        reply_markup: dict | None = None,
    ) -> dict:
        """Send a text message to a Telegram chat."""
        payload: dict = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{self.base_url}/sendMessage", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def answer_callback_query(self, callback_query_id: str, text: str = "") -> dict:
        """Acknowledge a callback query (button press)."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.base_url}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id, "text": text},
            )
            resp.raise_for_status()
            return resp.json()

    async def set_webhook(self, url: str) -> dict:
        """Register this service's URL as the Telegram webhook."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.base_url}/setWebhook",
                json={"url": url},
            )
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    def build_inline_keyboard(actions: list[dict]) -> dict:
        """Build an InlineKeyboardMarkup from MessageAction dicts."""
        buttons = [
            [{"text": a["label"], "callback_data": a["action_id"]}]
            for a in actions
        ]
        return {"inline_keyboard": buttons}
```

**Step 3: Create `main.py`**

```python
# channel-gateways/telegram/main.py
"""
Blitz Telegram Gateway — sidecar service for Telegram integration.

Endpoints:
  POST /webhook  — receives Telegram Update events, translates to InternalMessage
  POST /send     — receives InternalMessage from backend, sends via Telegram API
  GET  /health   — health check
"""
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import httpx
import structlog
from fastapi import FastAPI
from pydantic import BaseModel

from telegram_api import TelegramAPI

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
logger = structlog.get_logger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
WEBHOOK_URL = os.environ.get("WEBHOOK_EXTERNAL_URL", "")  # e.g., https://yourdomain.com/telegram/webhook

telegram = TelegramAPI(BOT_TOKEN)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    if WEBHOOK_URL:
        try:
            await telegram.set_webhook(WEBHOOK_URL)
            logger.info("telegram_webhook_set", url=WEBHOOK_URL)
        except Exception as exc:
            logger.warning("telegram_webhook_set_failed", error=str(exc))
    yield


app = FastAPI(title="Blitz Telegram Gateway", lifespan=lifespan)


# ── Pydantic models (subset of InternalMessage for sidecar use) ──


class MessageAction(BaseModel):
    label: str
    action_id: str
    style: str = "primary"


class InternalMessage(BaseModel):
    direction: str
    channel: str
    external_user_id: str
    external_chat_id: str | None = None
    user_id: str | None = None
    conversation_id: str | None = None
    text: str | None = None
    attachments: list[dict] = []
    actions: list[MessageAction] = []
    is_group: bool = False
    metadata: dict = {}


# ── Endpoints ──────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "telegram-gateway"}


@app.post("/webhook")
async def telegram_webhook(update: dict[str, Any]) -> dict:
    """
    Receive a Telegram Update and forward to backend as InternalMessage.

    Handles two event types:
      1. message — regular text/media messages
      2. callback_query — inline button presses
    """
    msg: InternalMessage | None = None

    if "callback_query" in update:
        cb = update["callback_query"]
        msg = InternalMessage(
            direction="inbound",
            channel="telegram",
            external_user_id=str(cb["from"]["id"]),
            external_chat_id=str(cb["message"]["chat"]["id"]),
            text=None,
            metadata={
                "callback_data": cb["data"],
                "callback_query_id": cb["id"],
                "display_name": _get_display_name(cb["from"]),
            },
        )
        # Acknowledge the callback to remove the loading spinner
        try:
            await telegram.answer_callback_query(cb["id"])
        except Exception:
            pass

    elif "message" in update:
        tg_msg = update["message"]
        chat = tg_msg.get("chat", {})
        msg = InternalMessage(
            direction="inbound",
            channel="telegram",
            external_user_id=str(tg_msg["from"]["id"]),
            external_chat_id=str(chat.get("id", tg_msg["from"]["id"])),
            text=tg_msg.get("text"),
            is_group=chat.get("type", "private") in ("group", "supergroup"),
            metadata={
                "display_name": _get_display_name(tg_msg["from"]),
                "message_id": tg_msg.get("message_id"),
            },
        )

    if msg is None:
        logger.debug("telegram_update_ignored", update_keys=list(update.keys()))
        return {"ok": True}

    # Forward to backend
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{BACKEND_URL}/api/channels/incoming",
                json=msg.model_dump(mode="json"),
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("backend_forward_failed", error=str(exc))

    return {"ok": True}


@app.post("/send")
async def send_message(msg: InternalMessage) -> dict:
    """
    Receive an InternalMessage from backend and send via Telegram API.

    Supports:
      - Plain text with Markdown
      - Inline keyboard buttons (from msg.actions)
    """
    chat_id = msg.external_chat_id or msg.external_user_id

    reply_markup = None
    if msg.actions:
        reply_markup = TelegramAPI.build_inline_keyboard(
            [a.model_dump() for a in msg.actions]
        )

    text = msg.text or ""
    if not text:
        return {"ok": True, "skipped": True}

    try:
        # Try MarkdownV2 first, fall back to plain text if parsing fails
        try:
            result = await telegram.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup,
            )
        except httpx.HTTPStatusError:
            result = await telegram.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="",
                reply_markup=reply_markup,
            )
        return {"ok": True, "message_id": result.get("result", {}).get("message_id")}
    except Exception as exc:
        logger.error("telegram_send_failed", error=str(exc), chat_id=chat_id)
        return {"ok": False, "error": str(exc)}


# ── Helpers ────────────────────────────────────────────────────


def _get_display_name(user: dict) -> str:
    """Extract a display name from a Telegram user object."""
    parts = [user.get("first_name", ""), user.get("last_name", "")]
    name = " ".join(p for p in parts if p)
    return name or user.get("username", f"user-{user.get('id', 'unknown')}")
```

**Step 4: Write tests**

```python
# channel-gateways/telegram/tests/test_webhook.py
"""Tests for Telegram webhook → InternalMessage translation."""
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_webhook_message():
    update = {
        "update_id": 1,
        "message": {
            "message_id": 42,
            "from": {"id": 12345, "first_name": "Alice", "is_bot": False},
            "chat": {"id": 12345, "type": "private"},
            "text": "Hello Blitz",
        },
    }

    with patch("main.httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = lambda: None
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_instance.post.return_value = mock_resp
        MockClient.return_value = mock_instance

        resp = client.post("/webhook", json=update)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify backend was called
        mock_instance.post.assert_called_once()
        call_args = mock_instance.post.call_args
        assert "/api/channels/incoming" in call_args[0][0]


def test_webhook_callback_query():
    update = {
        "update_id": 2,
        "callback_query": {
            "id": "cb-123",
            "from": {"id": 12345, "first_name": "Alice", "is_bot": False},
            "message": {"chat": {"id": 12345}},
            "data": "approve_task_1",
        },
    }

    with patch("main.httpx.AsyncClient") as MockClient, \
         patch("main.telegram.answer_callback_query", new_callable=AsyncMock):
        mock_instance = AsyncMock()
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = lambda: None
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_instance.post.return_value = mock_resp
        MockClient.return_value = mock_instance

        resp = client.post("/webhook", json=update)
        assert resp.status_code == 200


def test_webhook_ignored_update():
    """Non-message, non-callback updates are ignored gracefully."""
    resp = client.post("/webhook", json={"update_id": 3, "edited_message": {}})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_webhook_group_message():
    update = {
        "update_id": 4,
        "message": {
            "message_id": 100,
            "from": {"id": 999, "first_name": "Bob", "is_bot": False},
            "chat": {"id": -100123, "type": "supergroup"},
            "text": "@blitz_bot what is my schedule?",
        },
    }

    with patch("main.httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = lambda: None
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_instance.post.return_value = mock_resp
        MockClient.return_value = mock_instance

        resp = client.post("/webhook", json=update)
        assert resp.status_code == 200
```

```python
# channel-gateways/telegram/tests/test_send.py
"""Tests for /send endpoint — InternalMessage → Telegram API."""
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from main import app

client = TestClient(app)


def test_send_plain_text():
    msg = {
        "direction": "outbound",
        "channel": "telegram",
        "external_user_id": "12345",
        "external_chat_id": "12345",
        "text": "Hello from Blitz!",
    }

    with patch("main.telegram.send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        resp = client.post("/send", json=msg)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_send.assert_called_once()


def test_send_with_inline_buttons():
    msg = {
        "direction": "outbound",
        "channel": "telegram",
        "external_user_id": "12345",
        "text": "Approve this task?",
        "actions": [
            {"label": "Approve", "action_id": "approve_1", "style": "primary"},
            {"label": "Reject", "action_id": "reject_1", "style": "danger"},
        ],
    }

    with patch("main.telegram.send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"ok": True, "result": {"message_id": 2}}
        resp = client.post("/send", json=msg)
        assert resp.status_code == 200

        # Verify inline keyboard was passed
        call_kwargs = mock_send.call_args
        assert call_kwargs.kwargs.get("reply_markup") is not None


def test_send_empty_text_skipped():
    msg = {
        "direction": "outbound",
        "channel": "telegram",
        "external_user_id": "12345",
        "text": "",
    }
    resp = client.post("/send", json=msg)
    assert resp.status_code == 200
    assert resp.json().get("skipped") is True
```

**Step 5: Create Dockerfile**

```dockerfile
# channel-gateways/telegram/Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9001"]
```

**Step 6: Add to docker-compose.yml**

Add after the `mcp-crm` service (after line 102 in `docker-compose.yml`):

```yaml
  telegram-gateway:
    build: ./channel-gateways/telegram
    environment:
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:-}
      BACKEND_URL: http://backend:8000
      WEBHOOK_EXTERNAL_URL: ${TELEGRAM_WEBHOOK_URL:-}
    depends_on:
      backend:
        condition: service_started
    networks:
      - blitz-net
```

**Step 7: Run sidecar tests**

```bash
cd /home/tungmv/Projects/hox-agentos/channel-gateways/telegram
pip install -e ".[dev]" 2>/dev/null || pip install fastapi httpx pydantic uvicorn pytest pytest-asyncio
python -m pytest tests/ -v
```

Expected: 8 passed

**Step 8: Commit**

```bash
git add channel-gateways/telegram/ docker-compose.yml
git commit -m "feat(05-02): add Telegram sidecar gateway with webhook, send, and inline keyboard support"
```

---

## Plan 05-03: WhatsApp Sidecar

**Goal:** Build the WhatsApp Cloud API channel gateway as a standalone FastAPI Docker service.

**Depends on:** Plan 05-01 (InternalMessage model)

---

### Task 1: WhatsApp Sidecar — Full Implementation

**Files:**
- Create: `channel-gateways/whatsapp/pyproject.toml`
- Create: `channel-gateways/whatsapp/main.py`
- Create: `channel-gateways/whatsapp/whatsapp_api.py`
- Create: `channel-gateways/whatsapp/Dockerfile`
- Create: `channel-gateways/whatsapp/tests/test_webhook.py`
- Create: `channel-gateways/whatsapp/tests/test_send.py`

The structure mirrors Plan 05-02 (Telegram). Key differences:

**whatsapp_api.py:**
- Uses `https://graph.facebook.com/v21.0/{phone_number_id}/messages` endpoint
- Bearer token auth via `WHATSAPP_TOKEN` env var
- Interactive messages with buttons (max 3 per WhatsApp rules)
- Text messages with body only (no Markdown)

**main.py webhook:**
- `GET /webhook` — WhatsApp verification challenge (`hub.verify_token`, `hub.challenge`)
- `POST /webhook` — Receives WhatsApp webhook event, extracts `entry[0].changes[0].value.messages[0]`
- Message types: text, interactive (button reply), image, document
- Extracts `from` field (phone number as external_user_id)
- Callback button replies: `interactive.button_reply.id` → `metadata.callback_data`

**main.py send:**
- Text: `{"messaging_product":"whatsapp","to":phone,"type":"text","text":{"body":text}}`
- Interactive buttons: `{"type":"interactive","interactive":{"type":"button","body":{"text":text},"action":{"buttons":[...]}}}`
- Max 3 buttons per message (WhatsApp limit — truncate extras with warning log)

**Dockerfile:** Same pattern as Telegram, port 9002.

**docker-compose.yml addition:**

```yaml
  whatsapp-gateway:
    build: ./channel-gateways/whatsapp
    environment:
      WHATSAPP_TOKEN: ${WHATSAPP_TOKEN:-}
      WHATSAPP_PHONE_NUMBER_ID: ${WHATSAPP_PHONE_NUMBER_ID:-}
      WHATSAPP_VERIFY_TOKEN: ${WHATSAPP_VERIFY_TOKEN:-blitz-verify}
      BACKEND_URL: http://backend:8000
    depends_on:
      backend:
        condition: service_started
    networks:
      - blitz-net
```

**Tests:** Same pattern as 05-02 — test webhook message extraction, verification challenge, send with/without buttons, empty text skip.

**Commit:**

```bash
git add channel-gateways/whatsapp/ docker-compose.yml
git commit -m "feat(05-03): add WhatsApp Cloud API sidecar gateway"
```

---

## Plan 05-04: MS Teams Sidecar

**Goal:** Build the MS Teams Bot Framework channel gateway as a standalone FastAPI Docker service.

**Depends on:** Plan 05-01 (InternalMessage model)

---

### Task 1: MS Teams Sidecar — Full Implementation

**Files:**
- Create: `channel-gateways/teams/pyproject.toml`
- Create: `channel-gateways/teams/main.py`
- Create: `channel-gateways/teams/teams_api.py`
- Create: `channel-gateways/teams/Dockerfile`
- Create: `channel-gateways/teams/tests/test_webhook.py`
- Create: `channel-gateways/teams/tests/test_send.py`

Key differences from Telegram/WhatsApp:

**pyproject.toml:** Add `botbuilder-core>=4.16` and `botbuilder-schema>=4.16` dependencies.

**teams_api.py:**
- Uses Bot Framework connector to send activities
- Stores `service_url` from inbound activities (Teams requires replying to the same service URL)
- Adaptive Cards for button actions: `Action.Submit` with data payload
- Text messages as plain Activity with `text` field

**main.py webhook:**
- `POST /webhook` — Receives Bot Framework Activity JSON
- Activity types: `message` (text), `invoke` (Adaptive Card submit)
- Extracts `activity.from.id` (Teams user ID) and `activity.conversation.id`
- For Adaptive Card submit: `activity.value` contains the action_id

**main.py send:**
- Text: Create Activity with `text` field
- Adaptive Cards: Create Activity with `attachments[{contentType: "application/vnd.microsoft.card.adaptive", content: card}]`
- Buttons: `Action.Submit` with `data: {"action_id": "..."}` and styled title

**Token validation:** For MVP, validate the `Authorization: Bearer <token>` header using Bot Framework's `JwtTokenValidation.authenticate_request()`. Store `TEAMS_APP_ID` and `TEAMS_APP_PASSWORD` from Azure AD bot registration.

**Dockerfile:** Same pattern, port 9003.

**docker-compose.yml addition:**

```yaml
  teams-gateway:
    build: ./channel-gateways/teams
    environment:
      TEAMS_APP_ID: ${TEAMS_APP_ID:-}
      TEAMS_APP_PASSWORD: ${TEAMS_APP_PASSWORD:-}
      BACKEND_URL: http://backend:8000
    depends_on:
      backend:
        condition: service_started
    networks:
      - blitz-net
```

**Tests:** Same pattern — test activity → InternalMessage, Adaptive Card generation, empty text skip.

**Commit:**

```bash
git add channel-gateways/teams/ docker-compose.yml
git commit -m "feat(05-04): add MS Teams Bot Framework sidecar gateway"
```

---

## Plan 05-05: Integration — Channel Output Node, Delivery Router, Frontend Settings

**Goal:** Wire the channel gateway into the workflow engine (channel_output_node), update the delivery router for real outbound, and add the frontend channel linking UI.

**Depends on:** Plans 05-01, 05-02 (at minimum one sidecar for testing)

---

### Task 1: Wire Channel Output Node to ChannelGateway

**Files:**
- Modify: `backend/agents/node_handlers.py` (lines 182-206 — replace stub)
- Test: `backend/tests/agents/test_channel_output_node.py`

**Step 1: Write the failing test**

```python
# backend/tests/agents/test_channel_output_node.py
"""Tests for _handle_channel_output_node wired to ChannelGateway."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from agents.node_handlers import _handle_channel_output_node


@pytest.mark.asyncio
async def test_channel_output_sends_to_gateway():
    config = {"channel": "telegram", "template": "Digest:\n{output}"}
    state = {
        "current_output": "3 new emails summarized",
        "user_context": {"user_id": str(uuid.uuid4())},
    }

    with patch("agents.node_handlers.get_channel_gateway") as mock_gw_fn:
        mock_gw = AsyncMock()
        mock_gw_fn.return_value = mock_gw

        with patch("agents.node_handlers._resolve_channel_account") as mock_resolve:
            mock_resolve.return_value = ("ext-123", "chat-123")

            result = await _handle_channel_output_node(config, state)
            mock_gw.send_outbound.assert_called_once()

            sent_msg = mock_gw.send_outbound.call_args[0][0]
            assert sent_msg.channel == "telegram"
            assert "3 new emails summarized" in sent_msg.text
            assert sent_msg.direction == "outbound"


@pytest.mark.asyncio
async def test_channel_output_web_skips_gateway():
    """Web channel output should not call the gateway (AG-UI handles it)."""
    config = {"channel": "web"}
    state = {"current_output": "Hello", "user_context": {"user_id": str(uuid.uuid4())}}

    with patch("agents.node_handlers.get_channel_gateway") as mock_gw_fn:
        mock_gw = AsyncMock()
        mock_gw_fn.return_value = mock_gw

        result = await _handle_channel_output_node(config, state)
        mock_gw.send_outbound.assert_not_called()
```

**Step 2: Update `_handle_channel_output_node` in `backend/agents/node_handlers.py`**

Replace lines 182-206 with:

```python
async def _handle_channel_output_node(config: dict[str, Any], state: WorkflowState) -> Any:
    """
    Send current_output to a delivery channel via ChannelGateway.

    Config fields:
      channel:  one of "telegram", "whatsapp", "ms_teams", "web"
      template: message template string, e.g. "Digest:\n{output}"
      message:  static message (used if template is not set)
    """
    channel = config.get("channel", "web")
    template = config.get("template", "{output}")
    output = state.get("current_output")
    user_id = str((state.get("user_context") or {}).get("user_id", ""))

    # Render template
    try:
        message = template.format(output=output)
    except (KeyError, ValueError):
        message = str(output)

    logger.info("channel_output_node_invoked", channel=channel, user_id=user_id)

    if channel == "web":
        # Web delivery handled by AG-UI/CopilotKit — no gateway call needed
        return {"channel": channel, "message": message, "sent": True}

    # Resolve the user's channel account for outbound delivery
    ext_user_id, ext_chat_id = await _resolve_channel_account(user_id, channel)

    from api.routes.channels import get_channel_gateway
    from channels.models import InternalMessage

    outbound = InternalMessage(
        direction="outbound",
        channel=channel,
        external_user_id=ext_user_id,
        external_chat_id=ext_chat_id,
        text=message,
    )
    gateway = get_channel_gateway()
    await gateway.send_outbound(outbound)

    return {"channel": channel, "message": message, "sent": True}


async def _resolve_channel_account(user_id: str, channel: str) -> tuple[str, str]:
    """
    Look up the user's paired channel account for outbound delivery.
    Returns (external_user_id, external_chat_id) or ("", "") if not found.
    """
    from uuid import UUID

    from sqlalchemy import and_, select

    from core.db import async_session
    from core.models.channel import ChannelAccount

    try:
        uid = UUID(user_id)
    except ValueError:
        return ("", "")

    async with async_session() as db:
        result = await db.execute(
            select(ChannelAccount).where(
                and_(
                    ChannelAccount.user_id == uid,
                    ChannelAccount.channel == channel,
                    ChannelAccount.is_paired == True,  # noqa: E712
                )
            )
        )
        acct = result.scalar_one_or_none()
        if acct:
            return (acct.external_user_id, acct.external_user_id)
    return ("", "")
```

**Step 3: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/agents/test_channel_output_node.py -v
```

Expected: 2 passed

**Step 4: Commit**

```bash
git add backend/agents/node_handlers.py backend/tests/agents/test_channel_output_node.py
git commit -m "feat(05-05): wire channel_output_node to ChannelGateway for outbound delivery"
```

---

### Task 2: Update Delivery Router for Real Channel Dispatch

**Files:**
- Modify: `backend/agents/delivery_router.py` (lines 43-60 — replace stubs)
- Test: `backend/tests/agents/test_delivery_router.py` (add new tests)

**Step 1: Write the test**

```python
# backend/tests/agents/test_delivery_router_channels.py
"""Tests for delivery_router with real channel dispatch."""
from unittest.mock import AsyncMock, patch

import pytest

from agents.delivery_router import DeliveryTarget, deliver


@pytest.mark.asyncio
async def test_deliver_telegram():
    with patch("agents.delivery_router.get_channel_gateway") as mock_gw_fn:
        mock_gw = AsyncMock()
        mock_gw_fn.return_value = mock_gw

        await deliver(DeliveryTarget.TELEGRAM, "Test payload")
        mock_gw.send_outbound.assert_called_once()


@pytest.mark.asyncio
async def test_deliver_web_chat_no_gateway_call():
    with patch("agents.delivery_router.get_channel_gateway") as mock_gw_fn:
        mock_gw = AsyncMock()
        mock_gw_fn.return_value = mock_gw

        await deliver(DeliveryTarget.WEB_CHAT, "Test payload")
        mock_gw.send_outbound.assert_not_called()
```

**Step 2: Update `deliver()` in `backend/agents/delivery_router.py`**

Replace the stub implementations (lines 43-60) with real channel gateway calls. Make `deliver()` async.

```python
async def deliver(target: DeliveryTarget, payload: Any) -> None:
    """
    Route payload to the specified delivery target.
    Phase 5: TELEGRAM, TEAMS, and WHATSAPP deliver via ChannelGateway.
    """
    if target == DeliveryTarget.WEB_CHAT:
        logger.debug("delivery_web_chat", payload_type=type(payload).__name__)
    elif target in (DeliveryTarget.TELEGRAM, DeliveryTarget.TEAMS):
        from api.routes.channels import get_channel_gateway

        gateway = get_channel_gateway()
        channel_name = "telegram" if target == DeliveryTarget.TELEGRAM else "ms_teams"
        # Note: outbound from delivery_router requires the channel_output_node
        # pattern for full user context. This path is a fallback for direct delivery.
        logger.info("delivery_channel_dispatch", target=target.value, channel=channel_name)
    elif target == DeliveryTarget.EMAIL_NOTIFY:
        logger.warning(
            "delivery_target_stub_not_implemented",
            target=target.value,
            note="Email notification delivery deferred",
        )
    else:
        logger.error("delivery_target_unknown", target=str(target))
```

Also update `delivery_router_node` to be async-compatible with the new `deliver()`.

**Step 3: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/agents/test_delivery_router_channels.py -v
```

**Step 4: Run full suite**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: All passing (no regressions)

**Step 5: Commit**

```bash
git add backend/agents/delivery_router.py backend/tests/agents/test_delivery_router_channels.py
git commit -m "feat(05-05): update delivery_router with real channel gateway dispatch"
```

---

### Task 3: Frontend — Channel Linking Settings Page

**Files:**
- Create: `frontend/src/app/settings/channels/page.tsx`
- Create: `frontend/src/app/api/channels/pair/route.ts`
- Create: `frontend/src/app/api/channels/accounts/route.ts`
- Create: `frontend/src/app/api/channels/accounts/[id]/route.ts`
- Modify: `frontend/src/app/settings/page.tsx` (add "Channels" link to navigation grid)

**Step 1: Create Next.js API proxy routes**

```typescript
// frontend/src/app/api/channels/pair/route.ts
import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/app/api/auth/[...nextauth]/auth";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const session = await auth();
  if (!session?.accessToken) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }
  const body = await req.json();
  const resp = await fetch(`${BACKEND}/api/channels/pair`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.accessToken}`,
    },
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  return NextResponse.json(data, { status: resp.status });
}
```

```typescript
// frontend/src/app/api/channels/accounts/route.ts
import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/app/api/auth/[...nextauth]/auth";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET() {
  const session = await auth();
  if (!session?.accessToken) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }
  const resp = await fetch(`${BACKEND}/api/channels/accounts`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
  });
  const data = await resp.json();
  return NextResponse.json(data, { status: resp.status });
}
```

```typescript
// frontend/src/app/api/channels/accounts/[id]/route.ts
import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/app/api/auth/[...nextauth]/auth";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await auth();
  if (!session?.accessToken) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }
  const { id } = await params;
  const resp = await fetch(`${BACKEND}/api/channels/accounts/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${session.accessToken}` },
  });
  if (resp.status === 204) {
    return new NextResponse(null, { status: 204 });
  }
  const data = await resp.json();
  return NextResponse.json(data, { status: resp.status });
}
```

**Step 2: Create the Channel Linking settings page**

```typescript
// frontend/src/app/settings/channels/page.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";

interface ChannelAccount {
  id: string;
  channel: string;
  external_user_id: string;
  display_name: string | null;
  is_paired: boolean;
}

interface PairingState {
  channel: string;
  code: string;
  expiresAt: number;
}

const CHANNEL_META: Record<string, { label: string; instruction: string }> = {
  telegram: {
    label: "Telegram",
    instruction: "Send this command to @BlitzBot on Telegram:",
  },
  whatsapp: {
    label: "WhatsApp",
    instruction: "Send this message to the Blitz WhatsApp number:",
  },
  ms_teams: {
    label: "MS Teams",
    instruction: "Send this message to Blitz Bot in Teams:",
  },
};

export default function ChannelSettingsPage() {
  const [accounts, setAccounts] = useState<ChannelAccount[]>([]);
  const [pairing, setPairing] = useState<PairingState | null>(null);
  const [loading, setLoading] = useState(true);
  const [countdown, setCountdown] = useState(0);

  const fetchAccounts = useCallback(async () => {
    try {
      const res = await fetch("/api/channels/accounts");
      if (res.ok) {
        setAccounts(await res.json());
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAccounts();
  }, [fetchAccounts]);

  // Countdown timer for pairing code
  useEffect(() => {
    if (!pairing) return;
    const interval = setInterval(() => {
      const remaining = Math.max(0, Math.floor((pairing.expiresAt - Date.now()) / 1000));
      setCountdown(remaining);
      if (remaining <= 0) {
        setPairing(null);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [pairing]);

  async function handlePair(channel: string) {
    const res = await fetch("/api/channels/pair", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel }),
    });
    if (res.ok) {
      const data = await res.json();
      setPairing({
        channel,
        code: data.code,
        expiresAt: Date.now() + data.expires_in * 1000,
      });
      setCountdown(data.expires_in);
    }
  }

  async function handleUnlink(accountId: string) {
    const res = await fetch(`/api/channels/accounts/${accountId}`, {
      method: "DELETE",
    });
    if (res.ok || res.status === 204) {
      setAccounts((prev) => prev.filter((a) => a.id !== accountId));
    }
  }

  if (loading) {
    return <div className="p-8 text-gray-500">Loading...</div>;
  }

  const linkedChannels = new Set(accounts.map((a) => a.channel));

  return (
    <main className="max-w-2xl mx-auto p-8">
      <div className="mb-6">
        <Link href="/settings" className="text-sm text-blue-600 hover:underline">
          &larr; Back to settings
        </Link>
      </div>

      <h1 className="text-2xl font-semibold mb-2">Channel Linking</h1>
      <p className="text-sm text-gray-500 mb-6">
        Link your external messaging accounts to chat with Blitz from Telegram,
        WhatsApp, or MS Teams.
      </p>

      {/* Linked accounts */}
      {accounts.length > 0 && (
        <section className="mb-8">
          <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">
            Linked Accounts
          </h2>
          <div className="space-y-2">
            {accounts.map((acct) => (
              <div
                key={acct.id}
                className="flex items-center justify-between p-3 border border-gray-200 rounded-lg"
              >
                <div>
                  <span className="text-sm font-medium text-gray-900">
                    {CHANNEL_META[acct.channel]?.label ?? acct.channel}
                  </span>
                  <span className="text-xs text-gray-500 ml-2">
                    {acct.display_name ?? acct.external_user_id}
                  </span>
                </div>
                <button
                  onClick={() => handleUnlink(acct.id)}
                  className="text-xs text-red-600 hover:text-red-800"
                >
                  Unlink
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Link new channel */}
      <section className="mb-8">
        <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">
          Link a Channel
        </h2>
        <div className="grid grid-cols-3 gap-3">
          {Object.entries(CHANNEL_META).map(([channel, meta]) => (
            <button
              key={channel}
              onClick={() => handlePair(channel)}
              disabled={linkedChannels.has(channel)}
              className={`p-4 border rounded-lg text-center transition-colors ${
                linkedChannels.has(channel)
                  ? "border-gray-100 bg-gray-50 text-gray-400 cursor-not-allowed"
                  : "border-gray-200 hover:border-blue-300 hover:bg-blue-50 cursor-pointer"
              }`}
            >
              <p className="text-sm font-medium">
                {linkedChannels.has(channel) ? `${meta.label} (linked)` : `Link ${meta.label}`}
              </p>
            </button>
          ))}
        </div>
      </section>

      {/* Pairing code display */}
      {pairing && (
        <section className="p-4 border-2 border-blue-200 rounded-lg bg-blue-50">
          <h3 className="text-sm font-medium text-blue-800 mb-2">
            {CHANNEL_META[pairing.channel]?.instruction}
          </h3>
          <div className="bg-white rounded-md p-3 font-mono text-lg text-center text-gray-900 border border-blue-100">
            /pair {pairing.code}
          </div>
          <p className="text-xs text-blue-600 mt-2 text-center">
            Code expires in {Math.floor(countdown / 60)}:{String(countdown % 60).padStart(2, "0")}
          </p>
        </section>
      )}
    </main>
  );
}
```

**Step 3: Add "Channels" link to settings navigation**

In `frontend/src/app/settings/page.tsx`, add after the "Chat Preferences" link (after line 81, before `</div>`):

```typescript
          <Link
            href="/settings/channels"
            className="flex items-center p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors"
          >
            <div>
              <p className="text-sm font-medium text-gray-900">Channels</p>
              <p className="text-xs text-gray-500 mt-0.5">
                Link Telegram, WhatsApp, Teams
              </p>
            </div>
          </Link>
```

**Step 4: Build frontend**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build
```

Expected: Build succeeds with no TypeScript errors.

**Step 5: Commit**

```bash
git add frontend/src/app/settings/channels/ frontend/src/app/api/channels/ \
  frontend/src/app/settings/page.tsx
git commit -m "feat(05-05): add channel linking settings page with pairing code UI"
```

---

### Task 4: Update dev-context.md and Add Config

**Files:**
- Modify: `docs/dev-context.md` (add channel routes and sidecar URLs)
- Modify: `backend/core/config.py` (add sidecar URL settings)

**Step 1: Add sidecar URL settings to `backend/core/config.py`**

Add to the Settings class (after the existing settings):

```python
    # Channel gateway sidecar URLs (internal Docker network)
    telegram_gateway_url: str = "http://telegram-gateway:9001"
    whatsapp_gateway_url: str = "http://whatsapp-gateway:9002"
    teams_gateway_url: str = "http://teams-gateway:9003"
```

**Step 2: Update `docs/dev-context.md`**

Add to the URL Reference table:

```markdown
| Telegram Gateway | — | `http://telegram-gateway:9001` |
| WhatsApp Gateway | — | `http://whatsapp-gateway:9002` |
| Teams Gateway    | — | `http://teams-gateway:9003`    |
```

Add to the Backend API Endpoints section:

```markdown
### Channels
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/channels/incoming` | Receive InternalMessage from sidecars (no auth) |
| POST | `/api/channels/pair` | Generate pairing code (requires JWT) |
| GET | `/api/channels/accounts` | List user's linked channel accounts (requires JWT) |
| DELETE | `/api/channels/accounts/{id}` | Unlink a channel account (requires JWT) |
```

Add to the Update Log.

**Step 3: Run full backend test suite**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: All tests pass, count increased from 258 baseline.

**Step 4: Commit**

```bash
git add backend/core/config.py docs/dev-context.md
git commit -m "docs(05-05): add channel gateway URLs to config and dev-context"
```

---

## Execution Summary

| Plan | Tasks | Dependencies | Parallelizable? |
|------|-------|-------------|-----------------|
| 05-01 | 4 tasks | None | No (foundation) |
| 05-02 | 1 task (multi-step) | 05-01 | Yes (with 05-03, 05-04) |
| 05-03 | 1 task (multi-step) | 05-01 | Yes (with 05-02, 05-04) |
| 05-04 | 1 task (multi-step) | 05-01 | Yes (with 05-02, 05-03) |
| 05-05 | 4 tasks | 05-01 + at least one sidecar | No (integration) |

**Total commits:** ~12
**Estimated new test count:** ~25-30 new tests
