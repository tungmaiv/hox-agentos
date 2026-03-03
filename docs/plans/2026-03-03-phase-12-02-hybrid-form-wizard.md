# Phase 12-02: Hybrid Form Wizard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the chat-only AI Builder at `/admin/create` with a hybrid: structured form (left panel) + AI chat assistant (right panel). The AI calls a `fill_form` tool that directly updates form field values in real time. Includes: artifact type selector, hardcoded templates, debounced name-conflict check, permission checklist, and clone-from-existing support.

**Architecture:** Backend adds `check-name` query endpoints to each admin artifact route (4 files, ~10 lines each). The `artifact_builder` agent gains a `fill_form` LangGraph tool that updates `artifact_draft` state fields; `copilotkit_emit_state` propagates updates to the frontend. Frontend replaces `/admin/create/page.tsx` with a split-panel component. Clone entry points are added to existing `ArtifactTable` and `ArtifactCardGrid` components. The existing catch-all proxy at `frontend/src/app/api/admin/[...path]/route.ts` already covers the new check-name endpoint — no proxy changes needed.

**Tech Stack:** FastAPI, LangGraph, CopilotKit AG-UI, SQLAlchemy async, Next.js 15, TypeScript strict, Zod

---

## Canonical Commands

```bash
# Backend tests
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q

# TypeScript check only
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit

# Full frontend build (catches TypeScript + build errors)
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build
```

## Pre-flight Check

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
# Expected: 586+ passed, 0 failed
```

---

## Task 1: Backend — add `check-name` endpoint to each admin route

**Files:**
- Modify: `backend/api/routes/admin_agents.py`
- Modify: `backend/api/routes/admin_tools.py`
- Modify: `backend/api/routes/admin_skills.py`

**Context:** Each admin route file already has a `router = APIRouter(prefix="/api/admin/{type}", ...)` and a `_require_registry_manager` dependency. Add a single `GET /check-name?name=xxx` endpoint to each file. Returns `{"available": true/false}`. Case-insensitive match. Checks only active rows (`status != "inactive"` or equivalent — look at how existing list endpoints filter).

**Important:** Check each file to confirm the exact model name (`AgentDefinition`, `ToolDefinition`, `SkillDefinition`) and how status filtering works before writing. Read each file first.

**Step 1: Read all three files**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
grep -n "class.*Definition\|status\|Model" api/routes/admin_agents.py | head -20
grep -n "class.*Definition\|status\|Model" api/routes/admin_tools.py | head -20
grep -n "class.*Definition\|status\|Model" api/routes/admin_skills.py | head -20
```

**Step 2: Add to `admin_agents.py`**

Find the imports. Add `func` to the sqlalchemy imports:
```python
from sqlalchemy import func, select, update
```

Add this endpoint **before** the `/{agent_id}` route (order matters — string paths must come before UUID paths):

```python
@router.get("/check-name")
async def check_agent_name(
    name: str = Query(..., min_length=1),
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Check if an agent name is available (case-insensitive)."""
    async with session.begin():
        count = await session.scalar(
            select(func.count()).where(
                func.lower(AgentDefinition.name) == name.lower()
            )
        )
    return {"available": (count or 0) == 0}
```

**Step 3: Add to `admin_tools.py`** — same pattern, use `ToolDefinition`

**Step 4: Add to `admin_skills.py`** — same pattern, use `SkillDefinition`

**Step 5: Check for MCP server route file**

```bash
ls backend/api/routes/admin*.py
```

If `admin_mcp_servers.py` exists, add the same endpoint there using the MCP server model. If MCP servers are managed differently (check `mcp_servers.py`), add it there. Read the file before editing.

**Step 6: Verify imports compile**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. python -c "from main import app; print('OK')"
# Expected: OK
```

**Step 7: Commit**

```bash
git add backend/api/routes/admin_agents.py backend/api/routes/admin_tools.py backend/api/routes/admin_skills.py
git commit -m "feat(12-02): add check-name endpoint to agent, tool, skill admin routes"
```

---

## Task 2: Tests for `check-name` endpoints

**Files:**
- Modify: `backend/tests/api/test_admin_agents.py`
- Modify: `backend/tests/api/test_admin_tools.py`
- Modify: `backend/tests/api/test_admin_skills.py`

**Step 1: Add to `test_admin_agents.py`**

Append these tests to the existing file. The fixture setup (`admin_client`, `sqlite_db`) is already there:

```python
# ---------------------------------------------------------------------------
# GET /api/admin/agents/check-name
# ---------------------------------------------------------------------------


def test_check_agent_name_available(admin_client):
    resp = admin_client.get("/api/admin/agents/check-name?name=new-agent")
    assert resp.status_code == 200
    assert resp.json() == {"available": True}


def test_check_agent_name_taken(admin_client):
    # Create an agent first
    admin_client.post(
        "/api/admin/agents",
        json={"name": "existing-agent"},
    )
    resp = admin_client.get("/api/admin/agents/check-name?name=existing-agent")
    assert resp.status_code == 200
    assert resp.json() == {"available": False}


def test_check_agent_name_case_insensitive(admin_client):
    admin_client.post("/api/admin/agents", json={"name": "MyAgent"})
    resp = admin_client.get("/api/admin/agents/check-name?name=myagent")
    assert resp.status_code == 200
    assert resp.json() == {"available": False}


def test_check_agent_name_forbidden(employee_client):
    resp = employee_client.get("/api/admin/agents/check-name?name=test")
    assert resp.status_code == 403
```

**Step 2: Add equivalent tests to `test_admin_tools.py` and `test_admin_skills.py`**

Same pattern — use `POST /api/admin/tools` and `GET /api/admin/tools/check-name`, etc.

**Step 3: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/api/test_admin_agents.py tests/api/test_admin_tools.py tests/api/test_admin_skills.py -v
# Expected: all pass including new check-name tests
```

**Step 4: Full suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
# Expected: 586+ passed, 0 failed
```

**Step 5: Commit**

```bash
git add backend/tests/api/test_admin_agents.py backend/tests/api/test_admin_tools.py backend/tests/api/test_admin_skills.py
git commit -m "test(12-02): add check-name endpoint tests"
```

---

## Task 3: Backend — update `ArtifactBuilderState` with `form_values`

**Files:**
- Modify: `backend/agents/state/artifact_builder_types.py`

**Context:** The current `ArtifactBuilderState` has `artifact_type`, `artifact_draft`, `validation_errors`, `is_complete`. We add a `form_values` field that the agent reads to understand the current state of the form (what the user has already filled in), so the AI doesn't re-ask for information already entered.

**Step 1: Update the TypedDict**

```python
class ArtifactBuilderState(TypedDict):
    """State for the artifact builder LangGraph agent."""

    messages: Annotated[list[BaseMessage], add_messages]
    # "agent" | "tool" | "skill" | "mcp_server" — set after first user message or form
    artifact_type: str | None
    # Field values set by the AI via fill_form tool — merged into frontend form state
    artifact_draft: dict | None
    # Validation errors from last Pydantic check (empty = valid)
    validation_errors: list[str]
    # True when artifact_draft passes schema validation
    is_complete: bool
    # Current form values from the frontend (user-edited fields) — injected into AI context
    form_values: dict | None
```

**Step 2: Commit**

```bash
git add backend/agents/state/artifact_builder_types.py
git commit -m "feat(12-02): add form_values field to ArtifactBuilderState"
```

---

## Task 4: Backend — add `fill_form` tool to `artifact_builder` agent

**Files:**
- Modify: `backend/agents/artifact_builder.py`

**Context:** The current agent has 3 nodes (gather_type, gather_details, validate_and_present). We keep this topology but add a LangChain tool `fill_form` that the LLM can call to update specific form fields. When the LLM calls `fill_form(name="email-digest", permissions=["tool:email"])`, the node captures the tool result and emits it as `artifact_draft` state, which flows to the frontend via `copilotkit_emit_state`.

**How CopilotKit tool binding works:** Bind tools to the LLM with `llm.bind_tools([fill_form_tool])`. When the LLM response contains a tool call, the node handles it manually by invoking the tool and merging the result into `artifact_draft`.

**Step 1: Add `fill_form` tool definition** (add near the top of the file, after imports)

```python
from langchain_core.tools import tool

# All known permission strings — must match security/rbac.py ROLE_PERMISSIONS
_ALL_PERMISSIONS = [
    "chat", "tool:email", "tool:calendar", "tool:project",
    "crm:read", "crm:write", "tool:reports", "workflow:create",
    "workflow:approve", "tool:admin", "sandbox:execute", "registry:manage",
]


@tool
def fill_form(
    name: str | None = None,
    description: str | None = None,
    artifact_type: str | None = None,
    version: str | None = None,
    required_permissions: list[str] | None = None,
    model_alias: str | None = None,
    system_prompt: str | None = None,
    url: str | None = None,
    handler_module: str | None = None,
    entry_point: str | None = None,
    sandbox_required: bool | None = None,
) -> str:
    """
    Fill one or more artifact form fields directly.

    Use this tool whenever you want to suggest or set values for the creation form.
    Only provide the fields you want to change — unspecified fields are left as-is.
    The frontend form will update immediately when this tool is called.

    Args:
        name: Artifact name (lowercase, hyphens allowed, e.g. 'email-digest-agent')
        description: Human-readable description of what this artifact does
        artifact_type: One of: agent, tool, skill, mcp_server
        version: Semantic version string, e.g. '1.0.0'
        required_permissions: List of permission strings from the allowed set
        model_alias: For agents — one of: blitz/master, blitz/fast, blitz/coder, blitz/summarizer
        system_prompt: For agents — the system prompt text
        url: For MCP servers — the SSE endpoint URL
        handler_module: For tools — Python module path to the tool handler
        entry_point: For skills — Python module path to the skill entry point
        sandbox_required: For tools/skills — whether Docker sandbox execution is required
    """
    # Build the field update dict (exclude None values)
    update: dict = {}
    if name is not None: update["name"] = name
    if description is not None: update["description"] = description
    if artifact_type is not None: update["artifact_type"] = artifact_type
    if version is not None: update["version"] = version
    if required_permissions is not None:
        valid = [p for p in required_permissions if p in _ALL_PERMISSIONS]
        update["required_permissions"] = valid
    if model_alias is not None: update["model_alias"] = model_alias
    if system_prompt is not None: update["system_prompt"] = system_prompt
    if url is not None: update["url"] = url
    if handler_module is not None: update["handler_module"] = handler_module
    if entry_point is not None: update["entry_point"] = entry_point
    if sandbox_required is not None: update["sandbox_required"] = sandbox_required

    return json.dumps(update)
```

**Step 2: Update `_gather_details_node` to bind and handle `fill_form`**

Replace the `_gather_details_node` function with one that:
1. Binds `fill_form` to the LLM
2. Handles tool calls in the response
3. Merges tool results into `artifact_draft`

```python
async def _gather_details_node(state: ArtifactBuilderState, config: RunnableConfig) -> dict:
    """Ask type-specific questions and build the artifact draft via fill_form tool calls."""
    artifact_type = state["artifact_type"]
    messages = state.get("messages", [])
    current_draft = state.get("artifact_draft") or {}
    form_values = state.get("form_values") or {}

    sys_prompt = get_system_prompt(artifact_type)

    # Include current form state so AI doesn't re-ask for already-filled fields
    form_context = ""
    if form_values or current_draft:
        merged = {**current_draft, **form_values}
        form_context = (
            f"\n\nCurrent form values (already filled by user or previous AI suggestions):\n"
            f"```json\n{json.dumps(merged, indent=2)}\n```\n"
            f"Do not ask about fields that already have values. "
            f"Use fill_form() to suggest or correct values. "
            f"When you believe the form is complete, say so and set is_complete=true."
        )

    full_system = sys_prompt + form_context
    llm = get_llm("blitz/master").bind_tools([fill_form])

    try:
        response = await llm.ainvoke([
            SystemMessage(content=full_system),
            *messages,
        ])
    except Exception as exc:
        logger.error("llm_error", node="gather_details", error=str(exc))
        await _emit_builder_state(config, artifact_type, current_draft, [], False)
        return {
            "messages": [AIMessage(content="I encountered an issue. Could you repeat your last response?")],
            "artifact_type": artifact_type,
            "artifact_draft": current_draft,
        }

    # Process tool calls from the LLM response
    updated_draft = dict(current_draft)
    tool_results = []
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            if tc.get("name") == "fill_form":
                try:
                    result_json = fill_form.invoke(tc["args"])
                    field_updates = json.loads(result_json)
                    updated_draft.update(field_updates)
                    tool_results.append(result_json)
                except Exception as exc:
                    logger.warning("fill_form_tool_error", error=str(exc))

    # Also try to extract JSON draft from text response (backward compat)
    if not tool_results and hasattr(response, "content") and response.content:
        updated_draft = _extract_draft_from_response(response.content, updated_draft)

    looks_complete = (
        _DRAFT_COMPLETE_MARKER in (response.content or "")
        or bool(updated_draft.get("name") and updated_draft.get("description"))
    )

    validation_errors: list[str] = []
    if looks_complete:
        validation_errors = validate_artifact_draft(artifact_type, updated_draft)
        if validation_errors:
            looks_complete = False

    await _emit_builder_state(config, artifact_type, updated_draft, validation_errors, looks_complete)
    return {
        "messages": [response],
        "artifact_type": artifact_type,
        "artifact_draft": updated_draft,
        "validation_errors": validation_errors,
        "is_complete": looks_complete,
    }
```

**Step 3: Update `_emit_builder_state` to also emit `form_values`-merged state**

The existing `_emit_builder_state` call signature can stay the same — the `artifact_draft` now contains fill_form-populated values which is what the frontend merges.

**Step 4: Verify import compiles**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. python -c "from agents.artifact_builder import create_artifact_builder_graph; print('OK')"
# Expected: OK
```

**Step 5: Run existing artifact builder tests if any**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -k "artifact" -v
# Expected: all pass (or none if no existing tests)
```

**Step 6: Commit**

```bash
git add backend/agents/artifact_builder.py
git commit -m "feat(12-02): add fill_form tool to artifact_builder agent"
```

---

## Task 5: Backend — update artifact_builder system prompts

**Files:**
- Modify: `backend/prompts/artifact_builder_gather_type.md` (if it exists)
- Check what prompt files exist: `ls backend/prompts/artifact_builder*.md`

**Step 1: Check existing prompts**

```bash
ls /home/tungmv/Projects/hox-agentos/backend/prompts/artifact_builder*.md
cat /home/tungmv/Projects/hox-agentos/backend/prompts/artifact_builder_gather_type.md
```

**Step 2: Update the gather_type prompt**

Add instruction to use `fill_form` tool to update the type when detected. The key addition:

```markdown
## Your Role
You help admins create artifact definitions for Blitz AgentOS. You have a structured form on the left side of the screen. Use the `fill_form` tool to suggest values — your tool calls update the form fields immediately and the admin can see the changes in real time.

## When to Use fill_form
- As soon as you understand what the user wants, call fill_form() with the relevant fields
- Don't wait until you have all information — call fill_form() with partial values to show progress
- If the user says "create an email digest agent", immediately call fill_form(artifact_type="agent", name="email-digest-agent", description="...", required_permissions=["tool:email"])
```

Update each type-specific prompt (agent, tool, skill, mcp_server) with similar guidance about using `fill_form` instead of asking questions one at a time.

**Step 3: Commit**

```bash
git add backend/prompts/
git commit -m "feat(12-02): update artifact_builder prompts to use fill_form tool"
```

---

## Task 6: Frontend — `artifact-wizard.tsx` core component

**Files:**
- Create: `frontend/src/components/admin/artifact-wizard.tsx`

**Context:** This is the top-level wrapper component for `/admin/create`. It wraps everything in `CopilotKit` and renders the split-panel layout. Left panel: form. Right panel: CopilotChat. The component subscribes to `useCoAgentStateRender` to receive `artifact_draft` updates from the AI and merges them into form state.

**Step 1: Write the component**

```typescript
"use client";
/**
 * ArtifactWizard — split-panel hybrid wizard.
 *
 * Left (45%): Structured form (type selector, templates, fields, preview, actions)
 * Right (55%): CopilotKit chat assistant that fills form fields via fill_form tool
 *
 * The AI calls fill_form() → backend emits artifact_draft state → frontend merges
 * into form fields in real time. Form is always the source of truth.
 */
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import { useCoAgentStateRender } from "@copilotkit/react-core";
import "@copilotkit/react-ui/styles.css";
import { useEffect, useRef, useState, useCallback } from "react";
import { ArtifactWizardForm } from "./artifact-wizard-form";

export type ArtifactType = "agent" | "tool" | "skill" | "mcp_server";

export interface WizardFormValues {
  artifact_type: ArtifactType | null;
  name: string;
  description: string;
  version: string;
  // Agent-specific
  model_alias: string;
  system_prompt: string;
  // Tool/Skill-specific
  required_permissions: string[];
  sandbox_required: boolean;
  handler_module: string;
  entry_point: string;
  // MCP-specific
  url: string;
  auth_token: string;
}

export const DEFAULT_FORM_VALUES: WizardFormValues = {
  artifact_type: null,
  name: "",
  description: "",
  version: "1.0.0",
  model_alias: "blitz/master",
  system_prompt: "",
  required_permissions: [],
  sandbox_required: false,
  handler_module: "",
  entry_point: "",
  url: "",
  auth_token: "",
};

/** Shape of co-agent state emitted by artifact_builder backend agent */
interface BuilderAgentState {
  artifact_type: string | null;
  artifact_draft: Record<string, unknown> | null;
  validation_errors: string[];
  is_complete: boolean;
}

export function ArtifactWizard() {
  return (
    <CopilotKit runtimeUrl="/api/copilotkit" agent="artifact_builder">
      <WizardInner />
    </CopilotKit>
  );
}

function WizardInner() {
  const [formValues, setFormValues] = useState<WizardFormValues>(DEFAULT_FORM_VALUES);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Buffer AI state updates to avoid setState during render
  const pendingDraftRef = useRef<Record<string, unknown> | null>(null);

  useCoAgentStateRender<BuilderAgentState>({
    name: "artifact_builder",
    render: ({ state }) => {
      if (state?.artifact_draft) {
        pendingDraftRef.current = state.artifact_draft;
      }
      return null;
    },
  });

  // Apply buffered AI state outside render phase
  useEffect(() => {
    const id = setInterval(() => {
      if (pendingDraftRef.current) {
        const draft = pendingDraftRef.current;
        pendingDraftRef.current = null;
        setFormValues((prev) => ({
          ...prev,
          // Merge AI-provided values into form state
          ...(typeof draft.name === "string" ? { name: draft.name } : {}),
          ...(typeof draft.description === "string" ? { description: draft.description } : {}),
          ...(typeof draft.artifact_type === "string" ? { artifact_type: draft.artifact_type as ArtifactType } : {}),
          ...(typeof draft.version === "string" ? { version: draft.version } : {}),
          ...(Array.isArray(draft.required_permissions) ? { required_permissions: draft.required_permissions as string[] } : {}),
          ...(typeof draft.model_alias === "string" ? { model_alias: draft.model_alias } : {}),
          ...(typeof draft.system_prompt === "string" ? { system_prompt: draft.system_prompt } : {}),
          ...(typeof draft.url === "string" ? { url: draft.url } : {}),
          ...(typeof draft.handler_module === "string" ? { handler_module: draft.handler_module } : {}),
          ...(typeof draft.entry_point === "string" ? { entry_point: draft.entry_point } : {}),
          ...(typeof draft.sandbox_required === "boolean" ? { sandbox_required: draft.sandbox_required } : {}),
        }));
      }
    }, 150);
    return () => clearInterval(id);
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!formValues.artifact_type || !formValues.name.trim()) return;
    setSubmitting(true);
    setSubmitError(null);

    const typeToPath: Record<ArtifactType, string> = {
      agent: "agents",
      tool: "tools",
      skill: "skills",
      mcp_server: "mcp-servers",
    };
    const path = typeToPath[formValues.artifact_type];

    // Build payload — only include relevant fields for this type
    const payload: Record<string, unknown> = {
      name: formValues.name.trim(),
      description: formValues.description.trim() || null,
      version: formValues.version.trim() || "1.0.0",
    };
    if (formValues.artifact_type === "agent") {
      payload.model_alias = formValues.model_alias || null;
      payload.config_json = formValues.system_prompt
        ? { system_prompt: formValues.system_prompt }
        : null;
    }
    if (formValues.artifact_type === "tool" || formValues.artifact_type === "skill") {
      payload.required_permissions = formValues.required_permissions;
      payload.sandbox_required = formValues.sandbox_required;
      if (formValues.artifact_type === "tool") payload.handler_module = formValues.handler_module || null;
      if (formValues.artifact_type === "skill") payload.entry_point = formValues.entry_point || null;
    }
    if (formValues.artifact_type === "mcp_server") {
      payload.url = formValues.url.trim();
      if (formValues.auth_token.trim()) payload.auth_token = formValues.auth_token.trim();
    }

    try {
      const res = await fetch(`/api/admin/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const data = (await res.json()) as { detail?: string };
        setSubmitError(data.detail ?? `Failed (${res.status})`);
        return;
      }
      const created = (await res.json()) as { id: string; name: string };
      setSubmitSuccess(`Created! View it in /admin/${path}`);
      setFormValues(DEFAULT_FORM_VALUES);
      setTimeout(() => setSubmitSuccess(null), 4000);
    } catch {
      setSubmitError("Network error — could not reach backend.");
    } finally {
      setSubmitting(false);
    }
  }, [formValues]);

  const handleReset = useCallback(() => {
    setFormValues(DEFAULT_FORM_VALUES);
    setSubmitError(null);
    setSubmitSuccess(null);
  }, []);

  return (
    <div className="flex gap-0 h-[calc(100vh-140px)] min-h-[600px]">
      {/* Left panel — structured form */}
      <div className="w-[45%] flex flex-col border-r border-gray-200 overflow-y-auto">
        <ArtifactWizardForm
          values={formValues}
          onChange={setFormValues}
          onSubmit={handleSubmit}
          onReset={handleReset}
          submitting={submitting}
          submitSuccess={submitSuccess}
          submitError={submitError}
        />
      </div>

      {/* Right panel — AI assistant */}
      <div className="w-[55%] flex flex-col bg-gray-50">
        <div className="px-4 py-3 border-b border-gray-200 bg-white">
          <h3 className="text-sm font-semibold text-gray-900">AI Assistant</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Describe what you want to build — the AI will fill in the form fields for you.
          </p>
        </div>
        <div className="flex-1 overflow-hidden">
          <CopilotChat
            instructions="You are an expert at creating Blitz AgentOS artifact definitions. When the user describes what they want to build, use the fill_form tool to populate form fields directly. Don't ask many clarifying questions — make reasonable assumptions and fill the form, then ask if adjustments are needed."
            labels={{
              title: "AI Artifact Assistant",
              initial: "Tell me what you want to build. For example: 'Create an email digest agent that fetches emails and sends a summary to Telegram every morning.'",
            }}
            className="h-full"
          />
        </div>
      </div>
    </div>
  );
}
```

**Step 2: TypeScript check**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
# Expected: 0 errors
```

**Step 3: Commit**

```bash
git add frontend/src/components/admin/artifact-wizard.tsx
git commit -m "feat(12-02): add ArtifactWizard split-panel core component"
```

---

## Task 7: Frontend — `artifact-wizard-name-check.tsx`

**Files:**
- Create: `frontend/src/components/admin/artifact-wizard-name-check.tsx`

**Context:** Debounced name availability check. After 300ms of no typing, calls `GET /api/admin/{type}/check-name?name={name}`. Shows ✓ available or ✗ taken inline. The catch-all proxy at `frontend/src/app/api/admin/[...path]/route.ts` forwards this automatically.

**Step 1: Write the component**

```typescript
"use client";
/**
 * NameAvailabilityBadge — debounced name conflict check for artifact wizard.
 * Calls GET /api/admin/{type}/check-name?name={name} after 300ms idle.
 */
import { useEffect, useState } from "react";
import type { ArtifactType } from "./artifact-wizard";

interface NameAvailabilityBadgeProps {
  name: string;
  artifactType: ArtifactType | null;
}

type CheckState = "idle" | "checking" | "available" | "taken" | "error";

const TYPE_TO_PATH: Record<ArtifactType, string> = {
  agent: "agents",
  tool: "tools",
  skill: "skills",
  mcp_server: "mcp-servers",
};

export function NameAvailabilityBadge({ name, artifactType }: NameAvailabilityBadgeProps) {
  const [state, setState] = useState<CheckState>("idle");

  useEffect(() => {
    if (!name.trim() || !artifactType) {
      setState("idle");
      return;
    }

    setState("checking");
    const timer = setTimeout(async () => {
      try {
        const path = TYPE_TO_PATH[artifactType];
        const res = await fetch(
          `/api/admin/${path}/check-name?name=${encodeURIComponent(name.trim())}`
        );
        if (!res.ok) { setState("error"); return; }
        const data = (await res.json()) as { available: boolean };
        setState(data.available ? "available" : "taken");
      } catch {
        setState("error");
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [name, artifactType]);

  if (state === "idle" || !name.trim()) return null;

  return (
    <span
      className={[
        "ml-2 text-xs font-medium",
        state === "available" ? "text-green-600" : "",
        state === "taken" ? "text-red-600" : "",
        state === "checking" ? "text-gray-400" : "",
        state === "error" ? "text-yellow-600" : "",
      ].filter(Boolean).join(" ")}
    >
      {state === "checking" && "Checking..."}
      {state === "available" && "✓ Available"}
      {state === "taken" && "✗ Name taken"}
      {state === "error" && "Could not check"}
    </span>
  );
}
```

**Step 2: TypeScript check**

```bash
pnpm exec tsc --noEmit
# Expected: 0 errors
```

**Step 3: Commit**

```bash
git add frontend/src/components/admin/artifact-wizard-name-check.tsx
git commit -m "feat(12-02): add NameAvailabilityBadge debounced name check component"
```

---

## Task 8: Frontend — `artifact-wizard-form.tsx` (full form fields)

**Files:**
- Create: `frontend/src/components/admin/artifact-wizard-form.tsx`

**Context:** Renders the left panel content. Sections: type selector, template picker, common fields (name with name-check badge, description, version), type-specific fields, JSON preview, action buttons. Imports `NameAvailabilityBadge` and `ArtifactWizardTemplates`. Permissions shown as a checklist, not free-text.

**All known permission strings** (from `backend/security/rbac.py`):
`chat`, `tool:email`, `tool:calendar`, `tool:project`, `crm:read`, `crm:write`, `tool:reports`, `workflow:create`, `workflow:approve`, `tool:admin`, `sandbox:execute`, `registry:manage`

**Step 1: Write the component**

```typescript
"use client";
/**
 * ArtifactWizardForm — left panel of the hybrid wizard.
 * Renders type selector, templates, fields, JSON preview, and action buttons.
 */
import { useRouter } from "next/navigation";
import type { ArtifactType, WizardFormValues } from "./artifact-wizard";
import { DEFAULT_FORM_VALUES } from "./artifact-wizard";
import { NameAvailabilityBadge } from "./artifact-wizard-name-check";
import { ArtifactWizardTemplates } from "./artifact-wizard-templates";

const ARTIFACT_TYPES: { value: ArtifactType; label: string; description: string }[] = [
  { value: "agent", label: "Agent", description: "AI sub-agent with tools" },
  { value: "tool", label: "Tool", description: "Single callable action" },
  { value: "skill", label: "Skill", description: "Reusable code skill" },
  { value: "mcp_server", label: "MCP Server", description: "External tool server" },
];

const ALL_PERMISSIONS = [
  "chat", "tool:email", "tool:calendar", "tool:project",
  "crm:read", "crm:write", "tool:reports", "workflow:create",
  "workflow:approve", "tool:admin", "sandbox:execute", "registry:manage",
];

const MODEL_ALIASES = [
  "blitz/master", "blitz/fast", "blitz/coder", "blitz/summarizer",
];

interface ArtifactWizardFormProps {
  values: WizardFormValues;
  onChange: React.Dispatch<React.SetStateAction<WizardFormValues>>;
  onSubmit: () => void;
  onReset: () => void;
  submitting: boolean;
  submitSuccess: string | null;
  submitError: string | null;
}

export function ArtifactWizardForm({
  values,
  onChange,
  onSubmit,
  onReset,
  submitting,
  submitSuccess,
  submitError,
}: ArtifactWizardFormProps) {
  const router = useRouter();

  function update(patch: Partial<WizardFormValues>) {
    onChange((prev) => ({ ...prev, ...patch }));
  }

  function togglePermission(perm: string) {
    const has = values.required_permissions.includes(perm);
    update({
      required_permissions: has
        ? values.required_permissions.filter((p) => p !== perm)
        : [...values.required_permissions, perm],
    });
  }

  // Compute the JSON preview
  const previewJson = JSON.stringify(
    Object.fromEntries(
      Object.entries(values).filter(([, v]) => v !== "" && v !== null && v !== false && !(Array.isArray(v) && v.length === 0))
    ),
    null,
    2
  );

  const canSubmit = !!values.artifact_type && !!values.name.trim() && !submitting;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Create Artifact</h2>
        <p className="text-sm text-gray-500 mt-1">
          Fill in the form or describe what you want in the chat — the AI will fill fields for you.
        </p>
      </div>

      {/* Section 1: Artifact Type */}
      <section>
        <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-2">
          Artifact Type <span className="text-red-500">*</span>
        </label>
        <div className="grid grid-cols-2 gap-2">
          {ARTIFACT_TYPES.map((t) => (
            <button
              key={t.value}
              onClick={() => update({ artifact_type: t.value })}
              className={[
                "p-3 rounded-lg border-2 text-left transition-colors",
                values.artifact_type === t.value
                  ? "border-blue-500 bg-blue-50"
                  : "border-gray-200 hover:border-blue-300",
              ].join(" ")}
            >
              <div className="text-sm font-medium text-gray-900">{t.label}</div>
              <div className="text-xs text-gray-500 mt-0.5">{t.description}</div>
            </button>
          ))}
        </div>
      </section>

      {/* Section 2: Templates */}
      {values.artifact_type && (
        <section>
          <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-2">
            Start From
          </label>
          <ArtifactWizardTemplates
            artifactType={values.artifact_type}
            onSelectTemplate={(template) => onChange((prev) => ({ ...DEFAULT_FORM_VALUES, ...template, artifact_type: prev.artifact_type }))}
            onReset={onReset}
          />
        </section>
      )}

      {/* Section 3: Common Fields */}
      <section className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Name <span className="text-red-500">*</span>
            <NameAvailabilityBadge name={values.name} artifactType={values.artifact_type} />
          </label>
          <input
            type="text"
            value={values.name}
            onChange={(e) => update({ name: e.target.value })}
            placeholder="e.g. email-digest-agent"
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Description</label>
          <textarea
            value={values.description}
            onChange={(e) => update({ description: e.target.value })}
            placeholder="What does this artifact do?"
            rows={3}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white resize-y"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Version</label>
          <input
            type="text"
            value={values.version}
            onChange={(e) => update({ version: e.target.value })}
            placeholder="1.0.0"
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white"
          />
        </div>
      </section>

      {/* Section 4: Type-specific fields */}
      {values.artifact_type === "agent" && (
        <section className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Model Alias</label>
            <select
              value={values.model_alias}
              onChange={(e) => update({ model_alias: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white"
            >
              {MODEL_ALIASES.map((alias) => (
                <option key={alias} value={alias}>{alias}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">System Prompt</label>
            <textarea
              value={values.system_prompt}
              onChange={(e) => update({ system_prompt: e.target.value })}
              placeholder="You are a specialized agent that..."
              rows={5}
              className="w-full px-3 py-2 text-sm font-mono border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white resize-y"
            />
          </div>
        </section>
      )}

      {(values.artifact_type === "tool" || values.artifact_type === "skill") && (
        <section className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-2">
              Required Permissions
            </label>
            <div className="grid grid-cols-2 gap-1.5 p-3 border border-gray-200 rounded-md bg-gray-50">
              {ALL_PERMISSIONS.map((perm) => (
                <label key={perm} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={values.required_permissions.includes(perm)}
                    onChange={() => togglePermission(perm)}
                    className="h-3.5 w-3.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-xs text-gray-700 font-mono">{perm}</span>
                </label>
              ))}
            </div>
          </div>
          <div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={values.sandbox_required}
                onChange={(e) => update({ sandbox_required: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-xs font-medium text-gray-700">Requires Docker sandbox</span>
            </label>
          </div>
          {values.artifact_type === "tool" && (
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Handler Module</label>
              <input
                type="text"
                value={values.handler_module}
                onChange={(e) => update({ handler_module: e.target.value })}
                placeholder="tools.email_tools"
                className="w-full px-3 py-2 text-sm font-mono border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white"
              />
            </div>
          )}
          {values.artifact_type === "skill" && (
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Entry Point</label>
              <input
                type="text"
                value={values.entry_point}
                onChange={(e) => update({ entry_point: e.target.value })}
                placeholder="skills.summarizer.run"
                className="w-full px-3 py-2 text-sm font-mono border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white"
              />
            </div>
          )}
        </section>
      )}

      {values.artifact_type === "mcp_server" && (
        <section className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              SSE URL <span className="text-red-500">*</span>
            </label>
            <input
              type="url"
              value={values.url}
              onChange={(e) => update({ url: e.target.value })}
              placeholder="http://mcp-service:8001"
              className="w-full px-3 py-2 text-sm font-mono border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Auth Token <span className="text-gray-400">(optional)</span>
            </label>
            <input
              type="password"
              value={values.auth_token}
              onChange={(e) => update({ auth_token: e.target.value })}
              placeholder="Bearer token if the server requires auth"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white"
            />
          </div>
        </section>
      )}

      {/* Section 5: JSON Preview */}
      {values.artifact_type && (
        <section>
          <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-2">
            JSON Preview
          </label>
          <pre className="p-3 bg-gray-900 text-green-300 text-xs rounded-md overflow-x-auto whitespace-pre-wrap font-mono max-h-48">
            {previewJson}
          </pre>
        </section>
      )}

      {/* Section 6: Actions */}
      {submitSuccess && (
        <div className="p-3 bg-green-50 border border-green-200 rounded text-sm text-green-700">
          {submitSuccess}{" "}
          <button
            onClick={() => router.push(`/admin/${values.artifact_type === "mcp_server" ? "mcp-servers" : (values.artifact_type ?? "agents") + "s"}`)}
            className="underline"
          >
            Go there →
          </button>
        </div>
      )}
      {submitError && (
        <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          {submitError}
        </div>
      )}
      <div className="flex items-center gap-3 pb-6">
        <button
          onClick={onSubmit}
          disabled={!canSubmit}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {submitting ? "Creating..." : "Create Artifact →"}
        </button>
        <button
          onClick={onReset}
          className="px-4 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-200 transition-colors"
        >
          Reset
        </button>
      </div>
    </div>
  );
}
```

**Step 2: TypeScript check**

```bash
pnpm exec tsc --noEmit
# Expected: 0 errors (or fix any type errors found)
```

**Step 3: Commit**

```bash
git add frontend/src/components/admin/artifact-wizard-form.tsx
git commit -m "feat(12-02): add ArtifactWizardForm left-panel component"
```

---

## Task 9: Frontend — `artifact-wizard-templates.tsx`

**Files:**
- Create: `frontend/src/components/admin/artifact-wizard-templates.tsx`

**Context:** Template picker shown in the "Start From" section. Hardcoded templates per artifact type. Clicking a template calls `onSelectTemplate` with pre-filled form values.

**Step 1: Write the component**

```typescript
"use client";
/**
 * ArtifactWizardTemplates — template card picker for the artifact wizard.
 * Each card pre-fills form values when clicked.
 */
import type { ArtifactType, WizardFormValues } from "./artifact-wizard";

type TemplateValues = Partial<Omit<WizardFormValues, "artifact_type">>;

interface Template {
  id: string;
  label: string;
  values: TemplateValues;
}

const TEMPLATES: Record<ArtifactType, Template[]> = {
  agent: [
    {
      id: "email-digest",
      label: "Email Digest Agent",
      values: {
        name: "email-digest-agent",
        description: "Fetches emails, summarizes them, and sends a digest to a specified channel.",
        model_alias: "blitz/master",
        system_prompt: "You are an email digest agent. Fetch the user's recent emails, summarize the key topics and action items, and deliver a concise digest.",
      },
    },
    {
      id: "project-status",
      label: "Project Status Agent",
      values: {
        name: "project-status-agent",
        description: "Retrieves project status and task updates from connected project management tools.",
        model_alias: "blitz/fast",
        system_prompt: "You are a project status agent. Retrieve current project status, upcoming deadlines, and blocked tasks. Present a clear summary.",
      },
    },
  ],
  tool: [
    {
      id: "rest-api",
      label: "REST API Tool",
      values: {
        name: "rest-api-tool",
        description: "Calls an external REST API endpoint and returns the response.",
        required_permissions: ["chat"],
        handler_module: "tools.rest_api_tool",
        sandbox_required: false,
      },
    },
    {
      id: "python-script",
      label: "Python Script Tool",
      values: {
        name: "python-script-tool",
        description: "Executes a Python script in a sandboxed environment.",
        required_permissions: ["sandbox:execute"],
        handler_module: "tools.python_script_tool",
        sandbox_required: true,
      },
    },
  ],
  skill: [
    {
      id: "summarizer",
      label: "Text Summarizer Skill",
      values: {
        name: "summarizer-skill",
        description: "Summarizes long text into key points using an LLM.",
        required_permissions: ["chat"],
        entry_point: "skills.summarizer.run",
        sandbox_required: false,
      },
    },
    {
      id: "data-extractor",
      label: "Data Extractor Skill",
      values: {
        name: "data-extractor-skill",
        description: "Extracts structured data from unstructured text using pattern matching.",
        required_permissions: ["chat"],
        entry_point: "skills.data_extractor.run",
        sandbox_required: false,
      },
    },
  ],
  mcp_server: [
    {
      id: "openapi-mcp",
      label: "OpenAPI MCP Server",
      values: {
        name: "openapi-mcp-server",
        description: "Exposes endpoints from an OpenAPI-described service as MCP tools.",
        url: "http://mcp-service:8001",
      },
    },
  ],
};

interface ArtifactWizardTemplatesProps {
  artifactType: ArtifactType;
  onSelectTemplate: (values: TemplateValues) => void;
  onReset: () => void;
}

export function ArtifactWizardTemplates({
  artifactType,
  onSelectTemplate,
  onReset,
}: ArtifactWizardTemplatesProps) {
  const templates = TEMPLATES[artifactType] ?? [];

  return (
    <div className="flex flex-wrap gap-2">
      <button
        onClick={onReset}
        className="px-3 py-1.5 text-xs font-medium border border-gray-300 rounded-md hover:bg-gray-50 text-gray-600 transition-colors"
      >
        Start Blank
      </button>
      {templates.map((t) => (
        <button
          key={t.id}
          onClick={() => onSelectTemplate(t.values)}
          className="px-3 py-1.5 text-xs font-medium border border-blue-200 bg-blue-50 rounded-md hover:bg-blue-100 text-blue-700 transition-colors"
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
```

**Step 2: TypeScript check + commit**

```bash
pnpm exec tsc --noEmit
git add frontend/src/components/admin/artifact-wizard-templates.tsx
git commit -m "feat(12-02): add ArtifactWizardTemplates hardcoded template picker"
```

---

## Task 10: Frontend — Update `/admin/create/page.tsx`

**Files:**
- Modify: `frontend/src/app/admin/create/page.tsx`

**Step 1: Replace the page to use the new wizard**

```typescript
/**
 * Artifact creation wizard — hybrid form + AI assistant.
 * See frontend/src/components/admin/artifact-wizard.tsx for implementation.
 */
import { ArtifactWizard } from "@/components/admin/artifact-wizard";

export default function ArtifactWizardPage() {
  return <ArtifactWizard />;
}
```

**Step 2: TypeScript check**

```bash
pnpm exec tsc --noEmit
# Expected: 0 errors
```

**Step 3: Commit**

```bash
git add frontend/src/app/admin/create/page.tsx
git commit -m "feat(12-02): replace /admin/create with hybrid ArtifactWizard"
```

---

## Task 11: Frontend — Add Clone button to artifact tables

**Files:**
- Modify: `frontend/src/components/admin/artifact-table.tsx`
- Modify: `frontend/src/components/admin/artifact-card-grid.tsx`

**Context:** The Clone button navigates to `/admin/create?clone_type={type}&clone_id={id}`. The wizard reads these query params on mount and pre-fills the form from the artifact's current values.

**Step 1: Read both files first**

```bash
cat frontend/src/components/admin/artifact-table.tsx | head -80
cat frontend/src/components/admin/artifact-card-grid.tsx | head -60
```

**Step 2: Add `onClone` prop and Clone button to `ArtifactTable`**

Find the props interface for `ArtifactTable`. Add:
```typescript
onClone?: (id: string, type: string) => void;
```

Find where action buttons are rendered per row (likely near the status patch button). Add a Clone button:
```tsx
{onClone && (
  <button
    onClick={() => onClone(item.id, artifactType)}
    className="text-xs text-blue-600 hover:underline"
  >
    Clone
  </button>
)}
```

**Step 3: Add `onClone` to `ArtifactCardGrid` similarly**

**Step 4: Update each admin artifact page to pass `onClone`**

In `frontend/src/app/admin/agents/page.tsx`, `tools/page.tsx`, `skills/page.tsx`, `mcp-servers/page.tsx`:

```typescript
import { useRouter } from "next/navigation";

// Inside the component:
const router = useRouter();
const handleClone = (id: string) => {
  router.push(`/admin/create?clone_type=agent&clone_id=${id}`);
};

// In JSX:
<ArtifactTable items={items} onPatchStatus={patchStatus} onActivateVersion={activateVersion} onClone={handleClone} />
```

**Step 5: Add clone pre-fill logic to `artifact-wizard.tsx`**

In `ArtifactWizard`, read query params on mount and fetch the artifact to pre-fill:

```typescript
import { useSearchParams } from "next/navigation";

// Inside WizardInner:
const searchParams = useSearchParams();

useEffect(() => {
  const cloneType = searchParams.get("clone_type") as ArtifactType | null;
  const cloneId = searchParams.get("clone_id");
  if (!cloneType || !cloneId) return;

  const typeToPath: Record<string, string> = {
    agent: "agents", tool: "tools", skill: "skills", mcp_server: "mcp-servers",
  };
  const path = typeToPath[cloneType];
  if (!path) return;

  void fetch(`/api/admin/${path}/${cloneId}`)
    .then((r) => r.json())
    .then((data: Record<string, unknown>) => {
      setFormValues((prev) => ({
        ...prev,
        artifact_type: cloneType,
        name: typeof data.name === "string" ? `${data.name}_copy` : prev.name,
        description: typeof data.description === "string" ? data.description : prev.description,
        version: typeof data.version === "string" ? data.version : prev.version,
      }));
    });
}, [searchParams]);
```

**Step 6: TypeScript check**

```bash
pnpm exec tsc --noEmit
# Fix any type errors found
```

**Step 7: Commit**

```bash
git add frontend/src/components/admin/artifact-table.tsx \
        frontend/src/components/admin/artifact-card-grid.tsx \
        frontend/src/app/admin/agents/page.tsx \
        frontend/src/app/admin/tools/page.tsx \
        frontend/src/app/admin/skills/page.tsx \
        frontend/src/app/admin/mcp-servers/page.tsx \
        frontend/src/components/admin/artifact-wizard.tsx
git commit -m "feat(12-02): add Clone button to artifact tables; wizard reads clone query params"
```

---

## Task 12: Final verification

**Step 1: Backend test suite**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
# Expected: 586+ passed (new tests add to count), 0 failed
```

**Step 2: TypeScript full build**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build
# Expected: 0 TypeScript errors, build succeeds
```

**Step 3: Fix any issues found, then commit**

```bash
git add -A
git commit -m "fix(12-02): address build and type check issues"
```

---

## Success Criteria Checklist

- [ ] `/admin/create` shows form panel (left, 45%) + AI chat panel (right, 55%)
- [ ] Selecting Agent/Tool/Skill/MCP Server shows type-specific fields below type selector
- [ ] Clicking a template card pre-fills name, description, and relevant type-specific fields
- [ ] Typing a name in the Name field shows "✓ Available" or "✗ Name taken" badge within 500ms
- [ ] Permissions field is a checkbox list (not free-text); all 12 known permissions shown
- [ ] Typing "create an email digest agent" in AI chat causes form fields to populate automatically
- [ ] Clone button on artifact rows navigates to `/admin/create` with form pre-filled from that artifact's values, name has `_copy` suffix
- [ ] Submitting creates the artifact; success message appears without page reload
- [ ] 586+ backend tests pass, TypeScript strict 0 errors, `pnpm run build` succeeds
