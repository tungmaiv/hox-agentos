"""
Medium-term memory: episode summaries for MemoryEpisode table.

Functions:
  save_episode()                  — insert one episode row (embedding null, Celery fills it)
  load_recent_episodes()          — return n most recent episodes for a user (descending by created_at)
  get_episode_threshold_db()      — fetch episode threshold from system_config or settings fallback
  get_episode_threshold_cached()  — episode threshold with 60s TTL cache keyed by user_id
  clear_threshold_cache()         — clear threshold cache (used in tests)

SECURITY INVARIANT:
All queries are parameterized on user_id from JWT context — never from request body.
"""

from uuid import UUID

import structlog
from cachetools import TTLCache
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.models.memory_long_term import MemoryEpisode

logger = structlog.get_logger(__name__)

# Episode threshold cache — 60s TTL, max 200 entries (one per user).
_threshold_cache: TTLCache = TTLCache(maxsize=200, ttl=60)


async def get_episode_threshold_db(user_id: UUID, session: AsyncSession) -> int:
    """Fetch episode threshold from system_config or settings fallback."""
    from sqlalchemy import select as _select
    from core.models.system_config import SystemConfig
    result = await session.execute(
        _select(SystemConfig).where(SystemConfig.key == "memory.episode_turn_threshold")
    )
    row = result.scalar_one_or_none()
    if row and row.value:
        try:
            return int(row.value)
        except (ValueError, TypeError):
            pass
    return settings.episode_turn_threshold


async def get_episode_threshold_cached(user_id: UUID, session: AsyncSession) -> int:
    """Episode threshold with 60s TTL cache keyed by user_id."""
    if user_id in _threshold_cache:
        return _threshold_cache[user_id]
    value = await get_episode_threshold_db(user_id, session)
    _threshold_cache[user_id] = value
    return value


def clear_threshold_cache() -> None:
    """Clear threshold cache. Used in tests."""
    _threshold_cache.clear()


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
