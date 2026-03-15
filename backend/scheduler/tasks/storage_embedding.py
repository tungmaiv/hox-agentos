"""
Celery task for extracting text from stored files and indexing into long-term memory.

embed_file_content:
  - Routes to queue: embedding (CPU-bound text extraction + bge-m3 embedding)
  - Downloads file bytes from MinIO, extracts text, dispatches embed_and_store
  - Supports: PDF, DOCX, TXT, MD (EXTRACTABLE_MIME_TYPES)
  - Gracefully handles missing files and non-extractable MIME types
  - Retries up to 3 times on transient errors

SECURITY:
  user_id always comes from request context (route sets it from JWT, never user input).
  Celery workers run as the job owner — see CLAUDE.md §7 Scheduler Security.
"""
import asyncio

import structlog

from scheduler.celery_app import celery_app

# Module-level imports for testability (can be patched in tests)
from core.db import async_session
from storage.service import StorageService
from scheduler.tasks.embedding import embed_and_store

logger = structlog.get_logger(__name__)


def _embed_file_content_body(
    self: object,
    file_id_str: str,
    user_id_str: str,
) -> None:
    """Raw implementation body — defined separately so tests can call it with a mock self.

    The Celery task delegate below wraps this function with bind=True.
    Tests access this via ``embed_file_content.__wrapped__`` (assigned below).
    """
    from uuid import UUID
    from sqlalchemy import select
    from core.models.storage_file import StorageFile
    from storage.text_extractor import extract_text_from_file

    async def _run() -> None:
        file_id = UUID(file_id_str)

        async with async_session() as session:
            result = await session.execute(
                select(StorageFile).where(StorageFile.id == file_id)
            )
            file_record = result.scalar_one_or_none()
            if file_record is None:
                logger.error("embed_file_content_file_not_found", file_id=file_id_str)
                return

        service = StorageService()
        content_bytes = await service.download_bytes(file_record.object_key)

        text = extract_text_from_file(content_bytes, file_record.mime_type)
        if not text.strip():
            logger.warning(
                "embed_file_content_no_text",
                file_id=file_id_str,
                mime_type=file_record.mime_type,
            )
            return

        embed_and_store.delay(text, user_id_str, "fact")

        logger.info(
            "embed_file_content_dispatched",
            file_id=file_id_str,
            user_id=user_id_str,
            text_length=len(text),
        )

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(
            "embed_file_content_failed",
            file_id=file_id_str,
            user_id=user_id_str,
            error=str(exc),
        )
        raise self.retry(exc=exc)  # type: ignore[attr-defined]


@celery_app.task(
    queue="embedding",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="scheduler.tasks.storage_embedding.embed_file_content",
)
def embed_file_content(self, file_id_str: str, user_id_str: str) -> None:  # type: ignore[override]
    """Extract text from a stored file and embed it into long-term memory.

    Downloads the file from MinIO, extracts text using the MIME-type-aware extractor,
    and dispatches embed_and_store to persist the embedding in pgvector memory_facts.

    Args:
        file_id_str: UUID string of the StorageFile record.
        user_id_str: UUID string of the file owner — from request context, never user input.
    """
    _embed_file_content_body(self, file_id_str, user_id_str)


# Expose the raw body function for test patching via embed_file_content.__wrapped__
# Tests call embed_file_content.__wrapped__(mock_self, file_id, user_id) to test self.retry
embed_file_content.__wrapped__ = _embed_file_content_body  # type: ignore[attr-defined]
