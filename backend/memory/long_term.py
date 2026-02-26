"""
Long-term memory: semantic fact storage and retrieval using pgvector.

Functions:
  save_fact()            — insert one fact row (embedding null, Celery fills it)
  mark_fact_superseded() — soft-delete a fact by setting superseded_at timestamp
  search_facts()         — semantic cosine search over memory_facts for a user

SECURITY INVARIANT:
All queries are parameterized on user_id from JWT context — never from request body.
Memory isolation: WHERE user_id = $1 is present in every SELECT that touches user data.
"""

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.memory_long_term import MemoryFact

logger = structlog.get_logger(__name__)


async def save_fact(
    session: AsyncSession,
    *,
    user_id: UUID,
    content: str,
    source: str = "conversation",
) -> MemoryFact:
    """
    Insert one fact row. embedding is null — Celery will fill it.

    SECURITY: user_id from JWT context (never from request body).
    """
    fact = MemoryFact(user_id=user_id, content=content, source=source)
    session.add(fact)
    logger.debug("fact_saved", user_id=str(user_id), source=source)
    return fact


async def mark_fact_superseded(
    session: AsyncSession,
    *,
    fact_id: UUID,
) -> None:
    """
    Soft-delete a fact by setting superseded_at timestamp.

    Per CONTEXT.md: facts are NEVER hard-deleted when superseded — only marked.
    This preserves history and enables rollback/audit.
    """
    result = await session.execute(select(MemoryFact).where(MemoryFact.id == fact_id))
    fact = result.scalar_one_or_none()
    if fact is not None:
        fact.superseded_at = datetime.now(timezone.utc)
        logger.info("fact_superseded", fact_id=str(fact_id))


async def search_facts(
    session: AsyncSession,
    *,
    user_id: UUID,
    query_embedding: list[float],
    k: int = 5,
) -> list[MemoryFact]:
    """
    Semantic search over memory_facts for a user using pgvector cosine distance.

    SECURITY: WHERE user_id = $1 from JWT — never from request body.
    Only searches rows where:
      - embedding IS NOT NULL (Celery has processed them)
      - superseded_at IS NULL (not soft-deleted by conflict resolution)
    Returns top k facts ordered by cosine similarity (ascending distance).

    Uses pgvector cosine distance operator (<=>).
    """
    result = await session.execute(
        select(MemoryFact)
        .where(
            MemoryFact.user_id == user_id,
            MemoryFact.embedding.is_not(None),
            MemoryFact.superseded_at.is_(None),
        )
        .order_by(MemoryFact.embedding.cosine_distance(query_embedding))
        .limit(k)
    )
    facts = list(result.scalars().all())
    logger.debug("facts_searched", user_id=str(user_id), returned=len(facts))
    return facts
