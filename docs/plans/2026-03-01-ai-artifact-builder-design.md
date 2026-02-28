# AI-Assisted Artifact Builder — Design Document

**Date:** 2026-03-01
**Status:** Approved
**Phase:** 6 Enhancement (Extensibility Registries)

## Problem

Admin creation forms for agents, tools, skills, and MCP servers only collect basic fields (name, description). Complex fields like `routing_keywords`, `config_json`, `handler_module`, `input_schema`, `output_schema`, and `procedure_json` are missing from the UI. Admins must use curl/API to create fully-formed artifacts.

## Solution: Conversational Co-Agent (Approach A)

A new `/admin/create` page with a CopilotKit chat panel and live artifact preview. A LangGraph `artifact_builder` agent asks questions step-by-step, generates the artifact definition progressively, and the admin reviews/edits before saving via the existing admin API.

## Architecture

```
Frontend: /admin/create
  ├─ Chat Panel (CopilotChat, agent="artifact_builder")
  └─ Preview Panel (live JSON + rendered fields)
       └─ Save Button → POST /api/admin/registry/{type}

Backend: gateway/runtime.py
  ├─ Routes agent="artifact_builder" (Gate 2: registry:manage)
  └─ agents/artifact_builder.py (LangGraph)
       └─ ArtifactBuilderState → 4 nodes
```

Key: The builder agent is **separate** from `blitz_master`. Same CopilotKit runtime endpoint, same JWT auth flow, same AG-UI streaming protocol. The frontend saves via existing admin API — no new save endpoints.

## Backend: LangGraph Agent

### State

```python
class ArtifactBuilderState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    artifact_type: str | None          # "agent" | "tool" | "skill" | "mcp_server"
    artifact_draft: dict | None        # Partial/complete artifact JSON
    validation_errors: list[str]
    is_complete: bool
```

No `user_id` / memory nodes — this agent is a stateless builder.

### Graph

```
START → route_intent (conditional)
  ├→ gather_type           (if artifact_type not set)
  ├→ gather_details        (if type set but draft incomplete)
  ├→ refine                (if user asks to change something)
  └→ validate_and_present  (if draft looks ready)
       ├→ valid: is_complete=true → END
       └→ invalid: validation_errors populated → gather_details
```

### Nodes

1. **`route_intent`** — Conditional edge. Reads state to decide next node.

2. **`gather_type`** — AI asks artifact type if not specified. Sets `artifact_type`.

3. **`gather_details`** — Main node. Type-specific questions:
   - Agent: "What does it do? What routing keywords?"
   - Tool: "Backend, MCP, or sandbox? What inputs/outputs?"
   - Skill: "Instructional or procedural? Slash command?"
   - MCP Server: "Server URL? Auth token needed?"

   Updates `artifact_draft` progressively after each answer.

4. **`validate_and_present`** — Validates `artifact_draft` against Pydantic schema (`AgentDefinitionCreate`, `ToolDefinitionCreate`, `SkillDefinitionCreate`, `McpServerCreate`). Valid → `is_complete=true`. Invalid → populates `validation_errors`, loops back.

### Validation Rules

- Handler modules must start with allowed prefixes (`tools.`, `agents.`, `skills.`, `mcp.`, `gateway.`)
- `mcp_server_id` must reference an existing MCP server row
- Skill `procedure_json` required for procedural type, `instruction_markdown` for instructional
- Name + version must be unique (checked at save time by existing API)

### Registration

```python
# gateway/runtime.py
_builder_agent = LangGraphAGUIAgent(
    name="artifact_builder",
    description="AI-assisted artifact definition builder",
    graph=create_artifact_builder_graph(),
)

# Route by agentId; require registry:manage for builder
```

### LLM

Uses `get_llm("blitz/master")` with type-specific system prompts containing schema field definitions, examples from seed data, and constraint rules.

## Frontend: /admin/create

### Layout

Split panel — chat (45% left), preview (55% right).

### Component Tree

```
/admin/create/page.tsx (Server Component)
  └─ ArtifactBuilderClient.tsx ("use client")
       └─ CopilotKit (runtimeUrl="/api/copilotkit", agent="artifact_builder")
            └─ BuilderInner.tsx
                 ├─ CopilotChat (left — conversational AI)
                 └─ ArtifactPreview (right)
                      ├─ TypeBadge
                      ├─ FieldsView (rendered key-value pairs)
                      ├─ JsonEditor (collapsible raw JSON)
                      ├─ ValidationErrors
                      └─ SaveButton
```

### Key Behaviors

- **Live preview:** `useCoAgentStateRender` subscribes to `artifact_draft` — preview updates on every AI turn.
- **Save:** Enabled when `is_complete === true` and `validation_errors` empty. Calls `POST /api/admin/registry/{artifact_type}`. On success → redirect to list page.
- **Edit JSON:** Toggle to raw JSON textarea. Manual edits trigger re-validation via AI message.
- **No persistence:** No `threadId` — each visit starts fresh. No conversation history saved.
- **Navigation guard:** `beforeunload` dialog if `artifact_draft` is non-null and unsaved.

## Data Flow

```
1. Admin opens /admin/create
2. CopilotKit mounts → agent/run → route_intent → gather_type
3. AI asks "What type?" → Admin answers
4. route_intent → gather_details → AI asks type-specific questions
5. Each round: artifact_draft grows, preview updates live
6. After 2-4 rounds → validate_and_present → is_complete=true
7. Admin clicks Save → POST /api/admin/registry/{type} → 201 → redirect
```

State progression:
```
Round 1: { artifact_type: null,   artifact_draft: null,              is_complete: false }
Round 2: { artifact_type: "tool", artifact_draft: { name: "..." },   is_complete: false }
Round 3: { artifact_type: "tool", artifact_draft: { name, handler }, is_complete: false }
Round 4: { artifact_type: "tool", artifact_draft: { <all fields> },  is_complete: true  }
```

## Error Handling

### AI-Side
- Invalid handler module → validation rejects, AI fixes
- Non-existent MCP server → validation queries DB, rejects with error
- Malformed JSON schema → Pydantic catches, `validation_errors` populated
- Skill type mismatch → `@model_validator` catches, loops back

### Frontend
- 409 duplicate → toast with suggestion to change name/version
- 422 validation → toast with details (rare — backend pre-validates)
- 403 permission lost → redirect to login
- Network error → CopilotKit retry, then "Connection lost" message
- Unsaved navigation → browser confirmation dialog

### Backend
- LLM failure → node catches, returns friendly AI message, no crash
- Permission revoked → next agent/run returns 403
- Double validation: agent validates during generation + admin API validates on save

## Testing

### Backend Unit Tests (`tests/agents/test_artifact_builder.py`)
- Route intent logic for each state combination
- Gather details builds draft progressively
- Validate accepts valid schemas, rejects invalid ones
- Handler module prefix validation
- MCP server existence check

### Backend Integration Tests (`tests/gateway/test_runtime.py`)
- Runtime info includes `artifact_builder` agent
- Builder requires `registry:manage` permission (403 for non-admin)
- Builder allowed for admin users

### Frontend
- TypeScript type checking (`pnpm exec tsc --noEmit`)
- Build verification (`pnpm run build`)

### Manual UAT Checklist
1. Create tool via AI conversation → verify in /admin/tools list
2. Create agent → verify routing_keywords populated
3. Create skill (both types) → verify procedure_json / instruction_markdown
4. Create MCP server → verify in /admin/mcp-servers list
5. Non-admin access → verify 403
6. Navigate away unsaved → verify confirmation dialog
7. Edit JSON manually → re-validate → save

## Scope Boundaries

**In scope:**
- New LangGraph agent with 4 nodes
- New frontend page with split-panel layout
- Registration in existing CopilotKit runtime
- Security gate (registry:manage)

**Out of scope (deferred):**
- Fixing existing admin forms (missing fields) — AI builder replaces the need
- Artifact import/export
- Artifact versioning UI
- Artifact dependency graphs
- Template catalog (Approach C — rejected)
