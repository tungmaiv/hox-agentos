# backend/agents/state/artifact_builder_types.py
"""
ArtifactBuilderState — state for the AI-assisted artifact builder agent.

Separate from BlitzState because this agent has no memory, no user_id,
no conversation persistence. It is a stateless builder that generates
artifact definitions through conversational Q&A.

Extended in Phase 12 to include form_* fields for bidirectional sync
with the frontend wizard form via the fill_form tool.
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
    # Form field values for bidirectional sync — the fill_form tool writes here
    form_name: str | None
    form_description: str | None
    form_version: str | None
    form_required_permissions: list[str] | None
    form_model_alias: str | None
    form_system_prompt: str | None
    form_handler_module: str | None
    form_sandbox_required: bool | None
    form_entry_point: str | None
    form_url: str | None
    # Name of clone source artifact (for context-aware AI greeting)
    clone_source_name: str | None
