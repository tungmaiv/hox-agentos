"""
AI-Assisted Artifact Builder — LangGraph agent.

A conversational agent that helps admins create artifact definitions
(agents, tools, skills, MCP servers) through step-by-step Q&A.

Graph topology:
  START → route_intent (conditional entry point)
    |-> gather_type           (if artifact_type not set)
    |-> gather_details        (if type set but draft incomplete)
    |-> validate_and_present  (if draft looks ready)
    |-> fill_form_node        (after fill_form tool call — emits form state)
  Each node -> END (runs once per user message turn)

This agent is separate from blitz_master. It has no memory nodes,
no user_id tracking, and no conversation persistence.
"""
import json
import re

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.artifact_builder_prompts import get_gather_type_prompt, get_skill_generation_prompt, get_system_prompt
from agents.artifact_builder_validation import validate_artifact_draft
from agents.state.artifact_builder_types import ArtifactBuilderState
from copilotkit.langgraph import copilotkit_emit_state
from core.config import get_llm

logger = structlog.get_logger(__name__)

# Keywords to detect artifact type from user messages.
# Uses word-boundary matching via regex to avoid false positives.
_TYPE_KEYWORDS: list[tuple[str, str]] = [
    (r"\bmcp[_ ]server\b", "mcp_server"),
    (r"\bmcp\b", "mcp_server"),
    (r"\bagent\b", "agent"),
    (r"\btool\b", "tool"),
    (r"\bskill\b", "skill"),
]

# Marker the LLM outputs when draft is ready for validation.
_DRAFT_COMPLETE_MARKER = "[DRAFT_COMPLETE]"


@tool
def fill_form(
    name: str | None = None,
    description: str | None = None,
    artifact_type: str | None = None,
    required_permissions: list[str] | None = None,
    model_alias: str | None = None,
    system_prompt: str | None = None,
    handler_module: str | None = None,
    sandbox_required: bool | None = None,
    entry_point: str | None = None,
    url: str | None = None,
    version: str | None = None,
    instruction_markdown: str | None = None,
) -> str:
    """
    Fill one or more form fields in the artifact creation form.
    Only provide the fields you want to set or change — omitted fields are unchanged.
    After calling this tool, the user will see the form fields update live.
    """
    # Build a summary of what was filled for the tool return message
    filled = {
        k: v for k, v in {
            "name": name, "description": description, "artifact_type": artifact_type,
            "required_permissions": required_permissions, "model_alias": model_alias,
            "system_prompt": system_prompt, "handler_module": handler_module,
            "sandbox_required": sandbox_required, "entry_point": entry_point,
            "url": url, "version": version,
        }.items() if v is not None
    }
    return f"Filled {len(filled)} field(s): {', '.join(filled.keys())}"


def _route_intent(state: ArtifactBuilderState) -> str:
    """Conditional entry point: decide which node to run next."""
    # Check if the last message is a ToolMessage from fill_form
    messages = state.get("messages", [])
    if messages:
        last_msg = messages[-1]
        if isinstance(last_msg, ToolMessage):
            return "fill_form_node"

    if state.get("artifact_type") is None:
        return "gather_type"
    if state.get("is_complete"):
        return "validate_and_present"

    # Route to content generation when we have name+description but no content yet.
    # Applies to skills (missing procedure_json or instruction_markdown) and tools
    # (missing handler_code). The gather_details node populates name/description first.
    artifact_type = state.get("artifact_type")
    draft = state.get("artifact_draft") or {}
    if artifact_type in ("skill", "tool") and draft.get("name") and draft.get("description"):
        if artifact_type == "tool" and not state.get("handler_code"):
            return "generate_skill_content"
        if artifact_type == "skill":
            skill_type = draft.get("skill_type", "instructional")
            if skill_type == "procedural" and not draft.get("procedure_json"):
                return "generate_skill_content"
            if skill_type != "procedural" and not draft.get("instruction_markdown"):
                return "generate_skill_content"

    return "gather_details"


def _detect_artifact_type(text: str) -> str | None:
    """Try to detect artifact type from user message text using word boundaries."""
    lower = text.lower()
    for pattern, atype in _TYPE_KEYWORDS:
        if re.search(pattern, lower):
            return atype
    return None


def _try_extract_fill_form_args(content: str) -> dict | None:
    """Try to extract fill_form arguments from text-format tool call in message content.

    Some models (e.g. Ollama/qwen3.5) output tool calls as text JSON rather than
    structured tool_calls in the AIMessage. This handles both formats:
      - {"name": "fill_form", "arguments": {...}}
      - {"name": "fill_form", "args": {...}}
    """
    if not content or "fill_form" not in content:
        return None

    try:
        for match in re.finditer(r"\{", content):
            start = match.start()
            depth = 0
            for i, ch in enumerate(content[start:]):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = content[start : start + i + 1]
                        try:
                            parsed = json.loads(candidate)
                            if (
                                isinstance(parsed, dict)
                                and parsed.get("name") == "fill_form"
                            ):
                                args = parsed.get("arguments") or parsed.get("args") or {}
                                if isinstance(args, dict):
                                    return args
                        except json.JSONDecodeError:
                            pass
                        break
    except Exception:
        pass

    return None


# Mapping from fill_form arg names to co-agent state field names.
_FILL_FORM_ARG_TO_STATE: dict[str, str] = {
    "name": "form_name",
    "description": "form_description",
    "version": "form_version",
    "model_alias": "form_model_alias",
    "system_prompt": "form_system_prompt",
    "handler_module": "form_handler_module",
    "entry_point": "form_entry_point",
    "url": "form_url",
    "required_permissions": "form_required_permissions",
    "sandbox_required": "form_sandbox_required",
    "instruction_markdown": "form_instruction_markdown",
    # artifact_type is stored directly (no "form_" prefix)
    "artifact_type": "artifact_type",
}


def _args_to_form_updates(args: dict) -> dict:
    """Convert fill_form args dict to co-agent state field names."""
    updates: dict = {}
    for arg_key, state_key in _FILL_FORM_ARG_TO_STATE.items():
        val = args.get(arg_key)
        if val is not None:
            updates[state_key] = val
    return updates


# Mapping from artifact_draft keys to co-agent form state field names.
# Used to sync draft fields into form_updates after any LLM response.
_DRAFT_TO_FORM: dict[str, str] = {
    "name": "form_name",
    "description": "form_description",
    "version": "form_version",
    "model_alias": "form_model_alias",
    "system_prompt": "form_system_prompt",
    "handler_module": "form_handler_module",
    "entry_point": "form_entry_point",
    "url": "form_url",
    "required_permissions": "form_required_permissions",
    "sandbox_required": "form_sandbox_required",
    "instruction_markdown": "form_instruction_markdown",
}


def _merge_draft_into_form(draft: dict, form_updates: dict) -> dict:
    """Merge draft fields into form_updates for any key not already set."""
    merged = dict(form_updates)
    for draft_key, state_key in _DRAFT_TO_FORM.items():
        if draft_key in draft and state_key not in merged:
            merged[state_key] = draft[draft_key]
    return merged


def _fix_triple_quotes(text: str) -> str:
    """Convert Python-style triple-quoted strings to valid JSON strings.

    LLMs sometimes output ``"key": \"\"\"\nmultiline\n\"\"\"`` which is
    invalid JSON.  We replace each ``\"\"\"...\"\"\"`` span with a properly
    escaped JSON string using ``\\n`` for newlines.
    """
    def _replacer(m: re.Match) -> str:
        inner = m.group(1)
        escaped = (
            inner
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\t", "\\t")
        )
        return f'"{escaped}"'

    return re.sub(r'"""([\s\S]*?)"""', _replacer, text)


def _extract_draft_from_response(content: str, current_draft: dict) -> dict:
    """Try to extract a JSON object from the AI response to update the draft.

    Looks for ```json ... ``` code blocks.  When the LLM outputs multiple
    code blocks (e.g. input_schema, output_schema, full definition), we
    pick the **largest** dict (by serialised length) — that is almost always
    the complete artifact definition rather than a nested sub-schema.

    If a code block contains Python-style triple-quoted strings (common LLM
    mistake for multiline content like instruction_markdown), we attempt to
    fix them before parsing.

    Falls back to current_draft if no valid JSON block is found.
    """
    pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
    matches = re.findall(pattern, content)

    best: dict | None = None
    best_size = -1

    for match in matches:
        raw = match.strip()
        # Try parsing as-is first, then with triple-quote fix
        for attempt in (raw, _fix_triple_quotes(raw)):
            try:
                parsed = json.loads(attempt)
                if isinstance(parsed, dict) and len(raw) > best_size:
                    best = parsed
                    best_size = len(raw)
                    break
            except (json.JSONDecodeError, ValueError):
                continue

    if best is not None:
        # Filter out None values so LLM-returned null fields don't overwrite
        # existing draft values (e.g., a partial extraction should not blank
        # out a field the user already filled in).
        filtered = {k: v for k, v in best.items() if v is not None}
        return {**current_draft, **filtered}

    # Fallback: try parsing the entire content as raw JSON (no code fences).
    # LLMs sometimes output {"name": "artifact_name", "arguments": {...}} as plain text.
    # If the parsed dict has an "arguments" key containing a dict, use that as the
    # draft update (the LLM mistook the artifact name for a tool call name).
    raw = content.strip()
    for attempt in (raw, _fix_triple_quotes(raw)):
        try:
            parsed = json.loads(attempt)
            if isinstance(parsed, dict):
                args = parsed.get("arguments") or parsed.get("args")
                if isinstance(args, dict) and len(args) >= 1:
                    # LLM output a tool-call-shaped blob — use the arguments dict.
                    # If the outer "name" is not "fill_form", it's the artifact name.
                    outer_name = parsed.get("name")
                    name_override: dict = {}
                    if outer_name and outer_name != "fill_form" and "name" not in args:
                        name_override = {"name": outer_name}
                    # Filter None values from args to avoid overwriting existing draft
                    filtered_args = {k: v for k, v in args.items() if v is not None}
                    return {**current_draft, **filtered_args, **name_override}
                if len(parsed) > 1 and "arguments" not in parsed and "args" not in parsed:
                    # LLM output a flat dict of skill fields directly; filter None values
                    filtered_parsed = {k: v for k, v in parsed.items() if v is not None}
                    return {**current_draft, **filtered_parsed}
        except (json.JSONDecodeError, ValueError):
            continue

    return current_draft


async def _emit_builder_state(
    config: RunnableConfig,
    artifact_type: str | None,
    artifact_draft: dict | None,
    validation_errors: list[str],
    is_complete: bool,
    form_updates: dict | None = None,
) -> None:
    """Emit co-agent state to CopilotKit for live preview + form field rendering."""
    state: dict = {
        "artifact_type": artifact_type,
        "artifact_draft": artifact_draft,
        "validation_errors": validation_errors,
        "is_complete": is_complete,
    }
    if form_updates:
        state.update(form_updates)
    await copilotkit_emit_state(config, state)


async def _gather_type_node(state: ArtifactBuilderState, config: RunnableConfig) -> dict:
    """Ask the user what type of artifact they want, or detect from message."""
    messages = state.get("messages", [])
    llm = get_llm("blitz/master").bind_tools([fill_form])

    # Check if the user already mentioned a type in their last message
    if messages:
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            detected = _detect_artifact_type(last_msg.content)
            if detected:
                try:
                    sys_prompt = get_system_prompt(detected)
                    response = await llm.ainvoke([
                        SystemMessage(content=sys_prompt),
                        HumanMessage(content=last_msg.content),
                    ])
                except Exception as exc:
                    logger.error("llm_error", node="gather_type", error=str(exc))
                    await _emit_builder_state(config, detected, {}, [], False)
                    return {
                        "messages": [AIMessage(
                            content="I encountered an issue processing your request. "
                            "Could you try again?"
                        )],
                        "artifact_type": detected,
                        "artifact_draft": {},
                    }
                form_updates = _args_to_form_updates(
                    _try_extract_fill_form_args(response.content) or {}
                )
                updated_draft = _extract_draft_from_response(response.content, {})
                form_updates = _merge_draft_into_form(updated_draft, form_updates)
                await _emit_builder_state(config, detected, updated_draft, [], False, form_updates or None)
                return {
                    "messages": [response],
                    "artifact_type": detected,
                    "artifact_draft": updated_draft,
                    **form_updates,
                }

    # No type detected — ask explicitly
    try:
        response = await llm.ainvoke([
            SystemMessage(content=get_gather_type_prompt()),
            *messages,
        ])
    except Exception as exc:
        logger.error("llm_error", node="gather_type", error=str(exc))
        return {
            "messages": [AIMessage(
                content="I'm having trouble connecting. What type of artifact "
                "would you like to create? (agent, tool, skill, or MCP server)"
            )],
        }
    form_updates = _args_to_form_updates(
        _try_extract_fill_form_args(response.content) or {}
    )
    if form_updates:
        detected_type = form_updates.pop("artifact_type", None)
        await _emit_builder_state(config, detected_type, {}, [], False, form_updates or None)
        return {"messages": [response], "artifact_type": detected_type, **form_updates}
    return {"messages": [response]}


async def _gather_details_node(state: ArtifactBuilderState, config: RunnableConfig) -> dict:
    """Ask type-specific questions and build the artifact draft progressively."""
    artifact_type = state["artifact_type"]
    messages = state.get("messages", [])
    current_draft = state.get("artifact_draft") or {}

    sys_prompt = get_system_prompt(artifact_type)

    draft_context = (
        f"\n\nCurrent artifact_draft so far:\n```json\n{json.dumps(current_draft, indent=2)}\n```\n"
        f"Continue asking questions for missing fields. When you have enough information "
        f"to create a valid definition, output the complete artifact_draft as a JSON code block "
        f"and include the marker {_DRAFT_COMPLETE_MARKER} in your response.\n"
        f"You can also call the fill_form tool to update the frontend form fields directly."
        if current_draft
        else "\n\nNo fields collected yet. Start by asking about the artifact's purpose and name. "
             "You can call the fill_form tool to update the frontend form fields as you gather information."
    )

    try:
        llm = get_llm("blitz/master").bind_tools([fill_form])
        response = await llm.ainvoke([
            SystemMessage(content=sys_prompt + draft_context),
            *messages,
        ])
    except Exception as exc:
        logger.error("llm_error", node="gather_details", error=str(exc))
        await _emit_builder_state(config, artifact_type, current_draft, [], False)
        return {
            "messages": [AIMessage(
                content="I encountered an issue. Could you repeat your last response?"
            )],
            "artifact_type": artifact_type,
            "artifact_draft": current_draft,
        }

    updated_draft = _extract_draft_from_response(response.content, current_draft)

    looks_complete = _DRAFT_COMPLETE_MARKER in response.content

    # If the LLM claims the draft is complete, run validation immediately.
    # This prevents the frontend from showing "Save to Registry" for an
    # invalid draft (e.g. missing required `name` field).
    validation_errors: list[str] = []
    if looks_complete:
        validation_errors = validate_artifact_draft(artifact_type, updated_draft)
        if validation_errors:
            looks_complete = False

    # Also parse text-format fill_form calls (for models that output tool calls as text)
    form_updates = _args_to_form_updates(
        _try_extract_fill_form_args(response.content) or {}
    )
    # Merge draft fields into form_updates so the form reflects the latest draft
    # (handles models that update artifact_draft without calling fill_form)
    form_updates = _merge_draft_into_form(updated_draft, form_updates)

    await _emit_builder_state(
        config, artifact_type, updated_draft, validation_errors, looks_complete,
        form_updates or None,
    )
    return {
        "messages": [response],
        "artifact_type": artifact_type,
        "artifact_draft": updated_draft,
        "validation_errors": validation_errors,
        "is_complete": looks_complete,
        **form_updates,
    }


async def _validate_and_present_node(state: ArtifactBuilderState, config: RunnableConfig) -> dict:
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
        await _emit_builder_state(config, artifact_type, draft, errors, False)
        return {
            "messages": [msg],
            "artifact_type": artifact_type,
            "artifact_draft": draft,
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
    await _emit_builder_state(config, artifact_type, draft, [], True)
    return {
        "messages": [msg],
        "artifact_type": artifact_type,
        "artifact_draft": draft,
        "validation_errors": [],
        "is_complete": True,
    }


async def _fill_form_node(state: ArtifactBuilderState, config: RunnableConfig) -> dict:
    """Process fill_form tool call results and emit updated form state."""
    # Extract form field values from the last AI message's tool calls
    # to update the state, then emit them to the frontend.
    messages = state.get("messages", [])

    # Find the most recent AIMessage with tool_calls to extract fill_form arguments
    form_state_updates: dict = {}
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get("name") == "fill_form":
                    args = tc.get("args", {})
                    if args.get("name") is not None:
                        form_state_updates["form_name"] = args["name"]
                    if args.get("description") is not None:
                        form_state_updates["form_description"] = args["description"]
                    if args.get("version") is not None:
                        form_state_updates["form_version"] = args["version"]
                    if args.get("required_permissions") is not None:
                        form_state_updates["form_required_permissions"] = args["required_permissions"]
                    if args.get("model_alias") is not None:
                        form_state_updates["form_model_alias"] = args["model_alias"]
                    if args.get("system_prompt") is not None:
                        form_state_updates["form_system_prompt"] = args["system_prompt"]
                    if args.get("handler_module") is not None:
                        form_state_updates["form_handler_module"] = args["handler_module"]
                    if args.get("sandbox_required") is not None:
                        form_state_updates["form_sandbox_required"] = args["sandbox_required"]
                    if args.get("entry_point") is not None:
                        form_state_updates["form_entry_point"] = args["entry_point"]
                    if args.get("url") is not None:
                        form_state_updates["form_url"] = args["url"]
                    if args.get("artifact_type") is not None:
                        form_state_updates["artifact_type"] = args["artifact_type"]
                    if args.get("instruction_markdown") is not None:
                        form_state_updates["form_instruction_markdown"] = args["instruction_markdown"]
            break

    # Merge into existing form state
    current_form = {
        "form_name": state.get("form_name"),
        "form_description": state.get("form_description"),
        "form_version": state.get("form_version"),
        "form_required_permissions": state.get("form_required_permissions"),
        "form_model_alias": state.get("form_model_alias"),
        "form_system_prompt": state.get("form_system_prompt"),
        "form_handler_module": state.get("form_handler_module"),
        "form_sandbox_required": state.get("form_sandbox_required"),
        "form_entry_point": state.get("form_entry_point"),
        "form_url": state.get("form_url"),
        "form_instruction_markdown": state.get("form_instruction_markdown"),
    }
    merged = {**current_form, **form_state_updates}

    await _emit_builder_state(
        config,
        state.get("artifact_type"),
        state.get("artifact_draft"),
        state.get("validation_errors", []),
        state.get("is_complete", False),
        form_updates=merged,
    )
    return {**merged}


def _extract_python_code_block(content: str) -> str | None:
    """Extract the content of the first ```python ... ``` code block."""
    pattern = r"```(?:python)?\s*\n?([\s\S]*?)\n?```"
    match = re.search(pattern, content)
    if match:
        return match.group(1).strip()
    return None


async def _generate_skill_content_node(
    state: ArtifactBuilderState, config: RunnableConfig
) -> dict:
    """Generate full skill content or tool stub using a single LLM call.

    Routes based on artifact_type and skill_type:
    - Procedural skill → procedure_json with steps array
    - Instructional skill → instruction_markdown string
    - Tool artifact → handler_code Python stub with InputModel/OutputModel

    The generated content is merged into artifact_draft (for skill fields)
    or returned as handler_code (for tool stubs).
    """
    artifact_type = state.get("artifact_type", "skill")
    draft = state.get("artifact_draft") or {}

    prompt = get_skill_generation_prompt(artifact_type, draft)
    llm = get_llm("blitz/master")

    try:
        response = await llm.ainvoke([
            SystemMessage(content=prompt),
        ])
    except Exception as exc:
        logger.error("llm_error", node="generate_skill_content", error=str(exc))
        await _emit_builder_state(config, artifact_type, draft, [], False)
        return {
            "messages": [AIMessage(content="I encountered an issue generating content. Please try again.")],
            "artifact_type": artifact_type,
            "artifact_draft": draft,
        }

    content = response.content if isinstance(response.content, str) else str(response.content)
    updated_draft = dict(draft)
    handler_code: str | None = state.get("handler_code")

    if artifact_type == "tool":
        # Extract Python code block for tool stubs
        extracted = _extract_python_code_block(content)
        if extracted:
            handler_code = extracted
        else:
            # Fallback: use full content if no code block found
            handler_code = content
    elif artifact_type == "skill":
        skill_type = draft.get("skill_type", "instructional")
        if skill_type == "procedural":
            # Extract procedure_json from JSON code block
            parsed = _extract_draft_from_response(content, {})
            if "procedure_json" in parsed:
                updated_draft["procedure_json"] = parsed["procedure_json"]
            elif "steps" in parsed:
                # LLM returned the steps object directly
                updated_draft["procedure_json"] = parsed
        else:
            # Instructional: content is the markdown
            # Strip code blocks if LLM wrapped it in one (shouldn't happen but handle it)
            if content.startswith("```"):
                extracted = _extract_python_code_block(content)
                updated_draft["instruction_markdown"] = extracted or content
            else:
                updated_draft["instruction_markdown"] = content

    await _emit_builder_state(config, artifact_type, updated_draft, [], False)

    result: dict = {
        "messages": [response],
        "artifact_type": artifact_type,
        "artifact_draft": updated_draft,
    }
    if handler_code is not None:
        result["handler_code"] = handler_code

    return result


def create_artifact_builder_graph() -> CompiledStateGraph:
    """Build and compile the artifact builder LangGraph."""
    graph = StateGraph(ArtifactBuilderState)

    graph.add_node("gather_type", _gather_type_node)
    graph.add_node("gather_details", _gather_details_node)
    graph.add_node("validate_and_present", _validate_and_present_node)
    graph.add_node("fill_form_node", _fill_form_node)
    graph.add_node("generate_skill_content", _generate_skill_content_node)

    # Conditional entry point: routes to correct node based on state
    graph.set_conditional_entry_point(
        _route_intent,
        {
            "gather_type": "gather_type",
            "gather_details": "gather_details",
            "validate_and_present": "validate_and_present",
            "fill_form_node": "fill_form_node",
            "generate_skill_content": "generate_skill_content",
        },
    )

    # After gather_type: route based on draft completeness.
    # - Type is skill/tool + draft already has all required content → validate_and_present
    # - Type is skill/tool (any draft state) → generate_skill_content to fill/complete it
    # - Other artifact types or no type detected → END (wait for next user message)
    def _route_after_gather_type(state: ArtifactBuilderState) -> str:
        draft = state.get("artifact_draft") or {}
        atype = state.get("artifact_type")
        if atype == "tool":
            if state.get("handler_code"):
                return "validate_and_present"
            return "generate_skill_content"
        if atype == "skill":
            skill_type = draft.get("skill_type", "instructional")
            if skill_type == "procedural" and draft.get("procedure_json"):
                return "validate_and_present"
            if skill_type != "procedural" and draft.get("instruction_markdown"):
                return "validate_and_present"
            return "generate_skill_content"
        return END

    graph.add_conditional_edges(
        "gather_type",
        _route_after_gather_type,
        {
            "generate_skill_content": "generate_skill_content",
            "validate_and_present": "validate_and_present",
            END: END,
        },
    )
    graph.add_edge("gather_details", END)
    graph.add_edge("validate_and_present", END)
    graph.add_edge("fill_form_node", END)
    graph.add_edge("generate_skill_content", "validate_and_present")

    return graph.compile(checkpointer=MemorySaver())
