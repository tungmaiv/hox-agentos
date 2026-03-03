# Phase 14: Ecosystem Capabilities — Design Document

**Date:** 2026-03-04
**Phase:** 14 of v1.2 Developer Experience
**Depends on:** Phase 12 (Unified Admin Desk)
**Status:** Design approved, ready for planning

---

## Goal

Agents and users can introspect what the platform can do, any OpenAPI-described service can be wired in as an MCP server in minutes, and external skill repositories can be browsed, imported, and exported in a standard format — turning AgentOS into an open, extensible ecosystem.

## Success Criteria (from ROADMAP.md)

1. **ECO-01:** User (or agent) sends "what can you do?" → structured list of all agents, tools, skills, MCP servers
2. **ECO-02:** User provides OpenAPI URL → selects endpoints → new MCP server appears, callable immediately
3. **ECO-03:** Admin adds/removes external skill repositories by URL from `/admin`
4. **ECO-04:** User browses/searches skills from registered repositories in the UI
5. **ECO-05:** User imports a skill from a repo → `pending_review` → admin approves → available
6. **ECO-06:** Admin exports any skill as agentskills.io-compliant zip from admin panel

## Decisions

| Decision | Rationale |
|----------|-----------|
| Capabilities is agent tool only (no REST endpoint) | Master agent invokes `system.capabilities` on intent detection; simpler, fits chat UX |
| API-to-MCP uses in-process proxy (not Docker containers) | YAGNI — no need to build/manage Docker images for MVP; a generic httpx proxy is sufficient |
| API-to-MCP interaction is admin panel only | Deterministic form UX; fits existing admin desk pattern from Phase 12 |
| Static API key per OpenAPI server (not per-user OAuth) | Matches existing `mcp_servers.auth_token` pattern; per-user OAuth deferred |
| Skill repos use custom JSON index format + agentskills.io SKILL.md | agentskills.io has no repo index spec; we define a thin index, skills follow the standard |
| Skill export as zip directory (not single file) | Full agentskills.io directory structure with SKILL.md + scripts/ + references/ |
| Separate backend modules per feature (Approach B) | Clean separation of concerns; each module independently testable |

---

## Architecture: Separate Modules

Four new backend modules, each with clear boundaries:

```
backend/
├── capabilities/         # ECO-01: system.capabilities agent tool
├── openapi_bridge/       # ECO-02: OpenAPI spec parser + in-process proxy
├── skill_repos/          # ECO-03/04/05: external repo management + browsing + import
└── skill_export/         # ECO-06: agentskills.io zip export
```

All modules follow existing patterns: Pydantic schemas, async SQLAlchemy, structlog logging, `registry:manage` for admin endpoints, standard 3-gate security.

---

## Module 1: Capabilities Tool (ECO-01)

### Overview

A registered agent tool `system.capabilities` that queries all four registries and returns a user-scoped structured response.

### Files

```
backend/capabilities/
├── __init__.py
├── tool.py          # system_capabilities(user_id, session) → CapabilitiesResponse
└── schemas.py       # CapabilitiesResponse, AgentInfo, ToolInfo, SkillInfo, McpServerInfo
```

### Response Schema

```python
class CapabilitiesResponse(BaseModel):
    agents: list[AgentInfo]       # name, display_name, description, status
    tools: list[ToolInfo]         # name, display_name, description, handler_type
    skills: list[SkillInfo]       # name, display_name, description, slash_command
    mcp_servers: list[McpServerInfo]  # name, display_name, tools_count
    summary: str                  # "4 agents, 12 tools, 3 skills, 2 MCP servers"
```

### Tool Registration

Seeded in migration 019 as a `tool_definitions` row:
- `name`: `system.capabilities`
- `handler_type`: `backend`
- `handler_module`: `capabilities.tool`
- `handler_function`: `system_capabilities`
- `required_permissions`: `["chat"]`

### Permission Model

- Tool requires `chat` permission (any authenticated user)
- Results filtered by `batch_check_artifact_permissions()` — users only see artifacts they're allowed to use
- MCP servers visible to all (no per-server ACL currently)

### Agent Integration

The master agent's `_pre_route` keyword routing already handles intent classification. Add `capabilities`/`what can you do` keywords to route to the `system.capabilities` tool.

---

## Module 2: OpenAPI Bridge (ECO-02)

### Overview

Fetch and parse OpenAPI 3.x specs, let admins select endpoints, register them as callable tools with an in-process HTTP proxy.

### Files

```
backend/openapi_bridge/
├── __init__.py
├── parser.py         # fetch_and_parse_openapi(url) → list[EndpointInfo]
├── proxy.py          # call_openapi_tool(tool_def, arguments, api_key) → dict
├── schemas.py        # EndpointInfo, OpenAPIParseRequest/Response, RegisterRequest
├── service.py        # register_openapi_endpoints(server_name, endpoints, api_key, session)
└── routes.py         # POST /api/admin/openapi/parse, POST /api/admin/openapi/register
```

### Flow

```
Admin pastes OpenAPI URL
  → POST /api/admin/openapi/parse
  → Backend: httpx.get(url) → parse YAML/JSON → extract operations
  → Return: list of EndpointInfo { method, path, summary, parameters, requestBody }

Admin selects endpoints, names the server, provides API key
  → POST /api/admin/openapi/register
  → Backend:
    1. Create mcp_servers row (url=base_url, openapi_spec_url=spec_url, auth_token=encrypted_key)
    2. For each endpoint: create tool_definitions row with handler_type='openapi_proxy'
       - name: f"{server_name}.{operation_id or method_path}"
       - input_schema: derived from OpenAPI parameters + requestBody
       - config_json: { method, path, base_url, parameters, ... }
    3. Invalidate tool cache
  → Return: { server_id, tools_created: int }
```

### OpenAPI Parser Details

- Supports OpenAPI 3.0.x and 3.1.x (JSON and YAML)
- Extracts: operationId, method, path, summary, description, parameters (path/query/header), requestBody schema
- Generates `input_schema` for each tool from OpenAPI parameters (maps to Pydantic-compatible JSON Schema)
- Ignores deprecated operations by default
- Validates spec structure (not full validation — just enough to extract operations)

### Runtime Proxy

When `gateway/tool_registry.py` dispatches a tool with `handler_type='openapi_proxy'`:

1. Load operation config from `tool_definitions.config_json`
2. Decrypt API key from `mcp_servers.auth_token`
3. Build HTTP request:
   - URL: `base_url` + path (with path parameter substitution)
   - Method: from config
   - Query params: from tool arguments matching `in: query` parameters
   - Headers: `Authorization: Bearer <api_key>` (or custom auth scheme from config)
   - Body: from tool arguments matching requestBody schema
4. Execute via `httpx.AsyncClient` (30s timeout)
5. Return response JSON (or error structure on non-2xx)

### DB Changes

- Add `openapi_spec_url` (nullable Text) to `mcp_servers` table
- New `handler_type` value: `'openapi_proxy'` (for `tool_definitions`)

### Security

- Admin endpoints: `registry:manage` permission required
- Runtime proxy: standard 3-gate security (JWT → RBAC → Tool ACL)
- API keys: AES-256 encrypted in DB, same pattern as existing `mcp_servers.auth_token`
- API keys never exposed to LLM or frontend
- Audit log: every proxy call logged with user_id, tool, duration_ms

---

## Module 3: Skill Repositories (ECO-03, ECO-04, ECO-05)

### Overview

Manage external skill repositories, browse/search their catalogs, and import skills into AgentOS with the existing security pipeline.

### Files

```
backend/skill_repos/
├── __init__.py
├── models.py         # SkillRepository SQLAlchemy model
├── schemas.py        # RepoCreate, RepoInfo, SkillBrowseItem, ImportRequest, IndexSchema
├── service.py        # fetch_index(), sync_repo(), browse_skills(), import_from_repo()
└── routes.py         # admin + user-facing endpoints
```

### Repository Index Format

A repository serves an `agentskills-index.json` at its base URL:

```json
{
  "repository": {
    "name": "blitz-community-skills",
    "description": "Community-contributed skills for Blitz AgentOS",
    "url": "https://skills.example.com",
    "version": "1.0"
  },
  "skills": [
    {
      "name": "pdf-processing",
      "description": "Extract text and tables from PDF files...",
      "version": "1.0",
      "skill_url": "https://skills.example.com/skills/pdf-processing/SKILL.md",
      "directory_url": "https://skills.example.com/skills/pdf-processing/",
      "metadata": {
        "author": "example-org",
        "license": "Apache-2.0"
      }
    }
  ]
}
```

Individual skills follow the [agentskills.io SKILL.md specification](https://agentskills.io/specification):
- YAML frontmatter with required `name` and `description`
- Optional: `license`, `compatibility`, `metadata`, `allowed-tools`
- Markdown body with skill instructions
- Optional `scripts/`, `references/`, `assets/` directories

### New DB Table: `skill_repositories`

```python
class SkillRepository(Base):
    __tablename__ = "skill_repositories"

    id: Mapped[uuid.UUID]              # PK
    name: Mapped[str]                  # unique, from index
    url: Mapped[str]                   # base URL
    description: Mapped[str | None]
    is_active: Mapped[bool]            # default True
    last_synced_at: Mapped[datetime | None]
    cached_index: Mapped[dict | None]  # JSONB — cached agentskills-index.json
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

### Admin API Endpoints

```
GET    /api/admin/skill-repos              — list repos
POST   /api/admin/skill-repos              — add repo (fetches + validates index)
DELETE /api/admin/skill-repos/{id}         — remove repo (imported skills stay)
POST   /api/admin/skill-repos/{id}/sync    — re-fetch index
```

All require `registry:manage`.

### User-Facing API Endpoints

```
GET    /api/skill-repos/browse             — search skills from all active repos
                                             ?q=keyword (optional)
POST   /api/skill-repos/import             — import { repository_id, skill_name }
```

Require `chat` permission.

### Browse/Search Logic

1. Load `cached_index` from all active `skill_repositories`
2. Aggregate all skill entries
3. If `?q=` provided: filter by substring match on `name` + `description`
4. Return `SkillBrowseItem` list: name, description, version, repository_name, metadata

### Import Flow

1. Look up skill in repo's cached index → get `skill_url`
2. Call existing `SkillImporter.import_from_url(skill_url)` → parse SKILL.md
3. Run `SecurityScanner.scan()` → get score + recommendation
4. Create `skill_definitions` row with `status='pending_review'`, `source_type='imported'`
5. Admin reviews via existing `POST /api/admin/skills/{id}/review`
6. On approval: `status='active'`, skill becomes available

---

## Module 4: Skill Export (ECO-06)

### Overview

Export any skill definition as an agentskills.io-compliant zip directory.

### Files

```
backend/skill_export/
├── __init__.py
├── exporter.py       # build_skill_zip(skill_def) → BytesIO
├── schemas.py        # ExportMetadata (for internal tracking)
└── routes.py         # GET /api/admin/skills/{id}/export
```

### Export Zip Structure

```
skill-name/
├── SKILL.md              # agentskills.io format
├── scripts/
│   └── procedure.json    # procedure_json (if procedural skill)
└── references/
    └── schemas.json      # input_schema + output_schema (if defined)
```

### SKILL.md Generation

```yaml
---
name: morning-digest
description: Fetch and summarize morning emails for a daily digest
license: Proprietary
metadata:
  author: blitz-agentos
  version: "1.0"
  skill_type: procedural
  slash_command: /digest
  source_type: user_created
  exported_at: "2026-03-04T12:00:00Z"
---

<instruction_markdown content from DB>
```

### Admin API Endpoint

```
GET /api/admin/skills/{id}/export   →  application/zip response
```

Requires `registry:manage`.

---

## Frontend Changes

### Admin Panel

| Area | Change |
|------|--------|
| `/admin` — new "Connect API" section | OpenAPI URL form → endpoint picker → register |
| `/admin` — new "Skill Repositories" tab | Repo list + add/remove/sync |
| `/admin` — Skills tab | Add "Export" button per skill row |

### User-Facing

| Area | Change |
|------|--------|
| New "Skill Store" section (accessible from sidebar or `/admin`) | Browse/search external skills, "Import" button |

### New Next.js API Proxy Routes

```
POST /api/admin/openapi/parse          → backend
POST /api/admin/openapi/register       → backend
GET  /api/admin/skill-repos            → backend
POST /api/admin/skill-repos            → backend
DELETE /api/admin/skill-repos/[id]     → backend
POST /api/admin/skill-repos/[id]/sync  → backend
GET  /api/skill-repos/browse           → backend
POST /api/skill-repos/import           → backend
GET  /api/admin/skills/[id]/export     → backend (stream zip)
```

---

## Database Migration (019)

Single migration adding:
1. `skill_repositories` table
2. `openapi_spec_url` column on `mcp_servers` (nullable Text)
3. Seed `system.capabilities` tool in `tool_definitions`

---

## Plan Breakdown

| Plan | Scope | Backend | Frontend | Tests |
|------|-------|---------|----------|-------|
| 14-01 | Capabilities tool | `capabilities/` module, tool registration, agent routing | — | Capabilities returns filtered results per role |
| 14-02 | OpenAPI bridge | `openapi_bridge/` module, parser, proxy, admin routes | Admin "Connect API" UI + proxy routes | Parser handles 3.0/3.1, proxy constructs correct requests |
| 14-03 | Skill repos + browse + import | `skill_repos/` module, DB model, migration, admin/user routes | Admin "Repositories" tab, "Skill Store" browse UI + proxy routes | Repo sync, browse search, import → pending_review flow |
| 14-04 | Skill export | `skill_export/` module, zip builder, admin route | Export button in Skills tab + proxy route | Valid SKILL.md in zip, correct frontmatter |

**Dependency:** Plan 14-03 includes the migration (019) since it has the new table. Plans 14-01, 14-02, 14-04 depend on 14-03 for the migration but can otherwise be developed independently.

---

## What's NOT in Scope

- Docker container generation for MCP servers (deferred — hybrid plan)
- Per-user OAuth for external APIs (static API key only)
- Repository authentication (public repos only for MVP)
- Skill versioning across imports (import always creates a new version)
- REST endpoint for capabilities (agent tool only)
- Chat-based API-to-MCP interaction (admin panel only)

---

## References

- [agentskills.io Specification](https://agentskills.io/specification) — SKILL.md format
- [Phase 12 Design](docs/plans/) — Unified Admin Desk (dependency)
- [ROADMAP.md](.planning/ROADMAP.md) — Phase 14 requirements ECO-01 through ECO-06
- Existing infrastructure: `gateway/tool_registry.py`, `skills/importer.py`, `skills/security_scanner.py`, `mcp/registry.py`
