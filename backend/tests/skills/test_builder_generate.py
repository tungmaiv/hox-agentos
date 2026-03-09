"""
Tests for skill builder content generation node.

SKBLD-01: Builder generates substantive procedural skill content (procedure_json with steps)
SKBLD-02: Builder generates substantive instructional skill content (instruction_markdown)
SKBLD-03: Builder generates Python handler stub for tool artifacts (handler_code)
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agents.artifact_builder import _generate_skill_content_node
from agents.state.artifact_builder_types import ArtifactBuilderState


def _make_state(artifact_type: str, draft: dict) -> ArtifactBuilderState:
    """Build a minimal ArtifactBuilderState for testing."""
    return ArtifactBuilderState(
        messages=[HumanMessage(content="Please generate the content")],
        artifact_type=artifact_type,
        artifact_draft=draft,
        validation_errors=[],
        is_complete=False,
        form_name=draft.get("name"),
        form_description=draft.get("description"),
        form_version=None,
        form_required_permissions=None,
        form_model_alias=None,
        form_system_prompt=None,
        form_handler_module=None,
        form_sandbox_required=None,
        form_entry_point=None,
        form_url=None,
        clone_source_name=None,
        similar_skills=None,
        security_report=None,
        fork_source=None,
        handler_code=None,
    )


def _make_config() -> dict:
    """Return a minimal RunnableConfig for the node."""
    return {"configurable": {"thread_id": "test-thread"}}


@pytest.mark.asyncio
async def test_generate_procedural_skill_content() -> None:
    """SKBLD-01: Node calls LLM and sets procedure_json with steps array in artifact_draft."""
    procedure_response = json.dumps({
        "procedure_json": {
            "schema_version": "1.0",
            "steps": [
                {"step": 1, "tool": "email.fetch", "prompt": "Fetch emails"},
                {"step": 2, "tool": "llm.summarize", "prompt": "Summarize: {{step1.output}}"},
            ],
        }
    })

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AIMessage(content=f"```json\n{procedure_response}\n```")

    state = _make_state(
        "skill",
        {"name": "email_digest", "description": "Summarize daily emails", "skill_type": "procedural"},
    )
    config = _make_config()

    with patch("agents.artifact_builder.get_llm", return_value=mock_llm), \
         patch("agents.artifact_builder.copilotkit_emit_state", new_callable=AsyncMock):
        result = await _generate_skill_content_node(state, config)

    assert "artifact_draft" in result
    draft = result["artifact_draft"]
    assert "procedure_json" in draft, "procedure_json must be set in artifact_draft"
    assert "steps" in draft["procedure_json"], "procedure_json must have steps"
    assert len(draft["procedure_json"]["steps"]) >= 1, "steps must be non-empty"


@pytest.mark.asyncio
async def test_generate_instructional_skill_content() -> None:
    """SKBLD-02: Node calls LLM and sets instruction_markdown as non-empty string in artifact_draft."""
    instruction_response = "# Email Digest\n\nThis skill fetches and summarizes your daily emails.\n\n## Usage\nTrigger with /digest command.\n"

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AIMessage(content=instruction_response)

    state = _make_state(
        "skill",
        {"name": "email_digest", "description": "Summarize daily emails", "skill_type": "instructional"},
    )
    config = _make_config()

    with patch("agents.artifact_builder.get_llm", return_value=mock_llm), \
         patch("agents.artifact_builder.copilotkit_emit_state", new_callable=AsyncMock):
        result = await _generate_skill_content_node(state, config)

    assert "artifact_draft" in result
    draft = result["artifact_draft"]
    assert "instruction_markdown" in draft, "instruction_markdown must be set in artifact_draft"
    assert isinstance(draft["instruction_markdown"], str), "instruction_markdown must be a string"
    assert len(draft["instruction_markdown"]) > 0, "instruction_markdown must be non-empty"


@pytest.mark.asyncio
async def test_generate_tool_stub() -> None:
    """SKBLD-03: Node generates Python stub and sets handler_code in state."""
    python_stub = '''```python
from pydantic import BaseModel


class InputModel(BaseModel):
    query: str


class OutputModel(BaseModel):
    result: str


async def handler(input: InputModel) -> OutputModel:
    """Handle the tool call."""
    return OutputModel(result=f"Processed: {input.query}")
```'''

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AIMessage(content=python_stub)

    state = _make_state(
        "tool",
        {"name": "search_tool", "description": "Search for information"},
    )
    config = _make_config()

    with patch("agents.artifact_builder.get_llm", return_value=mock_llm), \
         patch("agents.artifact_builder.copilotkit_emit_state", new_callable=AsyncMock):
        result = await _generate_skill_content_node(state, config)

    assert "handler_code" in result, "handler_code must be returned in state"
    assert result["handler_code"] is not None, "handler_code must not be None"
    assert "InputModel" in result["handler_code"], "handler_code must contain InputModel class"
    assert "OutputModel" in result["handler_code"], "handler_code must contain OutputModel class"
