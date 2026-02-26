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
from langgraph.checkpoint.memory import MemorySaver
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

    # CopilotKit sends the full message history in each agent/run request (via
    # setMessages on mount + accumulated turns). Skip DB loading when messages
    # are already present to avoid doubling context sent to the LLM.
    if state.get("messages"):
        logger.debug("load_memory_skipped", reason="messages already in state (CopilotKit provided history)")
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


_DEFAULT_SYSTEM_PROMPT = (
    "You are Blitz, an intelligent AI assistant for Blitz employees. "
    "You are professional but warm — like a smart, helpful colleague. "
    "You are clear, direct, and occasionally light in tone.\n\n"
    "When asked about capabilities: Be honest. In this phase you can reason, "
    "answer questions, read uploaded documents, and help with writing and coding. "
    "You cannot yet fetch emails, check calendars, or query projects — those "
    "capabilities are coming soon.\n\n"
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
    from sqlalchemy import func, select as sa_select
    from core.models.memory import ConversationTurn

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
            sa_select(func.count()).where(
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
    return graph.compile(checkpointer=MemorySaver())
