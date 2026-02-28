"""
AI-Assisted Artifact Builder — LangGraph agent.

A conversational agent that helps admins create artifact definitions
(agents, tools, skills, MCP servers) through step-by-step Q&A.

Graph topology:
  START → route_intent (conditional)
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
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.artifact_builder_prompts import get_gather_type_prompt, get_system_prompt
from agents.artifact_builder_validation import validate_artifact_draft
from agents.state.artifact_builder_types import ArtifactBuilderState
from core.config import get_llm

logger = structlog.get_logger(__name__)

# Keywords to detect artifact type from user messages
_TYPE_KEYWORDS: dict[str, str] = {
    "agent": "agent",
    "tool": "tool",
    "skill": "skill",
    "mcp": "mcp_server",
    "mcp_server": "mcp_server",
    "mcp server": "mcp_server",
    "server": "mcp_server",
}


def _route_intent(state: ArtifactBuilderState) -> str:
    """Conditional edge: decide which node to run next."""
    if state.get("artifact_type") is None:
        return "gather_type"
    if state.get("is_complete"):
        return "validate_and_present"
    return "gather_details"


def _detect_artifact_type(text: str) -> str | None:
    """Try to detect artifact type from user message text."""
    lower = text.lower()
    for keyword, atype in _TYPE_KEYWORDS.items():
        if keyword in lower:
            return atype
    return None


def _extract_draft_from_response(content: str, current_draft: dict) -> dict:
    """Try to extract a JSON object from the AI response to update the draft.

    Looks for ```json ... ``` code blocks. Falls back to current_draft if none found.
    """
    pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
    matches = re.findall(pattern, content)

    for match in matches:
        try:
            parsed = json.loads(match.strip())
            if isinstance(parsed, dict):
                merged = {**current_draft, **parsed}
                return merged
        except (json.JSONDecodeError, ValueError):
            continue

    return current_draft


async def _gather_type_node(state: ArtifactBuilderState) -> dict:
    """Ask the user what type of artifact they want, or detect from message."""
    messages = state.get("messages", [])

    # Check if the user already mentioned a type in their last message
    if messages:
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            detected = _detect_artifact_type(last_msg.content)
            if detected:
                llm = get_llm("blitz/master")
                sys_prompt = get_system_prompt(detected)
                response = await llm.ainvoke([
                    SystemMessage(content=sys_prompt),
                    HumanMessage(content=last_msg.content),
                ])
                return {
                    "messages": [response],
                    "artifact_type": detected,
                    "artifact_draft": {},
                }

    # No type detected — ask explicitly
    llm = get_llm("blitz/master")
    response = await llm.ainvoke([
        SystemMessage(content=get_gather_type_prompt()),
        *messages,
    ])
    return {"messages": [response]}


async def _gather_details_node(state: ArtifactBuilderState) -> dict:
    """Ask type-specific questions and build the artifact draft progressively."""
    artifact_type = state["artifact_type"]
    messages = state.get("messages", [])
    current_draft = state.get("artifact_draft") or {}

    sys_prompt = get_system_prompt(artifact_type)

    draft_context = (
        f"\n\nCurrent artifact_draft so far:\n```json\n{json.dumps(current_draft, indent=2)}\n```\n"
        f"Continue asking questions for missing fields. When you have enough information "
        f"to create a valid definition, output the complete artifact_draft as a JSON code block "
        f"and tell the user the definition is ready for review."
        if current_draft
        else "\n\nNo fields collected yet. Start by asking about the artifact's purpose and name."
    )

    llm = get_llm("blitz/master")
    response = await llm.ainvoke([
        SystemMessage(content=sys_prompt + draft_context),
        *messages,
    ])

    updated_draft = _extract_draft_from_response(response.content, current_draft)

    content_lower = response.content.lower()
    looks_complete = any(phrase in content_lower for phrase in [
        "ready for review", "definition is ready", "ready to save",
        "here's the complete", "here is the complete",
        "definition is complete", "looks complete",
    ])

    return {
        "messages": [response],
        "artifact_draft": updated_draft,
        "is_complete": looks_complete,
    }


async def _validate_and_present_node(state: ArtifactBuilderState) -> dict:
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
        return {
            "messages": [msg],
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
    return {
        "messages": [msg],
        "validation_errors": [],
        "is_complete": True,
    }


def create_artifact_builder_graph() -> CompiledStateGraph:
    """Build and compile the artifact builder LangGraph."""
    graph = StateGraph(ArtifactBuilderState)

    graph.add_node("gather_type", _gather_type_node)
    graph.add_node("gather_details", _gather_details_node)
    graph.add_node("validate_and_present", _validate_and_present_node)

    graph.set_entry_point("gather_type")

    graph.add_edge("gather_type", END)
    graph.add_edge("gather_details", END)
    graph.add_edge("validate_and_present", END)

    return graph.compile()
