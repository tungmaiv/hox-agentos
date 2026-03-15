---
created: 2026-03-15T06:51:58.504Z
title: "Implement Runtime Permission Approval HITL (Topic #01)"
area: auth
priority: high
target: v1.4-foundation
effort: 1 phase
existing_code: 30%
depends_on: []
design_doc: docs/enhancement/topics/01-runtime-permission-approval/00-specification.md
files:
  - backend/core/models/tool_acl.py
  - backend/agents/node_handlers.py
  - backend/api/routes/workflows.py
  - backend/security/acl.py
---

## Problem

The 3-gate security model (JWT → RBAC → Tool ACL) exists but Gate 3 is binary allow/deny. There is no concept of temporal permissions, permission escalation requests, or auto-approval rules. Workflow HITL (pause/resume) exists for workflow execution, but NOT for permission elevation during agent conversations.

## What Exists (30%)

- Gate 3 (`ToolAcl` model): user_id, tool_name, allowed (bool), granted_by, created_at
- Workflow HITL: `_handle_hitl_approval_node()` with LangGraph `interrupt()` + checkpoint resumption
- HITL approval API: `GET /api/workflows/runs/pending-hitl`, `POST .../approve`, `POST .../reject`
- `WorkflowRun.status` includes `paused_hitl`

## What's Needed

- **`permission_requests` table** — queue for user requests for tool access
- **`auto_approve_rules` table** — rules engine for automatic permission escalation
- **Temporal constraints on ToolAcl** — `duration_type`, `expires_at`, `valid_until` fields
- **Permission approval UI** — frontend dialog for admin to approve/reject permission requests
- **User-initiated permission request flow** — API to submit requests, pending queue
- **Approval notification system** — notify admins of pending permission requests
- **Integration with existing Gate 3** — extend, not replace, current security model

## Solution

Follow specification at `docs/enhancement/topics/01-runtime-permission-approval/00-specification.md`.
