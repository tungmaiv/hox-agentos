# backend/api/routes/user_instructions.py
"""
Custom instructions API — per-user system prompt customization.

GET  /api/user/instructions  — retrieve current user's instructions
PUT  /api/user/instructions  — set/update current user's instructions

Security: user_id always from JWT — never from request body.
Instructions are stored as plaintext (not credentials — safe to log truncated).
"""
import uuid
from uuid import UUID

import structlog
from cachetools import TTLCache
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.user import UserContext
from core.models.user_instructions import UserInstructions
from security.deps import get_current_user, get_user_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/user/instructions", tags=["user"])

MAX_INSTRUCTIONS_LENGTH = 4000  # ~1000 tokens

# User instructions cache — 60s TTL, max 200 entries (one per user).
_instructions_cache: TTLCache = TTLCache(maxsize=200, ttl=60)


class UserInstructionsRequest(BaseModel):
    instructions: str = Field(
        ...,
        max_length=MAX_INSTRUCTIONS_LENGTH,
        description="Custom instructions appended to agent system prompt",
    )


class UserInstructionsResponse(BaseModel):
    instructions: str
    updated_at: str  # ISO timestamp


async def get_user_instructions_db(
    user_id: UUID,
    session: AsyncSession,
) -> str:
    """Raw DB fetch of custom instructions — no caching."""
    result = await session.execute(
        select(UserInstructions).where(UserInstructions.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    return row.instructions if row else ""


async def get_user_instructions_cached(
    user_id: UUID,
    session: AsyncSession,
) -> str:
    """User instructions with 60s TTL cache keyed by user_id."""
    if user_id in _instructions_cache:
        return _instructions_cache[user_id]
    value = await get_user_instructions_db(user_id, session)
    _instructions_cache[user_id] = value
    return value


# Keep backward-compatible alias used by master_agent.py
async def get_user_instructions(user_id: UUID, session: AsyncSession) -> str:
    return await get_user_instructions_cached(user_id, session)


def clear_instructions_cache() -> None:
    """Clear instructions cache. Used in tests."""
    _instructions_cache.clear()


@router.get("/", response_model=UserInstructionsResponse)
async def get_instructions(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> UserInstructionsResponse:
    """Get current user's custom instructions."""
    instructions = await get_user_instructions(user["user_id"], session)
    result = await session.execute(
        select(UserInstructions).where(UserInstructions.user_id == user["user_id"])
    )
    row = result.scalar_one_or_none()
    return UserInstructionsResponse(
        instructions=instructions,
        updated_at=row.updated_at.isoformat() if row else "",
    )


@router.put("/", response_model=UserInstructionsResponse)
async def update_instructions(
    body: UserInstructionsRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> UserInstructionsResponse:
    """
    Set or update current user's custom instructions (upsert).

    Instructions are appended to the agent system prompt for all future conversations.
    """
    result = await session.execute(
        select(UserInstructions).where(UserInstructions.user_id == user["user_id"])
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.instructions = body.instructions
        await session.commit()
        await session.refresh(existing)
        row = existing
    else:
        row = UserInstructions(
            user_id=user["user_id"],
            instructions=body.instructions,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)

    # Invalidate cache so the next read picks up the updated instructions.
    _instructions_cache.pop(user["user_id"], None)
    logger.info(
        "user_instructions_updated",
        user_id=str(user["user_id"]),
        length=len(body.instructions),
    )
    return UserInstructionsResponse(
        instructions=row.instructions,
        updated_at=row.updated_at.isoformat(),
    )
