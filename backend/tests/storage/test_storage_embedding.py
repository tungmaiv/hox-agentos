"""
TDD tests for scheduler/tasks/storage_embedding.py — Phase 28 (STOR-05).

RED phase: tests fail until storage_embedding.py is implemented.

Behaviors:
  - embed_file_content task fetches file from DB, downloads bytes, extracts text, dispatches embed_and_store
  - embed_file_content with missing file_id logs error and returns without raising
  - embed_file_content with empty extracted text logs warning and does NOT dispatch embed_and_store
  - embed_file_content retries on exception (self.retry called)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


def _make_mock_file_record(
    *,
    file_id: str | None = None,
    object_key: str = "users/abc/def",
    mime_type: str = "text/plain",
    in_memory: bool = True,
) -> MagicMock:
    record = MagicMock()
    record.id = file_id or str(uuid4())
    record.object_key = object_key
    record.mime_type = mime_type
    record.in_memory = in_memory
    return record


def test_embed_file_content_dispatches_embed_and_store() -> None:
    """Task fetches file, downloads bytes, extracts text, dispatches embed_and_store.delay."""
    from scheduler.tasks.storage_embedding import embed_file_content  # type: ignore[import]

    file_id = str(uuid4())
    user_id = str(uuid4())
    mock_file = _make_mock_file_record(file_id=file_id, mime_type="text/plain")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_file)

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_async_session = MagicMock(return_value=mock_session)

    mock_storage = AsyncMock()
    mock_storage.download_bytes = AsyncMock(return_value=b"extracted text content")

    mock_embed_and_store = MagicMock()
    mock_embed_and_store.delay = MagicMock()

    with (
        patch("scheduler.tasks.storage_embedding.async_session", mock_async_session),  # type: ignore[attr-defined]
        patch("scheduler.tasks.storage_embedding.StorageService", return_value=mock_storage),  # type: ignore[attr-defined]
        patch("scheduler.tasks.storage_embedding.embed_and_store", mock_embed_and_store),  # type: ignore[attr-defined]
    ):
        # Call synchronously — task wraps asyncio.run() internally
        embed_file_content(file_id, user_id)  # type: ignore[call-arg]

    mock_embed_and_store.delay.assert_called_once_with(
        "extracted text content", user_id, "fact"
    )


def test_embed_file_content_missing_file_returns_without_raising() -> None:
    """embed_file_content logs error and returns gracefully when file_id not found."""
    from scheduler.tasks.storage_embedding import embed_file_content  # type: ignore[import]

    file_id = str(uuid4())
    user_id = str(uuid4())

    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_async_session = MagicMock(return_value=mock_session)

    mock_embed_and_store = MagicMock()
    mock_embed_and_store.delay = MagicMock()

    with (
        patch("scheduler.tasks.storage_embedding.async_session", mock_async_session),  # type: ignore[attr-defined]
        patch("scheduler.tasks.storage_embedding.embed_and_store", mock_embed_and_store),  # type: ignore[attr-defined]
    ):
        # Should not raise
        embed_file_content(file_id, user_id)  # type: ignore[call-arg]

    mock_embed_and_store.delay.assert_not_called()


def test_embed_file_content_empty_text_does_not_dispatch() -> None:
    """embed_file_content logs warning and does NOT call embed_and_store when text is empty."""
    from scheduler.tasks.storage_embedding import embed_file_content  # type: ignore[import]

    file_id = str(uuid4())
    user_id = str(uuid4())
    mock_file = _make_mock_file_record(file_id=file_id, mime_type="image/png")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_file)

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_async_session = MagicMock(return_value=mock_session)

    mock_storage = AsyncMock()
    mock_storage.download_bytes = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n")

    mock_embed_and_store = MagicMock()
    mock_embed_and_store.delay = MagicMock()

    with (
        patch("scheduler.tasks.storage_embedding.async_session", mock_async_session),  # type: ignore[attr-defined]
        patch("scheduler.tasks.storage_embedding.StorageService", return_value=mock_storage),  # type: ignore[attr-defined]
        patch("scheduler.tasks.storage_embedding.embed_and_store", mock_embed_and_store),  # type: ignore[attr-defined]
    ):
        embed_file_content(file_id, user_id)  # type: ignore[call-arg]

    mock_embed_and_store.delay.assert_not_called()


def test_embed_file_content_retries_on_exception() -> None:
    """embed_file_content calls self.retry when an exception is raised."""
    from scheduler.tasks.storage_embedding import embed_file_content  # type: ignore[import]

    file_id = str(uuid4())
    user_id = str(uuid4())

    # self is the Celery task instance — mock it with a retry that raises RuntimeError
    class _RetryError(RuntimeError):
        pass

    mock_self = MagicMock()
    mock_self.retry = MagicMock(side_effect=_RetryError("retry called"))

    mock_async_session = MagicMock(side_effect=RuntimeError("db connection failed"))

    with (
        patch("scheduler.tasks.storage_embedding.async_session", mock_async_session),  # type: ignore[attr-defined]
        pytest.raises(_RetryError),
    ):
        embed_file_content.__wrapped__(mock_self, file_id, user_id)  # type: ignore[attr-defined]

    mock_self.retry.assert_called_once()
