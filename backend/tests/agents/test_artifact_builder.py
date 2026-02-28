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
