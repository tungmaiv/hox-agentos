"""
TDD tests for storage share model and check_file_access helper — Phase 28 (STOR-04).

RED phase: tests fail until StorageShare model and check_file_access are implemented.

Behaviors:
  - StorageShare allows file_id=None with folder_id set (folder-only share)
  - StorageShare allows folder_id=None with file_id set (file-only share)
  - check_file_access returns True when user is the file owner
  - check_file_access returns True when a direct file_id share exists for the user
  - check_file_access returns False for a user with no ownership or share record
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from core.db import Base


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:  # type: ignore[misc]
    """In-memory SQLite async session — same pattern as memory tests."""
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


# ---------------------------------------------------------------------------
# StorageShare model column tests (no DB needed)
# ---------------------------------------------------------------------------


def test_storage_share_allows_file_id_only() -> None:
    """StorageShare can be instantiated with file_id set and folder_id=None."""
    from core.models.storage_share import StorageShare  # type: ignore[import]

    share = StorageShare()
    share.file_id = uuid4()
    share.folder_id = None
    assert share.file_id is not None
    assert share.folder_id is None


def test_storage_share_allows_folder_id_only() -> None:
    """StorageShare can be instantiated with folder_id set and file_id=None."""
    from core.models.storage_share import StorageShare  # type: ignore[import]

    share = StorageShare()
    share.folder_id = uuid4()
    share.file_id = None
    assert share.folder_id is not None
    assert share.file_id is None


# ---------------------------------------------------------------------------
# check_file_access helper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_file_access_owner_returns_true(db_session: AsyncSession) -> None:
    """check_file_access returns True when the user is the file owner."""
    from core.models.storage_file import StorageFile  # type: ignore[import]
    from api.routes.storage import check_file_access  # type: ignore[import]

    user_id = uuid4()
    file_id = uuid4()

    file_record = StorageFile()
    file_record.id = file_id
    file_record.owner_user_id = user_id
    file_record.name = "test.txt"
    file_record.object_key = f"users/{user_id}/{file_id}"
    file_record.content_hash = "abc123"
    file_record.mime_type = "text/plain"
    file_record.size_bytes = 11
    file_record.in_memory = False
    db_session.add(file_record)
    await db_session.commit()

    result = await check_file_access(db_session, file_id, user_id)
    assert result is True


@pytest.mark.asyncio
async def test_check_file_access_shared_returns_true(db_session: AsyncSession) -> None:
    """check_file_access returns True when a direct file_id share exists for the user."""
    from core.models.storage_file import StorageFile  # type: ignore[import]
    from core.models.storage_share import StorageShare  # type: ignore[import]
    from api.routes.storage import check_file_access  # type: ignore[import]

    owner_id = uuid4()
    viewer_id = uuid4()
    file_id = uuid4()

    file_record = StorageFile()
    file_record.id = file_id
    file_record.owner_user_id = owner_id
    file_record.name = "shared.txt"
    file_record.object_key = f"users/{owner_id}/{file_id}"
    file_record.content_hash = "def456"
    file_record.mime_type = "text/plain"
    file_record.size_bytes = 5
    file_record.in_memory = False

    share_record = StorageShare()
    share_record.id = uuid4()
    share_record.file_id = file_id
    share_record.folder_id = None
    share_record.shared_with_user_id = viewer_id
    share_record.shared_by_user_id = owner_id
    share_record.permission = "READ"

    db_session.add(file_record)
    db_session.add(share_record)
    await db_session.commit()

    result = await check_file_access(db_session, file_id, viewer_id)
    assert result is True


@pytest.mark.asyncio
async def test_check_file_access_no_access_returns_false(
    db_session: AsyncSession,
) -> None:
    """check_file_access returns False for user with no ownership or share record."""
    from core.models.storage_file import StorageFile  # type: ignore[import]
    from api.routes.storage import check_file_access  # type: ignore[import]

    owner_id = uuid4()
    stranger_id = uuid4()
    file_id = uuid4()

    file_record = StorageFile()
    file_record.id = file_id
    file_record.owner_user_id = owner_id
    file_record.name = "private.txt"
    file_record.object_key = f"users/{owner_id}/{file_id}"
    file_record.content_hash = "ghi789"
    file_record.mime_type = "text/plain"
    file_record.size_bytes = 7
    file_record.in_memory = False

    db_session.add(file_record)
    await db_session.commit()

    result = await check_file_access(db_session, file_id, stranger_id)
    assert result is False
