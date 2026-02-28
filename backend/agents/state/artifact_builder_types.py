# backend/agents/state/artifact_builder_types.py
"""
ArtifactBuilderState — state for the AI-assisted artifact builder agent.

Separate from BlitzState because this agent has no memory, no user_id,
no conversation persistence. It is a stateless builder that generates
artifact definitions through conversational Q&A.
"""
from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class ArtifactBuilderState(TypedDict):
    """State for the artifact builder LangGraph agent."""

    messages: Annotated[list[BaseMessage], add_messages]
    # "agent" | "tool" | "skill" | "mcp_server" — set after first user message
    artifact_type: str | None
    # Progressive artifact definition — grows as AI asks questions
    artifact_draft: dict | None
    # Validation errors from last Pydantic check (empty = valid)
    validation_errors: list[str]
    # True when artifact_draft passes schema validation
    is_complete: bool
