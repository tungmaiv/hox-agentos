# backend/tests/agents/test_artifact_builder.py
"""Tests for the artifact_builder LangGraph agent."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_config():
    """Return a minimal RunnableConfig for testing nodes that accept config."""
    return {"callbacks": []}


@pytest.fixture(autouse=True)
def _patch_emit_state():
    """Patch copilotkit_emit_state for all tests — prevents actual event dispatch."""
    with patch("agents.artifact_builder.copilotkit_emit_state", new_callable=AsyncMock):
        yield


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


def test_create_artifact_builder_graph_returns_compiled():
    """create_artifact_builder_graph returns a CompiledStateGraph."""
    from langgraph.graph.state import CompiledStateGraph
    with patch("agents.artifact_builder.get_llm") as mock_get_llm:
        mock_get_llm.return_value = MagicMock()
        from agents.artifact_builder import create_artifact_builder_graph
        graph = create_artifact_builder_graph()
    assert isinstance(graph, CompiledStateGraph)


def test_route_intent_no_type():
    """route_intent returns 'gather_type' when artifact_type is None."""
    from agents.artifact_builder import _route_intent
    state = {
        "messages": [], "artifact_type": None, "artifact_draft": None,
        "validation_errors": [], "is_complete": False,
    }
    assert _route_intent(state) == "gather_type"


def test_route_intent_no_draft():
    """route_intent returns 'gather_details' when type set but no draft."""
    from agents.artifact_builder import _route_intent
    state = {
        "messages": [], "artifact_type": "tool", "artifact_draft": None,
        "validation_errors": [], "is_complete": False,
    }
    assert _route_intent(state) == "gather_details"


def test_route_intent_has_draft_not_complete():
    """route_intent returns 'gather_details' when draft exists but incomplete."""
    from agents.artifact_builder import _route_intent
    state = {
        "messages": [], "artifact_type": "tool", "artifact_draft": {"name": "partial"},
        "validation_errors": [], "is_complete": False,
    }
    assert _route_intent(state) == "gather_details"


def test_route_intent_complete():
    """route_intent returns 'validate_and_present' when is_complete is True."""
    from agents.artifact_builder import _route_intent
    state = {
        "messages": [], "artifact_type": "tool",
        "artifact_draft": {"name": "done", "handler_type": "backend"},
        "validation_errors": [], "is_complete": True,
    }
    assert _route_intent(state) == "validate_and_present"


def test_get_system_prompt_returns_string_for_each_type():
    """get_system_prompt returns a non-empty string for each artifact type."""
    from agents.artifact_builder_prompts import get_system_prompt
    for artifact_type in ["agent", "tool", "skill", "mcp_server"]:
        prompt = get_system_prompt(artifact_type)
        assert isinstance(prompt, str)
        assert len(prompt) > 100, f"Prompt for {artifact_type} is too short"


def test_get_system_prompt_contains_schema_fields():
    """System prompts must mention the key fields for their artifact type.

    The agent prompt was redesigned in Phase 12-02 to focus on fill_form fields
    (model_alias, system_prompt) rather than the underlying registry schema fields
    (routing_keywords, handler_module) — those are now managed by the form directly.
    Tool, skill, and mcp_server prompts retain their full schema field documentation.
    """
    from agents.artifact_builder_prompts import get_system_prompt
    agent_prompt = get_system_prompt("agent")
    # Agent prompt focuses on fill_form fields for the new wizard
    assert "model_alias" in agent_prompt
    assert "system_prompt" in agent_prompt

    tool_prompt = get_system_prompt("tool")
    assert "handler_type" in tool_prompt
    assert "input_schema" in tool_prompt

    skill_prompt = get_system_prompt("skill")
    assert "skill_type" in skill_prompt
    assert "procedure_json" in skill_prompt

    mcp_prompt = get_system_prompt("mcp_server")
    assert "url" in mcp_prompt


def test_get_gather_type_prompt():
    """get_gather_type_prompt returns a non-empty string."""
    from agents.artifact_builder_prompts import get_gather_type_prompt
    prompt = get_gather_type_prompt()
    assert isinstance(prompt, str)
    assert "agent" in prompt.lower()
    assert "tool" in prompt.lower()
    assert "skill" in prompt.lower()


@pytest.mark.asyncio
async def test_gather_type_detects_tool_from_message():
    """gather_type node detects 'tool' from user message and sets artifact_type."""
    from langchain_core.messages import HumanMessage, AIMessage

    mock_response = AIMessage(content="Great! Let's create a tool. What will it do?")

    with patch("agents.artifact_builder.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_get_llm.return_value = mock_llm

        from agents.artifact_builder import _gather_type_node

        state = {
            "messages": [HumanMessage(content="I need a tool that searches CRM contacts")],
            "artifact_type": None,
            "artifact_draft": None,
            "validation_errors": [],
            "is_complete": False,
        }
        result = await _gather_type_node(state, _mock_config())

    assert result["artifact_type"] == "tool"
    assert result["artifact_draft"] == {}
    assert len(result["messages"]) == 1


@pytest.mark.asyncio
async def test_validate_and_present_valid_draft():
    """validate_and_present marks valid draft as complete."""
    from agents.artifact_builder import _validate_and_present_node

    state = {
        "messages": [],
        "artifact_type": "agent",
        "artifact_draft": {"name": "test_agent", "description": "A test"},
        "validation_errors": [],
        "is_complete": True,
    }
    result = await _validate_and_present_node(state, _mock_config())

    assert result["is_complete"] is True
    assert result["validation_errors"] == []
    assert "valid" in result["messages"][0].content.lower() or "ready" in result["messages"][0].content.lower()


@pytest.mark.asyncio
async def test_validate_and_present_invalid_draft():
    """validate_and_present catches invalid draft and returns errors."""
    from agents.artifact_builder import _validate_and_present_node

    state = {
        "messages": [],
        "artifact_type": "skill",
        "artifact_draft": {"name": "bad_skill", "skill_type": "instructional"},
        "validation_errors": [],
        "is_complete": True,
    }
    result = await _validate_and_present_node(state, _mock_config())

    assert result["is_complete"] is False
    assert len(result["validation_errors"]) > 0
    assert any("instruction_markdown" in e.lower() for e in result["validation_errors"])


# ---------------------------------------------------------------------------
# _extract_draft_from_response tests
# ---------------------------------------------------------------------------


def test_extract_draft_from_json_code_block():
    """Extracts JSON from a ```json code block."""
    from agents.artifact_builder import _extract_draft_from_response
    content = 'Here is the draft:\n```json\n{"name": "test", "version": "1.0.0"}\n```\nLooks good?'
    result = _extract_draft_from_response(content, {})
    assert result == {"name": "test", "version": "1.0.0"}


def test_extract_draft_from_plain_code_block():
    """Extracts JSON from a ``` code block without json tag."""
    from agents.artifact_builder import _extract_draft_from_response
    content = 'Draft:\n```\n{"name": "x"}\n```'
    result = _extract_draft_from_response(content, {})
    assert result == {"name": "x"}


def test_extract_draft_merges_with_existing():
    """New fields merge with existing draft, overriding shared keys."""
    from agents.artifact_builder import _extract_draft_from_response
    content = '```json\n{"description": "new", "version": "2.0.0"}\n```'
    result = _extract_draft_from_response(content, {"name": "old", "version": "1.0.0"})
    assert result == {"name": "old", "description": "new", "version": "2.0.0"}


def test_extract_draft_malformed_json_returns_current():
    """Malformed JSON falls back to current draft."""
    from agents.artifact_builder import _extract_draft_from_response
    content = '```json\n{invalid json}\n```'
    current = {"name": "keep"}
    result = _extract_draft_from_response(content, current)
    assert result == current


def test_extract_draft_no_code_block_returns_current():
    """No code block at all returns current draft unchanged."""
    from agents.artifact_builder import _extract_draft_from_response
    result = _extract_draft_from_response("Just some text", {"name": "unchanged"})
    assert result == {"name": "unchanged"}


def test_extract_draft_fixes_triple_quoted_strings():
    """LLMs sometimes use Python triple-quotes for multiline values — we fix them."""
    from agents.artifact_builder import _extract_draft_from_response

    content = (
        '```json\n'
        '{\n'
        '  "name": "daily_summary",\n'
        '  "skill_type": "instructional",\n'
        '  "instruction_markdown": """\n'
        '# Guide\n'
        '## Step 1\n'
        'Do something.\n'
        '"""\n'
        '}\n'
        '```'
    )
    result = _extract_draft_from_response(content, {})
    assert result["name"] == "daily_summary"
    assert result["skill_type"] == "instructional"
    assert "# Guide" in result["instruction_markdown"]
    assert "Step 1" in result["instruction_markdown"]


def test_extract_draft_prefers_largest_json_block():
    """When multiple JSON blocks exist, pick the largest (complete definition)."""
    from agents.artifact_builder import _extract_draft_from_response

    content = (
        'Here is the input schema:\n'
        '```json\n{"type": "object", "properties": {"q": {"type": "string"}}}\n```\n'
        '\nAnd the full definition:\n'
        '```json\n{"name": "crm_search", "handler_type": "backend", '
        '"input_schema": {"type": "object", "properties": {"q": {"type": "string"}}}}\n```\n'
    )
    result = _extract_draft_from_response(content, {})
    # Should pick the larger block (complete definition), not the input_schema
    assert result["name"] == "crm_search"
    assert result["handler_type"] == "backend"
    assert "input_schema" in result


# ---------------------------------------------------------------------------
# gather_details validation-on-complete tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gather_details_validates_before_marking_complete():
    """When LLM says DRAFT_COMPLETE but draft is invalid, is_complete stays False."""
    from langchain_core.messages import HumanMessage, AIMessage

    # Draft with DRAFT_COMPLETE marker but missing required 'name' field
    mock_response = AIMessage(
        content='```json\n{"handler_type": "backend", "description": "search stuff"}\n```\n\n[DRAFT_COMPLETE]'
    )

    with patch("agents.artifact_builder.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        # bind_tools returns itself so ainvoke is still accessible
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_get_llm.return_value = mock_llm

        from agents.artifact_builder import _gather_details_node

        state = {
            "messages": [HumanMessage(content="That looks good")],
            "artifact_type": "tool",
            "artifact_draft": {},
            "validation_errors": [],
            "is_complete": False,
        }
        result = await _gather_details_node(state, _mock_config())

    # Should NOT be marked complete since 'name' is missing
    assert result["is_complete"] is False
    assert len(result["validation_errors"]) > 0
    assert any("name" in e.lower() for e in result["validation_errors"])


# ---------------------------------------------------------------------------
# _detect_artifact_type word-boundary tests
# ---------------------------------------------------------------------------


def test_detect_type_tool_word_boundary():
    """'tool' matches as a whole word."""
    from agents.artifact_builder import _detect_artifact_type
    assert _detect_artifact_type("I need a tool that searches") == "tool"


def test_detect_type_server_does_not_match():
    """'server' alone should NOT match mcp_server (only 'mcp' or 'mcp server' do)."""
    from agents.artifact_builder import _detect_artifact_type
    assert _detect_artifact_type("I need a tool that connects to our server") == "tool"


def test_detect_type_mcp_server_matches():
    """'mcp server' matches mcp_server."""
    from agents.artifact_builder import _detect_artifact_type
    assert _detect_artifact_type("I want to add an mcp server") == "mcp_server"


def test_detect_type_mcp_alone_matches():
    """'mcp' alone matches mcp_server."""
    from agents.artifact_builder import _detect_artifact_type
    assert _detect_artifact_type("Register an MCP endpoint") == "mcp_server"


# ---------------------------------------------------------------------------
# _gather_details_node tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gather_details_extracts_draft():
    """gather_details node extracts draft from LLM response."""
    from langchain_core.messages import HumanMessage, AIMessage

    mock_response = AIMessage(
        content='Here is the draft:\n```json\n{"name": "crm_search", "handler_type": "mcp"}\n```\nWhat else?'
    )

    with patch("agents.artifact_builder.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_get_llm.return_value = mock_llm

        from agents.artifact_builder import _gather_details_node

        state = {
            "messages": [HumanMessage(content="It should search CRM contacts")],
            "artifact_type": "tool",
            "artifact_draft": {},
            "validation_errors": [],
            "is_complete": False,
        }
        result = await _gather_details_node(state, _mock_config())

    assert result["artifact_draft"]["name"] == "crm_search"
    assert result["is_complete"] is False


@pytest.mark.asyncio
async def test_gather_details_detects_draft_complete_marker():
    """gather_details sets is_complete when LLM outputs [DRAFT_COMPLETE] marker."""
    from langchain_core.messages import HumanMessage, AIMessage

    mock_response = AIMessage(
        content='```json\n{"name": "test_agent", "description": "A test"}\n```\n\n[DRAFT_COMPLETE]'
    )

    with patch("agents.artifact_builder.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_get_llm.return_value = mock_llm

        from agents.artifact_builder import _gather_details_node

        state = {
            "messages": [HumanMessage(content="Name it test_agent, it's for testing")],
            "artifact_type": "agent",
            "artifact_draft": {},
            "validation_errors": [],
            "is_complete": False,
        }
        result = await _gather_details_node(state, _mock_config())

    assert result["is_complete"] is True
    assert result["artifact_draft"]["name"] == "test_agent"


@pytest.mark.asyncio
async def test_gather_details_llm_error_returns_friendly_message():
    """gather_details handles LLM errors gracefully."""
    from langchain_core.messages import HumanMessage

    with patch("agents.artifact_builder.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM timeout"))
        mock_get_llm.return_value = mock_llm

        from agents.artifact_builder import _gather_details_node

        state = {
            "messages": [HumanMessage(content="Some input")],
            "artifact_type": "tool",
            "artifact_draft": {"name": "existing"},
            "validation_errors": [],
            "is_complete": False,
        }
        result = await _gather_details_node(state, _mock_config())

    assert "issue" in result["messages"][0].content.lower() or "encountered" in result["messages"][0].content.lower()
    assert result["artifact_draft"] == {"name": "existing"}


@pytest.mark.asyncio
async def test_gather_type_llm_error_returns_friendly_message():
    """gather_type handles LLM errors gracefully when no type detected."""
    from langchain_core.messages import HumanMessage

    with patch("agents.artifact_builder.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("Connection refused"))
        mock_get_llm.return_value = mock_llm

        from agents.artifact_builder import _gather_type_node

        state = {
            "messages": [HumanMessage(content="hello")],
            "artifact_type": None,
            "artifact_draft": None,
            "validation_errors": [],
            "is_complete": False,
        }
        result = await _gather_type_node(state, _mock_config())

    assert "trouble" in result["messages"][0].content.lower() or "having" in result["messages"][0].content.lower()
