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
    form_instruction_markdown: str | None
    form_skill_type: str | None
    # Name of clone source artifact (for context-aware AI greeting)
    clone_source_name: str | None
    # Phase 23 — Enhanced builder fields ──────────────────────────────────────
    # Top-k results from skill_repo_index cosine search (SKBLD-04)
    # Each dict: {name, description, repository_name, source_url, category, tags}
    similar_skills: list[dict] | None
    # SecurityReport serialized: {score, factors, recommendation, injection_matches}
    security_report: dict | None
    # Attribution for forked external skills, e.g. "skill-name@https://source-url"
    fork_source: str | None
    # Python stub text generated for tool artifacts (SKBLD-03)
    handler_code: str | None
    # Tool Resolver Node — populated for procedural skills only ────────────
    # Steps successfully matched to registry tools:
    # Each dict: {intent, tool, args_hint, permissions}
    resolved_tools: list[dict] | None
    # Steps with no matching tool (MISSING:intent-name):
    # Each dict: {intent, tool, args_hint, required_permissions}
    tool_gaps: list[dict] | None
