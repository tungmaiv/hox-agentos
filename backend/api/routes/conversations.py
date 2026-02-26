# backend/api/routes/conversations.py
"""
Conversation list and message history API.

Security: user_id from JWT only — never from request body.
"""
from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.conversation_title import ConversationTitle
from core.models.memory import ConversationTurn
from core.models.user import UserContext
from security.deps import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationSummary(BaseModel):
    conversation_id: UUID
    title: str
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

    Title resolution order:
      1. Custom title from conversation_titles table (user-renamed)
      2. First user message (auto-generated fallback)

    Isolation: WHERE user_id=$1 from JWT enforced at query level.
    """
    # Correlated subquery: chronologically first user message per conversation.
    # func.min(content) returns the lexicographically smallest string, not the
    # oldest message — wrong for titles. This subquery orders by created_at.
    inner = aliased(ConversationTurn)
    first_user_msg_subq = (
        select(inner.content)
        .where(
            inner.user_id == user["user_id"],
            inner.conversation_id == ConversationTurn.conversation_id,
            inner.role == "user",
        )
        .order_by(inner.created_at.asc())
        .limit(1)
        .correlate(ConversationTurn)
        .scalar_subquery()
    )

    # Fetch auto-titles and metadata
    result = await session.execute(
        select(
            ConversationTurn.conversation_id,
            first_user_msg_subq.label("first_user_message"),
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

    if not rows:
        return []

    # Fetch any custom titles for these conversations in one query
    conv_ids = [row.conversation_id for row in rows]
    title_result = await session.execute(
        select(ConversationTitle).where(
            ConversationTitle.user_id == user["user_id"],
            ConversationTitle.conversation_id.in_(conv_ids),
        )
    )
    custom_titles: dict[UUID, str] = {
        row.conversation_id: row.title for row in title_result.scalars().all()
    }

    summaries = []
    for row in rows:
        if row.conversation_id in custom_titles:
            title = custom_titles[row.conversation_id]
        else:
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


class RenameTitleRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


@router.patch("/{conversation_id}/title", status_code=204)
async def rename_conversation(
    conversation_id: UUID,
    body: RenameTitleRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """
    Set or update a custom title for a conversation (upsert).

    Security: user_id from JWT — users can only rename their own conversations.
    Validates the conversation belongs to the user before upserting.
    """
    # Verify user owns this conversation
    exists = await session.execute(
        select(ConversationTurn.id)
        .where(
            ConversationTurn.conversation_id == conversation_id,
            ConversationTurn.user_id == user["user_id"],
        )
        .limit(1)
    )
    if not exists.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Upsert custom title
    result = await session.execute(
        select(ConversationTitle).where(
            ConversationTitle.user_id == user["user_id"],
            ConversationTitle.conversation_id == conversation_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.title = body.title
    else:
        session.add(
            ConversationTitle(
                user_id=user["user_id"],
                conversation_id=conversation_id,
                title=body.title,
            )
        )
    await session.commit()
    logger.info(
        "conversation_renamed",
        user_id=str(user["user_id"]),
        conversation_id=str(conversation_id),
    )


class TurnResponse(BaseModel):
    id: UUID
    role: str
    content: str


@router.get("/{conversation_id}/messages", response_model=list[TurnResponse])
async def get_conversation_messages(
    conversation_id: UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[TurnResponse]:
    """
    Return all turns for a conversation (oldest first) for the current user.

    Isolation: WHERE user_id=$1 from JWT — users can only read their own turns.
    """
    result = await session.execute(
        select(ConversationTurn)
        .where(
            ConversationTurn.conversation_id == conversation_id,
            ConversationTurn.user_id == user["user_id"],
        )
        .order_by(ConversationTurn.created_at.asc())
    )
    turns = result.scalars().all()
    if not turns:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return [TurnResponse(id=t.id, role=t.role, content=t.content) for t in turns]
