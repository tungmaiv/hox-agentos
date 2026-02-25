# backend/api/routes/conversations.py
"""
Conversation list API — returns the current user's conversations for the sidebar.

Security: user_id from JWT only — never from request body.
"""
from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.memory import ConversationTurn
from core.models.user import UserContext
from security.deps import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationSummary(BaseModel):
    conversation_id: UUID
    title: str  # First user message (auto-generated name)
    last_message_at: datetime
    message_count: int


@router.get("/", response_model=list[ConversationSummary])
async def list_conversations(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
) -> list[ConversationSummary]:
    """
    List the current user's conversations (most recent first).

    Returns up to `limit` conversations with auto-generated titles
    (first user message in each conversation).

    Isolation: WHERE user_id=$1 from JWT enforced at query level.
    """
    # Subquery: first user message per conversation (for auto-title)
    # and latest message timestamp (for ordering)
    result = await session.execute(
        select(
            ConversationTurn.conversation_id,
            func.min(ConversationTurn.content).filter(
                ConversationTurn.role == "user"
            ).label("first_user_message"),
            func.max(ConversationTurn.created_at).label("last_message_at"),
            func.count(ConversationTurn.id).label("message_count"),
        )
        .where(ConversationTurn.user_id == user["user_id"])
        .group_by(ConversationTurn.conversation_id)
        .order_by(func.max(ConversationTurn.created_at).desc())
        .limit(limit)
        .offset(offset)
    )
    rows = result.all()

    summaries = []
    for row in rows:
        title = row.first_user_message or "New conversation"
        if len(title) > 60:
            title = title[:57] + "..."
        summaries.append(
            ConversationSummary(
                conversation_id=row.conversation_id,
                title=title,
                last_message_at=row.last_message_at,
                message_count=row.message_count,
            )
        )
    logger.debug(
        "conversations_listed",
        user_id=str(user["user_id"]),
        count=len(summaries),
    )
    return summaries
