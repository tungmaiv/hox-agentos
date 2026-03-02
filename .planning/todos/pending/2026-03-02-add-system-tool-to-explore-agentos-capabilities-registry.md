---
created: 2026-03-02T03:46:09.011Z
title: Add system tool to explore AgentOS capabilities registry
area: api
files:
  - backend/tools/
  - backend/gateway/tool_registry.py
  - backend/core/models/agent_definition.py
  - backend/core/models/tool_definition.py
  - backend/core/models/skill_definition.py
  - backend/core/models/mcp_server.py
---

## Problem

When an agent (or user) wants to create a new Agent, Tool, Skill, or MCP server, they have no way to query the current registry state from inside a conversation. This leads to:
- Duplicate registrations (same tool name already exists)
- Naming inconsistencies (not matching existing conventions)
- No awareness of what's already available before building something new

There is no "introspection tool" that lets the master agent or a user ask: "What agents/tools/skills/MCP servers are currently registered?"

## Solution

Create a `system.capabilities` built-in tool in `backend/tools/system_tools.py`:

```python
async def explore_capabilities(
    artifact_type: Literal["agents", "tools", "skills", "mcp_servers", "all"],
    status_filter: str = "active",
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    """Return registry contents for the requested artifact type(s)."""
```

### Tool behavior:
- **`artifact_type="all"`** — returns summary counts + names for all four types
- **`artifact_type="tools"`** — returns name, display_name, handler_type, description, version for each active tool
- **`artifact_type="agents"`** — returns name, display_name, routing_keywords, handler_module
- **`artifact_type="skills"`** — returns name, skill_type, slash_command, description
- **`artifact_type="mcp_servers"`** — returns name, url, status, last_seen_at

### Registration:
- Register as `system.capabilities` in tool_definitions via seed/migration
- `required_permissions: ["system:read"]` — all authenticated users can call it
- `handler_type: "backend"`

### Use cases:
1. User: "What tools do I have available?" → agent calls `system.capabilities(artifact_type="tools")`
2. User: "Create a new email tool" → agent calls capabilities first to check for naming conflicts
3. Admin: building new MCP server → queries existing MCP servers to avoid port/name conflicts
4. Master agent: uses capability list to decide which sub-agent to route to

### Frontend integration (optional):
- Display result as a structured capability browser card in the chat UI via A2UI
