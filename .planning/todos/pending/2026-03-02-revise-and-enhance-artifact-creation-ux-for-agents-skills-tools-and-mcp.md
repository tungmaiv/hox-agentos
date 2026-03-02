---
created: 2026-03-02T03:46:09.001Z
title: Revise and enhance artifact creation UX for agents, skills, tools, and MCP
area: ui
files:
  - backend/api/routes/admin_agents.py
  - backend/api/routes/admin_tools.py
  - backend/api/routes/admin_skills.py
  - backend/api/routes/mcp_servers.py
  - backend/core/schemas/registry.py
  - frontend/src/app/admin/
---

## Problem

The current artifact creation flow (agents, skills, tools, MCP servers) is purely API-driven with no guided UX. Creating a new artifact requires:
- Knowing the exact JSON schema for each type
- Manually crafting `POST /api/admin/*` requests
- No validation feedback until submission
- No templates or starting points
- No contextual help (e.g., "what permissions are available?")

From today's exploration session, the current implementation is solid at the DB/API layer but the creation experience is raw and technical, making it inaccessible to non-developers.

## Solution

### Backend improvements

1. **Creation templates endpoint** — `GET /api/admin/{type}/templates`
   - Returns 2–3 starter templates per artifact type (e.g., "simple backend tool", "MCP-backed tool", "instructional skill")
   - Reduces blank-slate creation friction

2. **Dry-run / validate endpoint** — `POST /api/admin/{type}/validate` (already exists for skills, add for agents/tools/MCP)
   - Validate schema without persisting
   - Return field-level errors with suggestions

3. **Naming conflict check** — `GET /api/admin/{type}/check-name?name=my_tool`
   - Returns whether name is taken + suggestions for alternatives
   - Useful before form submission

4. **Clone endpoint** — `POST /api/admin/{type}/{id}/clone`
   - Creates a new version or copy from an existing artifact
   - Pre-fills all fields, user adjusts what changed

5. **Bulk import** — `POST /api/admin/{type}/bulk`
   - Accept array of definitions in one request
   - Returns per-item success/failure

### Frontend improvements (admin desk — `/admin`)

6. **Guided creation wizard** for each artifact type:
   - Step 1: Choose type/subtype (backend tool / MCP tool / sandbox tool)
   - Step 2: Fill form with inline validation and contextual help
   - Step 3: Preview generated definition JSON
   - Step 4: Submit → show result with direct link

7. **Template picker** — show starter templates from backend templates endpoint

8. **Live name availability check** — debounced check as user types the name field

9. **Permission picker** — dropdown of available permissions (from RBAC table) instead of free-text for `required_permissions`

10. **Handler module browser** — for backend tools/agents, show discovered Python modules and functions via a helper endpoint

### References
- Current admin routes: `backend/api/routes/admin_*.py`
- Current schemas: `backend/core/schemas/registry.py`
- Admin desk target: `frontend/src/app/admin/` (see todo: consolidate admin to /admin)
- Skills validate endpoint already exists: `POST /api/admin/skills/{id}/validate`
