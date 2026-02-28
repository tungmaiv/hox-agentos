# Phase 6: Extensibility Registries — Design Document

> **Date:** 2026-02-28
> **Status:** Approved
> **Phase:** 6 (Extensibility Registries)
> **Depends on:** Phases 4 and 5 (complete)

---

## 1. Goal

Admins and developers can manage the platform's agents, tools, skills, and MCP servers as runtime artifacts through database-backed registries with granular permissions. Skills are invokable via `/command` in chat and can be imported from trusted external repositories with security scanning.

## 2. Success Criteria

1. Every agent, tool, skill, and MCP server has a database registry entry with name, description, version, status, and required permissions
2. Admin can add, edit, disable, and re-enable any artifact via API — disabled artifacts are unavailable to agents
3. Developer can register a new tool or MCP server and it becomes available to authorized users without restarting the backend
4. Permissions can be assigned per artifact per role
5. Removing an artifact from the registry prevents all future invocations; existing running workflows complete gracefully
6. Users can invoke skills via `/command` in chat with streaming progress
7. Skills can be imported from external AgentSkills-compatible repositories with security scoring and admin review

## 3. Requirements Traced

| Req ID | Description | Covered by |
|--------|-------------|------------|
| EXTD-01 | DB registry entries for all artifact types | Section 4 (Data Model) |
| EXTD-02 | Admin CRUD for artifacts | Section 5 (APIs) |
| EXTD-03 | Hot-registration without restart | Section 7 (Runtime Integration) |
| EXTD-04 | Per-artifact per-role permissions | Section 6 (RBAC Migration) |
| EXTD-05 | Graceful artifact removal | Section 7.4 (Graceful Shutdown) |
| EXTD-06 | Skill runtime and provisioning | Sections 8 and 9 |

---

## 4. Data Model

### 4.1 Architecture Choice: Per-Type Registry Tables

Separate table per artifact type (`agent_definitions`, `tool_definitions`, `skill_definitions`) plus the existing `mcp_servers` table. Shared `artifact_permissions` and `role_permissions` tables handle authorization.

**Rationale:** Each type has distinct columns (tools need `sandbox_required`, MCP needs `url`+`auth_token`, skills need `procedure_json`). Per-type tables give DB-level type safety. We have exactly 4 artifact types — a unified table adds abstraction without benefit. The existing `mcp_servers` table evolves rather than being replaced.

### 4.2 New Tables

#### `agent_definitions`

Replaces hardcoded agent wiring in `create_master_graph()`.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `name` | TEXT UNIQUE | e.g., `email_agent`, `calendar_agent` |
| `display_name` | TEXT | Human-readable: "Email Agent" |
| `description` | TEXT | |
| `version` | TEXT | Semver |
| `status` | ENUM(active, disabled, deprecated) | |
| `handler_module` | TEXT | Python import path: `agents.subagents.email_agent` |
| `handler_function` | TEXT | Entry point: `email_agent_node` |
| `routing_keywords` | JSONB | Keywords for `_pre_route()`: `["email", "inbox", "mail"]` |
| `config_json` | JSONB | Agent-specific config (model alias, max tokens) |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

#### `tool_definitions`

Replaces in-process `_registry` dict in `gateway/tool_registry.py`.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `name` | TEXT UNIQUE | e.g., `email.fetch_inbox` |
| `display_name` | TEXT | "Fetch Inbox" |
| `description` | TEXT | |
| `version` | TEXT | |
| `status` | ENUM(active, disabled, deprecated) | |
| `handler_type` | ENUM(backend, mcp, sandbox) | Dispatch strategy |
| `handler_module` | TEXT NULL | For backend tools |
| `handler_function` | TEXT NULL | For backend tools |
| `mcp_server_id` | UUID FK -> mcp_servers NULL | For MCP tools |
| `mcp_tool_name` | TEXT NULL | Tool name on MCP server |
| `sandbox_required` | BOOL DEFAULT false | |
| `input_schema` | JSONB NULL | JSON Schema for validation |
| `output_schema` | JSONB NULL | |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

#### `skill_definitions`

New concept — multi-step procedures and instructional capabilities.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `name` | TEXT UNIQUE | e.g., `morning_digest` |
| `display_name` | TEXT | "Morning Digest" |
| `description` | TEXT | AgentSkills-style: trigger condition |
| `version` | TEXT | |
| `status` | ENUM(active, disabled, deprecated, pending_review, rejected) | |
| `skill_type` | ENUM(instructional, procedural) | See Section 8.1 |
| `slash_command` | TEXT UNIQUE NULL | `/morning_digest` — NULL = not slash-invokable |
| `instruction_markdown` | TEXT NULL | For instructional skills (AgentSkills body) |
| `procedure_json` | JSONB NULL | For procedural skills (step pipeline) |
| `input_schema` | JSONB NULL | What the user must provide |
| `output_schema` | JSONB NULL | What the skill returns |
| `source_type` | ENUM(builtin, admin_created, imported, user_created) | |
| `source_url` | TEXT NULL | Import origin URL |
| `security_score` | INT NULL | 0-100, computed at import |
| `security_report` | JSONB NULL | Full scan results |
| `reviewed_by` | UUID NULL | Admin who approved |
| `reviewed_at` | TIMESTAMPTZ NULL | |
| `created_by` | UUID NULL | User who created it |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

#### `mcp_servers` — Evolved (existing table)

Add columns:

| Column | Type | Notes |
|--------|------|-------|
| `version` | TEXT NULL | **New** |
| `display_name` | TEXT NULL | **New** |
| `status` | ENUM(active, disabled, deprecated) | **New** — replaces `is_active` boolean |

Migrate `is_active=true` -> `status='active'`, `is_active=false` -> `status='disabled'`.

#### `artifact_permissions`

Per-artifact per-role permission overrides.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `artifact_type` | ENUM(agent, tool, skill, mcp_server) | |
| `artifact_id` | UUID | Polymorphic — no FK (same pattern as user_id) |
| `role` | TEXT | Keycloak role name |
| `allowed` | BOOL DEFAULT true | |
| UNIQUE | `(artifact_type, artifact_id, role)` | |

No-row = default allow (same pattern as `tool_acl`). Explicit `allowed=false` = deny.

#### `role_permissions`

Replaces hardcoded `ROLE_PERMISSIONS` dict in `security/rbac.py`.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `role` | TEXT | e.g., `employee`, `it-admin` |
| `permission` | TEXT | e.g., `chat`, `tool:email`, `registry:manage` |
| UNIQUE | `(role, permission)` | |

Seeded with exact values from current hardcoded dict.

### 4.3 Skill Procedure JSON Schema

For `skill_type = 'procedural'`:

```json
{
  "schema_version": "1.0",
  "steps": [
    {
      "id": "fetch",
      "type": "tool",
      "tool": "email.fetch_inbox",
      "params": { "max_results": 10, "label": "INBOX" },
      "description": "Fetch recent emails"
    },
    {
      "id": "summarize",
      "type": "llm",
      "model_alias": "blitz/fast",
      "prompt_template": "Summarize these emails concisely:\n\n{{fetch.output}}",
      "description": "Summarize email content"
    },
    {
      "id": "check",
      "type": "condition",
      "expression": "len({{fetch.output}}) > 0",
      "true_step": "summarize",
      "false_step": null,
      "description": "Skip if no emails"
    }
  ],
  "output": "{{summarize.output}}"
}
```

Step types:
- **`tool`** — calls a registered tool through 3-gate security
- **`llm`** — calls an LLM via `get_llm()` with a prompt template
- **`condition`** — branch based on previous step output

Variable references (`{{step_id.output}}`) chain data between steps. Simple string interpolation — no Jinja2.

---

## 5. API Layer

### 5.1 Admin Registry APIs (require `registry:manage` permission)

#### Agents — `/api/admin/agents`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/agents` | List all agent definitions |
| POST | `/api/admin/agents` | Register new agent |
| GET | `/api/admin/agents/{id}` | Get agent details |
| PUT | `/api/admin/agents/{id}` | Update agent |
| PATCH | `/api/admin/agents/{id}/status` | Quick enable/disable |

#### Tools — `/api/admin/tools`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/tools` | List all tool definitions |
| POST | `/api/admin/tools` | Register new backend tool |
| GET | `/api/admin/tools/{id}` | Get tool details |
| PUT | `/api/admin/tools/{id}` | Update tool |
| PATCH | `/api/admin/tools/{id}/status` | Quick enable/disable |

#### Skills — `/api/admin/skills`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/skills` | List all skill definitions |
| POST | `/api/admin/skills` | Create new skill |
| GET | `/api/admin/skills/{id}` | Get skill details |
| PUT | `/api/admin/skills/{id}` | Update skill |
| PATCH | `/api/admin/skills/{id}/status` | Quick enable/disable |
| POST | `/api/admin/skills/{id}/validate` | Dry-run validate procedure JSON |
| POST | `/api/admin/skills/import` | Import from URL/ClawHub/paste |
| GET | `/api/admin/skills/pending` | List skills awaiting review |
| POST | `/api/admin/skills/{id}/review` | Approve/reject with decision |
| GET | `/api/admin/skills/{id}/security-report` | View security scan results |

#### MCP Servers — existing `/api/admin/mcp-servers` evolved

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/mcp-servers/{id}/health` | **New** — check server reachability |
| PATCH | `/api/admin/mcp-servers/{id}/status` | **New** — enable/disable |

#### Permissions — `/api/admin/permissions`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/permissions/roles` | List all role-permission mappings |
| PUT | `/api/admin/permissions/roles/{role}` | Set permissions for a role |
| GET | `/api/admin/permissions/artifacts/{type}/{id}` | Get artifact permission overrides |
| PUT | `/api/admin/permissions/artifacts/{type}/{id}` | Set per-role permissions for artifact |

### 5.2 User-Facing APIs (require `chat` permission)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/skills` | List skills available to current user (filtered by role) |
| POST | `/api/skills/{name}/run` | Execute a skill by name |
| GET | `/api/tools` | List tools available to current user |

---

## 6. RBAC Migration

### 6.1 Current State

`ROLE_PERMISSIONS` is a hardcoded Python dict in `security/rbac.py`:

```
employee:  chat, tool:email, tool:calendar, tool:project, crm:read
manager:   + crm:write, tool:reports, workflow:create
team-lead: + workflow:approve
it-admin:  + tool:admin, sandbox:execute, registry:manage
executive: chat, tool:reports
```

### 6.2 Target State

All role-permission mappings stored in `role_permissions` DB table. The Alembic migration seeds the table with the exact values from the current hardcoded dict.

### 6.3 Updated `has_permission()`

```python
# Before: hardcoded dict
def has_permission(user: UserContext, permission: str) -> bool:
    for role in user["roles"]:
        if permission in ROLE_PERMISSIONS.get(role, set()):
            return True
    return False

# After: DB-backed with in-process cache (60s TTL)
async def has_permission(user: UserContext, permission: str) -> bool:
    role_perms = await _get_role_permissions_cached()  # 60s TTL
    for role in user["roles"]:
        if permission in role_perms.get(role, set()):
            return True
    return False
```

Admin write endpoints invalidate the cache immediately.

### 6.4 New Artifact Permission Check (Gate 2.5)

```python
async def check_artifact_permission(
    user: UserContext,
    artifact_type: ArtifactType,
    artifact_id: UUID,
) -> bool:
    """Check if user's roles allow access to a specific artifact.

    No row = default allow (same pattern as tool_acl).
    Explicit allowed=False = deny.
    """
```

### 6.5 Updated Security Gate Model

1. **Gate 1:** JWT validation (unchanged)
2. **Gate 2:** RBAC permission check (now DB-backed via `role_permissions`)
3. **Gate 2.5:** Artifact permission check (new — `artifact_permissions` table)
4. **Gate 3:** Tool ACL per-user override (unchanged — `tool_acl` table)

Gate 2.5 fires when dispatching to a specific artifact. It checks "does this user's role have access to this specific artifact?"

### 6.6 Backward Compatibility

- Seed migration inserts exact same permissions as current hardcoded dict
- All existing tests pass (same permissions, just from DB)
- Empty DB = all denials (fail-secure)
- `tool_acl` (Gate 3) unchanged

---

## 7. Runtime Integration

### 7.1 Tool Registry (`gateway/tool_registry.py`)

**Before:** In-process dict `_registry`, hardcoded CRM tools + startup MCP discovery.

**After:**
- `register_tool()` upserts into `tool_definitions` table
- `get_tool()` reads from in-process cache populated from DB (60s TTL)
- `list_tools()` returns only `status='active'` tools
- `MCPToolRegistry.refresh()` upserts into `tool_definitions` instead of `_registry` dict
- Admin disable -> cache invalidated -> tool immediately unavailable

### 7.2 Agent Registry (`agents/master_agent.py`)

**Before:** Hardcoded nodes in `create_master_graph()`, hardcoded keyword sets in `_pre_route()`.

**After:**
- `create_master_graph()` queries `agent_definitions WHERE status='active'`
- Dynamically imports `handler_module.handler_function` for each active agent
- Routing keywords loaded from `routing_keywords` column
- Graph rebuilt per-request (already the existing pattern) — no restart needed

### 7.3 MCP Server Registry

**Before:** DB-backed `mcp_servers` + in-process `_clients` cache.

**After:**
- `is_active` column replaced by `status` enum
- `MCPToolRegistry.refresh()` respects status field
- New health-check endpoint verifies reachability
- Delete/disable correctly evicts from `_clients` cache (fixes current gap)

### 7.4 Graceful Artifact Shutdown

**Disable != Delete.** Admin sets `status='disabled'` (soft). DB row persists.

Lifecycle: `active` -> `disabled` -> `deprecated` -> hard `DELETE` (with `force=true`).

When admin disables an artifact, the API returns a count of active workflow runs that reference it. Admin can choose to wait or force-disable.

Tool/agent dispatch checks status at invocation time. A running workflow's next node will fail if the tool/agent was disabled mid-execution — this is acceptable because the workflow records the failure and can be retried.

---

## 8. Skill System

### 8.1 Skill Types

| Type | Format | How it works |
|------|--------|-------------|
| **Instructional** | `instruction_markdown` (TEXT) | Markdown instructions injected into agent context. Agent reads them and autonomously decides tool calls. Compatible with AgentSkills standard. |
| **Procedural** | `procedure_json` (JSONB) | Deterministic step-by-step pipeline. Each tool call explicit. No LLM discretion on which tools to call. |

Both are valuable:
- **Instructional** = flexible, adapts to context, less predictable
- **Procedural** = deterministic, auditable, rigid

### 8.2 Skill Invocation Flow

```
User types "/morning_digest" in chat
    |
CopilotKit sends message to master agent
    |
master_agent._pre_route() detects "/" prefix
    |
Queries: skill_definitions WHERE slash_command = '/morning_digest' AND status = 'active'
    |
Checks artifact_permissions: is user's role allowed?
    |
Dispatches based on skill_type:
    |
    +-- instructional: inject instruction_markdown into agent context,
    |   let agent execute autonomously with tool access
    |
    +-- procedural: call SkillExecutor.run(skill, user_context, user_input)
        process steps sequentially, stream progress via AG-UI
```

### 8.3 SkillExecutor (Procedural Skills)

```python
class SkillExecutor:
    """Runs a skill's procedure_json as a sequence of steps."""

    async def run(
        self,
        skill: SkillDefinition,
        user_context: UserContext,
        user_input: dict | None = None,
    ) -> SkillResult:
        context = StepContext(user_input=user_input, outputs={})

        for step in skill.procedure_json["steps"]:
            match step.get("type", "tool"):
                case "tool":
                    result = await self._run_tool_step(step, context, user_context)
                case "llm":
                    result = await self._run_llm_step(step, context)
                case "condition":
                    result = await self._run_condition_step(step, context)
            context.outputs[step["id"]] = result

        return SkillResult(
            output=self._resolve_template(skill.procedure_json["output"], context),
            step_outputs=context.outputs,
        )
```

Design decisions:
- **Sequential execution only** — no parallel branches in v1. If a skill needs parallelism, use a workflow (canvas).
- **Tool steps go through 3-gate security** — the skill executor calls `check_tool_acl()` for each tool step, using the invoking user's context. No privilege escalation.
- **LLM steps use model aliases** — `get_llm(step["model_alias"])` ensures all calls go through LiteLLM proxy.
- **Variable resolution** — `{{step_id.output}}` resolved by simple string interpolation. No Jinja2.
- **Error handling** — if a step fails, the skill stops and returns a partial result with the error. No retry in v1.
- **Streaming** — emits AG-UI events as steps complete for real-time progress (e.g., "Fetching emails...", "Summarizing...").
- **Audit logging** — each step logs via `get_audit_logger()` with `skill_name`, `step_id`, `tool_name`, `user_id`, `duration_ms`.

### 8.4 Skill vs. Workflow

| Aspect | Skill | Workflow |
|--------|-------|---------|
| Invocation | `/command` in chat or agent delegation | Canvas trigger (cron, webhook, manual) |
| Complexity | Linear sequence, 2-10 steps | Arbitrary graph with branches, loops, HITL |
| Editing | Admin API (JSON procedure) or imported | Visual canvas (React Flow) |
| Runtime | `SkillExecutor` (lightweight) | LangGraph `StateGraph` (full graph engine) |
| State | Ephemeral — no persistence | Persisted via checkpointer |
| Target user | End user running quick commands | Power user building automations |

---

## 9. Skill Provisioning Pipeline

### 9.1 Skill Sources

| Source | Trust Level | Auto-approve? |
|--------|-------------|---------------|
| **Built-in** (seed migration) | Fully trusted | Yes |
| **Admin-created** (via API) | Trusted | Yes |
| **Imported from trusted repo** | Conditional | If score >= threshold |
| **Imported from unknown URL** | Untrusted | No — always quarantine |
| **User-created** (future) | Untrusted | No — needs guardrails |

### 9.2 Import Flow

```
External Repository                    AgentOS

  AgentSkills repo    --import-->  [ Validator ]
  ClawHub registry    --import-->  [ Security Scanner ]
  Custom URL          --import-->  [ Trust Scorer ]
  Manual paste        --import-->       |
                                        v
                                  +---------------+
                                  |  QUARANTINE   |  status = 'pending_review'
                                  |  (not usable) |
                                  +-------+-------+
                                          |
                                     Admin reviews
                                     security report
                                          |
                                          v
                                  +---------------+
                                  |    ACTIVE     |  status = 'active'
                                  |   (usable)    |
                                  +---------------+
```

**Step 1: Fetch** — Admin provides: URL to `SKILL.md`, ClawHub slug, raw JSONB, or file upload.

**Step 2: Parse** — Convert to internal format. AgentSkills `SKILL.md` -> parse YAML frontmatter + markdown body. Instructional: store `instruction_markdown`. Procedural: parse `procedure_json` from metadata.

**Step 3: Validate** — Schema and reference checks:

| Check | Verifies | Fail Action |
|-------|----------|-------------|
| Schema validation | Required fields, valid step types, variable refs resolve | Reject |
| Tool reference check | Every tool in `procedure_json` exists in `tool_definitions` | Warn |
| Permission analysis | Compute required permissions for all referenced tools | Report |
| Resource limits | Step count <= 20, prompt template size <= 10KB, no recursive refs | Reject |

**Step 4: Security Score** — Compute 0-100:

| Factor | Weight | Scoring |
|--------|--------|---------|
| Source reputation | 30% | Known registry = 100. Unknown URL = 20. Manual paste = 40. |
| Tool scope | 25% | Read-only tools = 100. Write tools = 60. Sandbox = 30. Admin = 0. |
| Prompt safety | 25% | No injection patterns = 100. Suspicious = 50. Known injection = 0. |
| Complexity | 10% | <=5 steps = 100. 6-10 = 70. 11-20 = 40. |
| Author verification | 10% | Signed = 100. Unsigned = 50. |

**Minimum acceptance score:** configurable, default **60**. Below threshold = auto-reject.

**Step 5: Quarantine** — `status='pending_review'` with security report, required permissions summary, tool dependency list.

**Step 6: Admin Review** — Approve (-> active), approve with role restrictions, or reject (-> rejected, kept for audit trail).

### 9.3 Prompt Safety Scanner

Checks `instruction_markdown` and `prompt_template` fields for known injection patterns:

```python
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"forget\s+(everything|all|your)",
    r"you\s+are\s+now\s+a",
    r"system\s*:\s*",
    r"<\|im_start\|>",
    r"Human:\s*|Assistant:\s*",
    r"(curl|wget|fetch)\s+http",
    r"base64\.(encode|decode)",
    r"eval\(|exec\(|__import__",
]
```

### 9.4 Trusted Source Registry

Configurable via `system_config` table:

```json
{
  "skill_trusted_sources": {
    "agentskills.io": {"reputation": 95, "auto_approve_threshold": 80},
    "clawhub.openclaw.ai": {"reputation": 90, "auto_approve_threshold": 75},
    "git.blitz.local/skills": {"reputation": 100, "auto_approve_threshold": 90}
  },
  "skill_min_acceptance_score": 60
}
```

High-trust sources with score >= `auto_approve_threshold` skip quarantine (auto-approved). This prevents admin fatigue from reviewing every import from a trusted source.

---

## 10. Frontend Changes

Minimal frontend work in Phase 6:

1. **Skill menu in chat sidebar** — lists available `/commands` with descriptions. Clicking auto-fills chat input with `/skill_name`.
2. **No admin UI** — per PROJECT.md constraint: "admin UI for artifact management -- code/config-first; admin dashboard is post-MVP." Phase 6 is API-only for admin operations.

---

## 11. Seed Data Migration

The Alembic migration seeds the following:

- **`role_permissions`** — exact copy of current `ROLE_PERMISSIONS` dict (5 roles, ~20 permission rows)
- **`agent_definitions`** — 4 rows: email_agent, calendar_agent, project_agent, master_agent (from current hardcoded graph)
- **`tool_definitions`** — all tools from current `_registry` dict + 3 CRM MCP tools
- **`skill_definitions`** — 2 built-in example skills: `morning_digest` (procedural), `project_status_report` (procedural)

---

## 12. Files Changed (Estimated)

### New Files
- `core/models/agent_definition.py` — ORM model
- `core/models/tool_definition.py` — ORM model
- `core/models/skill_definition.py` — ORM model
- `core/models/artifact_permission.py` — ORM model
- `core/models/role_permission.py` — ORM model
- `core/schemas/registry.py` — Pydantic request/response schemas
- `api/routes/admin_agents.py` — Agent CRUD API
- `api/routes/admin_tools.py` — Tool CRUD API
- `api/routes/admin_skills.py` — Skill CRUD API (incl. import/review)
- `api/routes/admin_permissions.py` — Permission management API
- `api/routes/user_skills.py` — User skill listing + execution
- `skills/executor.py` — SkillExecutor runtime
- `skills/validator.py` — Schema validation
- `skills/security_scanner.py` — Prompt safety + trust scoring
- `skills/importer.py` — AgentSkills/ClawHub import parser
- Alembic migration `012_extensibility_registries.py`

### Modified Files
- `gateway/tool_registry.py` — DB-backed instead of in-process dict
- `agents/master_agent.py` — dynamic agent wiring from DB + `/command` dispatch
- `security/rbac.py` — DB-backed `has_permission()` + new `check_artifact_permission()`
- `security/acl.py` — integrate artifact permission check
- `mcp/registry.py` — upsert into `tool_definitions` + respect `status` field
- `core/models/mcp_server.py` — add `version`, `display_name`, `status` columns
- `core/models/__init__.py` — register new models
- `main.py` — register new route modules
- `frontend/src/components/chat/` — skill `/command` menu in sidebar

---

## 13. Locked Decisions

| Decision | Rationale |
|----------|-----------|
| Per-type tables (not unified registry) | Type-specific columns, DB-level validation, evolves existing mcp_servers |
| Full RBAC migration to DB | User requested; enables runtime permission management |
| Two skill types (instructional + procedural) | Instructional = AgentSkills-compatible; procedural = deterministic pipelines |
| Security scoring on import (0-100) | Enterprise security requirement; prevents untrusted skill injection |
| Quarantine -> admin review workflow | Skills from unknown sources must be reviewed before activation |
| Sequential execution only for skills | YAGNI — parallel execution lives in workflows (canvas) |
| No admin UI in Phase 6 | Per PROJECT.md: admin dashboard is post-MVP; API-only management |
| 60s TTL cache for role permissions | Permissions change rarely; admin writes invalidate immediately |
| Gate 2.5 for artifact permissions | Granular per-artifact per-role checks without modifying existing gates |
