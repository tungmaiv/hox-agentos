---
created: 2026-03-02T03:46:09.001Z
title: Add skill to assess app API endpoints and auto-generate MCP server
area: api
files:
  - backend/tools/
  - backend/mcp/
  - infra/mcp-crm/main.py
  - backend/core/models/mcp_server.py
  - backend/api/routes/mcp_servers.py
---

## Problem

Creating an MCP server for an existing application requires:
1. Manually reading the app's API docs or OpenAPI spec
2. Hand-writing a FastAPI MCP server with correct `tools/list` and `tools/call` handlers
3. Adding to docker-compose, registering in AgentOS
4. Repeat for every API endpoint worth exposing

This is tedious and error-prone. There is no automated path from "I have an API" to "I have an MCP server".

## Solution

### Skill: `api-to-mcp` (procedural skill)

A multi-step procedural skill that:

**Step 1 — Discover API spec**
- Accept input: `base_url` (e.g., `https://myapp.com`) or `openapi_url` (e.g., `https://myapp.com/openapi.json`)
- If only `base_url` given: probe common spec paths (`/openapi.json`, `/swagger.json`, `/api-docs`, `/docs`)
- Fetch and parse OpenAPI 3.x or Swagger 2.0 spec

**Step 2 — Assess & filter endpoints**
- Parse all endpoints from spec
- Score each endpoint for MCP suitability:
  - Prefer GET (read) and POST (action) endpoints
  - Skip auth/login/token endpoints (security boundary)
  - Skip bulk/streaming endpoints (not suitable for tool calls)
- Present filtered list to user for confirmation (which endpoints to expose)

**Step 3 — Generate MCP server code**
- Use LLM (`blitz/coder`) to generate a FastAPI MCP server:
  - `tools/list` handler returning selected endpoints as tool definitions
  - `tools/call` handler routing to correct API endpoint with arg mapping
  - Auth header injection (Bearer token from AgentOS credential store)
- Write generated code to `infra/mcp-{app_name}/main.py`
- Generate `Dockerfile` and `requirements.txt`

**Step 4 — Register and activate**
- Add service to `docker-compose.yml` for the new MCP server
- Call `POST /api/admin/mcp-servers` to register in AgentOS
- Trigger `MCPToolRegistry.refresh()` to auto-discover and register tools
- Report: list of tools now available with their names

### Backend support tools needed

- `tool: api_spec_fetcher` — fetches and parses OpenAPI/Swagger JSON from a URL
- `tool: mcp_code_generator` — generates MCP server code from endpoint list (LLM-backed)
- `tool: docker_compose_updater` — appends new service to docker-compose.yml safely

### Input schema

```json
{
  "base_url": "https://myapp.com",
  "openapi_url": "https://myapp.com/openapi.json",  // optional override
  "app_name": "myapp",                               // used for naming
  "auth_type": "bearer" | "api_key" | "none",
  "endpoints_filter": ["GET /projects", "POST /tasks"]  // optional manual selection
}
```

### References
- Example MCP server: `infra/mcp-crm/main.py`
- MCP registration: `POST /api/admin/mcp-servers`
- MCP discovery: `backend/mcp/registry.py` → `MCPToolRegistry.refresh()`
- Tool for import: builds on existing `POST /api/admin/skills/import` pattern
