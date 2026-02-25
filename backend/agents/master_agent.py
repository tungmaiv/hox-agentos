# backend/agents/master_agent.py
"""
Master agent — Phase 2 conversational ReAct graph with short-term memory.

Graph topology (Phase 2):
    START → load_memory → master_agent → [_route_after_master] → save_memory → END

Memory nodes read/write conversation turns using user_id and conversation_id from
BlitzState, which is set by gateway/runtime.py from the validated JWT and threadId
before invocation. If not present in state, nodes fall back to core/context.py
contextvars, then skip gracefully (safe for direct test invocation).

Deduplication: BlitzState.initial_message_count tracks message count before graph
invocation. save_memory only saves messages at index >= initial_message_count,
preventing re-saving of history loaded by load_memory.
"""
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.state.types import BlitzState
from core.config import get_llm
from core.context import current_conversation_id_ctx, current_user_ctx
from core.db import async_session

import structlog

logger = structlog.get_logger(__name__)


async def _load_memory_node(state: BlitzState) -> dict:
    """
    Load last 20 turns from memory_conversations and prepend to messages.

    Reads user_id and conversation_id from BlitzState. Falls back to
    core/context.py contextvars (set by gateway/runtime.py) if not in state.
    Returns empty dict (no change) if neither source provides the IDs —
    safe fallback for direct invocation in tests.
    """
    from memory.short_term import load_recent_turns

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

    async with async_session() as session:
        turns = await load_recent_turns(session, user_id=user_id, conversation_id=conversation_id, n=20)

    history: list[BaseMessage] = []
    for turn in turns:
        if turn.role == "user":
            history.append(HumanMessage(content=turn.content))
        elif turn.role == "assistant":
            history.append(AIMessage(content=turn.content))

    if history:
        logger.debug("memory_loaded", turns=len(history), conversation_id=str(conversation_id))
        return {"messages": history}
    return {}


async def _master_node(state: BlitzState) -> dict[str, list[BaseMessage]]:
    """
    Call blitz/master LLM with current conversation messages and return response.

    Uses get_llm() — never a direct provider SDK. The LiteLLM proxy routes
    'blitz/master' to the configured primary (Ollama/Qwen2.5) or fallback (Claude Sonnet).

    Loads custom user instructions from DB (via current_user_ctx contextvar) and
    prepends them as a SystemMessage so every conversation respects the user's
    preferences (e.g. "Always respond in Vietnamese").
    """
    from api.routes.user_instructions import get_user_instructions

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

    # Prepend system message with custom instructions if set
    if custom_instructions:
        system_msg = SystemMessage(
            content=(
                f"Additional user instructions (follow these for all responses):\n\n"
                f"{custom_instructions}"
            )
        )
        messages = [system_msg] + messages

    response = await llm.ainvoke(messages)
    logger.info("master_agent_response", content_length=len(str(response.content)))
    return {"messages": [response]}


async def _save_memory_node(state: BlitzState) -> dict:
    """
    Persist only the newly-added turns from this graph invocation.

    DEDUP GUARD: load_memory_node prepends historical turns into state['messages'].
    Without a guard, save_memory would re-save all of those loaded turns, creating
    duplicate rows in memory_conversations.

    Solution: BlitzState includes 'initial_message_count' — the number of messages
    present BEFORE the graph was invoked (set in gateway/runtime.py before ainvoke).
    save_memory only saves messages at index >= initial_message_count.

    Skips gracefully if user_id or conversation_id not set (direct invocation in tests).
    """
    from memory.short_term import save_turn

    user_id = state.get("user_id")
    conversation_id = state.get("conversation_id")

    if not user_id or not conversation_id:
        return {}

    messages = state["messages"]
    # initial_message_count is the length of state['messages'] before the graph ran.
    # Messages at index < initial_message_count were loaded from history — don't re-save.
    initial_count = state.get("initial_message_count", 0)  # type: ignore[attr-defined]
    new_messages = messages[initial_count:]

    if not new_messages:
        return {}

    async with async_session() as session:
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

    logger.debug("memory_saved", new_turns=len(new_messages), conversation_id=str(conversation_id))
    return {}


def _route_after_master(state: BlitzState) -> str:
    """
    Routing conditional after master_agent node (Phase 2 stub → always save_memory).
    Phase 3 will extend this to route to sub-agent nodes before saving memory.
    """
    return "save_memory"


def create_master_graph() -> CompiledStateGraph:
    """
    Build and compile the master agent StateGraph with memory.

    Returns a compiled graph ready for CopilotKit streaming or direct invocation.
    Call once at startup and reuse — LangGraph compilation is expensive.

    Phase 2 graph topology:
        START → load_memory → master_agent → [_route_after_master] → save_memory → END

    The routing conditional is a stub in Phase 2 (always → save_memory).
    Phase 3 adds sub-agent edges from master_agent without restructuring this graph.
    """
    graph = StateGraph(BlitzState)
    graph.add_node("load_memory", _load_memory_node)
    graph.add_node("master_agent", _master_node)
    graph.add_node("save_memory", _save_memory_node)
    graph.set_entry_point("load_memory")
    graph.add_edge("load_memory", "master_agent")
    # Routing conditional: Phase 2 always goes to save_memory.
    # Phase 3 extends _route_after_master to return sub-agent node names.
    graph.add_conditional_edges(
        "master_agent",
        _route_after_master,
        {"save_memory": "save_memory"},  # Phase 3: add sub-agent entries here
    )
    graph.add_edge("save_memory", END)
    return graph.compile()
