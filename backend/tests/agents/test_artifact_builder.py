# backend/tests/agents/test_artifact_builder.py
"""Tests for the artifact_builder LangGraph agent."""
import pytest


def test_artifact_builder_state_has_required_fields():
    """ArtifactBuilderState must declare all fields from the design."""
    from agents.state.artifact_builder_types import ArtifactBuilderState

    annotations = ArtifactBuilderState.__annotations__
    assert "messages" in annotations
    assert "artifact_type" in annotations
    assert "artifact_draft" in annotations
    assert "validation_errors" in annotations
    assert "is_complete" in annotations


def test_artifact_builder_state_messages_has_reducer():
    """messages field must use add_messages reducer for LangGraph accumulation."""
    from agents.state.artifact_builder_types import ArtifactBuilderState
    import typing

    ann = typing.get_type_hints(ArtifactBuilderState, include_extras=True)
    messages_ann = ann["messages"]
    assert hasattr(messages_ann, "__metadata__"), (
        "messages must be Annotated with add_messages reducer"
    )


def test_validate_draft_valid_agent():
    """Valid agent draft passes validation."""
    from agents.artifact_builder_validation import validate_artifact_draft
    draft = {"name": "test_agent", "description": "A test agent"}
    errors = validate_artifact_draft("agent", draft)
    assert errors == []


def test_validate_draft_missing_agent_name():
    """Agent draft without name fails validation."""
    from agents.artifact_builder_validation import validate_artifact_draft
    draft = {"description": "No name"}
    errors = validate_artifact_draft("agent", draft)
    assert len(errors) > 0
    assert any("name" in e.lower() for e in errors)


def test_validate_draft_valid_tool():
    """Valid tool draft with handler_type passes."""
    from agents.artifact_builder_validation import validate_artifact_draft
    draft = {"name": "crm_search", "handler_type": "mcp", "mcp_tool_name": "search_contacts"}
    errors = validate_artifact_draft("tool", draft)
    assert errors == []


def test_validate_draft_invalid_tool_handler_type():
    """Tool with invalid handler_type fails."""
    from agents.artifact_builder_validation import validate_artifact_draft
    draft = {"name": "bad_tool", "handler_type": "invalid"}
    errors = validate_artifact_draft("tool", draft)
    assert len(errors) > 0


def test_validate_draft_skill_instructional_missing_markdown():
    """Instructional skill without instruction_markdown fails cross-field validation."""
    from agents.artifact_builder_validation import validate_artifact_draft
    draft = {"name": "test_skill", "skill_type": "instructional"}
    errors = validate_artifact_draft("skill", draft)
    assert any("instruction_markdown" in e.lower() for e in errors)


def test_validate_draft_skill_procedural_valid():
    """Valid procedural skill passes."""
    from agents.artifact_builder_validation import validate_artifact_draft
    draft = {
        "name": "deploy_skill", "skill_type": "procedural",
        "procedure_json": {"steps": [{"tool": "deploy", "args": {}}]},
    }
    errors = validate_artifact_draft("skill", draft)
    assert errors == []


def test_validate_draft_mcp_server_valid():
    """Valid MCP server draft passes."""
    from agents.artifact_builder_validation import validate_artifact_draft
    draft = {"name": "crm", "url": "http://mcp-crm:8001"}
    errors = validate_artifact_draft("mcp_server", draft)
    assert errors == []


def test_validate_draft_mcp_server_missing_url():
    """MCP server without url fails."""
    from agents.artifact_builder_validation import validate_artifact_draft
    draft = {"name": "crm"}
    errors = validate_artifact_draft("mcp_server", draft)
    assert any("url" in e.lower() for e in errors)


def test_validate_draft_unknown_type():
    """Unknown artifact type returns error."""
    from agents.artifact_builder_validation import validate_artifact_draft
    errors = validate_artifact_draft("unknown", {"name": "x"})
    assert any("unknown" in e.lower() for e in errors)


def test_validate_handler_module_prefix():
    """Handler module outside allowed prefixes is flagged."""
    from agents.artifact_builder_validation import validate_artifact_draft
    draft = {"name": "bad_agent", "handler_module": "os.system", "handler_function": "run"}
    errors = validate_artifact_draft("agent", draft)
    assert any("handler_module" in e.lower() or "prefix" in e.lower() for e in errors)
