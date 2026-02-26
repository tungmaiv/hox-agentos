"""
Memory settings API for per-user fact/episode management.

Endpoints:
  GET    /api/user/memory/facts              — list user's stored facts (non-superseded)
  DELETE /api/user/memory/facts/{fact_id}    — soft-delete one fact (sets superseded_at)
  DELETE /api/user/memory/facts              — soft-delete ALL facts for the user
  GET    /api/user/memory/episodes           — list user's episode summaries
  GET    /api/user/preferences               — get user chat preferences
  PUT    /api/user/preferences               — update user chat preferences

SECURITY INVARIANT:
  All queries parameterized on user_id from JWT — never from request body.
  Ownership check on individual fact delete: fact.user_id == jwt_user_id.
"""
from datetime import datetime, timezone
from uuid import UUID
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from core.db import get_db
from core.models.memory_long_term import MemoryFact, MemoryEpisode
from core.models.user import UserContext
from memory.long_term import mark_fact_superseded
from security.deps import get_current_user

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/user", tags=["user"])


# ---------------------------------------------------------------------------
# Memory Facts
# ---------------------------------------------------------------------------


@router.get("/memory/facts")
async def list_facts(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    List non-superseded memory facts for the authenticated user.

    SECURITY: user_id from JWT — never from request body.
    Returns up to 100 most recent facts.
    """
    result = await session.execute(
        select(MemoryFact)
        .where(
            MemoryFact.user_id == user["user_id"],
            MemoryFact.superseded_at.is_(None),
        )
        .order_by(MemoryFact.created_at.desc())
        .limit(100)
    )
    facts = result.scalars().all()
    return [
        {
            "id": str(f.id),
            "content": f.content,
            "source": f.source,
            "created_at": f.created_at.isoformat(),
        }
        for f in facts
    ]


@router.delete("/memory/facts/{fact_id}")
async def delete_fact(
    fact_id: UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Soft-delete one fact (sets superseded_at timestamp).

    SECURITY: verifies fact.user_id == user_id from JWT before deletion.
    Returns 404 if fact not found or owned by a different user.
    """
    result = await session.execute(
        select(MemoryFact).where(
            MemoryFact.id == fact_id,
            MemoryFact.user_id == user["user_id"],  # ownership check
        )
    )
    fact = result.scalar_one_or_none()
    if fact is None:
        raise HTTPException(
            status_code=404, detail="Fact not found or not owned by user"
        )
    await mark_fact_superseded(session, fact_id=fact_id)
    await session.commit()
    logger.info(
        "fact_deleted_by_user",
        fact_id=str(fact_id),
        user_id=str(user["user_id"]),
    )
    return {"status": "deleted"}


@router.delete("/memory/facts")
async def clear_all_facts(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Soft-delete ALL active facts for the user.

    SECURITY: WHERE user_id = $1 from JWT — never deletes another user's facts.
    """
    result = await session.execute(
        select(MemoryFact).where(
            MemoryFact.user_id == user["user_id"],
            MemoryFact.superseded_at.is_(None),
        )
    )
    facts = result.scalars().all()
    now = datetime.now(timezone.utc)
    for fact in facts:
        fact.superseded_at = now
    await session.commit()
    logger.info(
        "all_facts_cleared",
        user_id=str(user["user_id"]),
        count=len(facts),
    )
    return {"status": "cleared", "count": str(len(facts))}


# ---------------------------------------------------------------------------
# Memory Episodes
# ---------------------------------------------------------------------------


@router.get("/memory/episodes")
async def list_episodes(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    List episode summaries for the authenticated user.

    SECURITY: WHERE user_id = $1 from JWT.
    Returns up to 50 most recent episodes.
    """
    result = await session.execute(
        select(MemoryEpisode)
        .where(MemoryEpisode.user_id == user["user_id"])
        .order_by(MemoryEpisode.created_at.desc())
        .limit(50)
    )
    episodes = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "summary": e.summary,
            "created_at": e.created_at.isoformat(),
        }
        for e in episodes
    ]


# ---------------------------------------------------------------------------
# Chat Preferences — stored in system_config keyed per user
# ---------------------------------------------------------------------------


class ChatPreferences(BaseModel):
    rendering_mode: str = "markdown"  # "markdown" | "card_wrapped" | "inline_chips"


@router.get("/preferences")
async def get_preferences(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ChatPreferences:
    """
    Get chat rendering preferences for the authenticated user.
    Returns default (markdown) if no preferences stored yet.
    """
    from core.models.system_config import SystemConfig

    key = f"user.{user['user_id']}.chat_preferences"
    result = await session.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return ChatPreferences()
    return ChatPreferences.model_validate(row.value)


@router.put("/preferences")
async def update_preferences(
    body: ChatPreferences,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ChatPreferences:
    """
    Update chat rendering preferences for the authenticated user.
    Uses upsert pattern: create row if missing, update if present.
    """
    from core.models.system_config import SystemConfig

    key = f"user.{user['user_id']}.chat_preferences"
    result = await session.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = SystemConfig(key=key, value=body.model_dump())
        session.add(row)
    else:
        row.value = body.model_dump()
    await session.commit()
    logger.info(
        "preferences_updated",
        user_id=str(user["user_id"]),
        rendering_mode=body.rendering_mode,
    )
    return body
