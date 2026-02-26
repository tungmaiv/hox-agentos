# backend/memory/short_term.py
"""
Short-term memory — conversation turn persistence.

Loads and saves conversation turns from memory_conversations table.

SECURITY INVARIANT:
All queries are parameterized on user_id extracted from JWT by get_current_user().
user_id is NEVER accepted from request body or agent state input.
Cross-user reads are physically impossible at the query level.
"""
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.memory import ConversationTurn

logger = structlog.get_logger(__name__)


async def load_recent_turns(
    session: AsyncSession,
    *,
    user_id: UUID,
    conversation_id: UUID,
    n: int = 20,
) -> list[ConversationTurn]:
    """
    Load the most recent n turns for a user's conversation.

    Returns turns in chronological order (oldest first) for correct
    LangGraph message history injection.

    Isolation: WHERE user_id=$1 ensures user A cannot read user B's turns,
    even if they share a conversation_id (which the UUID distribution makes
    practically impossible, but the query enforces it anyway).
    """
    result = await session.execute(
        select(ConversationTurn)
        .where(
            ConversationTurn.user_id == user_id,
            ConversationTurn.conversation_id == conversation_id,
        )
        .order_by(ConversationTurn.created_at.desc())
        .limit(n)
    )
    turns = result.scalars().all()
    # Reverse to chronological order (DESC retrieves newest first, we want oldest first)
    return list(reversed(turns))


async def save_turn(
    session: AsyncSession,
    *,
    user_id: UUID,
    conversation_id: UUID,
    role: str,
    content: str,
) -> ConversationTurn:
    """
    Persist one conversation turn.

    Args:
        session: Async DB session
        user_id: From JWT — never from request body
        conversation_id: Frontend-generated UUID sent in AG-UI request
        role: 'user' | 'assistant' | 'tool'
        content: Message text

    Returns the saved ConversationTurn row.
    """
    turn = ConversationTurn(
        user_id=user_id,
        conversation_id=conversation_id,
        role=role,
        content=content,
    )
    session.add(turn)
    # Deliberately no commit() here — the caller owns the transaction.
    # Batch callers (e.g. _save_memory_node) commit once after the loop for
    # atomicity. Single callers must commit themselves after calling save_turn.
    logger.debug("turn_saved", role=role, conversation_id=str(conversation_id))
    return turn
