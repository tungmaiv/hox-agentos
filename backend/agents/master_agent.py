# backend/agents/master_agent.py
"""
Master agent — Phase 3 conversational graph with sub-agent routing, short-term + long-term memory.

Graph topology (Phase 3):
    START → load_memory → master_agent → [_route_after_master]
                                              ├── email_agent    → delivery_router → save_memory → END
                                              ├── calendar_agent → delivery_router → save_memory → END
                                              ├── project_agent  → delivery_router → save_memory → END
                                              └── delivery_router → save_memory → END (general)

Memory nodes read/write conversation turns using user_id and conversation_id from
BlitzState, which is set by gateway/runtime.py from the validated JWT and threadId
before invocation. If not present in state, nodes fall back to core/context.py
contextvars, then skip gracefully (safe for direct test invocation).

Deduplication: BlitzState.initial_message_count tracks message count before graph
invocation. save_memory only saves messages at index >= initial_message_count,
preventing re-saving of history loaded by load_memory.

Long-term memory (Phase 3):
- _load_memory_node: embeds last user message → semantic search → injects top-5 facts
- _save_memory_node: dispatches embed_and_store.delay for AI turns (fire-and-forget)
  and summarize_episode.delay at configurable threshold
"""
import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import func, select

from agents.state.types import BlitzState
from api.routes.user_instructions import get_user_instructions
from core.config import get_llm, settings
from core.context import current_conversation_id_ctx, current_user_ctx
from core.db import async_session
from core.models.memory import ConversationTurn
from memory.embeddings import BGE_M3Provider
from memory.long_term import search_facts
from memory.medium_term import load_recent_episodes
from memory.short_term import load_recent_turns, save_turn
from scheduler.tasks.embedding import embed_and_store, summarize_episode

logger = structlog.get_logger(__name__)


async def _load_memory_node(state: BlitzState) -> dict:
    """
    Load last 20 turns from memory_conversations and inject long-term facts.

    Phase 3 additions:
    - Embeds the last user message using BGE_M3Provider (run_in_executor, non-blocking).
    - Performs cosine semantic search over memory_facts (top 5, user-scoped).
    - Injects matching facts as a SystemMessage prefix before the conversation history.
    - Returns loaded_facts list for audit trail.

    Reads user_id and conversation_id from BlitzState. Falls back to
    core/context.py contextvars (set by gateway/runtime.py) if not in state.
    Returns empty dict (no change) if neither source provides the IDs —
    safe fallback for direct invocation in tests.
    """
    user_id = state.get("user_id")
    conversation_id = state.get("conversation_id")

    # Contextvar fallback: gateway/runtime.py sets these before graph invocation
    if not user_id:
        try:
            ctx_user = current_user_ctx.get()
            user_id = ctx_user["user_id"]
        except LookupError:
            pass

    if not conversation_id:
        try:
            conversation_id = current_conversation_id_ctx.get()
        except LookupError:
            pass

    if not user_id or not conversation_id:
        logger.debug("load_memory_skipped", reason="no user_id or conversation_id available")
        return {}

    # CopilotKit sends the full message history in each agent/run request (via
    # setMessages on mount + accumulated turns). Skip DB loading when messages
    # are already present to avoid doubling context sent to the LLM.
    if state.get("messages"):
        logger.debug("load_memory_skipped", reason="messages already in state (CopilotKit provided history)")
        # Still inject long-term facts even when short-term history is skipped.
        # Fall through to long-term memory injection below.
        history: list[BaseMessage] = list(state.get("messages", []))
        skip_short_term = True
    else:
        async with async_session() as session:
            turns = await load_recent_turns(session, user_id=user_id, conversation_id=conversation_id, n=20)

        history = []
        for turn in turns:
            if turn.role == "user":
                history.append(HumanMessage(content=turn.content))
            elif turn.role == "assistant":
                history.append(AIMessage(content=turn.content))

        if history:
            logger.debug("memory_loaded", turns=len(history), conversation_id=str(conversation_id))

        skip_short_term = False

    # Long-term memory: semantic search for relevant facts about this user.
    # Embed the last user message and search memory_facts using pgvector cosine distance.
    # BGE_M3Provider.embed() uses run_in_executor internally — non-blocking in FastAPI.
    last_user_message = next(
        (m.content for m in reversed(state.get("messages", [])) if isinstance(m, HumanMessage)),
        None,
    )
    loaded_facts: list[str] = []
    if last_user_message and user_id:
        try:
            provider = BGE_M3Provider()
            query_embedding = (await provider.embed([str(last_user_message)]))[0]
            async with async_session() as session:
                facts = await search_facts(
                    session,
                    user_id=user_id,
                    query_embedding=query_embedding,
                    k=5,
                )
            loaded_facts = [f.content for f in facts]
            if loaded_facts:
                facts_context = "\n".join(f"- {fact}" for fact in loaded_facts)
                # Insert as first SystemMessage so it appears before conversation history
                history.insert(
                    0,
                    SystemMessage(
                        content=f"[Long-term memory — relevant facts about this user:]\n{facts_context}"
                    ),
                )
                logger.debug(
                    "long_term_memory_loaded",
                    fact_count=len(loaded_facts),
                    user_id=str(user_id),
                )
        except Exception:
            # Graceful degradation: long-term memory failure must not block the agent
            logger.warning("long_term_memory_load_failed", user_id=str(user_id))

    # Medium-term memory: recent episode summaries (cross-session context).
    # Loaded unconditionally on user_id — not query-dependent like long-term facts.
    if user_id:
        try:
            async with async_session() as session:
                episodes = await load_recent_episodes(session, user_id=user_id, n=3)
            if episodes:
                episode_context = "\n".join(f"- {ep.summary}" for ep in episodes)
                history.insert(
                    0,
                    SystemMessage(
                        content=(
                            "[Medium-term memory — summaries of past conversations:]\n"
                            + episode_context
                        )
                    ),
                )
                logger.debug(
                    "medium_term_memory_loaded",
                    episode_count=len(episodes),
                    user_id=str(user_id),
                )
        except Exception:
            # Graceful degradation: episode load failure must not block the agent
            logger.warning("medium_term_memory_load_failed", user_id=str(user_id))

    if skip_short_term:
        # Short-term was already in state; only return the newly loaded facts
        return {"loaded_facts": loaded_facts}

    if history or loaded_facts:
        return {"messages": history, "loaded_facts": loaded_facts}
    return {}


_DEFAULT_SYSTEM_PROMPT = (
    "You are Blitz, an intelligent AI assistant for Blitz employees. "
    "You are professional but warm — like a smart, helpful colleague. "
    "You are clear, direct, and occasionally light in tone.\n\n"
    "When you don't know something: Say so directly. Don't make up information.\n\n"
    "Format your responses with markdown when it improves clarity (headers, bold, "
    "code blocks). Keep responses focused and appropriately concise.\n\n"
    "IMPORTANT — math formatting rules you must always follow:\n"
    "- NEVER use LaTeX notation. No backslashes, no \\frac, no \\times, no \\cdot.\n"
    "- NEVER wrap math in ( ) or [ ] delimiters like ( x ) or [ x = 5 ].\n"
    "- NEVER wrap math in backticks or code blocks.\n"
    "- Write math as plain readable prose: '15 / 3 = 5', '1239 × 17 = 21063'.\n"
    "- Use the Unicode × character for multiplication, ÷ for division."
)


async def _master_node(state: BlitzState) -> dict[str, list[BaseMessage]]:
    """
    Call blitz/master LLM with current conversation messages and return response.

    Uses get_llm() — never a direct provider SDK. The LiteLLM proxy routes
    'blitz/master' to the configured primary (Ollama/Qwen2.5) or fallback (Claude Sonnet).

    Always prepends _DEFAULT_SYSTEM_PROMPT as the first SystemMessage so formatting
    rules (no LaTeX, markdown etc.) reach the LLM regardless of CopilotKit's
    instructions prop handling. Appends per-user custom instructions if set in DB.
    """
    llm = get_llm("blitz/master")

    # Load custom instructions (empty string if not set or no user context)
    custom_instructions = ""
    try:
        user = current_user_ctx.get()
        async with async_session() as session:
            custom_instructions = await get_user_instructions(user["user_id"], session)
    except LookupError:
        pass  # No user context in tests — skip custom instructions

    messages = list(state["messages"])

    # Build system content: default prompt + optional per-user instructions.
    # Always injected so the LLM sees formatting rules on every call.
    system_content = _DEFAULT_SYSTEM_PROMPT
    if custom_instructions:
        system_content += (
            f"\n\nAdditional user instructions (follow these for all responses):\n\n"
            f"{custom_instructions}"
        )
    messages = [SystemMessage(content=system_content)] + messages

    response = await llm.ainvoke(messages)
    logger.info("master_agent_response", content_length=len(str(response.content)))
    return {"messages": [response]}


async def _get_episode_threshold() -> int:
    """
    Read episode summarization threshold from system_config DB.

    Falls back to settings.episode_turn_threshold (default 10) if the key is not set
    or DB read fails. This allows runtime configuration via admin API without a redeploy.
    """
    from core.models.system_config import SystemConfig

    try:
        async with async_session() as s:
            result = await s.execute(
                select(SystemConfig).where(
                    SystemConfig.key == "memory.episode_turn_threshold"
                )
            )
            row = result.scalar_one_or_none()
            if row is not None:
                return int(row.value)
    except Exception:
        pass
    return settings.episode_turn_threshold  # fallback to 10


async def _save_memory_node(state: BlitzState) -> dict:
    """
    Persist only the newly-added turns from this graph invocation.

    Phase 3 additions:
    - Dispatches embed_and_store.delay() for each new AI (assistant) turn.
      Fire-and-forget: Celery embedding worker picks it up asynchronously.
    - Triggers summarize_episode.delay() when total turn count reaches a multiple
      of the configurable threshold (system_config key 'memory.episode_turn_threshold',
      default 10 from settings.episode_turn_threshold).

    DEDUP GUARD: load_memory_node prepends historical turns into state['messages'].
    Without a guard, save_memory would re-save all of those loaded turns, creating
    duplicate rows in memory_conversations.

    Solution: Count existing turns in DB — anything beyond that count is new.
    Saves only new turns, then dispatches Celery tasks for embedding and summarization.

    Skips gracefully if user_id or conversation_id not set (direct invocation in tests).
    """
    user_id = state.get("user_id")
    conversation_id = state.get("conversation_id")

    # Contextvar fallback — mirrors _load_memory_node.
    # BlitzState fields are None when graph is invoked via LangGraphAGUIAgent
    # (the agent doesn't inject custom state fields); runtime.py sets these
    # as contextvars so both load and save nodes can find them.
    if not user_id:
        try:
            ctx_user = current_user_ctx.get()
            user_id = ctx_user["user_id"]
        except LookupError:
            pass

    if not conversation_id:
        try:
            conversation_id = current_conversation_id_ctx.get()
        except LookupError:
            pass

    if not user_id or not conversation_id:
        return {}

    messages = state["messages"]

    # Use DB turn count to determine which messages are new.
    # CopilotKit sends the full message history on every agent/run, so
    # initial_message_count (never set by LangGraphAGUIAgent) can't be trusted.
    # Instead, count existing turns in DB — anything beyond that is new.
    async with async_session() as session:
        count_result = await session.execute(
            select(func.count()).where(
                ConversationTurn.user_id == user_id,
                ConversationTurn.conversation_id == conversation_id,
            )
        )
        existing_count = count_result.scalar_one()
        new_messages = messages[existing_count:]

        if not new_messages:
            return {}

        for msg in new_messages:
            if isinstance(msg, HumanMessage):
                await save_turn(
                    session,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    role="user",
                    content=str(msg.content),
                )
            elif isinstance(msg, AIMessage):
                await save_turn(
                    session,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=str(msg.content),
                )
        # Single commit after the loop — all turns saved atomically.
        # save_turn() no longer commits internally; the session owner commits.
        await session.commit()

    logger.debug("memory_saved", new_turns=len(new_messages), conversation_id=str(conversation_id))

    # Dispatch async embedding for new AI (assistant) turns — fire-and-forget.
    # Celery embedding worker picks these up on the 'embedding' queue.
    # Only AI turns are embedded as facts (user messages are ephemeral context).
    for msg in new_messages:
        if isinstance(msg, AIMessage):
            embed_and_store.delay(str(msg.content), str(user_id), "fact")

    # Trigger episode summarization at configurable threshold.
    # Read threshold from system_config DB first; fall back to settings default.
    total_after = existing_count + len(new_messages)
    threshold = await _get_episode_threshold()
    if total_after > 0 and total_after % threshold == 0:
        summarize_episode.delay(str(conversation_id), str(user_id))
        logger.info(
            "episode_summarization_triggered",
            turn_count=total_after,
            threshold=threshold,
            conversation_id=str(conversation_id),
        )

    return {}


def _classify_by_keywords(text: str) -> str:
    """
    Keyword-based intent classification — no LLM call.

    Returns one of: "email", "calendar", "project", "general".

    Using keywords instead of an LLM here is intentional: routing functions
    run outside graph nodes, so any LLM call they make gets streamed by
    CopilotKit as a chat message (e.g. "general" appearing before the real
    answer). Keywords are instant and sufficient for Phase 3's explicit intents.
    """
    import re
    lowered = text.lower()
    words = set(re.findall(r"\w+", lowered))

    _EMAIL_KW = {"email", "emails", "inbox", "unread", "mail"}
    _CAL_KW = {"calendar", "schedule", "meeting", "meetings", "event", "events", "appointment"}
    _PROJECT_KW = {"project", "projects", "crm", "task", "tasks", "sprint", "milestone"}

    if words & _EMAIL_KW:
        return "email"
    if words & _CAL_KW:
        return "calendar"
    if words & _PROJECT_KW or "status of" in lowered or "status of project" in lowered:
        return "project"
    return "general"


async def _pre_route(state: BlitzState) -> str:
    """
    Routing conditional after load_memory, BEFORE master_agent runs.

    Uses keyword matching (no LLM) to classify intent. Sub-agent intents
    bypass the master LLM entirely — the sub-agent provides the full
    structured response. General intent falls through to master_agent.

    Keyword-based classification is used here because:
    - Routing functions run outside LangGraph nodes, so LLM calls made here
      get streamed by CopilotKit as chat messages (spurious "general" text).
    - Keyword matching is instant, restoring the typing indicator for the
      master agent without any extra latency.

    Returns node names:
      "email_agent"    — route directly to email sub-agent
      "calendar_agent" — route directly to calendar sub-agent
      "project_agent"  — route directly to project sub-agent
      "master_agent"   — general intent; run master LLM
    """
    from core.models.system_config import SystemConfig

    last_user_msg = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), ""
    )
    intent = _classify_by_keywords(str(last_user_msg))

    async def _agent_enabled(key: str) -> bool:
        try:
            async with async_session() as s:
                result = await s.execute(select(SystemConfig).where(SystemConfig.key == key))
                row = result.scalar_one_or_none()
                if row is None:
                    return True  # default enabled when not configured
                return bool(row.value)
        except Exception:
            return True  # fail open — agent enabled on DB error

    if intent == "email" and await _agent_enabled("agent.email.enabled"):
        return "email_agent"
    if intent == "calendar" and await _agent_enabled("agent.calendar.enabled"):
        return "calendar_agent"
    if intent == "project" and await _agent_enabled("agent.project.enabled"):
        return "project_agent"
    # General intent (or disabled sub-agent): run master LLM
    return "master_agent"


def create_master_graph() -> CompiledStateGraph:
    """
    Build and compile the master agent StateGraph with memory and sub-agent routing.

    Returns a compiled graph ready for CopilotKit streaming or direct invocation.
    Call once at startup and reuse — LangGraph compilation is expensive.

    Phase 3 graph topology:
        START → load_memory → [_pre_route]
                                  ├── "email_agent"    → email_agent_node    → delivery_router → save_memory → END
                                  ├── "calendar_agent" → calendar_agent_node → delivery_router → save_memory → END
                                  ├── "project_agent"  → project_agent_node  → delivery_router → save_memory → END
                                  └── "master_agent"   → master_agent_node   → delivery_router → save_memory → END

    Sub-agent intents skip the master LLM entirely — no apology text injected
    before the structured card response. General intents run the master LLM.
    """
    from agents.delivery_router import delivery_router_node
    from agents.subagents.calendar_agent import calendar_agent_node
    from agents.subagents.email_agent import email_agent_node
    from agents.subagents.project_agent import project_agent_node

    graph = StateGraph(BlitzState)
    graph.add_node("load_memory", _load_memory_node)
    graph.add_node("master_agent", _master_node)
    graph.add_node("email_agent", email_agent_node)
    graph.add_node("calendar_agent", calendar_agent_node)
    graph.add_node("project_agent", project_agent_node)
    graph.add_node("delivery_router", delivery_router_node)
    graph.add_node("save_memory", _save_memory_node)

    graph.set_entry_point("load_memory")

    # Intent classification before master LLM — sub-agent intents skip master entirely
    graph.add_conditional_edges(
        "load_memory",
        _pre_route,
        {
            "email_agent": "email_agent",
            "calendar_agent": "calendar_agent",
            "project_agent": "project_agent",
            "master_agent": "master_agent",
        },
    )

    # All paths converge at delivery_router → save_memory → END
    graph.add_edge("master_agent", "delivery_router")
    graph.add_edge("email_agent", "delivery_router")
    graph.add_edge("calendar_agent", "delivery_router")
    graph.add_edge("project_agent", "delivery_router")
    graph.add_edge("delivery_router", "save_memory")
    graph.add_edge("save_memory", END)

    return graph.compile(checkpointer=MemorySaver())
