# backend/agents/master_agent.py
"""
Master agent — Phase 3 conversational graph with sub-agent routing, short-term + long-term memory.

Graph topology (Phase 3):
    START → load_memory → master_agent → [_pre_route]
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
import importlib
import time
from datetime import datetime, timezone
from typing import Any

import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agents.state.types import BlitzState
from api.routes.user_instructions import get_user_instructions
from api.routes.user_preferences import get_user_preference_values
from core.config import get_llm, settings
from core.prompts import load_prompt
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
            async with session.begin():
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
                async with session.begin():
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
        except Exception as exc:
            # Graceful degradation: long-term memory failure must not block the agent
            logger.warning("long_term_memory_load_failed", user_id=str(user_id), error=str(exc))

    # Medium-term memory: recent episode summaries (cross-session context).
    # Loaded unconditionally on user_id — not query-dependent like long-term facts.
    if user_id:
        try:
            async with async_session() as session:
                async with session.begin():
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
        except Exception as exc:
            # Graceful degradation: episode load failure must not block the agent
            logger.warning("medium_term_memory_load_failed", user_id=str(user_id), error=str(exc))

    if skip_short_term:
        # Short-term was already in state; only return the newly loaded facts
        return {"loaded_facts": loaded_facts}

    if history or loaded_facts:
        return {"messages": history, "loaded_facts": loaded_facts}
    return {}


async def _master_node(state: BlitzState) -> dict[str, list[BaseMessage]]:
    """
    Call blitz/master LLM with current conversation messages and return response.

    Uses get_llm() — never a direct provider SDK. The LiteLLM proxy routes
    'blitz/master' to the configured primary (Ollama/Qwen2.5) or fallback (Claude Sonnet).

    Always prepends the master_agent prompt as the first SystemMessage so formatting
    rules (no LaTeX, markdown etc.) reach the LLM regardless of CopilotKit's
    instructions prop handling. Appends per-user custom instructions if set in DB.

    Injects dynamic context variables into the prompt template:
    - user_context: username and role info from JWT
    - current_datetime: current date/time for time-aware responses
    - available_tools: dynamically loaded tool list from registry
    """
    llm = get_llm("blitz/master")

    # Load custom instructions, user preferences, and user context
    # (empty/defaults if not set or no user context)
    custom_instructions = ""
    user_context_str = ""
    user_prefs: dict = {}
    try:
        user = current_user_ctx.get()
        user_context_str = f"User: {user.get('username', 'unknown')} ({user.get('email', '')})"
        async with async_session() as session:
            async with session.begin():
                custom_instructions = await get_user_instructions(user["user_id"], session)
                user_prefs = await get_user_preference_values(user["user_id"], session)
    except LookupError:
        pass  # No user context in tests or isolated runs — skip
    except Exception:
        logger.warning("custom_instructions_load_failed", exc_info=True)

    # Load available tools from registry for context injection
    available_tools_str = ""
    try:
        async with async_session() as session:
            async with session.begin():
                from gateway.tool_registry import list_tools
                tool_names = await list_tools(session)
                if tool_names:
                    available_tools_str = (
                        "Registered tools: " + ", ".join(tool_names)
                    )
    except Exception:
        logger.debug("tool_list_load_skipped", exc_info=True)

    messages = list(state["messages"])

    # Build system content: default prompt with context variables + optional per-user instructions.
    # Always injected so the LLM sees formatting rules on every call.
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    system_content = load_prompt(
        "master_agent",
        user_context=user_context_str,
        current_datetime=now_str,
        available_tools=available_tools_str,
    )
    if custom_instructions:
        system_content += (
            f"\n\nAdditional user instructions (follow these for all responses):\n\n"
            f"{custom_instructions}"
        )

    # Inject user preference directives (thinking mode, response style)
    if user_prefs:
        pref_directives: list[str] = []
        if user_prefs.get("thinking_mode"):
            pref_directives.append(
                "The user has enabled thinking mode. Before answering, briefly show "
                "your reasoning process in a <thinking> block, then provide the answer."
            )

        style = user_prefs.get("response_style", "concise")
        if style == "detailed":
            pref_directives.append(
                "The user prefers detailed responses. Provide thorough explanations "
                "with examples and context. Use structured formatting (headings, lists) "
                "for complex answers."
            )
        elif style == "conversational":
            pref_directives.append(
                "The user prefers a conversational style. Be friendly and engaging, "
                "use natural language, and feel free to ask follow-up questions."
            )
        # "concise" is the default — no extra directive needed (base prompt is already concise)

        if pref_directives:
            system_content += "\n\nUser preferences:\n" + "\n".join(
                f"- {d}" for d in pref_directives
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
            async with s.begin():
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
        try:
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
        except Exception:
            await session.rollback()
            raise

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


# ── Module-level keyword routing cache ──────────────────────────────────
# When DB agents are loaded, this map is populated from agent_definitions.routing_keywords.
# Format: {"keyword": "agent_name"} — e.g. {"email": "email_agent", "inbox": "email_agent"}
# Falls back to hardcoded _FALLBACK_KEYWORD_MAP if empty (backward compat).
_keyword_to_agent: dict[str, str] = {}

# ── Slash command cache (TTL = 60s) ────────────────────────────────────
# Maps slash_command string -> skill name for active skills.
# Avoids a DB query on every message that starts with "/".
_slash_cache: dict[str, str] = {}
_slash_cache_timestamp: float = 0.0
_SLASH_CACHE_TTL: float = 60.0

# ── Agent enabled cache (TTL = 60s) ────────────────────────────────────
# Maps "agent.{short_name}.enabled" config key -> bool.
# Avoids a DB query on every routed message.
_agent_enabled_cache: dict[str, bool] = {}
_agent_enabled_cache_timestamp: float = 0.0
_AGENT_ENABLED_CACHE_TTL: float = 60.0

_CAPABILITIES_PHRASES: list[str] = [
    "what can you do",
    "what are your capabilities",
    "list capabilities",
    "show capabilities",
    "available tools",
    "available skills",
    "show me your capabilities",
    "what capabilities",
    "list your capabilities",
]

_FALLBACK_KEYWORD_MAP: dict[str, str] = {
    # email
    "email": "email_agent", "emails": "email_agent", "inbox": "email_agent",
    "unread": "email_agent", "mail": "email_agent",
    # calendar
    "calendar": "calendar_agent", "schedule": "calendar_agent",
    "meeting": "calendar_agent", "meetings": "calendar_agent",
    "event": "calendar_agent", "events": "calendar_agent",
    "appointment": "calendar_agent",
    # project
    "project": "project_agent", "projects": "project_agent",
    "crm": "project_agent", "task": "project_agent",
    "tasks": "project_agent", "sprint": "project_agent",
    "milestone": "project_agent",
}


def _classify_by_keywords(text: str) -> str:
    """
    Keyword-based intent classification -- no LLM call.

    Phase 6: Uses _keyword_to_agent map if populated from DB agents,
    falls back to hardcoded keywords if empty (backward compat).

    Phase 14: Detects capabilities-intent phrases before agent routing.

    Returns the agent name (e.g. "email_agent"), "capabilities", or "general".

    Using keywords instead of an LLM here is intentional: routing functions
    run outside graph nodes, so any LLM call they make gets streamed by
    CopilotKit as a chat message (e.g. "general" appearing before the real
    answer). Keywords are instant and sufficient for explicit intents.
    """
    import re
    lowered = text.lower()
    words = set(re.findall(r"\w+", lowered))

    # Phase 14: Capabilities intent detection (checked before agent routing)
    for phrase in _CAPABILITIES_PHRASES:
        if phrase in lowered:
            return "capabilities"

    # DB mode: _keyword_to_agent is populated from agent_definitions.routing_keywords
    # by create_master_graph(). Fallback mode: uses _FALLBACK_KEYWORD_MAP when DB
    # agents are not loaded. The fallback includes a phrase pattern ("status of" ->
    # project_agent) that won't exist in DB mode unless explicitly added as a
    # routing keyword on the project_agent definition.
    kw_map = _keyword_to_agent if _keyword_to_agent else _FALLBACK_KEYWORD_MAP

    for word in words:
        if word in kw_map:
            return kw_map[word]

    # Phrase patterns only in fallback mode (DB agents define their own keywords)
    if not _keyword_to_agent:
        if "status of" in lowered:
            return "project_agent"

    return "general"


# TODO(tech-debt): Replace _route_after_master with Agent-as-Tool pattern.
# Current approach: keyword map routes to hardcoded sub-agent modules.
# This prevents adding agents without touching routing code and blocks
# multi-agent queries (e.g. "summarize my emails AND create a Jira ticket").
# Correct approach: each registered agent/skill is exposed as a callable tool
# to the master LLM — routing becomes natural tool selection by the LLM.
# Tracked as deferred work: Phase 11 CONTEXT.md -> Deferred Ideas.
# DO NOT remove this function until the Agent-as-Tool routing phase is complete.
async def _pre_route(state: BlitzState) -> str:
    """
    Routing conditional after load_memory, BEFORE master_agent runs.

    Phase 6: Detects /command prefix BEFORE keyword routing.
    If the user message starts with '/', look up in skill_definitions.
    If a matching skill is found, route to 'skill_executor' node.

    Uses DB-backed keyword routing from agent_definitions.routing_keywords
    when available. Falls back to hardcoded keywords if DB routing map is empty.

    Caching: Both slash command lookups and agent enabled checks use
    60s TTL in-process caches to avoid per-message DB queries.

    Returns node names:
      "skill_executor" -- route to skill executor (slash command detected)
      "{agent_name}" -- route directly to matching sub-agent
      "master_agent" -- general intent; run master LLM
    """
    last_user_msg = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), ""
    )
    last_msg_str = str(last_user_msg).strip()

    # Phase 6: Slash command detection before keyword routing (cached)
    if last_msg_str.startswith("/"):
        command = last_msg_str.split()[0]  # e.g., "/morning_digest"
        skill_name = await _lookup_slash_command(command)
        if skill_name is not None:
            logger.info(
                "slash_command_detected",
                command=command,
                skill_name=skill_name,
            )
            return "skill_executor"
        # Unknown /command: fall through to keyword routing / master_agent

    intent = _classify_by_keywords(last_msg_str)

    if intent == "general":
        return "master_agent"

    # Phase 14: Capabilities intent — route to capabilities_node
    if intent == "capabilities":
        return "capabilities_node"

    if await _agent_enabled(intent):
        return intent
    # Disabled agent: fall through to master LLM
    return "master_agent"


async def _refresh_slash_cache() -> None:
    """Reload slash command cache from skill_definitions table."""
    global _slash_cache, _slash_cache_timestamp
    from core.models.skill_definition import SkillDefinition as _SkillDef

    try:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(_SkillDef.slash_command, _SkillDef.name).where(
                        _SkillDef.slash_command.isnot(None),
                        _SkillDef.status == "active",
                        _SkillDef.is_active == True,  # noqa: E712
                    )
                )
                _slash_cache = {row[0]: row[1] for row in result.all()}
    except Exception as exc:
        logger.warning("slash_cache_refresh_failed", error=str(exc))
        # Keep stale cache on failure
    _slash_cache_timestamp = time.monotonic()


async def _lookup_slash_command(command: str) -> str | None:
    """Look up a slash command in the cached skill map. Returns skill name or None."""
    global _slash_cache_timestamp
    elapsed = time.monotonic() - _slash_cache_timestamp
    if elapsed >= _SLASH_CACHE_TTL or not _slash_cache_timestamp:
        await _refresh_slash_cache()
    return _slash_cache.get(command)


async def _refresh_agent_enabled_cache() -> None:
    """Reload agent enabled/disabled settings from system_config."""
    global _agent_enabled_cache, _agent_enabled_cache_timestamp
    from core.models.system_config import SystemConfig

    try:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(SystemConfig).where(
                        SystemConfig.key.like("agent.%.enabled")
                    )
                )
                rows = result.scalars().all()
                _agent_enabled_cache = {row.key: bool(row.value) for row in rows}
    except Exception as exc:
        logger.warning("agent_enabled_cache_refresh_failed", error=str(exc))
    _agent_enabled_cache_timestamp = time.monotonic()


async def _agent_enabled(agent_name: str) -> bool:
    """Check if an agent is enabled via cached system_config lookup."""
    global _agent_enabled_cache_timestamp
    elapsed = time.monotonic() - _agent_enabled_cache_timestamp
    if elapsed >= _AGENT_ENABLED_CACHE_TTL or not _agent_enabled_cache_timestamp:
        await _refresh_agent_enabled_cache()

    short_name = agent_name.replace("_agent", "")
    key = f"agent.{short_name}.enabled"
    # Default enabled when not configured
    return _agent_enabled_cache.get(key, True)


async def _skill_executor_node(state: BlitzState) -> dict[str, list[BaseMessage]]:
    """
    Execute a skill triggered by a /command in chat.

    Loads the matching skill from DB based on the slash command in the last message,
    then dispatches:
    - Procedural: runs SkillExecutor.run(), formats output as assistant message
    - Instructional: appends instruction_markdown as system message for LLM context

    For instructional skills, the instruction is injected and a follow-up LLM call
    is made so the agent can process the instructions with the user's context.
    """
    from core.models.skill_definition import SkillDefinition as _SkillDef
    from skills.executor import SkillExecutor

    last_user_msg = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), ""
    )
    command = str(last_user_msg).strip().split()[0]  # e.g., "/morning_digest"

    try:
        async with async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(_SkillDef).where(
                        _SkillDef.slash_command == command,
                        _SkillDef.status == "active",
                        _SkillDef.is_active == True,  # noqa: E712
                    )
                )
                skill = result.scalar_one_or_none()
    except Exception as exc:
        logger.error("skill_executor_db_error", command=command, error=str(exc))
        return {"messages": [AIMessage(content=f"Error loading skill for {command}: {str(exc)}")]}

    if skill is None:
        return {"messages": [AIMessage(content=f"Skill for command {command} not found or not active.")]}

    if skill.skill_type == "procedural":
        # Build user context from contextvar
        user_id = state.get("user_id")
        if not user_id:
            try:
                ctx_user = current_user_ctx.get()
                user_id = ctx_user["user_id"]
            except LookupError:
                pass

        if not user_id:
            return {"messages": [AIMessage(content="Cannot execute skill: no user context available.")]}

        try:
            user_ctx = current_user_ctx.get()
        except LookupError:
            user_ctx = {"user_id": user_id, "roles": [], "email": ""}

        user_context = {
            "user_id": user_ctx.get("user_id", user_id),
            "roles": user_ctx.get("roles", []),
            "email": user_ctx.get("email", ""),
        }

        executor = SkillExecutor()
        async with async_session() as session:
            try:
                skill_result = await executor.run(skill, user_context, session)
            except Exception:
                await session.rollback()
                raise

        logger.info(
            "skill_executor_completed",
            skill_name=skill.name,
            command=command,
            success=skill_result.success,
        )

        return {"messages": [AIMessage(content=skill_result.output)]}

    elif skill.skill_type == "instructional":
        # Inject instruction as system message, then let master_agent LLM process
        instruction = skill.instruction_markdown or ""
        llm = get_llm("blitz/master")

        messages = list(state["messages"])
        messages.insert(
            0,
            SystemMessage(
                content=f"[Skill: {skill.display_name or skill.name}]\n\n{instruction}"
            ),
        )
        messages = [SystemMessage(content=load_prompt("master_agent"))] + messages

        response = await llm.ainvoke(messages)

        logger.info(
            "skill_executor_instructional",
            skill_name=skill.name,
            command=command,
        )

        return {"messages": [response]}

    else:
        return {"messages": [AIMessage(content=f"Unknown skill type: {skill.skill_type}")]}


async def _capabilities_node(state: BlitzState) -> dict[str, list[BaseMessage]]:
    """
    Phase 14: Handle capabilities-intent messages by invoking system_capabilities().

    Builds a CapabilitiesResponse from all four artifact registries, then formats
    the result as a JSON-serializable A2UI card (agent="capabilities") for the
    frontend CapabilitiesCard component. Falls back to markdown summary for
    non-web channels (via delivery_router format_for_channel).

    This node is reached via _pre_route when the user message matches a
    capabilities-intent phrase (e.g. "what can you do", "list capabilities").
    """
    from capabilities.tool import system_capabilities

    user_id = state.get("user_id")
    if not user_id:
        try:
            ctx_user = current_user_ctx.get()
            user_id = ctx_user["user_id"]
        except LookupError:
            pass

    if not user_id:
        return {
            "messages": [AIMessage(content="Cannot list capabilities: no user context available.")]
        }

    try:
        async with async_session() as session:
            async with session.begin():
                result = await system_capabilities(user_id=user_id, session=session)

        # Serialize as A2UI card for frontend CapabilitiesCard rendering
        import json
        card_data = {
            "agent": "capabilities",
            "agents": [a.model_dump() for a in result.agents],
            "tools": [t.model_dump() for t in result.tools],
            "skills": [s.model_dump() for s in result.skills],
            "mcp_servers": [m.model_dump() for m in result.mcp_servers],
            "summary": result.summary,
        }
        content = json.dumps(card_data)
        logger.info("capabilities_node_complete", summary=result.summary)
        return {"messages": [AIMessage(content=content)]}

    except Exception as exc:
        logger.error("capabilities_node_error", error=str(exc))
        return {
            "messages": [AIMessage(content=f"Error fetching capabilities: {str(exc)}")]
        }


async def update_agent_last_seen(agent_name: str, session: AsyncSession) -> None:
    """
    Update last_seen_at on an agent after successful dispatch.

    Batched: only updates if last_seen_at is older than 60s or NULL,
    to avoid excessive DB writes on high-frequency agent invocations.

    Forward-compatibility: no production callers yet. Called from tests to validate the
    batching logic. Wire into the agent dispatch path when dynamic agent routing
    needs last_seen_at tracking in agent_definitions.
    """
    from core.models.agent_definition import AgentDefinition

    now = datetime.now(timezone.utc)
    cutoff = datetime.fromtimestamp(now.timestamp() - 60, tz=timezone.utc)

    result = await session.execute(
        select(AgentDefinition).where(
            AgentDefinition.name == agent_name,
            AgentDefinition.is_active == True,  # noqa: E712
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        return

    # Normalize for comparison: SQLite stores offset-naive datetimes
    last = agent.last_seen_at
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)

    if last is None or last < cutoff:
        await session.execute(
            update(AgentDefinition)
            .where(AgentDefinition.id == agent.id)
            .values(last_seen_at=now)
        )
        await session.commit()


def create_master_graph(
    session: AsyncSession | None = None,
    _db_agents: list[Any] | None = None,
    checkpointer: MemorySaver | None = None,
) -> CompiledStateGraph:
    """
    Build and compile the master agent StateGraph with memory and sub-agent routing.

    Phase 6: When _db_agents is provided (loaded from agent_definitions table),
    dynamically wires agent nodes using importlib. When None, falls back to
    hardcoded agent wiring (backward compat).

    The session parameter is accepted for signature compat but DB loading
    is done externally via async create_master_graph_from_db(). This function
    is sync because LangGraph graph.compile() is sync.

    Returns a compiled graph ready for CopilotKit streaming or direct invocation.
    """
    global _keyword_to_agent

    graph = StateGraph(BlitzState)
    graph.add_node("load_memory", _load_memory_node)
    graph.add_node("master_agent", _master_node)
    graph.add_node("skill_executor", _skill_executor_node)
    graph.add_node("capabilities_node", _capabilities_node)

    from agents.delivery_router import delivery_router_node

    graph.add_node("delivery_router", delivery_router_node)
    graph.add_node("save_memory", _save_memory_node)

    route_map: dict[str, str] = {
        "master_agent": "master_agent",
        "skill_executor": "skill_executor",
        "capabilities_node": "capabilities_node",
    }
    agent_nodes: list[str] = []

    if _db_agents is not None and len(_db_agents) > 0:
        # Dynamic wiring from DB agent_definitions
        new_kw_map: dict[str, str] = {}

        for agent_def in _db_agents:
            name = agent_def.name
            if name == "master_agent":
                continue  # master_agent is always hardcoded

            try:
                module = importlib.import_module(agent_def.handler_module)
                handler = getattr(module, agent_def.handler_function)
                graph.add_node(name, handler)
                route_map[name] = name
                agent_nodes.append(name)

                # Build keyword routing map from agent's routing_keywords
                for kw in (agent_def.routing_keywords or []):
                    new_kw_map[kw.lower()] = name

                logger.debug("agent_wired_from_db", agent=name, module=agent_def.handler_module)
            except Exception as exc:
                logger.warning("agent_wiring_failed", agent=name, error=str(exc))

        _keyword_to_agent = new_kw_map
    else:
        # Fallback: hardcoded agent wiring (backward compat)
        from agents.subagents.calendar_agent import calendar_agent_node
        from agents.subagents.email_agent import email_agent_node
        from agents.subagents.project_agent import project_agent_node

        graph.add_node("email_agent", email_agent_node)
        graph.add_node("calendar_agent", calendar_agent_node)
        graph.add_node("project_agent", project_agent_node)

        route_map.update({
            "email_agent": "email_agent",
            "calendar_agent": "calendar_agent",
            "project_agent": "project_agent",
        })
        agent_nodes = ["email_agent", "calendar_agent", "project_agent"]

        # Clear DB keyword map -- use fallback
        _keyword_to_agent = {}

    graph.set_entry_point("load_memory")

    # Intent classification before master LLM -- sub-agent intents skip master entirely
    graph.add_conditional_edges(
        "load_memory",
        _pre_route,
        route_map,
    )

    # All paths converge at delivery_router -> save_memory -> END
    graph.add_edge("master_agent", "delivery_router")
    graph.add_edge("skill_executor", "delivery_router")
    graph.add_edge("capabilities_node", "delivery_router")
    for node_name in agent_nodes:
        graph.add_edge(node_name, "delivery_router")
    graph.add_edge("delivery_router", "save_memory")
    graph.add_edge("save_memory", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())


async def create_master_graph_from_db(session: AsyncSession) -> CompiledStateGraph:
    """
    Load active agents from agent_definitions DB and build graph dynamically.

    This is the async entry point that queries the DB, then delegates to
    create_master_graph() for the sync graph compilation.

    Only loads agents with status='active' AND is_active=True.
    Also updates last_seen_at on dispatch (called by wrapper nodes).
    """
    from core.models.agent_definition import AgentDefinition

    result = await session.execute(
        select(AgentDefinition).where(
            AgentDefinition.status == "active",
            AgentDefinition.is_active == True,  # noqa: E712
        )
    )
    active_agents = result.scalars().all()

    if not active_agents:
        logger.info("no_db_agents_found", fallback="hardcoded")
        return create_master_graph()

    return create_master_graph(_db_agents=active_agents)
