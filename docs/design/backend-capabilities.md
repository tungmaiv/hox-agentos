<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# how we implement backend capabilities: Agents, skills, agent team, workflow, tool, mcp integration, I need detail design

Here’s a backend‑centric design for Blitz AgentOS that covers **agents, skills, agent teams, workflows, tools, and MCP integration** in detail, tailored to your FastAPI + LangGraph + Copilot Runtime stack.[^1][^2]

***

## 1. Core concepts and responsibilities

- **Agent**: LLM‑driven process with tools and memory, defined in Python (LangGraph/PydanticAI) and registered with Copilot Runtime.[^2]
- **Skill / Tool**: Executable capability.
    - Frontend Skill: UI/browser action (React, `useFrontendTool`).
    - Backend Tool: server function (Python `@tool`) with Pydantic schemas.[^1][^2]
- **Agent Team**: A master agent that delegates work to specialized sub‑agents, all orchestrated via LangGraph Deep Agent patterns.[^2]
- **Workflow**: User‑defined graph (from canvas) compiled to LangGraph `StateGraph`.
- **MCP Integration**: External toolsets exposed via Model Context Protocol, with ACL enforced in Copilot Runtime middleware.[^3][^2]

***

## 2. Agents and agent teams

### 2.1 Master agent (Blitz Orchestrator)

- Implemented via `create_deep_agent(...)` (LangGraph Deep Agent style).[^2]
- Responsibilities:
    - Understand user goals (from chat, canvas triggers, or scheduled jobs).
    - Plan multi‑step tasks (to‑do style list).
    - Delegate subtasks to sub‑agents (email, calendar, project, channel).
    - Call memory tools and MCP tools as needed.

Directory:

```text
backend/agents/
  master_agent.py
  graphs.py
  state/types.py
  subagents/
    email_agent.py
    calendar_agent.py
    project_agent.py
    channel_agent.py
```

Key elements in `master_agent.py`:

- System prompt: high‑level responsibilities and delegation rules.
- Tool list: includes generic tools (search, memory_search) and agent‑handoff tools (e.g., `call_email_agent`).
- Middleware:
    - Filesystem middleware (for local project context).
    - Sub‑agent middleware (spawn isolated loops for complex subtasks).
    - To‑do middleware (forces explicit planning and progress tracking).[^1][^2]


### 2.2 Sub‑agents (agent team)

Each sub‑agent:

- Has a narrow domain and its own tools + memory filters.
- Is invoked via either:
    - An explicit `@tool` wrapper that calls `run_email_agent(...)`.
    - A LangGraph node representing the sub‑agent.

Examples:

- `email_agent.py` – read/summarize emails, draft responses.
- `calendar_agent.py` – analyze schedules, propose times, create events.
- `project_agent.py` – interact with PM tools (MCP).
- `channel_agent.py` – decide which channel to notify and how.

In LangGraph, the **agent team** is a graph where the master agent node can transition to sub‑agent nodes depending on the plan.

***

## 3. Backend tools and skills

### 3.1 Split: Frontend Skills vs Backend Tools

From the stack design:[^1][^2]

- **Frontend Skills** (React / CopilotKit):
    - Implemented with `useFrontendTool` / `useCopilotAction`.
    - Examples: open modal, update canvas, scroll, copy to clipboard.
- **Backend Tools** (Python / LangGraph):
    - Implemented as `@tool` functions in `backend/tools/`.
    - Use Pydantic models for input/output validation.
    - Can:
        - Call databases.
        - Use MCP.
        - Touch filesystem (via sandbox).
        - Use internal APIs.


### 3.2 Backend tools structure

```text
backend/tools/
  email_tools.py
  calendar_tools.py
  project_tools.py
  memory_tools.py
  mcp_tools.py
  sandbox_tools.py
```

Example: `email_tools.py`

```python
from pydantic import BaseModel
from langgraph.prebuilt import tool

class FetchEmailsInput(BaseModel):
    user_id: str
    since: str

class EmailSummary(BaseModel):
    subject: str
    from_: str
    snippet: str

@tool
def fetch_emails(input: FetchEmailsInput) -> list[EmailSummary]:
    # Use internal email API / MCP server
    ...
```

Registration in `gateway/tool_registry.py` includes:

- `name`: `"email.fetch"`
- `description`
- `required_permissions`: `["tool:email.read"]`
- `sandbox_required`: `False` (or `True` for risky tools)
- `mcp_server` / `mcp_tool` if the tool is just a thin MCP wrapper.[^3][^2]


### 3.3 Backend “skills” like Claude Code

For capabilities similar to Claude Code/OpenClaw (filesystem, code execution):[^2][^1]

- Implement as backend tools with strict Pydantic schemas.
- Use Deep Agents:
    - Filesystem middleware: `read_file`, `write_file`, `ls`, `search`.
    - To‑do list middleware for multi‑step edits.
- Run any “execute code / shell” function inside the Docker sandbox (`sandbox_tools.py`), not on host.

Example: `sandbox_tools.py`

```python
class BashExecInput(BaseModel):
    command: str
    cwd: str | None = None

@tool
def bash_exec(input: BashExecInput) -> str:
    # Forward to sandbox executor; do NOT run directly
    return sandbox.executor.run_bash(input.command, cwd=input.cwd)
```


***

## 4. Workflow engine (LangGraph + canvas)

### 4.1 Data model \& backend representation

From earlier blueprint and canvas docs:[^4][^2]

- Frontend canvas saves workflow as JSON:
    - Nodes: `{ id, type, config, position }`
    - Edges: `{ source, target, condition }`

Stored in `core/models/workflow.py` as `definition_json`.

### 4.2 Compilation to LangGraph

`backend/agents/graphs.py`:

```python
from langgraph.graph import StateGraph
from .state.types import BlitzState

def compile_workflow_to_stategraph(definition_json: dict) -> StateGraph:
    graph = StateGraph(BlitzState)

    # 1. Create nodes
    for node in definition_json["nodes"]:
        if node["type"] == "agent":
            graph.add_node(node["id"], agent_node(node))
        elif node["type"] == "tool":
            graph.add_node(node["id"], tool_node(node))
        elif node["type"] == "mcp":
            graph.add_node(node["id"], mcp_node(node))
        elif node["type"] == "hitl":
            graph.add_node(node["id"], hitl_node(node))

    # 2. Add edges
    for edge in definition_json["edges"]:
        graph.add_edge(edge["source"], edge["target"], condition=edge.get("condition"))

    graph.set_entry_point(definition_json["entry_node"])
    return graph
```

Node builders:

- `agent_node` – wraps a sub‑agent invocation.
- `tool_node` – wraps a backend tool call.
- `mcp_node` – wraps MCP invocation.
- `hitl_node` – uses A2UI + `renderAndWait` to pause until user approves.[^4][^2]


### 4.3 Execution

- API: `POST /api/workflows/{id}/run`
    - Loads workflow, compiles StateGraph, instantiates with initial BlitzState.
    - Runs via LangGraph engine; can be synchronous or launched as a background job (e.g., for long workflows).
- Agent and tools are invoked within the LangGraph run according to edges and conditions.

***

## 5. MCP integration

### 5.1 MCP client and registry

`backend/mcp/client.py`:

- Discovers tools from external MCP servers.
- Provides an API:

```python
class MCPClient:
    def list_tools(self, server_name: str) -> list[MCPTool]:
        ...
    def call_tool(self, server_name: str, tool_name: str, params: dict) -> dict:
        ...
```

`backend/mcp/servers/`:

- Optional “local MCP servers” that expose internal systems (CRM, PM, docs DB).


### 5.2 Exposing MCP tools to agents

Two patterns:[^3][^2]

1. **Direct MCP tools**:
    - Register tools in `tool_registry` with `mcp_server` and `mcp_tool`.
    - A generic MCP wrapper tool reads these fields and forwards the call via `MCPClient`.
2. **Wrapped domain tools**:
    - Implement specific business tools (e.g., `crm.create_lead`) that internally call MCP.
    - Provides a stable internal API for agents even if MCP server names change.

Example wrapper `tools/mcp_tools.py`:

```python
class MCPCallInput(BaseModel):
    server: str
    tool: str
    params: dict

@tool
def mcp_call(input: MCPCallInput) -> dict:
    return mcp_client.call_tool(input.server, input.tool, input.params)
```


### 5.3 ACL for MCP tools

Using AG‑UI middleware as described in the ACL doc:[^3]

- Middleware inspects `TOOLCALL_START` events.
- If the tool is MCP‑backed, check `ToolAcl` with `mcp_server`/`mcp_tool`.
- Enforce:
    - Only allowed roles can call a given MCP tool (e.g., finance MCP only for finance roles).
- Frontend uses `available` flag for tools (via `useFrontendTool`) so unauthorized MCP tools are hidden from UI.[^3]

***

## 6. End‑to‑end execution flows

### 6.1 Chat with agent team

1. User sends message via web chat.
2. Frontend sends AG‑UI request → FastAPI runtime (JWT attached).
3. AG‑UI middleware:
    - Validates JWT and roles.
    - Attaches `user_context` to the request.[^5]
4. `master_agent.run_conversation`:
    - Fetches short‑term memory and relevant facts.
    - Plans tasks; may delegate to `email_agent`, `project_agent`.
    - Calls tools and MCP as needed.
5. Results streamed back via AG‑UI; A2UI components rendered for complex outputs.[^4][^2]

### 6.2 Workflow execution

1. User builds workflow on canvas and saves.
2. `definition_json` stored in `Workflow`.
3. User or scheduler triggers `run_workflow(workflow_id)`.
4. Backend compiles JSON → LangGraph `StateGraph`.
5. LangGraph executes nodes:
    - Agent nodes call sub‑agents.
    - Tool nodes call backend tools and MCP.
    - HITL nodes pause and await user input via A2UI.

### 6.3 MCP tool call with ACL

1. LLM chooses MCP tool (e.g., `mcp.crm.search_leads`).
2. AG‑UI sends `TOOLCALL_START` with tool name.
3. ACL middleware:
    - Extracts user roles from JWT.
    - Checks `ToolAcl` for that MCP tool.
    - If disallowed: respond with 403 and an A2UI error component.
4. If allowed: MCP wrapper calls server via `MCPClient` and returns data.

***

## 7. Tech stack recap for backend capabilities

- **Agents \& Agent Team**: LangGraph Deep Agents + PydanticAI in Python.[^2]
- **Skills**:
    - Frontend: CopilotKit hooks (`useFrontendTool`, `useCoAgent`).
    - Backend: Python `@tool` functions with Pydantic I/O models.[^1][^2]
- **Workflows**: LangGraph `StateGraph` compiled from canvas JSON; persisted in Postgres.
- **Tool Registry**: Central Python registry with security metadata and MCP mapping.[^2]
- **MCP**: `MCPClient` + `MCPAppsMiddleware` pattern, ACL‑guarded at Copilot Runtime.[^3][^2]
- **Security**: Keycloak JWT + AG‑UI middleware + Tool ACL.
- **Sandbox**: Docker for risky backend tools.

If you’d like, next step I can turn this into a concrete backend “spec” document (with module outlines and example code stubs) that your team can adopt as a starting implementation guide.

<div align="center">⁂</div>

[^1]: 17-Kien-truc-Tich-hop-Ky-nang-Backend-cho-AI-Agent.md

[^2]: 16-Kien-Truc-Trien-Khai-Agent-Va-Cong-Cu-Trong-Copilot-Kit.md

[^3]: 12-Trien-Khai-ACL-Cho-Cong-Cu-MCP-Trong-Copilot-Runtime.md

[^4]: 01-Kien-Truc-Ung-Dung-Agentic-Doanh-Nghiep-On-Premise.md

[^5]: 08-Tich-hop-Keycloak-vao-Bao-mat-Copilot-Runtime-va-Agentic-AI.md

