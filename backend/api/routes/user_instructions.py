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
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.user import UserContext
from core.models.user_instructions import UserInstructions
from security.deps import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/user/instructions", tags=["user"])

MAX_INSTRUCTIONS_LENGTH = 4000  # ~1000 tokens


class UserInstructionsRequest(BaseModel):
    instructions: str = Field(
        ...,
        max_length=MAX_INSTRUCTIONS_LENGTH,
        description="Custom instructions appended to agent system prompt",
    )


class UserInstructionsResponse(BaseModel):
    instructions: str
    updated_at: str  # ISO timestamp


async def get_user_instructions(
    user_id: UUID,
    session: AsyncSession,
) -> str:
    """
    Retrieve custom instructions for a user_id (internal helper for agents).

    Returns empty string if no instructions set.
    Call this from master_agent to inject into system prompt.
    """
    result = await session.execute(
        select(UserInstructions).where(UserInstructions.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    return row.instructions if row else ""


@router.get("/", response_model=UserInstructionsResponse)
async def get_instructions(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
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
    session: AsyncSession = Depends(get_db),
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

    logger.info(
        "user_instructions_updated",
        user_id=str(user["user_id"]),
        length=len(body.instructions),
    )
    return UserInstructionsResponse(
        instructions=row.instructions,
        updated_at=row.updated_at.isoformat(),
    )
