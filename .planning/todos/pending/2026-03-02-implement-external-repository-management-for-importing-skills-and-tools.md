---
created: 2026-03-02T03:46:09.001Z
title: Implement external repository management for importing skills and tools
area: api
files:
  - backend/api/routes/admin_skills.py
  - backend/core/models/skill_definition.py
  - backend/core/schemas/registry.py
---

## Problem

AgentOS has no way to browse, search, or import skills/tools from external registries. Users must manually define every artifact from scratch. There is a growing ecosystem of reusable agent skills and tools (agentskills.io, claude plugins, etc.) that AgentOS cannot consume. Additionally, AgentOS skills should be publishable and compliant with open standards like agentskills.io.

## Solution

### Phase A — Repository management (admin)

1. Add `skill_repositories` table to PostgreSQL:
   - `id`, `name`, `url`, `type` (`git` | `http_index` | `agentskills_io`), `is_active`, `last_synced_at`, `created_at`
2. Admin CRUD endpoints: `POST/GET/DELETE /api/admin/repositories`
3. Seed with default repos (can be disabled by admin):
   - `https://agentskills.io` (agentskills.io spec compliant)
   - Others as configured

### Phase B — Repository sync & search

4. `RepositoryIndexer` service in `backend/skills/repository_indexer.py`:
   - Fetches index from each active repository URL
   - Caches skill/tool listings in `skill_repository_cache` table (name, description, tags, source_url, raw_manifest)
   - Celery task: `sync_repositories` (scheduled or on-demand)
5. Search endpoint: `GET /api/admin/repositories/search?q=email&type=skill`
   - Returns matching items from cache with source repo info

### Phase C — Import & conversion

6. Import endpoint: `POST /api/admin/repositories/import`
   - Input: `{ source_url: "...", target_type: "skill" | "tool" }`
   - Fetches manifest from source URL
   - Converts to AgentOS `SkillDefinitionCreate` / `ToolDefinitionCreate`
   - Sets `source_type = "imported"`, `status = "pending_review"` (security scan before activation)
   - Returns created artifact UUID
7. Conversion adapters for each format:
   - `agentskills.io` → AgentOS skill (primary standard to comply with)
   - Claude plugin manifest → AgentOS tool
   - Generic markdown file → instructional skill

### Phase D — AgentOS skill compliance with agentskills.io

8. Ensure AgentOS `SkillDefinition` schema is a superset of agentskills.io spec
9. Export endpoint: `GET /api/admin/skills/{id}/export?format=agentskills` — returns compliant manifest
10. Validate imported agentskills.io manifests against spec before import

### Security

- All imported artifacts go through `pending_review` status — no auto-activation
- Security scan triggered on import (existing skill review flow)
- Repository URLs validated against allowlist if configured
- No arbitrary code execution from imported skills — procedural skills only call registered tools

### References
- agentskills.io spec: https://agentskills.io/home (primary compliance target)
- Existing import endpoint: `POST /api/admin/skills/import` (extend this)
- Existing security review: `POST /api/admin/skills/{id}/review`
