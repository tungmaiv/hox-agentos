# backend/api/routes/user_preferences.py
"""
User preferences API — per-user LLM interaction settings.

GET  /api/users/me/preferences  — retrieve current user's preferences (or defaults)
PUT  /api/users/me/preferences  — set/update preferences (partial or full update, upsert)

Security: user_id always from JWT — never from request body.
"""
from typing import Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.user import UserContext
from core.models.user_preferences import DEFAULT_PREFERENCES, UserPreferences
from security.deps import get_current_user, get_user_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/users/me/preferences", tags=["user"])


class UserPreferencesResponse(BaseModel):
    """Response schema for user preferences."""

    thinking_mode: bool
    response_style: Literal["concise", "detailed", "conversational"]


class UserPreferencesUpdate(BaseModel):
    """Request schema for updating user preferences (partial update supported)."""

    thinking_mode: bool | None = None
    response_style: Literal["concise", "detailed", "conversational"] | None = None


async def get_user_preference_values(
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    """
    Retrieve preference values for a user_id (internal helper for agents/prompt injection).

    Returns DEFAULT_PREFERENCES if no row exists.
    Call this from master_agent to inject thinking_mode / response_style into system prompt.
    """
    result = await session.execute(
        select(UserPreferences).where(UserPreferences.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return dict(DEFAULT_PREFERENCES)
    return dict(row.preferences)


@router.get("/", response_model=UserPreferencesResponse)
async def get_preferences(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> UserPreferencesResponse:
    """Get current user's LLM interaction preferences.

    Returns stored preferences if a row exists, otherwise returns defaults:
      thinking_mode=false, response_style=concise.
    """
    prefs = await get_user_preference_values(user["user_id"], session)
    return UserPreferencesResponse(
        thinking_mode=prefs.get("thinking_mode", DEFAULT_PREFERENCES["thinking_mode"]),
        response_style=prefs.get("response_style", DEFAULT_PREFERENCES["response_style"]),
    )


@router.put("/", response_model=UserPreferencesResponse)
async def update_preferences(
    body: UserPreferencesUpdate,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> UserPreferencesResponse:
    """
    Set or update current user's LLM interaction preferences (upsert, partial update).

    Only fields provided in the request body are updated; omitted fields retain
    their existing values (or defaults if no row yet exists).
    """
    result = await session.execute(
        select(UserPreferences).where(UserPreferences.user_id == user["user_id"])
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Merge new values into current preferences dict
        current = dict(existing.preferences)
        if body.thinking_mode is not None:
            current["thinking_mode"] = body.thinking_mode
        if body.response_style is not None:
            current["response_style"] = body.response_style
        # SQLAlchemy JSONB mutation tracking: reassign to trigger dirty tracking
        existing.preferences = current
        await session.commit()
        await session.refresh(existing)
        updated_prefs = existing.preferences
    else:
        # Build from defaults + provided values
        new_prefs: dict = dict(DEFAULT_PREFERENCES)
        if body.thinking_mode is not None:
            new_prefs["thinking_mode"] = body.thinking_mode
        if body.response_style is not None:
            new_prefs["response_style"] = body.response_style
        row = UserPreferences(
            user_id=user["user_id"],
            preferences=new_prefs,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        updated_prefs = row.preferences

    logger.info(
        "user_preferences_updated",
        user_id=str(user["user_id"]),
        thinking_mode=updated_prefs.get("thinking_mode"),
        response_style=updated_prefs.get("response_style"),
    )
    return UserPreferencesResponse(
        thinking_mode=updated_prefs.get("thinking_mode", DEFAULT_PREFERENCES["thinking_mode"]),
        response_style=updated_prefs.get("response_style", DEFAULT_PREFERENCES["response_style"]),
    )
