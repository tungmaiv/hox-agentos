# AgentOS Skill & Tool Platform — Assessment, Research & Roadmap

## Context

AgentOS has a functional skill/tool system (creation, storage, execution) but lacks the ecosystem features needed to become an open AI platform: import/export, discovery, sharing, dependency management, and interoperability with the industry-standard **Agent Skills** specification (agentskills.io). This document assesses the current state, maps it against the Agent Skills standard, and recommends a phased roadmap to make AgentOS a platform with "no limits."

---

## 1. Current State Assessment

### What Already Works Well

| Capability | Status | Key Files |
|---|---|---|
| **Skill DB model** | Complete | `core/models/skill_definition.py` — name, description, version, skill_type (instructional/procedural), slash_command, source_type, instruction_markdown, procedure_json, input/output schemas, security_score |
| **Skill execution** | Complete | `skills/executor.py` — SkillExecutor runs procedural pipelines step-by-step with 3-gate security + AG-UI streaming |
| **Skill CRUD API** | Complete | `api/routes/admin_skills.py` (admin), `api/routes/user_skills.py` (user) — full CRUD + import + review + validate + security-report |
| **SKILL.md import** | Partial | `skills/importer.py` — parses YAML frontmatter (name, description, version, slash_command, procedure, schemas) |
| **Security scanner** | Complete | `skills/security_scanner.py` — trust scoring: source reputation (30%), tool scope (25%), prompt safety (25%), complexity (10%), author (10%) |
| **Import quarantine** | Complete | Imported skills enter `pending_review` status; admin must approve before activation |
| **Skill validator** | Complete | `skills/validator.py` — validates procedure_json structure (steps, tool refs, conditions, no cycles) |
| **Tool DB model** | Complete | `core/models/tool_definition.py` — name, handler_type (backend/mcp/sandbox), handler_module/function, MCP linkage, schemas |
| **Tool registry** | Complete | `gateway/tool_registry.py` — DB-backed, 60s TTL cache, get/list/register/seed |
| **MCP client** | Complete | `mcp/client.py` — tools/list, tools/call against registered MCP servers |
| **AI artifact builder** | Complete | `agents/artifact_builder.py` — conversational creation of agents, tools, skills, MCP servers |
| **Frontend admin UI** | Complete | Admin pages for skills/tools/agents with CRUD, artifact builder component |
| **3 seeded skills** | Complete | `/summarize`, `/debug`, `/export` (migration 015) |
| **Master agent routing** | Complete | Slash command dispatch + keyword routing in `master_agent.py` |

### What's Missing (Gap Analysis)

| Gap | Impact | Agent Skills Standard Requirement? |
|---|---|---|
| **No skill export** | Can't share skills outside AgentOS | Yes — portability is core to the standard |
| **No bundle import** (ZIP with scripts/assets) | Can only import single SKILL.md files | Yes — directory structure with scripts/, references/, assets/ |
| **Missing SKILL.md fields** | `license`, `compatibility`, `allowed-tools`, `metadata` not parsed | Yes — part of the spec |
| **No name validation** | Names aren't enforced to Agent Skills rules (lowercase, hyphens, 1-64 chars) | Yes |
| **No skill discovery/catalog** | Users can't search, browse, or filter skills | No (platform concern), but essential for "no limits" vision |
| **No MCP registry discovery** | Can't browse or install MCP servers from the public registry | No, but MCP Registry exists at registry.modelcontextprotocol.io |
| **No dependency tracking** | Skills don't declare which tools they need | No (not in spec), but critical for reliable execution |
| **No allowed-tools enforcement** | If SKILL.md declares `allowed-tools`, executor doesn't restrict tool calls | Yes — security feature in the spec |
| **No update detection** | Imported skills have no way to check for newer versions | No, but essential for maintenance |
| **No skill sharing between users** | Skills are admin-managed; users can't share with each other | No, but essential for "no limits" vision |
| **No marketplace/catalog UI** | No frontend for browsing available skills | No, but essential for user experience |
| **No skill composition** | Can't chain skills (one skill calling another) | No, but needed for complex workflows |

---

## 2. Agent Skills Standard — Key Findings

### What Is It?

The **Agent Skills** open standard (agentskills.io) is the dominant specification for portable AI agent skills. Launched by Anthropic (Dec 2025), adopted by 30+ platforms including Claude Code, OpenAI Codex, GitHub Copilot, Google Antigravity, Cursor.

### SKILL.md Format

```yaml
---
name: morning-digest           # Required. Lowercase, hyphens, 1-64 chars.
description: >-
  Generate a morning briefing combining email,
  calendar, and project summaries.         # Required. Max 1024 chars.
license: Apache-2.0            # Optional.
compatibility: >-
  Requires email and calendar tool access.  # Optional. Max 500 chars.
metadata:                      # Optional. Arbitrary key-value.
  author: blitz-team
  version: "1.0.0"
allowed-tools: >-
  email.fetch calendar.list
  crm.get_project_status       # Optional. Space-delimited.
---

## Instructions

Generate a concise morning briefing for the user:

1. **Emails**: Summarize unread emails, highlight urgent items
2. **Calendar**: List today's meetings, flag any conflicts
3. **Projects**: Show status updates from the last 24 hours
```

### Directory Structure

```
skill-name/
├── SKILL.md          # Required — frontmatter + instructions
├── scripts/          # Optional — executable scripts
├── references/       # Optional — reference docs loaded on demand
└── assets/           # Optional — supporting files
```

### Progressive Disclosure (3-tier loading)

1. **Metadata** (~100 tokens): `name` + `description` loaded at startup for all skills
2. **Instructions** (<5000 tokens): Full SKILL.md body loaded when skill is activated
3. **Resources** (on demand): Files in scripts/references/assets loaded only when needed

### Ecosystem

| Marketplace | Scale | Notes |
|---|---|---|
| skills.sh (Vercel) | 20K+ installs on top skill within 6 hours of launch | "npm for agent behaviors" |
| skillsmp.com | 96K+ skills indexed | Indexed from public GitHub repos |
| anthropics/skills (official) | Canonical example library | Algorithmic art, frontend design, MCP generation |
| MCP Registry | 3K+ servers | REST API at registry.modelcontextprotocol.io |

### Concept Mapping: AgentOS ↔ Agent Skills

```
Agent Skills Standard          AgentOS Equivalent
========================       =========================
SKILL.md                  ↔    SkillDefinition (instructional type)
  name                    ↔    SkillDefinition.name (needs kebab-case enforcement)
  description             ↔    SkillDefinition.description
  license                 →    NEW field needed
  compatibility           →    NEW field needed
  metadata.author         ↔    SkillDefinition.created_by (UUID → Keycloak user)
  metadata.version        ↔    SkillDefinition.version
  metadata.*              →    NEW: metadata_json (JSONB)
  allowed-tools           →    NEW: allowed_tools (JSONB array)
  Markdown body           ↔    SkillDefinition.instruction_markdown
  scripts/                →    NEW: skill_assets table (type='script')
  references/             →    NEW: skill_assets table (type='reference')
  assets/                 →    NEW: skill_assets table (type='asset')

MCP Registry Server        ↔    McpServer row (exists)
MCP Tool                   ↔    ToolDefinition (handler_type='mcp', exists)

Procedural Skill           →    AgentOS EXTENSION (no Agent Skills equivalent)
  procedure_json                Our differentiator — multi-step tool pipelines
  SkillExecutor                 Not in spec; export via MANIFEST.json extension
```

**Key insight:** Agent Skills only covers instructional skills (markdown injected into agent context). AgentOS's procedural skills (multi-step tool pipelines) are a **superset**. On export, procedure_json goes into a `MANIFEST.json` extension file — other platforms ignore it, AgentOS roundtrips it correctly.

---

## 3. Recommended Architecture

### 3.1 New DB Columns & Tables (Migration 017)

**skill_definitions — new columns:**

| Column | Type | Purpose |
|---|---|---|
| `license` | TEXT, nullable | e.g., "Apache-2.0" |
| `compatibility` | TEXT, nullable, max 500 chars | Environment requirements |
| `metadata_json` | JSONB, nullable | Arbitrary key-value metadata |
| `allowed_tools` | JSONB, nullable | Array of tool name strings |
| `source_url` | TEXT, nullable | Import origin URL for update checks |
| `source_hash` | TEXT, nullable | SHA-256 of imported content |
| `tags` | JSONB, nullable | Array of string tags for search |
| `category` | VARCHAR(64), nullable | e.g., "productivity", "development" |

**NEW `skill_assets` table:**

```sql
CREATE TABLE skill_assets (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id      UUID NOT NULL REFERENCES skill_definitions(id) ON DELETE CASCADE,
    asset_type    VARCHAR(20) NOT NULL,  -- 'script' | 'reference' | 'asset'
    filename      TEXT NOT NULL,
    content       TEXT,                   -- text content
    content_binary BYTEA,                -- binary content (images, etc.)
    mime_type     VARCHAR(128),
    size_bytes    INTEGER,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(skill_id, filename)
);
```

**NEW `skill_dependencies` table:**

```sql
CREATE TABLE skill_dependencies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id        UUID NOT NULL REFERENCES skill_definitions(id) ON DELETE CASCADE,
    depends_on_type VARCHAR(20) NOT NULL,  -- 'skill' | 'tool' | 'mcp_server'
    depends_on_name TEXT NOT NULL,
    version_spec    VARCHAR(64),           -- semver range, e.g., ">=1.0.0"
    required        BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 3.2 Skill Package Format (Import/Export)

```
skill-name.zip
├── SKILL.md              # Agent Skills-standard file
├── MANIFEST.json         # AgentOS extensions (procedure_json, schemas, slash_command, deps)
├── scripts/              # Executable scripts
├── references/           # Reference documents
└── assets/               # Supporting files (images, data, etc.)
```

**MANIFEST.json structure** (AgentOS extension — ignored by other platforms):

```json
{
  "agentos_version": "1.0",
  "skill_type": "procedural",
  "slash_command": "/morning-digest",
  "procedure_json": { "steps": [...] },
  "input_schema": { ... },
  "output_schema": { ... },
  "dependencies": [
    { "type": "tool", "name": "email.fetch", "required": true },
    { "type": "mcp_server", "name": "crm-server", "required": false }
  ]
}
```

### 3.3 Core Modules

| Module | Purpose |
|---|---|
| `skills/importer.py` (extend) | Parse full Agent Skills fields + ZIP bundle import |
| `skills/exporter.py` (new) | Export to SKILL.md, ZIP package, or directory |
| `skills/catalog.py` (new) | Full-text search via PostgreSQL `tsvector`, category/tag filtering |
| `skills/dependencies.py` (new) | Dependency resolution and validation on activation |
| `mcp/registry_discovery.py` (new) | Query MCP Registry API for server discovery |

---

## 4. Phased Implementation Roadmap

### Phase A: Agent Skills Standard Compliance (3-4 days)

**Goal:** Make AgentOS import/export skills in the industry-standard format.

| Plan | Task | Files |
|------|------|-------|
| **A-1** | Schema evolution — add new columns + tables | NEW `alembic/versions/017_*.py`, MODIFY `core/models/skill_definition.py`, NEW `core/models/skill_asset.py`, NEW `core/models/skill_dependency.py`, MODIFY `core/schemas/registry.py` |
| **A-2** | Enhanced SKILL.md importer — parse all standard fields, name validation, source_hash | MODIFY `skills/importer.py`, MODIFY tests |
| **A-3** | Skill export — `SkillExporter` with SKILL.md and ZIP output, API endpoints | NEW `skills/exporter.py`, MODIFY `api/routes/admin_skills.py`, MODIFY `api/routes/user_skills.py` |
| **A-4** | ZIP bundle import — extract SKILL.md + MANIFEST.json + assets from ZIP | MODIFY `skills/importer.py`, MODIFY `api/routes/admin_skills.py` |

### Phase B: Discovery & Catalog (3-4 days)

**Goal:** Users and admins can search, browse, and discover skills and tools.

| Plan | Task | Files |
|------|------|-------|
| **B-1** | Skill catalog backend — full-text search via PostgreSQL `to_tsvector`, category/tag filtering, pagination | NEW `skills/catalog.py`, NEW `api/routes/skill_catalog.py` |
| **B-2** | Tool catalog backend — search/filter tools by handler_type | NEW `api/routes/tool_catalog.py` |
| **B-3** | MCP Registry discovery — query registry.modelcontextprotocol.io, admin-only browse + install | NEW `mcp/registry_discovery.py`, MODIFY `api/routes/mcp_servers.py` |
| **B-4** | Skill catalog frontend — /skills page with search, filters, skill cards | NEW `frontend/src/app/skills/page.tsx`, NEW components + hooks |

### Phase C: Dependency & Security Hardening (2-3 days)

**Goal:** Skills declare and enforce their tool requirements.

| Plan | Task | Files |
|------|------|-------|
| **C-1** | Dependency resolution — auto-extract deps from allowed_tools + procedure_json, validate on activation | NEW `skills/dependencies.py`, MODIFY `api/routes/admin_skills.py` |
| **C-2** | allowed-tools enforcement — restrict SkillExecutor tool calls to declared set | MODIFY `skills/executor.py` |
| **C-3** | Update checker — Celery periodic task re-fetches source_url, compares hash, creates pending_review version | NEW `scheduler/jobs/skill_update_checker.py` |

### Phase D: Sharing & Collaboration (2-3 days)

**Goal:** Users can share, export, and publish skills within the organization.

| Plan | Task | Files |
|------|------|-------|
| **D-1** | Skill sharing between users — reuse existing `artifact_permissions` system, add share UI | MODIFY frontend skill pages |
| **D-2** | Export for external sharing — download SKILL.md or ZIP from UI | MODIFY frontend skill components |
| **D-3** | On-premise marketplace — admin publishes approved skills, users browse and install | NEW `api/routes/skill_marketplace.py`, NEW `frontend/src/app/marketplace/page.tsx` |

### Phase E: Advanced Features (Post-MVP, 4-5 days)

**Goal:** Platform-level features for power users.

| Plan | Task |
|------|------|
| **E-1** | Skill composition — procedure_json step type "skill" calls another skill (max depth 3) |
| **E-2** | Skill analytics — execution count, success rate, average duration, popular skills dashboard |
| **E-3** | Skill versioning UI — version history, diff view, one-click rollback |
| **E-4** | AI skill generator enhancement — artifact builder auto-generates Agent Skills-compliant SKILL.md |
| **E-5** | External marketplace connector — admin browses skills.sh/skillsmp.com, imports with SecurityScanner quarantine |

### Dependency Graph

```
A-1 (schema) ──────────────────────────────────────────────┐
  ├── A-2 (enhanced importer)                              │
  │     └── A-4 (bundle import)                            │
  │     └── C-3 (update checker)                           │
  ├── A-3 (export) ─── D-2 (export UI)                    │
  ├── B-1 (catalog backend) ─── B-4 (catalog frontend)    │
  │                              └── D-1 (sharing)         │
  │                              └── D-3 (marketplace)     │
  ├── C-1 (dependency resolution)                          │
  └── C-2 (allowed-tools enforcement)                      │
                                                           │
B-2 (tool catalog) ─── no deps, can run in parallel        │
B-3 (MCP discovery) ─── no deps, can run in parallel       │
                                                           │
Phase E ─── depends on all of A-D ─────────────────────────┘
```

---

## 5. Security Invariants (Non-Negotiable)

These rules apply across ALL phases:

1. **Import quarantine** — Every imported skill goes through `SecurityScanner` → `pending_review`. No auto-activation.
2. **allowed-tools enforcement** — If SKILL.md declares `allowed-tools`, executor restricts tool calls to that set. Prevents privilege escalation.
3. **Bundle scanning** — ZIP imports scan all scripts for `INJECTION_PATTERNS`. Script files get elevated scrutiny.
4. **MCP discovery is read-only** — Admin browses the public registry but must manually approve + configure auth for installation.
5. **Export redaction** — Exporter strips credentials, user_ids, internal URLs from SKILL.md and MANIFEST.json.
6. **Dependency validation is local-only** — Only validates against local tool registry. No auto-install of missing tools from external sources.

---

## 6. Verification Plan

### After Phase A

```bash
# Test import with full Agent Skills fields
PYTHONPATH=. .venv/bin/pytest tests/test_skill_importer.py -v

# Test export produces valid SKILL.md
PYTHONPATH=. .venv/bin/pytest tests/test_skill_exporter.py -v

# Test ZIP bundle roundtrip (import → export → re-import produces same skill)
PYTHONPATH=. .venv/bin/pytest tests/test_skill_bundle.py -v

# Full suite regression
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

### After Phase B

```bash
# Test catalog search
PYTHONPATH=. .venv/bin/pytest tests/test_skill_catalog.py -v

# Manual: browse /skills page, search, filter by category
```

### After Phase C

```bash
# Test dependency resolution
PYTHONPATH=. .venv/bin/pytest tests/test_skill_dependencies.py -v

# Test allowed-tools enforcement blocks unauthorized tool calls
PYTHONPATH=. .venv/bin/pytest tests/skills/test_executor.py -v -k allowed_tools
```

### After Phase D

```bash
# Manual: share skill with another user, verify they can see and execute it
# Manual: export skill as ZIP, import on another AgentOS instance
```

---

## 7. Effort Summary

| Phase | Scope | Estimated Effort |
|---|---|---|
| **A** | Agent Skills Standard Compliance | 3-4 days |
| **B** | Discovery & Catalog | 3-4 days |
| **C** | Dependency & Security Hardening | 2-3 days |
| **D** | Sharing & Collaboration | 2-3 days |
| **E** | Advanced Features (post-MVP) | 4-5 days |
| **Total MVP (A-D)** | | **10-14 days** |
| **Total with E** | | **14-19 days** |

Phases A-D deliver a standards-compliant, discoverable, shareable skill platform. Phase E adds power-user and ecosystem features that can be deferred without blocking the core value proposition.
