"""
Celery tasks for embedding and episode summarization.

embed_and_store:
  - Routes to queue: embedding
  - Embeds text using BGE_M3Provider and stores result in memory_facts or memory_episodes.
  - entry_type="fact"    → INSERT into memory_facts (user preferences, facts)
  - entry_type="episode" → INSERT into memory_episodes (conversation summaries)

summarize_episode:
  - Routes to queue: default (LLM-backed, I/O-bound)
  - Reads last 50 turns of a conversation, calls blitz/summarizer LLM,
    then dispatches embed_and_store to persist the summary.

SECURITY:
  user_id always comes from request context (stored during the request lifecycle),
  NEVER from user input or task arguments supplied by callers outside the system.
  Celery workers run as the job owner — see CLAUDE.md §7 Scheduler Security.
"""

import asyncio
from uuid import UUID

import structlog

from scheduler.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    queue="embedding",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="scheduler.tasks.embedding.embed_and_store",
)
def embed_and_store(
    self,  # type: ignore[override]
    text: str,
    user_id_str: str,
    entry_type: str,
    conversation_id_str: str | None = None,
) -> None:
    """
    Embed text via bge-m3 and store in memory_facts or memory_episodes.

    Args:
        text: Content to embed and store.
        user_id_str: User UUID as string — from request context, never user input.
        entry_type: "fact" or "episode".
        conversation_id_str: Required when entry_type="episode".
    """
    from core.db import async_session
    from core.models.memory_long_term import MemoryEpisode, MemoryFact
    from memory.embeddings import BGE_M3Provider

    async def _run() -> None:
        user_id = UUID(user_id_str)
        provider = BGE_M3Provider()
        embeddings = await provider.embed([text])
        embedding_vector = embeddings[0]

        async with async_session() as session:
            if entry_type == "fact":
                fact = MemoryFact(
                    user_id=user_id,
                    content=text,
                    source="conversation",
                    embedding=embedding_vector,
                )
                session.add(fact)
            elif entry_type == "episode":
                if conversation_id_str is None:
                    logger.error(
                        "embed_and_store_episode_missing_conversation_id",
                        user_id=user_id_str,
                    )
                    return
                episode = MemoryEpisode(
                    user_id=user_id,
                    conversation_id=UUID(conversation_id_str),
                    summary=text,
                    embedding=embedding_vector,
                )
                session.add(episode)
            else:
                logger.error(
                    "embed_and_store_unknown_entry_type",
                    entry_type=entry_type,
                    user_id=user_id_str,
                )
                return

            await session.commit()
            logger.info(
                "embedding_stored",
                entry_type=entry_type,
                user_id=user_id_str,
            )

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(
            "embed_and_store_failed",
            error=str(exc),
            user_id=user_id_str,
            entry_type=entry_type,
        )
        raise self.retry(exc=exc)


@celery_app.task(
    queue="default",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name="scheduler.tasks.embedding.summarize_episode",
)
def summarize_episode(
    self,  # type: ignore[override]
    conversation_id_str: str,
    user_id_str: str,
) -> None:
    """
    Summarize a conversation into an episode, then dispatch embed_and_store.

    Reads the last 50 turns from memory_conversations, invokes blitz/summarizer
    to produce a 2-3 sentence summary, then dispatches embed_and_store to persist
    the summary with its bge-m3 embedding in memory_episodes.

    Args:
        conversation_id_str: Conversation UUID as string.
        user_id_str: User UUID as string — from request context, never user input.
    """
    from core.config import get_llm
    from core.db import async_session
    from memory.short_term import load_recent_turns

    async def _run() -> None:
        user_id = UUID(user_id_str)
        conversation_id = UUID(conversation_id_str)

        async with async_session() as session:
            turns = await load_recent_turns(
                session,
                user_id=user_id,
                conversation_id=conversation_id,
                n=50,
            )

        if not turns:
            logger.info(
                "summarize_episode_no_turns",
                conversation_id=conversation_id_str,
                user_id=user_id_str,
            )
            return

        # Format turns for LLM summarization
        transcript = "\n".join(
            f"{'User' if t.role == 'user' else 'Assistant'}: {t.content}"
            for t in turns
        )
        prompt = (
            "Summarize this conversation in 2-3 sentences. Focus on key facts, "
            "decisions, and preferences expressed by the user.\n\n" + transcript
        )

        from langchain_core.messages import HumanMessage

        llm = get_llm("blitz/summarizer")
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        summary = str(response.content).strip()

        # Dispatch embedding task — runs on embedding queue for CPU-bound bge-m3 work
        embed_and_store.delay(
            summary,
            user_id_str,
            "episode",
            conversation_id_str=conversation_id_str,
        )
        logger.info(
            "episode_summary_created",
            conversation_id=conversation_id_str,
            user_id=user_id_str,
            summary_length=len(summary),
        )

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(
            "summarize_episode_failed",
            error=str(exc),
            conversation_id=conversation_id_str,
            user_id=user_id_str,
        )
        raise self.retry(exc=exc)
