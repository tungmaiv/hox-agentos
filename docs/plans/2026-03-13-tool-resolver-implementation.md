# Tool Resolver Node Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `resolve_tools` LangGraph node to the artifact builder that maps procedural skill steps to verified registry tools, derives permissions automatically, gates activation on gap resolution, and auto-promotes skills to `pending_activation` when missing tools are created.

**Architecture:** A new `resolve_tools` node (blitz/fast) runs between `gather_details` and `generate_skill_content` for procedural skills only. It writes `resolved_tools` and `tool_gaps` to state. `SkillHandler.on_create()` enforces draft status when gaps exist. `ToolHandler.on_create()` scans draft skills for matching gaps and promotes them to `pending_activation`.

**Tech Stack:** Python 3.12, FastAPI, LangGraph, SQLAlchemy async, Next.js 15, Tailwind CSS

**Design doc:** `docs/plans/2026-03-13-tool-resolver-design.md`

---

## Task 1: Extend ArtifactBuilderState with resolver fields

**Files:**
- Modify: `backend/agents/state/artifact_builder_types.py`
- Test: `backend/tests/agents/test_artifact_builder.py`

**Step 1: Write the failing test**

Add to `backend/tests/agents/test_artifact_builder.py`:

```python
def test_artifact_builder_state_has_resolver_fields():
    """ArtifactBuilderState must declare resolved_tools and tool_gaps fields."""
    from agents.state.artifact_builder_types import ArtifactBuilderState
    annotations = ArtifactBuilderState.__annotations__
    assert "resolved_tools" in annotations, "resolved_tools field missing"
    assert "tool_gaps" in annotations, "tool_gaps field missing"
```

**Step 2: Run test to verify it fails**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py::test_artifact_builder_state_has_resolver_fields -v
```
Expected: FAIL with `AssertionError: resolved_tools field missing`

**Step 3: Add fields to ArtifactBuilderState**

In `backend/agents/state/artifact_builder_types.py`, after the `handler_code` field (line 54), add:

```python
    # Tool Resolver Node — populated for procedural skills only ────────────
    # Steps successfully matched to registry tools:
    # Each dict: {intent, tool, args_hint, permissions}
    resolved_tools: list[dict] | None
    # Steps with no matching tool (MISSING:intent-name):
    # Each dict: {intent, tool, args_hint, required_permissions}
    tool_gaps: list[dict] | None
```

**Step 4: Run test to verify it passes**

```bash
PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py::test_artifact_builder_state_has_resolver_fields -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add backend/agents/state/artifact_builder_types.py backend/tests/agents/test_artifact_builder.py
git commit -m "feat(tool-resolver): add resolved_tools and tool_gaps to ArtifactBuilderState"
```

---

## Task 2: Implement the `_resolve_tools_node` function

**Files:**
- Modify: `backend/agents/artifact_builder.py`
- Test: `backend/tests/agents/test_artifact_builder.py`

**Step 1: Write the failing test**

Add to `backend/tests/agents/test_artifact_builder.py`:

```python
@pytest.mark.asyncio
async def test_resolve_tools_node_matches_known_tool():
    """resolve_tools node maps a step intent to a matching tool from the registry."""
    from agents.artifact_builder import _resolve_tools_node
    from langchain_core.messages import HumanMessage

    state = {
        "messages": [HumanMessage(content="build a skill")],
        "artifact_type": "skill",
        "artifact_draft": {
            "name": "daily-standup",
            "description": "Fetch tasks and send summary",
            "skill_type": "procedural",
        },
        "resolved_tools": None,
        "tool_gaps": None,
        "validation_errors": [],
        "is_complete": False,
    }

    mock_llm_response = (
        '[{"intent": "fetch tasks", "tool": "project.list_tasks", '
        '"args_hint": {"date": "yesterday"}, "permissions": ["tool:project"]}]'
    )

    with patch("agents.artifact_builder._fetch_tool_reference_block", new_callable=AsyncMock, return_value="- **project.list_tasks**: Lists tasks"):
        with patch("agents.artifact_builder.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=mock_llm_response))
            mock_get_llm.return_value = mock_llm

            result = await _resolve_tools_node(state, _mock_config())

    assert result["resolved_tools"] is not None
    assert len(result["resolved_tools"]) == 1
    assert result["resolved_tools"][0]["tool"] == "project.list_tasks"
    assert result["tool_gaps"] == []


@pytest.mark.asyncio
async def test_resolve_tools_node_flags_missing_tool():
    """resolve_tools node flags steps with no matching tool as MISSING."""
    from agents.artifact_builder import _resolve_tools_node
    from langchain_core.messages import HumanMessage

    state = {
        "messages": [HumanMessage(content="build a skill")],
        "artifact_type": "skill",
        "artifact_draft": {
            "name": "slack-notifier",
            "description": "Send Slack message",
            "skill_type": "procedural",
        },
        "resolved_tools": None,
        "tool_gaps": None,
        "validation_errors": [],
        "is_complete": False,
    }

    mock_llm_response = (
        '[{"intent": "send Slack message", "tool": "MISSING:send-slack-message", '
        '"args_hint": {}, "permissions": []}]'
    )

    with patch("agents.artifact_builder._fetch_tool_reference_block", new_callable=AsyncMock, return_value=""):
        with patch("agents.artifact_builder.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=mock_llm_response))
            mock_get_llm.return_value = mock_llm

            result = await _resolve_tools_node(state, _mock_config())

    assert result["tool_gaps"] is not None
    assert len(result["tool_gaps"]) == 1
    assert result["tool_gaps"][0]["tool"].startswith("MISSING:")
    assert result["resolved_tools"] == []


@pytest.mark.asyncio
async def test_resolve_tools_node_falls_back_on_llm_error():
    """resolve_tools node falls through with empty lists on LLM error — no crash."""
    from agents.artifact_builder import _resolve_tools_node
    from langchain_core.messages import HumanMessage

    state = {
        "messages": [HumanMessage(content="build")],
        "artifact_type": "skill",
        "artifact_draft": {"name": "x", "skill_type": "procedural"},
        "resolved_tools": None,
        "tool_gaps": None,
        "validation_errors": [],
        "is_complete": False,
    }

    with patch("agents.artifact_builder._fetch_tool_reference_block", new_callable=AsyncMock, return_value=""):
        with patch("agents.artifact_builder.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM unavailable"))
            mock_get_llm.return_value = mock_llm

            result = await _resolve_tools_node(state, _mock_config())

    assert result["resolved_tools"] == []
    assert result["tool_gaps"] == []
```

**Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py::test_resolve_tools_node_matches_known_tool tests/agents/test_artifact_builder.py::test_resolve_tools_node_flags_missing_tool tests/agents/test_artifact_builder.py::test_resolve_tools_node_falls_back_on_llm_error -v
```
Expected: FAIL with `ImportError: cannot import name '_resolve_tools_node'`

**Step 3: Implement `_resolve_tools_node`**

Add the following function to `backend/agents/artifact_builder.py`, after `_fetch_tool_reference_block` (around line 379), before `_gather_type_node`:

```python
_RESOLVE_TOOLS_PROMPT = """\
You are a tool resolver. Your only job is to map each workflow step to the best matching tool from the list below.

{tool_reference}

Skill description: {description}

Output a JSON array only — no prose, no explanation, no markdown fences.
Each element:
{{
  "intent": "<what this step does>",
  "tool": "<exact tool name from list above, or MISSING:<kebab-intent> if no match>",
  "args_hint": {{<param: value pairs>}},
  "permissions": [<permission strings from the matching tool, empty list if MISSING>]
}}

Rules:
- Use EXACT tool names from the list above only
- If no tool matches, use "MISSING:" prefix followed by a kebab-case description of the intent
- Output valid JSON array only — nothing else
"""


async def _resolve_tools_node(
    state: ArtifactBuilderState, config: RunnableConfig
) -> dict:
    """Resolve procedural skill steps to verified registry tool names.

    Runs a single blitz/fast LLM call that maps each step intent to a tool
    in the registry. Splits results into resolved_tools (matched) and
    tool_gaps (MISSING). Falls back to empty lists on any error.
    """
    draft = state.get("artifact_draft") or {}
    description = draft.get("description") or draft.get("name") or "unknown skill"

    tool_reference = await _fetch_tool_reference_block()

    prompt = _RESOLVE_TOOLS_PROMPT.format(
        tool_reference=tool_reference or "(no tools registered yet)",
        description=description,
    )

    try:
        llm = get_llm("blitz/fast")
        response = await llm.ainvoke([SystemMessage(content=prompt)])
        content = response.content if isinstance(response.content, str) else str(response.content)

        # Strip markdown fences if model wrapped the output anyway
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```[a-z]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content)

        steps: list[dict] = json.loads(content)
        if not isinstance(steps, list):
            raise ValueError("Expected JSON array")

        resolved = [s for s in steps if not s.get("tool", "").startswith("MISSING:")]
        gaps = [s for s in steps if s.get("tool", "").startswith("MISSING:")]

        logger.info(
            "tool_resolver_complete",
            resolved_count=len(resolved),
            gap_count=len(gaps),
            skill_name=draft.get("name"),
        )
        return {
            "resolved_tools": resolved,
            "tool_gaps": gaps,
            "artifact_type": state.get("artifact_type"),
            "artifact_draft": draft,
        }

    except Exception as exc:
        logger.warning("tool_resolver_failed", error=str(exc), skill_name=draft.get("name"))
        return {
            "resolved_tools": [],
            "tool_gaps": [],
            "artifact_type": state.get("artifact_type"),
            "artifact_draft": draft,
        }
```

**Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py::test_resolve_tools_node_matches_known_tool tests/agents/test_artifact_builder.py::test_resolve_tools_node_flags_missing_tool tests/agents/test_artifact_builder.py::test_resolve_tools_node_falls_back_on_llm_error -v
```
Expected: 3 PASS

**Step 5: Commit**

```bash
git add backend/agents/artifact_builder.py backend/tests/agents/test_artifact_builder.py
git commit -m "feat(tool-resolver): implement _resolve_tools_node with fallback"
```

---

## Task 3: Wire `resolve_tools` into the graph and derive permissions

**Files:**
- Modify: `backend/agents/artifact_builder.py`
- Test: `backend/tests/agents/test_artifact_builder.py`

**Step 1: Write the failing test**

Add to `backend/tests/agents/test_artifact_builder.py`:

```python
def test_graph_has_resolve_tools_node():
    """create_artifact_builder_graph must include a resolve_tools node."""
    from agents.artifact_builder import create_artifact_builder_graph
    graph = create_artifact_builder_graph()
    assert "resolve_tools" in graph.nodes, "resolve_tools node missing from graph"


def test_derive_permissions_from_resolved_tools():
    """Permission union is computed correctly from resolved_tools list."""
    from agents.artifact_builder import _derive_permissions_from_resolved_tools

    resolved = [
        {"intent": "fetch tasks", "tool": "project.list_tasks", "permissions": ["tool:project"]},
        {"intent": "read calendar", "tool": "calendar.list_events", "permissions": ["tool:calendar"]},
        {"intent": "read emails", "tool": "email.fetch", "permissions": ["tool:email", "tool:project"]},
    ]
    perms = _derive_permissions_from_resolved_tools(resolved)
    assert set(perms) == {"tool:project", "tool:calendar", "tool:email"}
    assert len(perms) == len(set(perms)), "permissions must be deduplicated"
```

**Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py::test_graph_has_resolve_tools_node tests/agents/test_artifact_builder.py::test_derive_permissions_from_resolved_tools -v
```
Expected: FAIL

**Step 3: Add `_derive_permissions_from_resolved_tools` helper**

Add this function to `backend/agents/artifact_builder.py` immediately after `_resolve_tools_node`:

```python
def _derive_permissions_from_resolved_tools(resolved_tools: list[dict]) -> list[str]:
    """Compute deduplicated union of required_permissions from all resolved tools."""
    seen: set[str] = set()
    result: list[str] = []
    for step in resolved_tools:
        for perm in step.get("permissions", []):
            if perm not in seen:
                seen.add(perm)
                result.append(perm)
    return result
```

**Step 4: Wire the node into the graph**

In `create_artifact_builder_graph()` (around line 752):

1. Register the node — add after the existing `add_node` calls:
```python
graph.add_node("resolve_tools", _resolve_tools_node)
```

2. Replace the `generate_skill_content` edge from `gather_type` routing to go through `resolve_tools` for procedural skills. Update `_route_after_gather_type`:

```python
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
        # Procedural without content → resolve tools first
        if skill_type == "procedural":
            return "resolve_tools"
        return "generate_skill_content"
    return END
```

3. Update the conditional edges map to include `resolve_tools`:
```python
graph.add_conditional_edges(
    "gather_type",
    _route_after_gather_type,
    {
        "resolve_tools": "resolve_tools",
        "generate_skill_content": "generate_skill_content",
        "validate_and_present": "validate_and_present",
        END: END,
    },
)
```

4. Update `_route_intent` to route to `resolve_tools` before `generate_skill_content` for procedural skills without `resolved_tools`:

In `_route_intent` (around line 86), update the skill routing block:
```python
if artifact_type in ("skill", "tool") and draft.get("name") and draft.get("description"):
    if artifact_type == "tool" and not state.get("handler_code"):
        return "generate_skill_content"
    if artifact_type == "skill":
        skill_type = draft.get("skill_type", "instructional")
        if skill_type == "procedural" and not draft.get("procedure_json"):
            # Run tool resolver first if not yet done
            if state.get("resolved_tools") is None:
                return "resolve_tools"
            return "generate_skill_content"
        if skill_type != "procedural" and not draft.get("instruction_markdown"):
            return "generate_skill_content"
```

5. Add edge from `resolve_tools` to `generate_skill_content`:
```python
graph.add_edge("resolve_tools", "generate_skill_content")
```

6. Update the conditional edges map in the second routing block (around line 794) to include `resolve_tools`:
```python
{
    "resolve_tools": "resolve_tools",
    "generate_skill_content": "generate_skill_content",
    "validate_and_present": "validate_and_present",
    END: END,
}
```

**Step 5: Use `resolved_tools` in `_generate_skill_content_node`**

In `_generate_skill_content_node` (around line 651), after the `tool_reference = ""` block, add resolved tools context:

```python
    resolved_tools = state.get("resolved_tools") or []
    tool_gaps = state.get("tool_gaps") or []

    # Inject verified tool mapping for procedural skills
    resolved_context = ""
    if artifact_type == "skill" and resolved_tools:
        lines = ["\n\n## Verified Tool Mapping (use these exact tool names in procedure_json steps)"]
        for step in resolved_tools:
            lines.append(f"- intent: \"{step['intent']}\" → tool: \"{step['tool']}\" args_hint: {step.get('args_hint', {})}")
        resolved_context = "\n".join(lines)

    # Derive required_permissions from resolved tools
    if artifact_type == "skill" and resolved_tools:
        permissions = _derive_permissions_from_resolved_tools(resolved_tools)
        draft = dict(draft)
        draft["required_permissions"] = permissions
```

Add `resolved_context` to the prompt call. Find `prompt = get_skill_generation_prompt(artifact_type, draft, tool_reference)` and change to:
```python
    prompt = get_skill_generation_prompt(artifact_type, draft, tool_reference + resolved_context)
```

Also store `resolved_tools` and `tool_gaps` in the return value at the end of the node (around line 740):
```python
    result: dict = {
        "messages": [response],
        "artifact_type": artifact_type,
        "artifact_draft": updated_draft,
        "resolved_tools": resolved_tools,
        "tool_gaps": tool_gaps,
        **form_updates,
    }
```

**Step 6: Run tests to verify they pass**

```bash
PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py::test_graph_has_resolve_tools_node tests/agents/test_artifact_builder.py::test_derive_permissions_from_resolved_tools -v
```
Expected: 2 PASS

**Step 7: Run full test suite to check for regressions**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
Expected: 913 passed (same as before)

**Step 8: Commit**

```bash
git add backend/agents/artifact_builder.py
git commit -m "feat(tool-resolver): wire resolve_tools node into graph, derive permissions"
```

---

## Task 4: Show gap summary in `validate_and_present` node

**Files:**
- Modify: `backend/agents/artifact_builder.py`
- Test: `backend/tests/agents/test_artifact_builder.py`

**Step 1: Write the failing test**

Add to `backend/tests/agents/test_artifact_builder.py`:

```python
def test_format_gap_summary_with_gaps():
    """Gap summary message lists each MISSING tool with clear next-step instruction."""
    from agents.artifact_builder import _format_gap_summary

    gaps = [
        {"intent": "send Slack message", "tool": "MISSING:send-slack-message"},
        {"intent": "post to Teams", "tool": "MISSING:teams-post-message"},
    ]
    summary = _format_gap_summary(gaps)
    assert "MISSING" in summary or "missing" in summary.lower()
    assert "send-slack-message" in summary
    assert "teams-post-message" in summary
    assert "draft" in summary.lower() or "Draft" in summary
    assert "Tool Builder" in summary


def test_format_gap_summary_no_gaps():
    """Gap summary returns empty string when no gaps."""
    from agents.artifact_builder import _format_gap_summary
    assert _format_gap_summary([]) == ""
    assert _format_gap_summary(None) == ""
```

**Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py::test_format_gap_summary_with_gaps tests/agents/test_artifact_builder.py::test_format_gap_summary_no_gaps -v
```
Expected: FAIL with `ImportError: cannot import name '_format_gap_summary'`

**Step 3: Implement `_format_gap_summary`**

Add to `backend/agents/artifact_builder.py` after `_derive_permissions_from_resolved_tools`:

```python
def _format_gap_summary(tool_gaps: list[dict] | None) -> str:
    """Format a human-readable gap summary for the validate_and_present node.

    Returns empty string when no gaps. Otherwise returns a block describing
    each missing tool and instructions for resolving them.
    """
    if not tool_gaps:
        return ""

    lines = [
        "",
        "---",
        f"⚠️  **{len(tool_gaps)} unresolved tool gap(s)** — skill saved as **Draft**",
        "",
        "These steps have no matching tool in the registry:",
        "",
    ]
    for gap in tool_gaps:
        intent = gap.get("intent", "unknown")
        tool = gap.get("tool", "MISSING:unknown")
        slug = tool.replace("MISSING:", "")
        lines.append(f"  ⚠️  **{intent}** → needs tool: `{slug}`")

    lines += [
        "",
        "**Next steps:**",
        "1. Go to **Build → Tool Builder** and create each missing tool",
        "2. Return here — the system will detect the gaps are resolved and move this skill to **Pending Activation**",
        "3. Test the skill, then activate it",
        "",
        "This skill **cannot be activated** until all gaps are resolved.",
    ]
    return "\n".join(lines)
```

**Step 4: Inject gap summary into `_validate_and_present_node`**

In `_validate_and_present_node` (around line 526), find where the success message is assembled. After the existing preview block, append the gap summary:

```python
    tool_gaps = state.get("tool_gaps") or []
    gap_summary = _format_gap_summary(tool_gaps)

    # Append gap summary to the AI message content if gaps exist
    if gap_summary and isinstance(response_content, str):
        response_content = response_content + gap_summary
```

Read the node first to find the exact insertion point — look for where `AIMessage` is constructed with the preview content.

**Step 5: Run tests**

```bash
PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py::test_format_gap_summary_with_gaps tests/agents/test_artifact_builder.py::test_format_gap_summary_no_gaps -v
```
Expected: 2 PASS

**Step 6: Commit**

```bash
git add backend/agents/artifact_builder.py
git commit -m "feat(tool-resolver): add gap summary to validate_and_present output"
```

---

## Task 5: Enforce draft status + gap gate in SkillHandler and registry route

**Files:**
- Modify: `backend/registry/handlers/skill_handler.py`
- Modify: `backend/api/routes/registry.py`
- Test: `backend/tests/registry/test_skill_handler.py` (create if missing)
- Test: `backend/tests/api/test_registry_routes.py` (create if missing)

**Step 1: Write failing tests**

Check if `backend/tests/registry/test_skill_handler.py` exists:
```bash
ls /home/tungmv/Projects/hox-agentos/backend/tests/registry/
```

Create `backend/tests/registry/test_skill_handler.py` if missing:

```python
"""Tests for SkillHandler."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_skill_handler_forces_draft_when_tool_gaps_present():
    """on_create must override status to 'draft' when config.tool_gaps is non-empty."""
    from registry.handlers.skill_handler import SkillHandler

    handler = SkillHandler()
    entry = MagicMock()
    entry.name = "test-skill"
    entry.status = "active"  # admin tried to save as active
    entry.config = {
        "skill_type": "procedural",
        "procedure_json": {"steps": []},
        "tool_gaps": [{"intent": "send slack", "tool": "MISSING:send-slack"}],
    }
    session = AsyncMock()

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            "registry.handlers.skill_handler.scan_skill_with_fallback",
            AsyncMock(return_value={"score": 100}),
            raising=False,
        )
        await handler.on_create(entry, session)

    assert entry.status == "draft", "status must be forced to draft when gaps present"


@pytest.mark.asyncio
async def test_skill_handler_does_not_force_draft_when_no_gaps():
    """on_create must not change status when tool_gaps is empty."""
    from registry.handlers.skill_handler import SkillHandler

    handler = SkillHandler()
    entry = MagicMock()
    entry.name = "clean-skill"
    entry.status = "active"
    entry.config = {
        "skill_type": "procedural",
        "procedure_json": {"steps": []},
        "tool_gaps": [],
    }
    session = AsyncMock()

    await handler.on_create(entry, session)

    assert entry.status == "active", "status must not be changed when no gaps"
```

**Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. .venv/bin/pytest tests/registry/test_skill_handler.py -v
```
Expected: FAIL

**Step 3: Add gap enforcement to `SkillHandler.on_create()`**

In `backend/registry/handlers/skill_handler.py`, add the gap check at the END of `on_create`, after the scan block and before the final log:

```python
        # Enforce draft status when tool_gaps are present
        config = getattr(entry, "config", {}) or {}
        tool_gaps = config.get("tool_gaps", [])
        if tool_gaps:
            entry.status = "draft"  # type: ignore[attr-defined]
            logger.warning(
                "skill_saved_with_tool_gaps",
                name=getattr(entry, "name", None),
                gap_count=len(tool_gaps),
            )
```

**Step 4: Add gap gate to the update/activate route**

In `backend/api/routes/registry.py`, find the `update_entry` route (PUT `/{entry_id}`). Add a check before committing status changes:

First, read the update route to find the exact location. Then add after the entry is fetched but before saving:

```python
    # Gate: prevent activation when tool_gaps are present
    if body.status == "active":
        entry_config = entry.config or {}
        tool_gaps = entry_config.get("tool_gaps", [])
        if tool_gaps:
            raise HTTPException(
                status_code=422,
                detail="Skill has unresolved tool gaps. Create missing tools first.",
                headers={"X-Tool-Gaps": str(len(tool_gaps))},
            )
```

**Step 5: Run tests**

```bash
PYTHONPATH=. .venv/bin/pytest tests/registry/test_skill_handler.py -v
```
Expected: PASS

**Step 6: Run full suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
Expected: all pass

**Step 7: Commit**

```bash
git add backend/registry/handlers/skill_handler.py backend/api/routes/registry.py backend/tests/registry/test_skill_handler.py
git commit -m "feat(tool-resolver): enforce draft + activate gate when tool_gaps present"
```

---

## Task 6: Auto-resolve gaps in ToolHandler.on_create()

**Files:**
- Modify: `backend/registry/handlers/tool_handler.py`
- Test: `backend/tests/registry/test_tool_handler.py` (create if missing)

**Step 1: Write the failing test**

Create `backend/tests/registry/test_tool_handler.py`:

```python
"""Tests for ToolHandler gap auto-resolution."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_tool_handler_resolves_matching_skill_gap():
    """on_create promotes draft skill to pending_activation when its gap matches new tool."""
    from registry.handlers.tool_handler import ToolHandler

    handler = ToolHandler()

    # New tool being created
    new_tool = MagicMock()
    new_tool.name = "slack.send-message"

    # Draft skill with a matching gap
    skill_entry = MagicMock()
    skill_entry.id = "skill-uuid-1"
    skill_entry.name = "daily-standup"
    skill_entry.status = "draft"
    skill_entry.config = {
        "skill_type": "procedural",
        "tool_gaps": [
            {"intent": "send Slack message", "tool": "MISSING:slack-send-message"}
        ],
    }

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [skill_entry]

    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=mock_result)

    await handler.on_create(new_tool, session)

    assert skill_entry.status == "pending_activation", (
        "skill must be promoted to pending_activation when gap is resolved"
    )
    assert skill_entry.config["tool_gaps"] == [], (
        "tool_gaps must be cleared after resolution"
    )
    session.add.assert_called_with(skill_entry)


@pytest.mark.asyncio
async def test_tool_handler_does_not_promote_skill_with_remaining_gaps():
    """on_create must not promote skill if other gaps remain after partial resolution."""
    from registry.handlers.tool_handler import ToolHandler

    handler = ToolHandler()

    new_tool = MagicMock()
    new_tool.name = "slack.send-message"

    skill_entry = MagicMock()
    skill_entry.id = "skill-uuid-2"
    skill_entry.name = "complex-skill"
    skill_entry.status = "draft"
    skill_entry.config = {
        "tool_gaps": [
            {"intent": "send Slack", "tool": "MISSING:slack-send-message"},
            {"intent": "post to Teams", "tool": "MISSING:teams-post-message"},  # still missing
        ],
    }

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [skill_entry]

    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=mock_result)

    await handler.on_create(new_tool, session)

    assert skill_entry.status == "draft", "status must stay draft when gaps remain"
    assert len(skill_entry.config["tool_gaps"]) == 1, "only the resolved gap must be removed"


@pytest.mark.asyncio
async def test_tool_handler_gap_resolution_survives_db_error():
    """on_create must not crash when gap resolution DB query fails."""
    from registry.handlers.tool_handler import ToolHandler

    handler = ToolHandler()
    new_tool = MagicMock()
    new_tool.name = "some.tool"

    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(side_effect=Exception("DB error"))

    # Must not raise
    await handler.on_create(new_tool, session)
```

**Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. .venv/bin/pytest tests/registry/test_tool_handler.py -v
```
Expected: FAIL

**Step 3: Implement gap resolution in `ToolHandler.on_create()`**

Replace the current `on_create` in `backend/registry/handlers/tool_handler.py`:

```python
    async def on_create(self, entry: object, session: AsyncSession) -> None:
        """Log creation and auto-resolve matching gaps in draft skills."""
        tool_name: str = getattr(entry, "name", "") or ""
        logger.info("registry_tool_created", name=tool_name)

        # Convert tool name to slug for gap matching
        # e.g. "slack.send-message" → "slack-send-message"
        tool_slug = tool_name.replace(".", "-").replace("_", "-").lower()

        try:
            from sqlalchemy import select
            from registry.models import RegistryEntry

            result = await session.execute(
                select(RegistryEntry).where(
                    RegistryEntry.type == "skill",
                    RegistryEntry.status == "draft",
                    RegistryEntry.deleted_at.is_(None),
                )
            )
            draft_skills = result.scalars().all()

            for skill in draft_skills:
                config = skill.config or {}
                gaps: list[dict] = config.get("tool_gaps", [])
                if not gaps:
                    continue

                # Remove gaps whose MISSING slug matches the new tool slug
                remaining = [
                    g for g in gaps
                    if tool_slug not in g.get("tool", "").replace("MISSING:", "").lower()
                ]

                if len(remaining) == len(gaps):
                    continue  # no match — skip

                updated_config = {**config, "tool_gaps": remaining}

                if not remaining:
                    skill.status = "pending_activation"
                    logger.info(
                        "skill_gaps_resolved",
                        skill_id=str(getattr(skill, "id", "?")),
                        skill_name=getattr(skill, "name", "?"),
                        triggered_by_tool=tool_name,
                    )
                else:
                    logger.info(
                        "skill_gap_partially_resolved",
                        skill_id=str(getattr(skill, "id", "?")),
                        remaining_gaps=len(remaining),
                        triggered_by_tool=tool_name,
                    )

                skill.config = updated_config
                session.add(skill)

        except Exception as exc:
            logger.warning("tool_gap_resolution_failed", error=str(exc), tool_name=tool_name)
```

**Step 4: Run tests**

```bash
PYTHONPATH=. .venv/bin/pytest tests/registry/test_tool_handler.py -v
```
Expected: 3 PASS

**Step 5: Run full suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
Expected: all pass

**Step 6: Commit**

```bash
git add backend/registry/handlers/tool_handler.py backend/tests/registry/test_tool_handler.py
git commit -m "feat(tool-resolver): auto-resolve skill gaps and promote to pending_activation on tool creation"
```

---

## Task 7: Add `pending_activation` badge to frontend skills page

**Files:**
- Modify: `frontend/src/app/(authenticated)/admin/skills/page.tsx`

**Step 1: Locate the StatusBadge component**

In `frontend/src/app/(authenticated)/admin/skills/page.tsx`, find the `StatusBadge` component (around line 120):

```tsx
const StatusBadge = ({ status }: { status: string }) => (
  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
    status === "active" ? "bg-green-100 text-green-700"
    : status === "archived" ? "bg-gray-100 text-gray-500"
    : "bg-yellow-100 text-yellow-700"
  }`}>{status}</span>
);
```

**Step 2: Update StatusBadge to handle `pending_activation` distinctly**

Replace it with:

```tsx
const StatusBadge = ({ status }: { status: string }) => {
  const cls =
    status === "active" ? "bg-green-100 text-green-700"
    : status === "pending_activation" ? "bg-orange-100 text-orange-700"
    : status === "archived" ? "bg-gray-100 text-gray-500"
    : "bg-yellow-100 text-yellow-700";
  const label =
    status === "pending_activation" ? "pending activation" : status;
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {label}
    </span>
  );
};
```

**Step 3: Verify TypeScript builds clean**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
```
Expected: 0 errors

**Step 4: Commit**

```bash
git add frontend/src/app/\(authenticated\)/admin/skills/page.tsx
git commit -m "feat(tool-resolver): add pending_activation badge to skills list"
```

---

## Task 8: Update `artifact_builder_skill.md` prompt

**Files:**
- Modify: `backend/prompts/artifact_builder_skill.md`

**Step 1: Remove the hardcoded `required_permissions` list**

Find the `required_permissions` section (lines 37-51). Replace the entire static list with:

```markdown
- **required_permissions**: DERIVED AUTOMATICALLY — do not guess or invent permission strings.
  The system resolves permissions from the registered tools used by each step.
  For instructional skills only: use only permissions the skill's instructions explicitly require.
```

**Step 2: Add gap summary output template**

At the end of Phase 6 (Preview & Confirm), add a section:

```markdown
**If tool gaps exist (procedural skills only):**

After the normal preview, append:

```
⚠️  **N unresolved tool gap(s)** — skill saved as **Draft**

These steps have no matching tool in the registry:
  ⚠️  **[intent]** → needs tool: `[slug]`

**Next steps:**
1. Go to **Build → Tool Builder** and create each missing tool
2. Return here — the system will automatically detect resolution and move this skill to **Pending Activation**
3. Test the skill, then activate it

This skill **cannot be activated** until all gaps are resolved.
```
```

**Step 3: Commit**

```bash
git add backend/prompts/artifact_builder_skill.md
git commit -m "docs(tool-resolver): update skill builder prompt — derive permissions, add gap summary template"
```

---

## Task 9: Final integration verification

**Step 1: Run full backend test suite**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
Expected: all tests pass, no regressions from pre-feature baseline (913+)

**Step 2: Run frontend TypeScript check**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
```
Expected: 0 errors

**Step 3: Smoke test via API**

```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/api/auth/local/token" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create a procedural skill with a gap — should save as draft
curl -s -X POST "http://localhost:8000/api/registry" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "skill",
    "name": "test-gap-skill",
    "description": "test",
    "status": "active",
    "config": {
      "skill_type": "procedural",
      "procedure_json": {"steps": []},
      "tool_gaps": [{"intent": "send slack", "tool": "MISSING:slack-send"}]
    }
  }' | python3 -c "import sys,json; d=json.load(sys.stdin); print('status:', d.get('status'))"
# Expected: status: draft (not active)

# Try to activate it — should be blocked
SKILL_ID=$(curl -s "http://localhost:8000/api/registry?type=skill" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; items=json.load(sys.stdin); print(next(i['id'] for i in items if i['name']=='test-gap-skill'))")

curl -s -o /dev/null -w "%{http_code}" -X PUT "http://localhost:8000/api/registry/$SKILL_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "active"}'
# Expected: 422
```

**Step 4: Commit final verification note to STATE.md**

Add to `.planning/STATE.md` Decisions section:
```
- [tool-resolver]: resolve_tools node runs blitz/fast before generate_skill_content for procedural skills only — fallback to empty lists on error preserves existing instructional skill behavior
- [tool-resolver]: tool_gaps gap matching uses slug-based substring match (tool name dots/underscores → hyphens) — sufficient for MVP, can upgrade to semantic match later
- [tool-resolver]: pending_activation is a UI status only — no DB constraint change needed, registry.py update route gate enforces it
```

```bash
git add .planning/STATE.md
git commit -m "docs(tool-resolver): record implementation decisions in STATE.md"
```

---

## Summary of New/Modified Files

| File | Change |
|------|--------|
| `backend/agents/state/artifact_builder_types.py` | +2 fields: `resolved_tools`, `tool_gaps` |
| `backend/agents/artifact_builder.py` | +`_resolve_tools_node`, +`_derive_permissions_from_resolved_tools`, +`_format_gap_summary`, graph wiring, `generate_skill_content` reads resolved tools |
| `backend/registry/handlers/skill_handler.py` | `on_create` forces `draft` when `tool_gaps` non-empty |
| `backend/registry/handlers/tool_handler.py` | `on_create` auto-resolves gaps, promotes to `pending_activation` |
| `backend/api/routes/registry.py` | Update route gates activation when `tool_gaps` non-empty |
| `backend/prompts/artifact_builder_skill.md` | Remove hardcoded permissions list, add gap summary template |
| `frontend/src/app/(authenticated)/admin/skills/page.tsx` | `pending_activation` amber badge |
| `backend/tests/agents/test_artifact_builder.py` | 7 new tests |
| `backend/tests/registry/test_skill_handler.py` | 2 new tests (new file) |
| `backend/tests/registry/test_tool_handler.py` | 3 new tests (new file) |
