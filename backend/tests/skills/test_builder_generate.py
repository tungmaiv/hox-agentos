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
async def test_generate_instructional_syncs_form_field() -> None:
    """SKBLD-02b: instruction_markdown is also returned as form_instruction_markdown for form sync."""
    instruction_response = "# Email Digest\n\n## Steps\n1. Check emails\n2. Summarize\n"

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AIMessage(content=instruction_response)

    state = _make_state(
        "skill",
        {"name": "email-digest", "description": "Summarize daily emails", "skill_type": "instructional"},
    )

    with patch("agents.artifact_builder.get_llm", return_value=mock_llm), \
         patch("agents.artifact_builder.copilotkit_emit_state", new_callable=AsyncMock):
        result = await _generate_skill_content_node(state, _make_config())

    # form_instruction_markdown must be in the returned state so the frontend form field updates
    assert "form_instruction_markdown" in result, (
        "form_instruction_markdown must be in returned state to sync the Instructions form field"
    )
    assert "# Email Digest" in result["form_instruction_markdown"]


@pytest.mark.asyncio
async def test_generate_instructional_emits_form_field_to_copilotkit() -> None:
    """SKBLD-02c: _emit_builder_state is called with form_instruction_markdown so CopilotKit updates the form."""
    from unittest.mock import call

    instruction_response = "# My Skill\n\n## Steps\n1. Do something\n"

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AIMessage(content=instruction_response)

    state = _make_state(
        "skill",
        {"name": "my-skill", "description": "Does something", "skill_type": "instructional"},
    )

    emit_mock = AsyncMock()
    with patch("agents.artifact_builder.get_llm", return_value=mock_llm), \
         patch("agents.artifact_builder.copilotkit_emit_state", emit_mock):
        await _generate_skill_content_node(state, _make_config())

    # The emit must include form_instruction_markdown
    assert emit_mock.called, "copilotkit_emit_state must be called"
    emitted_state = emit_mock.call_args[0][1]  # second positional arg is the state dict
    assert "form_instruction_markdown" in emitted_state, (
        "emitted state must contain form_instruction_markdown"
    )
    assert "# My Skill" in emitted_state["form_instruction_markdown"]


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


@pytest.mark.asyncio
async def test_generate_procedural_sets_slash_command() -> None:
    """SKBLD-04: Node auto-derives slash_command from name for procedural skills."""
    procedure_response = json.dumps({
        "procedure_json": {
            "schema_version": "1.0",
            "steps": [
                {"step": 1, "tool": "calendar.check", "prompt": "Check calendar"},
            ],
        }
    })

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AIMessage(content=f"```json\n{procedure_response}\n```")

    state = _make_state(
        "skill",
        {"name": "daily-standup", "description": "Run daily standup", "skill_type": "procedural"},
    )

    with patch("agents.artifact_builder.get_llm", return_value=mock_llm), \
         patch("agents.artifact_builder.copilotkit_emit_state", new_callable=AsyncMock):
        result = await _generate_skill_content_node(state, _make_config())

    draft = result["artifact_draft"]
    assert draft.get("slash_command") == "/daily-standup", (
        "slash_command must be auto-derived as /<name>"
    )


@pytest.mark.asyncio
async def test_generate_procedural_sets_source_type_user_created() -> None:
    """SKBLD-05: Node sets source_type to 'user_created' for wizard-created skills."""
    procedure_response = json.dumps({
        "procedure_json": {
            "schema_version": "1.0",
            "steps": [{"step": 1, "tool": "llm.chat", "prompt": "Hello"}],
        }
    })

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AIMessage(content=f"```json\n{procedure_response}\n```")

    state = _make_state(
        "skill",
        {"name": "my-skill", "description": "Does something", "skill_type": "procedural"},
    )

    with patch("agents.artifact_builder.get_llm", return_value=mock_llm), \
         patch("agents.artifact_builder.copilotkit_emit_state", new_callable=AsyncMock):
        result = await _generate_skill_content_node(state, _make_config())

    draft = result["artifact_draft"]
    assert draft.get("source_type") == "user_created", (
        "source_type must be 'user_created' for wizard-created skills"
    )


@pytest.mark.asyncio
async def test_generate_procedural_strips_null_step_fields() -> None:
    """SKBLD-06: Node strips null fields from procedure_json steps (retry, timeout, save_as)."""
    procedure_response = json.dumps({
        "procedure_json": {
            "schema_version": "1.0",
            "steps": [
                {
                    "step": 1,
                    "tool": "calendar.check",
                    "prompt": "Check calendar",
                    "retry": None,
                    "timeout": None,
                    "save_as": None,
                },
            ],
        }
    })

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AIMessage(content=f"```json\n{procedure_response}\n```")

    state = _make_state(
        "skill",
        {"name": "calendar-check", "description": "Check calendar", "skill_type": "procedural"},
    )

    with patch("agents.artifact_builder.get_llm", return_value=mock_llm), \
         patch("agents.artifact_builder.copilotkit_emit_state", new_callable=AsyncMock):
        result = await _generate_skill_content_node(state, _make_config())

    draft = result["artifact_draft"]
    steps = draft["procedure_json"]["steps"]
    assert len(steps) == 1
    step = steps[0]
    assert "retry" not in step, "null 'retry' must be stripped from steps"
    assert "timeout" not in step, "null 'timeout' must be stripped from steps"
    assert "save_as" not in step, "null 'save_as' must be stripped from steps"


@pytest.mark.asyncio
async def test_generate_instructional_sets_source_type_user_created() -> None:
    """SKBLD-05b: Node sets source_type to 'user_created' for instructional skills too."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AIMessage(content="# My Skill\n\nDoes something useful.\n")

    state = _make_state(
        "skill",
        {"name": "my-skill", "description": "Does something", "skill_type": "instructional"},
    )

    with patch("agents.artifact_builder.get_llm", return_value=mock_llm), \
         patch("agents.artifact_builder.copilotkit_emit_state", new_callable=AsyncMock):
        result = await _generate_skill_content_node(state, _make_config())

    draft = result["artifact_draft"]
    assert draft.get("source_type") == "user_created", (
        "source_type must be 'user_created' for wizard-created skills"
    )
    assert draft.get("slash_command") == "/my-skill", (
        "slash_command must be auto-derived for instructional skills too"
    )
