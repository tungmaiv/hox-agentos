"""
TDD tests for embed_and_store and summarize_episode Celery tasks.

Uses CELERY_TASK_ALWAYS_EAGER for synchronous execution (no broker required).

Test strategy:
  - patch asyncio.run to verify task body is invoked without running real async code
    (which would require full DB/LLM setup)
  - For integration tests needing real DB access, use aiosqlite pattern from Phase 2 tests

CELERY_TASK_ALWAYS_EAGER configured at module level so all tests in this file
run synchronously without requiring a Redis connection.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from scheduler.celery_app import celery_app

# Run all Celery tasks synchronously in tests (no broker required)
celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)


def test_embed_and_store_task_exists() -> None:
    """embed_and_store task is registered in the Celery app."""
    from scheduler.tasks.embedding import embed_and_store

    assert embed_and_store.name == "scheduler.tasks.embedding.embed_and_store"


def test_summarize_episode_task_exists() -> None:
    """summarize_episode task is registered in the Celery app."""
    from scheduler.tasks.embedding import summarize_episode

    assert summarize_episode.name == "scheduler.tasks.embedding.summarize_episode"


def test_embed_and_store_routes_to_embedding_queue() -> None:
    """embed_and_store task is configured for the 'embedding' queue."""
    from scheduler.tasks.embedding import embed_and_store

    assert embed_and_store.queue == "embedding"


def test_summarize_episode_routes_to_default_queue() -> None:
    """summarize_episode task is configured for the 'default' queue."""
    from scheduler.tasks.embedding import summarize_episode

    assert summarize_episode.queue == "default"


def test_embed_and_store_fact_invokes_async_body() -> None:
    """embed_and_store with entry_type='fact' calls asyncio.run() (task body executes)."""
    user_id = str(uuid.uuid4())

    with patch("scheduler.tasks.embedding.asyncio.run") as mock_run:
        mock_run.return_value = None  # no-op for sync test

        from scheduler.tasks.embedding import embed_and_store

        embed_and_store.apply(args=["User prefers dark mode", user_id, "fact"])
        mock_run.assert_called_once()


def test_embed_and_store_episode_invokes_async_body() -> None:
    """embed_and_store with entry_type='episode' calls asyncio.run() (task body executes)."""
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())

    with patch("scheduler.tasks.embedding.asyncio.run") as mock_run:
        mock_run.return_value = None

        from scheduler.tasks.embedding import embed_and_store

        embed_and_store.apply(
            args=["Episode summary text", user_id, "episode"],
            kwargs={"conversation_id_str": conversation_id},
        )
        mock_run.assert_called_once()


def test_embed_and_store_unknown_entry_type_does_not_raise() -> None:
    """embed_and_store with unknown entry_type logs error but does not raise."""
    user_id = str(uuid.uuid4())

    with patch("scheduler.tasks.embedding.asyncio.run") as mock_run:
        mock_run.return_value = None

        from scheduler.tasks.embedding import embed_and_store

        # Should not raise even with bad entry_type
        embed_and_store.apply(args=["text", user_id, "unknown_type"])


def test_summarize_episode_invokes_async_body() -> None:
    """summarize_episode calls asyncio.run() (task body executes)."""
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())

    with patch("scheduler.tasks.embedding.asyncio.run") as mock_run:
        mock_run.return_value = None

        from scheduler.tasks.embedding import summarize_episode

        summarize_episode.apply(args=[conversation_id, user_id])
        mock_run.assert_called_once()


def test_celery_app_has_expected_queues() -> None:
    """Celery task_routes configures both embedding and default queues."""
    routes = celery_app.conf.task_routes
    assert "scheduler.tasks.embedding.embed_and_store" in routes
    assert routes["scheduler.tasks.embedding.embed_and_store"]["queue"] == "embedding"
    assert "scheduler.tasks.embedding.summarize_episode" in routes
    assert routes["scheduler.tasks.embedding.summarize_episode"]["queue"] == "default"
