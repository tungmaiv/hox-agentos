"""
AI-Assisted Artifact Builder — LangGraph agent.

A conversational agent that helps admins create artifact definitions
(agents, tools, skills, MCP servers) through step-by-step Q&A.

Graph topology:
  START → route_intent (conditional entry point)
    |-> gather_type           (if artifact_type not set)
    |-> gather_details        (if type set but draft incomplete)
    |-> validate_and_present  (if draft looks ready)
  Each node -> END (runs once per user message turn)

This agent is separate from blitz_master. It has no memory nodes,
no user_id tracking, and no conversation persistence.
"""
import json
import re

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.artifact_builder_prompts import get_gather_type_prompt, get_system_prompt
from agents.artifact_builder_validation import validate_artifact_draft
from agents.state.artifact_builder_types import ArtifactBuilderState
from copilotkit.langgraph import copilotkit_emit_state
from core.config import get_llm

logger = structlog.get_logger(__name__)

# Keywords to detect artifact type from user messages.
# Uses word-boundary matching via regex to avoid false positives.
_TYPE_KEYWORDS: list[tuple[str, str]] = [
    (r"\bmcp[_ ]server\b", "mcp_server"),
    (r"\bmcp\b", "mcp_server"),
    (r"\bagent\b", "agent"),
    (r"\btool\b", "tool"),
    (r"\bskill\b", "skill"),
]

# Marker the LLM outputs when draft is ready for validation.
_DRAFT_COMPLETE_MARKER = "[DRAFT_COMPLETE]"


def _route_intent(state: ArtifactBuilderState) -> str:
    """Conditional entry point: decide which node to run next."""
    if state.get("artifact_type") is None:
        return "gather_type"
    if state.get("is_complete"):
        return "validate_and_present"
    return "gather_details"


def _detect_artifact_type(text: str) -> str | None:
    """Try to detect artifact type from user message text using word boundaries."""
    lower = text.lower()
    for pattern, atype in _TYPE_KEYWORDS:
        if re.search(pattern, lower):
            return atype
    return None


def _fix_triple_quotes(text: str) -> str:
    """Convert Python-style triple-quoted strings to valid JSON strings.

    LLMs sometimes output ``"key": \"\"\"\nmultiline\n\"\"\"`` which is
    invalid JSON.  We replace each ``\"\"\"...\"\"\"`` span with a properly
    escaped JSON string using ``\\n`` for newlines.
    """
    def _replacer(m: re.Match) -> str:
        inner = m.group(1)
        escaped = (
            inner
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\t", "\\t")
        )
        return f'"{escaped}"'

    return re.sub(r'"""([\s\S]*?)"""', _replacer, text)


def _extract_draft_from_response(content: str, current_draft: dict) -> dict:
    """Try to extract a JSON object from the AI response to update the draft.

    Looks for ```json ... ``` code blocks.  When the LLM outputs multiple
    code blocks (e.g. input_schema, output_schema, full definition), we
    pick the **largest** dict (by serialised length) — that is almost always
    the complete artifact definition rather than a nested sub-schema.

    If a code block contains Python-style triple-quoted strings (common LLM
    mistake for multiline content like instruction_markdown), we attempt to
    fix them before parsing.

    Falls back to current_draft if no valid JSON block is found.
    """
    pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
    matches = re.findall(pattern, content)

    best: dict | None = None
    best_size = -1

    for match in matches:
        raw = match.strip()
        # Try parsing as-is first, then with triple-quote fix
        for attempt in (raw, _fix_triple_quotes(raw)):
            try:
                parsed = json.loads(attempt)
                if isinstance(parsed, dict) and len(raw) > best_size:
                    best = parsed
                    best_size = len(raw)
                    break
            except (json.JSONDecodeError, ValueError):
                continue

    if best is not None:
        return {**current_draft, **best}
    return current_draft


async def _emit_builder_state(
    config: RunnableConfig,
    artifact_type: str | None,
    artifact_draft: dict | None,
    validation_errors: list[str],
    is_complete: bool,
) -> None:
    """Emit co-agent state to CopilotKit for live preview rendering."""
    await copilotkit_emit_state(config, {
        "artifact_type": artifact_type,
        "artifact_draft": artifact_draft,
        "validation_errors": validation_errors,
        "is_complete": is_complete,
    })


async def _gather_type_node(state: ArtifactBuilderState, config: RunnableConfig) -> dict:
    """Ask the user what type of artifact they want, or detect from message."""
    messages = state.get("messages", [])
    llm = get_llm("blitz/master")

    # Check if the user already mentioned a type in their last message
    if messages:
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            detected = _detect_artifact_type(last_msg.content)
            if detected:
                try:
                    sys_prompt = get_system_prompt(detected)
                    response = await llm.ainvoke([
                        SystemMessage(content=sys_prompt),
                        HumanMessage(content=last_msg.content),
                    ])
                except Exception as exc:
                    logger.error("llm_error", node="gather_type", error=str(exc))
                    await _emit_builder_state(config, detected, {}, [], False)
                    return {
                        "messages": [AIMessage(
                            content="I encountered an issue processing your request. "
                            "Could you try again?"
                        )],
                        "artifact_type": detected,
                        "artifact_draft": {},
                    }
                await _emit_builder_state(config, detected, {}, [], False)
                return {
                    "messages": [response],
                    "artifact_type": detected,
                    "artifact_draft": {},
                }

    # No type detected — ask explicitly
    try:
        response = await llm.ainvoke([
            SystemMessage(content=get_gather_type_prompt()),
            *messages,
        ])
    except Exception as exc:
        logger.error("llm_error", node="gather_type", error=str(exc))
        return {
            "messages": [AIMessage(
                content="I'm having trouble connecting. What type of artifact "
                "would you like to create? (agent, tool, skill, or MCP server)"
            )],
        }
    return {"messages": [response]}


async def _gather_details_node(state: ArtifactBuilderState, config: RunnableConfig) -> dict:
    """Ask type-specific questions and build the artifact draft progressively."""
    artifact_type = state["artifact_type"]
    messages = state.get("messages", [])
    current_draft = state.get("artifact_draft") or {}

    sys_prompt = get_system_prompt(artifact_type)

    draft_context = (
        f"\n\nCurrent artifact_draft so far:\n```json\n{json.dumps(current_draft, indent=2)}\n```\n"
        f"Continue asking questions for missing fields. When you have enough information "
        f"to create a valid definition, output the complete artifact_draft as a JSON code block "
        f"and include the marker {_DRAFT_COMPLETE_MARKER} in your response."
        if current_draft
        else "\n\nNo fields collected yet. Start by asking about the artifact's purpose and name."
    )

    try:
        llm = get_llm("blitz/master")
        response = await llm.ainvoke([
            SystemMessage(content=sys_prompt + draft_context),
            *messages,
        ])
    except Exception as exc:
        logger.error("llm_error", node="gather_details", error=str(exc))
        await _emit_builder_state(config, artifact_type, current_draft, [], False)
        return {
            "messages": [AIMessage(
                content="I encountered an issue. Could you repeat your last response?"
            )],
            "artifact_type": artifact_type,
            "artifact_draft": current_draft,
        }

    updated_draft = _extract_draft_from_response(response.content, current_draft)

    looks_complete = _DRAFT_COMPLETE_MARKER in response.content

    # If the LLM claims the draft is complete, run validation immediately.
    # This prevents the frontend from showing "Save to Registry" for an
    # invalid draft (e.g. missing required `name` field).
    validation_errors: list[str] = []
    if looks_complete:
        validation_errors = validate_artifact_draft(artifact_type, updated_draft)
        if validation_errors:
            looks_complete = False

    await _emit_builder_state(config, artifact_type, updated_draft, validation_errors, looks_complete)
    return {
        "messages": [response],
        "artifact_type": artifact_type,
        "artifact_draft": updated_draft,
        "validation_errors": validation_errors,
        "is_complete": looks_complete,
    }


async def _validate_and_present_node(state: ArtifactBuilderState, config: RunnableConfig) -> dict:
    """Validate the artifact draft against its Pydantic schema."""
    artifact_type = state["artifact_type"]
    draft = state.get("artifact_draft") or {}

    errors = validate_artifact_draft(artifact_type, draft)

    if errors:
        error_text = "\n".join(f"- {e}" for e in errors)
        msg = AIMessage(
            content=f"I found some issues with the definition:\n\n{error_text}\n\n"
            f"Let me help fix these. What would you like to adjust?"
        )
        await _emit_builder_state(config, artifact_type, draft, errors, False)
        return {
            "messages": [msg],
            "artifact_type": artifact_type,
            "artifact_draft": draft,
            "validation_errors": errors,
            "is_complete": False,
        }

    draft_json = json.dumps(draft, indent=2)
    msg = AIMessage(
        content=f"The artifact definition is valid and ready to save!\n\n"
        f"```json\n{draft_json}\n```\n\n"
        f"Click **Save** to create this {artifact_type.replace('_', ' ')} in the registry, "
        f"or tell me if you'd like to make any changes."
    )
    await _emit_builder_state(config, artifact_type, draft, [], True)
    return {
        "messages": [msg],
        "artifact_type": artifact_type,
        "artifact_draft": draft,
        "validation_errors": [],
        "is_complete": True,
    }


def create_artifact_builder_graph() -> CompiledStateGraph:
    """Build and compile the artifact builder LangGraph."""
    graph = StateGraph(ArtifactBuilderState)

    graph.add_node("gather_type", _gather_type_node)
    graph.add_node("gather_details", _gather_details_node)
    graph.add_node("validate_and_present", _validate_and_present_node)

    # Conditional entry point: routes to correct node based on state
    graph.set_conditional_entry_point(
        _route_intent,
        {
            "gather_type": "gather_type",
            "gather_details": "gather_details",
            "validate_and_present": "validate_and_present",
        },
    )

    graph.add_edge("gather_type", END)
    graph.add_edge("gather_details", END)
    graph.add_edge("validate_and_present", END)

    return graph.compile(checkpointer=MemorySaver())
