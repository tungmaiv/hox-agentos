# Phase 24 Design: Unified Registry, MCP Platform & Skill Import Adapters

**Date:** 2026-03-12
**Status:** Approved
**Milestone:** v1.4

---

## Summary of Decisions

| # | Topic | Decision |
|---|-------|----------|
| 1 | Security scan gate model | Configurable per policy — admins set block/warn/log per rule severity |
| 2 | Skill type consolidation | Merge instructional + procedural into one type; optional `procedure` field; migration script |
| 3 | MCP stdio transport | MCP gateway container — single service managing stdio process pools |
| 4 | LLM admin configurability | Full provider management — add/remove providers, encrypted API keys, alias remapping |

---

## Plan 24-01: Tech Debt

Clears the path for all subsequent plans.

| Item | Fix |
|------|-----|
| SWR in Server Components | Add `"use client"` to `/settings/integrations` and `/settings/memory` pages |
| Keycloak SSO `Configuration` error | Investigate OIDC discovery URL / cert chain; fix or surface clear error message |
| `CREDENTIAL_ENCRYPTION_KEY` missing | Add to `.env.example`, validate on startup, log warning if absent |
| Page load performance | Audit and fix N+1 queries on admin pages |

---

## Plan 24-02: Unified Registry Foundation

### Data Model

Single `registry_entries` table replaces `agents`, `skills`, `tools`, and `mcp_servers` tables:

```
registry_entries
  id           UUID PK
  type         ENUM (agent | skill | tool | mcp_server | policy)
  name         VARCHAR unique
  display_name VARCHAR
  description  TEXT
  status       ENUM (active | inactive | pending_review)
  config       JSONB        -- type-specific config blob
  metadata     JSONB        -- tags, author, source_url, version, license
  created_by   UUID         -- user_id, no FK (Keycloak pattern)
  created_at   TIMESTAMP
  updated_at   TIMESTAMP
```

### Skill Type Merge

- `skill_type` column dropped; replaced by optional `config.procedure` field
- Existing instructional skills migrate with `config.procedure = null`
- Existing procedural skills migrate handler code into `config.procedure`
- Builder UI: type toggle removed; procedure section shown/hidden based on whether `config.procedure` is populated

### Strategy Handlers

Each `type` gets a `RegistryHandler` class implementing:
- `validate(config: dict) -> None` — raises on invalid config
- `activate(entry: RegistryEntry) -> None`
- `deactivate(entry: RegistryEntry) -> None`
- `test(entry: RegistryEntry) -> dict` — returns test result

Router dispatches to correct handler. No conditional logic in route handlers.

### API Routes

```
GET    /api/registry?type=skill&status=active
POST   /api/registry
GET    /api/registry/{id}
PUT    /api/registry/{id}
DELETE /api/registry/{id}
POST   /api/registry/{id}/clone
POST   /api/registry/{id}/test
```

Existing domain routes (`/api/skills/*`, `/api/tools/*`, `/api/agents/*`) kept as thin shims for one milestone, removed in v1.5.

---

## Plan 24-03: MCP Platform Enhancement

### New Service: `mcp-gateway` (port 8010)

Single Docker container managing all stdio-based MCP servers. Builtin HTTP+SSE servers (`mcp-crm`, `mcp-docs`) are unaffected.

```
mcp-gateway (port 8010)
  ├── ProcessPoolManager
  │     ├── pool["context7"]    → N stdio processes (npx @upstash/context7-mcp)
  │     ├── pool["fetch"]       → N stdio processes (uvx mcp-server-fetch)
  │     └── pool["filesystem"]  → N stdio processes (npx @modelcontextprotocol/server-filesystem)
  ├── MCPInstaller
  │     ├── npm install (Node-based servers)
  │     └── uv/pip install (Python-based servers)
  └── HTTP+SSE bridge
        → exposes each pool as /servers/{name}/sse
```

### Process Pool Manager

- Pool size per server: `registry_entries.config.pool_size` (default: 2)
- Round-robin dispatch across healthy processes
- Crashed process auto-replaced within 5s
- Pool size adjustable via admin API without gateway restart

### MCPInstaller

- Runs npm/uv install at server registration time, not at request time
- `registry_entries.config.installation_status`: `not_installed → installing → installed | error`
- Backend polls `installation_status` during MCP server activation

### OpenAPI Bridge

- Admin provides OpenAPI spec URL
- Gateway fetches spec, generates MCP tool definitions (one tool per operation)
- Registers `registry_entries` row: `type=mcp_server`, `config.server_type=openapi_bridge`
- No stdio process — gateway proxies tool calls directly to REST API
- Covers pending todo: "auto-generate MCP from API endpoints"

### Backend Integration

`backend/mcp/client.py` routes tool calls to stdio-based servers via `http://mcp-gateway:8010/servers/{name}/sse`. Builtin servers still addressed directly (`mcp-crm:8001`, `mcp-docs:8002`).

---

## Plan 24-04: Skill Import Adapters

### Adapter Interface

```python
class SkillImportAdapter(ABC):
    @abstractmethod
    def can_handle(self, source: str) -> bool: ...

    @abstractmethod
    async def fetch(self, source: str) -> list[RawSkill]: ...

    @abstractmethod
    def normalize(self, raw: RawSkill) -> SkillImportCandidate: ...
```

### Adapters

| Adapter | Trigger |
|---------|---------|
| `SkillRepoAdapter` | AgentSkills index URL (existing — refactored) |
| `ClaudeMarketAdapter` | Claude Code marketplace YAML/JSON skills |
| `GitHubAdapter` | GitHub repo URL → detect skill files by frontmatter |
| `ZipFileAdapter` | Local ZIP upload (existing — refactored) |

`UnifiedImportService.import(source)` auto-detects adapter via `can_handle()`, fetches, normalizes, then passes through the security gate pipeline.

### Security Gate Pipeline

```
RawSkill → normalize → [DependencyScan] → [SecretScan] → [CodeScan] → [PolicyValidate] → save
```

Each scan step reads the matched policy rule's `severity`:
- `error` → hard block; import fails with finding details returned to caller
- `warning` → import proceeds; `registry_entries.status = pending_review`; warning badge shown in UI
- `info` → import proceeds silently; finding logged to audit log

---

## Plan 24-05: Security Scan Module

### Architecture

Standalone Docker service at port `8003` following existing MCP server pattern.

```
infra/security-scanner/
  ├── main.py                       (FastAPI + MCP JSON-RPC handler)
  ├── scanners/
  │     ├── dependency_scanner.py   (pip-audit)
  │     ├── secret_scanner.py       (detect-secrets)
  │     └── code_scanner.py         (bandit)
  └── policies/
        ├── default-policies.yaml
        └── skill-policies.yaml
```

Replaces `backend/skills/security_scanner.py` (`WeightedSecurityScanner`) entirely.

`backend/mcp/security_scan_client.py` calls the Docker service. Backend has zero scanning logic.

### Policy Model

Each policy rule carries `severity: error | warning | info`. Scanner returns findings with severity; `UnifiedImportService` and skill save endpoint read severity to decide block/warn/log.

Admins manage policies via the Registry tab — policy entries are `registry_entries` rows with `type=policy`.

### Persistence

`secscan_results` table persists all scan outcomes:

```
secscan_results
  id            UUID PK
  resource_id   UUID         -- registry_entries.id
  resource_type VARCHAR      -- skill, workflow, etc.
  scan_type     VARCHAR      -- dependency, secret, code, policy
  status        VARCHAR      -- passed, failed, error
  findings      JSONB
  summary       TEXT
  created_at    TIMESTAMP
```

Scan history queryable per skill at `GET /api/security/history/{resource_id}`.

### WeightedSecurityScanner Removal

- `backend/skills/security_scanner.py` deleted
- All callers updated to use `SecurityScanClient`
- RBAC: new permissions `security:scan`, `security:admin`, `security:override`

---

## Plan 24-06: Admin UI & LLM Config

### Unified 4-Tab Admin Layout

```
/admin
  ├── Registry  — all entity CRUD (agents/skills/tools/mcp servers/policies)
  ├── Access    — users, roles, tool ACL, permissions (existing)
  ├── System    — identity config, platform config, LLM providers, health
  └── Build     — skill builder, import, repositories, security policies
```

Registry tab: single `ArtifactCardGrid` with type filter, backed by `/api/registry`. Full CRUD for all entity types.

### LLM Provider Management (System → LLM Providers)

**Level 1 — Providers:**
- List: name, type, status (reachable/unreachable), masked API key, edit/delete
- Add provider: name, type (Anthropic/OpenAI/Ollama/OpenRouter/Custom), base URL, API key
- Connection test button — verifies key + reachability before save

**Level 2 — Model Aliases:**
- Table: `blitz/master`, `blitz/fast`, `blitz/coder`, `blitz/summarizer` → provider + model
- Dropdown selects from provider's known model list

**Storage:** Provider configs (AES-256 encrypted API keys) in `platform_config` table — same pattern as Phase 18 Keycloak config.

**Hot-reload:** On save, backend calls LiteLLM proxy admin API (`POST /config/update`) to reload routing without container restart.

---

## Execution Order

Plans must execute in dependency order:

```
24-01 (tech debt)
  └── 24-02 (unified registry — foundation for all entity management)
        ├── 24-03 (MCP gateway — depends on registry for mcp_server entries)
        ├── 24-04 (skill import adapters — depends on registry for skill entries)
        │     └── 24-05 (security scanner — integrated into import pipeline)
        └── 24-06 (admin UI — depends on registry API being complete)
```

24-03, 24-04+24-05, and 24-06 can parallelize after 24-02 is complete.
