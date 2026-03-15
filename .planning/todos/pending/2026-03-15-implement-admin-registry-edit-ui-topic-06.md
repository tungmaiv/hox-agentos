---
created: 2026-03-15T06:51:58.504Z
title: "Implement Admin Registry Edit UI (Topic #06)"
area: ui
priority: high
target: v1.4-foundation
effort: 0.5 phase
existing_code: 40%
depends_on: []
design_doc: docs/enhancement/topics/06-admin-registry-edit-ui/00-specification.md
files:
  - frontend/src/app/(authenticated)/admin/agents/page.tsx
  - frontend/src/app/(authenticated)/admin/tools/page.tsx
  - frontend/src/app/(authenticated)/admin/mcp-servers/page.tsx
  - frontend/src/app/(authenticated)/admin/skills/[id]/page.tsx
  - backend/api/routes/registry.py
---

## Problem

Admin registry pages support listing, viewing details, creating, and changing status of agents/tools/MCP servers/skills. But there is no ability to **edit** existing entries (name, description, config fields) through the UI. Also missing: bottom pagination for large lists and MCP connection testing.

## What Exists (40%)

- List pages with search, filter by status, top pagination for agents, tools, MCP servers, skills
- Detail view pages (skills have Overview/Config/Scan Results tabs)
- Create forms (inline dialogs with form fields for each type)
- Status change (active/archived/draft) and delete actions
- `PUT /api/registry/{id}` backend endpoint exists

## What's Needed

- **Edit forms for existing entries** — dedicated edit page or inline edit UI for updating name, description, config
- **Type-specific edit forms** — conditional form fields based on entry type (tool handler, MCP URL/transport, agent config)
- **Bottom pagination controls** — duplicate pagination at bottom of large lists
- **MCP Connection Testing UI** — "Test Connection" button to verify MCP server connectivity with async feedback
- **Batch edit operations** — select-all, bulk status update

## Solution

Follow specification at `docs/enhancement/topics/06-admin-registry-edit-ui/00-specification.md`.
