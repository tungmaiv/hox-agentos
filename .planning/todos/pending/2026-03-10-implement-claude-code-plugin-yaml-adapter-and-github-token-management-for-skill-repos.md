---
created: 2026-03-10T03:40:00.040Z
title: Implement Claude Code plugin YAML adapter and GitHub token management for skill repos
area: api
files:
  - backend/skill_repos/service.py
  - backend/core/models/skill_repository.py
  - backend/alembic/versions/028_skill_repo_type.py
  - frontend/src/components/admin/skill-store-repos.tsx
---

## Problem

The skill store repo system only supports `agentskills-index.json` format. Real-world GitHub repos
(e.g. `coreyhaines31/marketingskills`, `anthropics/claude-plugins-official`) don't have this file.
Claude Code marketplace plugins use a different YAML structure. There is no adapter pattern — the
format is hardcoded in `fetch_index()` at `skill_repos/service.py:79`. Adding any non-compliant
repo results in Error 500.

The graceful GitHub fallback (gsd:quick) unblocks the 500 error, but full multi-format support
requires a proper `RepoAdapter` protocol and GitHub API token management.

## Solution

### Research needed (before coding)
- Fetch real Claude Code plugin YAML structure from `HKUDS/CLI-Anything` and
  `anthropics/claude-plugins-official/tree/main/plugins/agent-sdk-dev` — understand field names
  (`name`, `description`, `triggers`, `capabilities`, etc.)
- Decide GitHub token storage: credentials DB (per-user, complex) vs env var
  `GITHUB_API_TOKEN` in `backend/.env` (simpler, admin-scoped, fits YAGNI at 100-user scale)
- GitHub API rate limits: 60 req/hour anon, 5000 with token — Celery sync jobs will exhaust
  anon limit fast; token is likely required

### Implementation

1. **Migration 028** — add `repo_type VARCHAR(32) DEFAULT 'agentskills'` to `skill_repositories`
2. **`RepoAdapter` protocol** in `skill_repos/adapters.py`:
   - `AgentSkillsAdapter` — current behavior (agentskills-index.json)
   - `GitHubScanAdapter` — GitHub API: list files, find YAMLs, build synthetic index
   - `ClaudeCodePluginAdapter` — read plugin YAML, map capabilities → skill entries
3. **`detect_repo_type(url)` + `fetch_index()` dispatcher** in `service.py` — routes to correct adapter
4. **GitHub token** — read `settings.github_api_token` (optional), pass as Bearer header; log warning if absent
5. **Subdirectory repos** — parse `github.com/owner/repo/tree/branch/path` → GitHub API
   `GET /repos/{owner}/{repo}/contents/{path}`
6. **Frontend** — `repo_type` badge on repo cards ("AgentSkills", "GitHub", "Claude Plugin")

### References
- Phase 23 plan 03 design discussion (2026-03-10)
- Existing `fetch_index()`: `backend/skill_repos/service.py:65`
- `owner/repo` shorthand + graceful fallback already handled by gsd:quick task (2026-03-10)
- `RepoCreate` schema: `backend/skill_repos/schemas.py:16`
