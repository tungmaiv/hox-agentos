# AI-Assisted Artifact Builder — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a conversational CopilotKit co-agent that helps admins create agents, tools, skills, and MCP servers through natural language dialogue with live preview and Pydantic validation.

**Architecture:** A new `artifact_builder` LangGraph agent (separate from `blitz_master`) registered in `gateway/runtime.py`. Frontend split-panel page at `/admin/create` with CopilotChat (left) and live preview (right). The AI asks type-specific questions, builds `artifact_draft` progressively, validates against Pydantic schemas, and the admin saves via existing admin API endpoints.

**Tech Stack:** LangGraph (StateGraph), CopilotKit (`useCoAgent`, `useCoAgentStateRender`), FastAPI, Pydantic v2, Next.js 15 App Router

**Canonical test command:** `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q`
**Canonical build command:** `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm run build`

---

## Task 1: ArtifactBuilderState TypedDict

**Files:**
- Create: `backend/agents/state/artifact_builder_types.py`
- Test: `backend/tests/agents/test_artifact_builder.py`

**Step 1: Write the failing test**

```python
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
    # Annotated types have __metadata__
    assert hasattr(messages_ann, "__metadata__"), (
        "messages must be Annotated with add_messages reducer"
    )
```

**Step 2: Run test to verify it fails**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.state.artifact_builder_types'`

**Step 3: Write minimal implementation**

```python
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
```

**Step 4: Run test to verify it passes**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py -v`
Expected: 2 PASSED

**Step 5: Commit**

```bash
git add backend/agents/state/artifact_builder_types.py backend/tests/agents/test_artifact_builder.py
git commit -m "feat(artifact-builder): add ArtifactBuilderState TypedDict"
```

---

## Task 2: Validation Helper Module

**Files:**
- Create: `backend/agents/artifact_builder_validation.py`
- Test: `backend/tests/agents/test_artifact_builder.py` (append)

This module validates `artifact_draft` dicts against the corresponding Pydantic create schemas. It's used by the `validate_and_present` graph node.

**Step 1: Write the failing tests**

Append to `backend/tests/agents/test_artifact_builder.py`:

```python
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

    draft = {
        "name": "crm_search",
        "handler_type": "mcp",
        "mcp_tool_name": "search_contacts",
    }
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
        "name": "deploy_skill",
        "skill_type": "procedural",
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

    draft = {
        "name": "bad_agent",
        "handler_module": "os.system",
        "handler_function": "run",
    }
    errors = validate_artifact_draft("agent", draft)
    assert any("handler_module" in e.lower() or "prefix" in e.lower() for e in errors)
```

**Step 2: Run test to verify they fail**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py -v`
Expected: 10 new tests FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# backend/agents/artifact_builder_validation.py
"""
Validation helpers for the artifact builder agent.

Validates artifact_draft dicts against the corresponding Pydantic create schemas.
Returns a list of human-readable error strings (empty = valid).
"""
from typing import Any

from pydantic import ValidationError

from core.schemas.registry import (
    AgentDefinitionCreate,
    SkillDefinitionCreate,
    ToolDefinitionCreate,
)

# McpServerCreate is defined in the MCP routes module, not in registry schemas.
# Import it from there to avoid duplication.
from api.routes.mcp_servers import McpServerCreate

_ALLOWED_HANDLER_PREFIXES = (
    "tools.", "agents.", "skills.", "mcp.", "gateway.",
)

_SCHEMA_MAP: dict[str, type] = {
    "agent": AgentDefinitionCreate,
    "tool": ToolDefinitionCreate,
    "skill": SkillDefinitionCreate,
    "mcp_server": McpServerCreate,
}


def validate_artifact_draft(
    artifact_type: str, draft: dict[str, Any]
) -> list[str]:
    """Validate an artifact draft against its Pydantic schema.

    Returns a list of human-readable error strings. Empty list = valid.

    Also checks:
    - handler_module prefix is in the allowed list (agents, tools)
    """
    schema_cls = _SCHEMA_MAP.get(artifact_type)
    if schema_cls is None:
        return [f"Unknown artifact type: '{artifact_type}'. Valid: {list(_SCHEMA_MAP.keys())}"]

    errors: list[str] = []

    # Pydantic schema validation
    try:
        schema_cls.model_validate(draft)
    except ValidationError as exc:
        for err in exc.errors():
            field = " -> ".join(str(loc) for loc in err["loc"]) if err["loc"] else "root"
            errors.append(f"{field}: {err['msg']}")
    except Exception as exc:
        errors.append(f"Validation error: {exc}")

    # Extra: handler_module prefix check (for agents and tools)
    handler_module = draft.get("handler_module")
    if handler_module and not handler_module.startswith(_ALLOWED_HANDLER_PREFIXES):
        errors.append(
            f"handler_module '{handler_module}' must start with one of: "
            f"{', '.join(_ALLOWED_HANDLER_PREFIXES)}"
        )

    return errors
```

**Step 4: Run test to verify they pass**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py -v`
Expected: 12 PASSED

**Step 5: Commit**

```bash
git add backend/agents/artifact_builder_validation.py backend/tests/agents/test_artifact_builder.py
git commit -m "feat(artifact-builder): add validation helper with Pydantic schema checks"
```

---

## Task 3: System Prompts Module

**Files:**
- Create: `backend/agents/artifact_builder_prompts.py`
- Test: `backend/tests/agents/test_artifact_builder.py` (append)

Contains the type-specific system prompts that instruct the LLM how to ask questions and build artifact definitions.

**Step 1: Write the failing test**

Append to `backend/tests/agents/test_artifact_builder.py`:

```python
def test_get_system_prompt_returns_string_for_each_type():
    """get_system_prompt returns a non-empty string for each artifact type."""
    from agents.artifact_builder_prompts import get_system_prompt

    for artifact_type in ["agent", "tool", "skill", "mcp_server"]:
        prompt = get_system_prompt(artifact_type)
        assert isinstance(prompt, str)
        assert len(prompt) > 100, f"Prompt for {artifact_type} is too short"


def test_get_system_prompt_contains_schema_fields():
    """System prompts must mention the key fields for their artifact type."""
    from agents.artifact_builder_prompts import get_system_prompt

    agent_prompt = get_system_prompt("agent")
    assert "routing_keywords" in agent_prompt
    assert "handler_module" in agent_prompt

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
```

**Step 2: Run test to verify they fail**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py::test_get_system_prompt_returns_string_for_each_type tests/agents/test_artifact_builder.py::test_get_system_prompt_contains_schema_fields tests/agents/test_artifact_builder.py::test_get_gather_type_prompt -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# backend/agents/artifact_builder_prompts.py
"""
System prompts for the artifact builder LangGraph agent.

Each artifact type has a detailed prompt that tells the LLM:
- What fields to collect and their types/constraints
- What questions to ask the admin
- How to format the artifact_draft JSON
- Validation rules to follow
"""

_GATHER_TYPE_PROMPT = """You are an AI assistant that helps administrators create artifact definitions \
for the Blitz AgentOS platform. You need to find out what type of artifact the user wants to create.

Ask the user which type of artifact they want to create:
- **Agent**: An AI agent that handles specific tasks (email, calendar, project management, etc.)
- **Tool**: A callable function/API that agents use (backend handler, MCP wrapper, or sandboxed)
- **Skill**: A reusable instruction set or procedure (instructional markdown or procedural steps)
- **MCP Server**: An external Model Context Protocol server that provides tools

Be friendly and concise. If the user's message already implies a type (e.g., "I need a tool that..."), \
identify it directly without asking again.

Respond with ONLY a conversational message to the user. Do NOT output JSON."""

_AGENT_PROMPT = """You are helping an administrator create an Agent Definition for Blitz AgentOS.

You must collect these fields through conversation:
- **name** (required, string): unique identifier, snake_case (e.g., "crm_agent")
- **display_name** (optional, string): human-readable name (e.g., "CRM Agent")
- **description** (optional, string): what this agent does
- **version** (optional, default "1.0.0"): semantic version
- **handler_module** (optional, string): Python module path (must start with: tools., agents., skills., mcp., gateway.)
- **handler_function** (optional, string): function name within the module
- **routing_keywords** (optional, list of strings): keywords that route user messages to this agent (e.g., ["email", "inbox", "send"])
- **config_json** (optional, dict): additional configuration as JSON

Ask questions one at a time. Start with purpose/description, then ask about routing keywords, then handler details.
When you have enough information, set is_complete to true in your state update.

Output format: After each user answer, update artifact_draft with the fields collected so far.
Always include at least name and description in the draft."""

_TOOL_PROMPT = """You are helping an administrator create a Tool Definition for Blitz AgentOS.

You must collect these fields through conversation:
- **name** (required, string): unique identifier, snake_case (e.g., "crm_search")
- **display_name** (optional, string): human-readable name
- **description** (optional, string): what this tool does
- **version** (optional, default "1.0.0"): semantic version
- **handler_type** (required, one of: "backend", "mcp", "sandbox"):
  - "backend": Python function in the backend codebase
  - "mcp": Wraps a tool from an MCP server
  - "sandbox": Runs in an isolated Docker container
- **handler_module** (optional, for backend/sandbox): Python module (must start with: tools., agents., skills., mcp., gateway.)
- **handler_function** (optional, for backend/sandbox): function name
- **mcp_server_id** (optional, for mcp type): UUID of the MCP server
- **mcp_tool_name** (optional, for mcp type): tool name on the MCP server
- **sandbox_required** (boolean, default false): whether Docker sandbox is needed
- **input_schema** (optional, JSON Schema dict): describes expected input parameters
- **output_schema** (optional, JSON Schema dict): describes output format

Ask handler_type early — it determines which subsequent fields are relevant.
For "mcp" type, ask about the MCP server and tool name.
For "backend" type, ask about the Python handler module and function.
Generate input_schema and output_schema based on the user's description of what the tool does.

Output format: After each user answer, update artifact_draft with the fields collected so far."""

_SKILL_PROMPT = """You are helping an administrator create a Skill Definition for Blitz AgentOS.

You must collect these fields through conversation:
- **name** (required, string): unique identifier, snake_case (e.g., "daily_standup")
- **display_name** (optional, string): human-readable name
- **description** (optional, string): what this skill does
- **version** (optional, default "1.0.0"): semantic version
- **skill_type** (required, one of: "instructional", "procedural"):
  - "instructional": A markdown guide the agent follows
  - "procedural": A structured JSON procedure with steps
- **slash_command** (optional, string): command like "/standup" to invoke the skill
- **source_type** (default "user_created"): one of "builtin", "imported", "user_created"
- **instruction_markdown** (required if instructional): The markdown content guiding the agent
- **procedure_json** (required if procedural): JSON with steps array, e.g., {"steps": [{"tool": "...", "args": {...}}]}
- **input_schema** (optional, JSON Schema dict): describes input parameters
- **output_schema** (optional, JSON Schema dict): describes output format

CRITICAL: Ask skill_type early.
- If instructional: help the user write instruction_markdown
- If procedural: help the user define procedure_json steps

Always set source_type to "user_created" for manually created skills.

Output format: After each user answer, update artifact_draft with the fields collected so far."""

_MCP_SERVER_PROMPT = """You are helping an administrator register an MCP Server for Blitz AgentOS.

You must collect these fields through conversation:
- **name** (required, string): unique display name (e.g., "crm", "docs")
- **url** (required, string): HTTP endpoint base URL (e.g., "http://mcp-crm:8001")
- **auth_token** (optional, string): Bearer token for authentication (will be encrypted before storage)

This is a simple form — only 3 fields. Ask for the server name, then the URL, then whether auth is needed.

Output format: After each answer, update artifact_draft with the fields collected so far."""

_PROMPTS: dict[str, str] = {
    "agent": _AGENT_PROMPT,
    "tool": _TOOL_PROMPT,
    "skill": _SKILL_PROMPT,
    "mcp_server": _MCP_SERVER_PROMPT,
}


def get_gather_type_prompt() -> str:
    """Return the system prompt for the gather_type node."""
    return _GATHER_TYPE_PROMPT


def get_system_prompt(artifact_type: str) -> str:
    """Return the system prompt for a specific artifact type.

    Raises KeyError if artifact_type is not recognized.
    """
    return _PROMPTS[artifact_type]
```

**Step 4: Run test to verify they pass**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py -v`
Expected: 15 PASSED

**Step 5: Commit**

```bash
git add backend/agents/artifact_builder_prompts.py backend/tests/agents/test_artifact_builder.py
git commit -m "feat(artifact-builder): add type-specific system prompts"
```

---

## Task 4: LangGraph Agent — Graph Construction

**Files:**
- Create: `backend/agents/artifact_builder.py`
- Test: `backend/tests/agents/test_artifact_builder.py` (append)

The main agent module with 4 nodes and the graph builder function.

**Step 1: Write the failing tests**

Append to `backend/tests/agents/test_artifact_builder.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch


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
        "messages": [],
        "artifact_type": None,
        "artifact_draft": None,
        "validation_errors": [],
        "is_complete": False,
    }
    assert _route_intent(state) == "gather_type"


def test_route_intent_no_draft():
    """route_intent returns 'gather_details' when type set but no draft."""
    from agents.artifact_builder import _route_intent

    state = {
        "messages": [],
        "artifact_type": "tool",
        "artifact_draft": None,
        "validation_errors": [],
        "is_complete": False,
    }
    assert _route_intent(state) == "gather_details"


def test_route_intent_has_draft_not_complete():
    """route_intent returns 'gather_details' when draft exists but incomplete."""
    from agents.artifact_builder import _route_intent

    state = {
        "messages": [],
        "artifact_type": "tool",
        "artifact_draft": {"name": "partial"},
        "validation_errors": [],
        "is_complete": False,
    }
    assert _route_intent(state) == "gather_details"


def test_route_intent_complete():
    """route_intent returns 'validate_and_present' when is_complete is True."""
    from agents.artifact_builder import _route_intent

    state = {
        "messages": [],
        "artifact_type": "tool",
        "artifact_draft": {"name": "done", "handler_type": "backend"},
        "validation_errors": [],
        "is_complete": True,
    }
    assert _route_intent(state) == "validate_and_present"
```

**Step 2: Run test to verify they fail**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py::test_create_artifact_builder_graph_returns_compiled tests/agents/test_artifact_builder.py::test_route_intent_no_type tests/agents/test_artifact_builder.py::test_route_intent_no_draft tests/agents/test_artifact_builder.py::test_route_intent_has_draft_not_complete tests/agents/test_artifact_builder.py::test_route_intent_complete -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# backend/agents/artifact_builder.py
"""
AI-Assisted Artifact Builder — LangGraph agent.

A conversational agent that helps admins create artifact definitions
(agents, tools, skills, MCP servers) through step-by-step Q&A.

Graph: route_intent → gather_type | gather_details | validate_and_present → END

This agent is separate from blitz_master. It has no memory nodes,
no user_id tracking, and no conversation persistence.
"""
import json

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.artifact_builder_prompts import get_gather_type_prompt, get_system_prompt
from agents.artifact_builder_validation import validate_artifact_draft
from agents.state.artifact_builder_types import ArtifactBuilderState
from core.config import get_llm

logger = structlog.get_logger(__name__)

# Artifact types the user can say to select a type
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


async def _gather_type_node(state: ArtifactBuilderState) -> dict:
    """Ask the user what type of artifact they want, or detect from message."""
    messages = state.get("messages", [])

    # Check if the user already mentioned a type in their last message
    if messages:
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            detected = _detect_artifact_type(last_msg.content)
            if detected:
                # Type detected — move to gather_details with an acknowledgment
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

    # Include current draft state in the system prompt so LLM knows what's collected
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

    # Try to extract JSON from the AI response to update draft
    updated_draft = _extract_draft_from_response(response.content, current_draft)

    # Check if the AI thinks the draft is complete
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

    # Valid — present the final definition
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


def _extract_draft_from_response(content: str, current_draft: dict) -> dict:
    """Try to extract a JSON object from the AI response to update the draft.

    Looks for ```json ... ``` code blocks. Falls back to current_draft if none found.
    """
    import re

    # Look for JSON code blocks
    pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
    matches = re.findall(pattern, content)

    for match in matches:
        try:
            parsed = json.loads(match.strip())
            if isinstance(parsed, dict):
                # Merge with current draft (new fields override)
                merged = {**current_draft, **parsed}
                return merged
        except (json.JSONDecodeError, ValueError):
            continue

    return current_draft


def create_artifact_builder_graph() -> CompiledStateGraph:
    """Build and compile the artifact builder LangGraph."""
    graph = StateGraph(ArtifactBuilderState)

    graph.add_node("gather_type", _gather_type_node)
    graph.add_node("gather_details", _gather_details_node)
    graph.add_node("validate_and_present", _validate_and_present_node)

    graph.set_entry_point("gather_type")

    # gather_type always goes to END (next user message triggers route_intent)
    graph.add_edge("gather_type", END)
    # gather_details always goes to END
    graph.add_edge("gather_details", END)
    # validate_and_present always goes to END
    graph.add_edge("validate_and_present", END)

    return graph.compile()
```

**Note:** The `_route_intent` function is used as a conditional edge in the runtime dispatch (Task 5), not inside the graph itself. Each node runs once per user message and returns to END. The runtime dispatches to the correct node based on `_route_intent(state)` before calling the graph.

**Step 4: Run test to verify they pass**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py -v`
Expected: 19 PASSED

**Step 5: Run full test suite**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q`
Expected: All pass (existing + 19 new)

**Step 6: Commit**

```bash
git add backend/agents/artifact_builder.py backend/tests/agents/test_artifact_builder.py
git commit -m "feat(artifact-builder): add LangGraph agent with 4 nodes"
```

---

## Task 5: Register Agent in CopilotKit Runtime

**Files:**
- Modify: `backend/gateway/runtime.py`
- Test: `backend/tests/agents/test_artifact_builder.py` (append)

**Step 1: Write the failing test**

Append to `backend/tests/agents/test_artifact_builder.py`:

```python
def test_runtime_info_includes_artifact_builder():
    """Runtime info dict must include artifact_builder agent."""
    with patch("agents.artifact_builder.get_llm") as mock_get_llm, \
         patch("agents.master_agent.get_llm") as mock_master_llm:
        mock_get_llm.return_value = MagicMock()
        mock_master_llm.return_value = MagicMock()

        # Force reimport to pick up the new agent registration
        import importlib
        import gateway.runtime as runtime_mod
        importlib.reload(runtime_mod)

        assert "artifact_builder" in runtime_mod._RUNTIME_INFO["agents"]
```

**Step 2: Run test to verify it fails**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py::test_runtime_info_includes_artifact_builder -v`
Expected: FAIL (artifact_builder not in runtime info yet)

**Step 3: Modify runtime.py**

Add after the existing `_agent` registration (around line 72):

```python
# After: _agent = LangGraphAGUIAgent(...)

from agents.artifact_builder import create_artifact_builder_graph

_builder_graph = create_artifact_builder_graph()
_builder_agent = LangGraphAGUIAgent(
    name="artifact_builder",
    description="AI-assisted artifact definition builder for admins",
    graph=_builder_graph,
)
```

Update `_RUNTIME_INFO` to include both agents:

```python
_RUNTIME_INFO = {
    "version": "0.1.0",
    "agents": {
        "blitz_master": {
            "description": _agent.description,
        },
        "artifact_builder": {
            "description": _builder_agent.description,
        },
    },
    "audioFileTranscriptionEnabled": False,
}
```

Update `agent/connect` and `agent/run` blocks to route by `agent_id`. Replace the single-agent check:

```python
# In agent/connect block, replace:
#   if agent_id != _agent.name:
# With:
_AGENTS = {"blitz_master": _agent, "artifact_builder": _builder_agent}

# Then in both agent/connect and agent/run:
agent = _AGENTS.get(agent_id)
if agent is None:
    raise HTTPException(
        status_code=404,
        detail=f"Agent '{agent_id}' not found. Available: {list(_AGENTS.keys())}",
    )
```

For `agent/run` with `artifact_builder`, use `registry:manage` permission instead of `chat`:

```python
# In agent/run, after resolving agent, add permission check:
if agent_id == "artifact_builder":
    async with async_session() as session:
        if not await has_permission(user, "registry:manage", session):
            raise HTTPException(status_code=403, detail="Registry manage permission required")
```

For `agent/connect` with `artifact_builder`, skip history loading (no persistence):

```python
# In agent/connect, only load history for blitz_master:
if agent_id == "blitz_master" and input_data.thread_id:
    # existing history loading code
    ...
```

**Step 4: Run test to verify it passes**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py -v`
Expected: 20 PASSED

**Step 5: Run full test suite**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q`
Expected: All pass

**Step 6: Commit**

```bash
git add backend/gateway/runtime.py backend/tests/agents/test_artifact_builder.py
git commit -m "feat(artifact-builder): register artifact_builder agent in CopilotKit runtime"
```

---

## Task 6: Frontend — Create Page (Server Component + Client Shell)

**Files:**
- Create: `frontend/src/app/admin/create/page.tsx`
- Create: `frontend/src/components/admin/artifact-builder-client.tsx`
- Modify: `frontend/src/app/admin/layout.tsx` (add "AI Builder" tab)

**Step 1: Add navigation tab**

In `frontend/src/app/admin/layout.tsx`, add to `ADMIN_TABS`:

```typescript
const ADMIN_TABS = [
  { label: "Agents", href: "/admin/agents" },
  { label: "Tools", href: "/admin/tools" },
  { label: "Skills", href: "/admin/skills" },
  { label: "MCP Servers", href: "/admin/mcp-servers" },
  { label: "Permissions", href: "/admin/permissions" },
  { label: "AI Builder", href: "/admin/create" },
] as const;
```

**Step 2: Create the server component page**

```typescript
// frontend/src/app/admin/create/page.tsx
/**
 * AI-Assisted Artifact Builder — Server Component entry point.
 *
 * Renders the client-side ArtifactBuilderClient which manages
 * the CopilotKit co-agent for conversational artifact creation.
 */
import { ArtifactBuilderClient } from "@/components/admin/artifact-builder-client";

export default function ArtifactBuilderPage() {
  return <ArtifactBuilderClient />;
}
```

**Step 3: Create the client component shell**

```typescript
// frontend/src/components/admin/artifact-builder-client.tsx
"use client";
/**
 * ArtifactBuilderClient — CopilotKit co-agent for artifact creation.
 *
 * Split-panel layout:
 * - Left (45%): CopilotChat for conversational AI
 * - Right (55%): Live preview of the artifact being built
 *
 * Uses useCoAgentStateRender to subscribe to artifact_draft updates
 * from the backend LangGraph agent.
 */
import { useState, useEffect, useCallback } from "react";
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";

import { ArtifactPreview } from "./artifact-preview";

/** Co-agent state shape matching ArtifactBuilderState on backend */
interface BuilderState {
  artifact_type: string | null;
  artifact_draft: Record<string, unknown> | null;
  validation_errors: string[];
  is_complete: boolean;
}

export function ArtifactBuilderClient() {
  return (
    <CopilotKit runtimeUrl="/api/copilotkit" agent="artifact_builder">
      <BuilderInner />
    </CopilotKit>
  );
}

function BuilderInner() {
  const [builderState, setBuilderState] = useState<BuilderState>({
    artifact_type: null,
    artifact_draft: null,
    validation_errors: [],
    is_complete: false,
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Navigation guard: warn on unsaved draft
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (builderState.artifact_draft && !saveSuccess) {
        e.preventDefault();
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [builderState.artifact_draft, saveSuccess]);

  const handleSave = useCallback(async () => {
    if (!builderState.artifact_type || !builderState.artifact_draft) return;

    setSaving(true);
    setSaveError(null);

    // Map artifact_type to API path
    const typeToPath: Record<string, string> = {
      agent: "agents",
      tool: "tools",
      skill: "skills",
      mcp_server: "mcp-servers",
    };
    const path = typeToPath[builderState.artifact_type];
    if (!path) {
      setSaveError(`Unknown artifact type: ${builderState.artifact_type}`);
      setSaving(false);
      return;
    }

    try {
      const res = await fetch(`/api/admin/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(builderState.artifact_draft),
      });

      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as Record<
          string,
          unknown
        >;
        throw new Error(
          (body.detail as string | undefined) ?? `HTTP ${res.status}`
        );
      }

      setSaveSuccess(true);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }, [builderState]);

  if (saveSuccess) {
    const typeToPath: Record<string, string> = {
      agent: "agents",
      tool: "tools",
      skill: "skills",
      mcp_server: "mcp-servers",
    };
    const listPath = typeToPath[builderState.artifact_type ?? ""] ?? "agents";

    return (
      <div className="flex items-center justify-center h-[calc(100vh-140px)]">
        <div className="text-center p-8">
          <div className="text-4xl mb-4">&#10003;</div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            {builderState.artifact_type?.replace("_", " ")} created successfully!
          </h2>
          <div className="flex gap-3 justify-center mt-4">
            <a
              href={`/admin/${listPath}`}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
            >
              View in Registry
            </a>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 text-sm"
            >
              Create Another
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-4 h-[calc(100vh-140px)]">
      {/* Left panel: Chat */}
      <div className="w-[45%] flex flex-col border border-gray-200 rounded-lg overflow-hidden bg-white">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
          <h2 className="text-sm font-semibold text-gray-900">
            AI Artifact Builder
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Describe what you need and I&apos;ll help create it
          </p>
        </div>
        <div className="flex-1 overflow-hidden">
          <CopilotChat
            className="h-full"
            labels={{
              initial: "What artifact would you like to create? (agent, tool, skill, or MCP server)",
            }}
          />
        </div>
      </div>

      {/* Right panel: Preview */}
      <div className="w-[55%] flex flex-col border border-gray-200 rounded-lg overflow-hidden bg-white">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900">
            Artifact Preview
          </h2>
          {builderState.is_complete && builderState.validation_errors.length === 0 && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-3 py-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-xs font-medium disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save to Registry"}
            </button>
          )}
        </div>
        <div className="flex-1 overflow-auto p-4">
          <ArtifactPreview
            artifactType={builderState.artifact_type}
            draft={builderState.artifact_draft}
            validationErrors={builderState.validation_errors}
            isComplete={builderState.is_complete}
          />
          {saveError && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
              {saveError}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

**Step 4: Run frontend build**

Run: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm run build`
Expected: Will fail because `ArtifactPreview` component doesn't exist yet (created in Task 7)

**Step 5: Commit (partial — will complete after Task 7)**

Hold commit until Task 7 creates ArtifactPreview.

---

## Task 7: Frontend — ArtifactPreview Component

**Files:**
- Create: `frontend/src/components/admin/artifact-preview.tsx`

**Step 1: Create the preview component**

```typescript
// frontend/src/components/admin/artifact-preview.tsx
"use client";
/**
 * ArtifactPreview — live preview of the artifact being built.
 *
 * Shows:
 * - Type badge
 * - Key-value field view
 * - Collapsible raw JSON
 * - Validation errors (if any)
 */
import { useState } from "react";

interface ArtifactPreviewProps {
  artifactType: string | null;
  draft: Record<string, unknown> | null;
  validationErrors: string[];
  isComplete: boolean;
}

const TYPE_COLORS: Record<string, string> = {
  agent: "bg-purple-100 text-purple-700",
  tool: "bg-blue-100 text-blue-700",
  skill: "bg-green-100 text-green-700",
  mcp_server: "bg-orange-100 text-orange-700",
};

const TYPE_LABELS: Record<string, string> = {
  agent: "Agent",
  tool: "Tool",
  skill: "Skill",
  mcp_server: "MCP Server",
};

export function ArtifactPreview({
  artifactType,
  draft,
  validationErrors,
  isComplete,
}: ArtifactPreviewProps) {
  const [showJson, setShowJson] = useState(false);

  if (!artifactType && !draft) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <div className="text-center">
          <p className="text-sm">No artifact yet</p>
          <p className="text-xs mt-1">
            Start chatting to build an artifact definition
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Type badge + completion status */}
      <div className="flex items-center gap-2">
        {artifactType && (
          <span
            className={`px-2 py-0.5 rounded-full text-xs font-medium ${TYPE_COLORS[artifactType] ?? "bg-gray-100 text-gray-700"}`}
          >
            {TYPE_LABELS[artifactType] ?? artifactType}
          </span>
        )}
        {isComplete && validationErrors.length === 0 && (
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
            Ready to save
          </span>
        )}
        {validationErrors.length > 0 && (
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
            {validationErrors.length} issue{validationErrors.length > 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Field view */}
      {draft && Object.keys(draft).length > 0 && (
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <tbody>
              {Object.entries(draft).map(([key, value]) => (
                <tr key={key} className="border-b border-gray-100 last:border-0">
                  <td className="px-3 py-2 text-gray-500 font-mono text-xs w-1/3 bg-gray-50">
                    {key}
                  </td>
                  <td className="px-3 py-2 text-gray-900 text-xs">
                    {renderValue(value)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Validation errors */}
      {validationErrors.length > 0 && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-md">
          <h4 className="text-xs font-semibold text-red-800 mb-1">
            Validation Issues
          </h4>
          <ul className="list-disc list-inside text-xs text-red-700 space-y-0.5">
            {validationErrors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Raw JSON toggle */}
      {draft && Object.keys(draft).length > 0 && (
        <div>
          <button
            onClick={() => setShowJson(!showJson)}
            className="text-xs text-blue-600 hover:text-blue-800 font-medium"
          >
            {showJson ? "Hide" : "Show"} raw JSON
          </button>
          {showJson && (
            <pre className="mt-2 p-3 bg-gray-900 text-gray-100 rounded-md text-xs overflow-auto max-h-64 font-mono">
              {JSON.stringify(draft, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  if (Array.isArray(value)) {
    if (value.length === 0) return "[]";
    return value.map(String).join(", ");
  }
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}
```

**Step 2: Run frontend build**

Run: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm run build`
Expected: PASS (no TypeScript errors)

**Step 3: Commit Tasks 6 + 7 together**

```bash
git add frontend/src/app/admin/create/page.tsx \
        frontend/src/app/admin/layout.tsx \
        frontend/src/components/admin/artifact-builder-client.tsx \
        frontend/src/components/admin/artifact-preview.tsx
git commit -m "feat(artifact-builder): add /admin/create page with split-panel layout"
```

---

## Task 8: Wire useCoAgentStateRender for Live Preview

**Files:**
- Modify: `frontend/src/components/admin/artifact-builder-client.tsx`

The `BuilderInner` component needs to subscribe to the co-agent state using `useCoAgentStateRender` so the preview updates live as the backend builds the draft.

**Step 1: Add the hook**

In `artifact-builder-client.tsx`, add the import and hook call inside `BuilderInner`:

```typescript
import { useCoAgentStateRender } from "@copilotkit/react-core";

// Inside BuilderInner, add:
useCoAgentStateRender<BuilderState>({
  name: "artifact_builder",
  render: ({ state }) => {
    // Update local state from co-agent state
    if (state) {
      setBuilderState({
        artifact_type: state.artifact_type ?? null,
        artifact_draft: state.artifact_draft ?? null,
        validation_errors: state.validation_errors ?? [],
        is_complete: state.is_complete ?? false,
      });
    }
    return null; // No inline rendering — we use ArtifactPreview instead
  },
});
```

**Note:** If `useCoAgentStateRender` API doesn't match (it may differ by CopilotKit version), fall back to `useCoAgent` which provides a `state` property directly:

```typescript
// Alternative if useCoAgentStateRender API differs:
import { useCoAgent } from "@copilotkit/react-core";

const { state } = useCoAgent<BuilderState>({ name: "artifact_builder" });

useEffect(() => {
  if (state) {
    setBuilderState({
      artifact_type: state.artifact_type ?? null,
      artifact_draft: state.artifact_draft ?? null,
      validation_errors: state.validation_errors ?? [],
      is_complete: state.is_complete ?? false,
    });
  }
}, [state]);
```

Check the CopilotKit v1.51.4 API. If neither hook works with the current agent streaming protocol, parse `StateSnapshotEvent` data from the AG-UI stream manually in a custom message handler.

**Step 2: Run frontend build**

Run: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm run build`
Expected: PASS

**Step 3: Commit**

```bash
git add frontend/src/components/admin/artifact-builder-client.tsx
git commit -m "feat(artifact-builder): wire useCoAgentStateRender for live preview"
```

---

## Task 9: Backend Integration Test — Full Agent Run

**Files:**
- Test: `backend/tests/agents/test_artifact_builder.py` (append)

An integration test that invokes the full graph with a mocked LLM.

**Step 1: Write the test**

Append to `backend/tests/agents/test_artifact_builder.py`:

```python
@pytest.mark.asyncio
async def test_gather_type_detects_tool_from_message():
    """gather_type node detects 'tool' from user message and sets artifact_type."""
    from langchain_core.messages import HumanMessage, AIMessage

    mock_response = AIMessage(content="Great! Let's create a tool. What will it do?")

    with patch("agents.artifact_builder.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
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
        result = await _gather_type_node(state)

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
    result = await _validate_and_present_node(state)

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
    result = await _validate_and_present_node(state)

    assert result["is_complete"] is False
    assert len(result["validation_errors"]) > 0
    assert any("instruction_markdown" in e.lower() for e in result["validation_errors"])
```

**Step 2: Run test**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py -v`
Expected: All PASSED

**Step 3: Run full test suite**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q`
Expected: All pass

**Step 4: Commit**

```bash
git add backend/tests/agents/test_artifact_builder.py
git commit -m "test(artifact-builder): add integration tests for graph nodes"
```

---

## Task 10: Final Verification & Frontend Build

**Files:** None (verification only)

**Step 1: Run full backend test suite**

Run: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q`
Expected: All pass (existing + ~23 new artifact builder tests)

**Step 2: Run frontend build**

Run: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm run build`
Expected: PASS (no TypeScript errors)

**Step 3: Run TypeScript check**

Run: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm exec tsc --noEmit`
Expected: PASS

**Step 4: Verify file structure**

```
backend/agents/
  ├─ artifact_builder.py           # LangGraph agent
  ├─ artifact_builder_prompts.py   # System prompts
  ├─ artifact_builder_validation.py # Pydantic validation
  └─ state/
       └─ artifact_builder_types.py # ArtifactBuilderState

backend/tests/agents/
  └─ test_artifact_builder.py      # All tests

frontend/src/app/admin/
  └─ create/
       └─ page.tsx                 # Server component

frontend/src/components/admin/
  ├─ artifact-builder-client.tsx   # Client component + CopilotKit
  └─ artifact-preview.tsx          # Preview panel

gateway/runtime.py                 # Modified: artifact_builder registered
admin/layout.tsx                   # Modified: AI Builder tab added
```

**Step 5: No commit needed** — this is verification only.

---

## Summary

| Task | Description | Files | Tests |
|------|-------------|-------|-------|
| 1 | ArtifactBuilderState TypedDict | 1 new | 2 |
| 2 | Validation helper module | 1 new | 10 |
| 3 | System prompts module | 1 new | 3 |
| 4 | LangGraph agent (graph + nodes) | 1 new | 4 |
| 5 | Register in CopilotKit runtime | 1 modified | 1 |
| 6 | Frontend create page + client | 3 new, 1 modified | — |
| 7 | ArtifactPreview component | 1 new | — |
| 8 | Wire useCoAgentStateRender | 1 modified | — |
| 9 | Integration tests | — | 3 |
| 10 | Final verification | — | — |

**Total: 8 new files, 2 modified files, ~23 tests**
