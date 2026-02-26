"""
Medium-term memory: episode summaries for MemoryEpisode table.

Functions:
  save_episode()         — insert one episode row (embedding null, Celery fills it)
  load_recent_episodes() — return n most recent episodes for a user (descending by created_at)

SECURITY INVARIANT:
All queries are parameterized on user_id from JWT context — never from request body.
"""

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.memory_long_term import MemoryEpisode

logger = structlog.get_logger(__name__)


async def save_episode(
    session: AsyncSession,
    *,
    user_id: UUID,
    conversation_id: UUID,
    summary: str,
) -> MemoryEpisode:
    """
    Insert one episode row. embedding is null — Celery will fill it.

    SECURITY: user_id from JWT context (never from request body).
    """
    episode = MemoryEpisode(
        user_id=user_id,
        conversation_id=conversation_id,
        summary=summary,
    )
    session.add(episode)
    logger.debug("episode_saved", user_id=str(user_id), conversation_id=str(conversation_id))
    return episode


async def load_recent_episodes(
    session: AsyncSession,
    *,
    user_id: UUID,
    n: int = 5,
) -> list[MemoryEpisode]:
    """
    Load n most recent episode summaries for a user (descending by created_at).

    SECURITY: WHERE user_id = $1 from JWT — never from request body.
    """
    result = await session.execute(
        select(MemoryEpisode)
        .where(MemoryEpisode.user_id == user_id)
        .order_by(MemoryEpisode.created_at.desc())
        .limit(n)
    )
    episodes = list(result.scalars().all())
    logger.debug("episodes_loaded", user_id=str(user_id), count=len(episodes))
    return episodes
