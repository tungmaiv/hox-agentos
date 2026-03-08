# Phase 21: Skill Platform C — Dependency & Security Hardening - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Skills with `scripts/` directories must declare their Python dependencies explicitly, and SecurityScanner blocks undeclared subprocess/socket/os.system usage. At skill execution time, tool calls are restricted to the intersection of the skill's declared `allowed_tools` and the user's ACL. A Celery periodic task monitors imported skill source URLs for upstream content changes and creates a `pending_review` version when a change is detected. SecurityScanner gains two new scoring factors (dependency_risk and data_flow_risk) replacing the existing author_verification factor.

Skill sharing, export download, and the enhanced builder are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Dependency declaration format (SKSEC-01)
- Dependency declaration supports two locations: `dependencies:` list in SKILL.md frontmatter (primary) OR `scripts/requirements.txt` in the ZIP bundle (fallback). Importer checks frontmatter first, then falls back to `scripts/requirements.txt`.
- Python stdlib modules are always allowed without declaration — only third-party packages require explicit listing.
- If `scripts/` directory exists but NO dependency declaration is found in either location: import succeeds but SecurityScanner notes "no dependency declaration found" and reduces trust score. It does NOT block import outright.
- SecurityScanner performs static AST scan of `.py` files in `scripts/` using Python's `ast` module: extract all import/from statements, compare against declared deps + stdlib allowlist.
- Undeclared third-party import found → skill is rejected (trust score → 0, recommendation = "reject"). Admin sees the specific undeclared module name in the security report.
- Dependency check applies to imported skills only (`source_type='imported'`). Builtin and user_created skills are not checked.

### allowed-tools enforcement (SKSEC-02)
- `allowed_tools = null/empty` → permissive: all tools permitted that the user's ACL allows. Backwards-compatible with all existing procedural skills.
- When `allowed_tools` is set, the check runs BEFORE Gate 3 ACL check. If tool is not in `allowed_tools`, fail immediately without a DB lookup.
- Blocked by `allowed_tools` → fail the entire skill run. Return `SkillResult(success=False, failed_step=step_id)`. User sees: "Tool X not permitted by this skill."
- Audit log: structured structlog entry `skill_allowed_tools_denied` with fields: `skill_name`, `skill_id`, `tool_name`, `user_id`, `declared_allowed_tools`. Same log level as existing Gate 3 denials.

### Update checker (SKSEC-03)
- Celery periodic task runs **daily** (e.g., 2am).
- Change detection: SHA-256 hash of raw HTTP response body from `source_url`. If hash differs from stored `source_hash`, a change is detected.
- `source_hash` stored in a new `source_hash TEXT` column on `skill_definitions`. Populated at import time for skills with a `source_url`, updated when a new version row is created.
- On change detected: create a **new DB row** with the same `name`, patch-bumped `version` (e.g., `1.0.0` → `1.0.1`), status=`pending_review`. The original version row stays active until an admin reviews and approves.
- Admin notification: visual badge/indicator on the skill card in the admin catalog (e.g., "Update available"). No email or push notification. Admin discovers it the next time they open the catalog.
- Only skills with `source_type='imported'` and a non-null `source_url` are checked.

### SecurityScanner enhancement (SKSEC-04)
- Author verification factor (10%) is removed and replaced by two new factors.
- New scoring weights (sum = 100%):
  - `source_reputation`: 30%
  - `tool_scope`: 20% (reduced from 25%)
  - `prompt_safety`: 25%
  - `complexity`: 5% (reduced from 10%)
  - `dependency_risk`: 20% (new)
  - `data_flow_risk`: 0% → wait, 30+20+25+5+20 = 100 with no data_flow slot. Claude's discretion on final weight distribution — recommended: source_rep 25%, tool_scope 20%, prompt_safety 20%, complexity 5%, dependency_risk 20%, data_flow_risk 10% = 100%.

- **Dependency risk factor** scores on three signals:
  1. Dangerous module names in declared deps: requests, httpx, paramiko, cryptography, pycryptodome, scapy, nmap → score penalty.
  2. Package count/bloat: 0 deps = 100, 1–3 deps = 80, 4–10 deps = 50, 10+ deps = 20.
  3. Undeclared packages detected by AST scan: any undeclared import → factor score = 0 (maximum risk).

- **Data flow risk factor** detects three patterns:
  1. Data exfiltration paths: skill reads sensitive data (email.fetch, crm.get) and passes output to an external/outbound tool (http.post, sandbox.run). Lower score when this pattern is found.
  2. Secret/credential patterns in prompt templates: regex match for "api key", "password", "token", "Bearer" patterns in `prompt_template` fields.
  3. Tool chain risk escalation: tool output from a read-only tool flows into a write/admin/sandbox tool. Score based on the severity of the escalation.

### Claude's Discretion
- Exact final weight percentages for the 6 SecurityScanner factors (must sum to 100%)
- Specific scoring thresholds within each factor (e.g., exactly how much penalty per dangerous module name)
- AST-based import extraction implementation details (how to distinguish stdlib vs. third-party reliably — `sys.stdlib_module_names` in Python 3.10+)
- Celery beat schedule configuration (cron expression, task name)
- Exact patch version bump logic (semver parsing)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/skills/security_scanner.py`: `SecurityScanner.scan()` — add new `_score_dependency_risk()` and `_score_data_flow_risk()` methods; update `scan()` to include them and rebalance weights. `_COMPILED_PATTERNS` pattern approach reusable for data_flow credential pattern detection.
- `backend/skills/executor.py`: `SkillExecutor._run_tool_step()` — inject `allowed_tools` check BEFORE the existing `check_tool_acl()` call. `SkillStepError` is already the correct exception type.
- `backend/skills/importer.py`: `SkillImporter.parse_skill_md()` and ZIP import logic — extend to parse `dependencies:` frontmatter field and read `scripts/requirements.txt` from ZIP. Already parses `allowed-tools` (precedent for the same pattern).
- `backend/scheduler/tasks/`: Celery task infrastructure — add `check_skill_updates.py` task file here. `backend/scheduler/celery_app.py` for beat schedule registration.
- `backend/core/models/skill_definition.py`: add `source_hash TEXT` column (migration 023 — current head is 022 after Phase 20's usage_count migration).
- `backend/security/acl.py`: `check_tool_acl()` — this is called after the new `allowed_tools` check; order preserved.

### Established Patterns
- `JSON().with_variant(JSONB(), 'postgresql')` on JSONB columns for SQLite test compat — already in `skill_definitions`. New `source_hash` is TEXT so no variant needed.
- `structlog.get_logger(__name__)` for all logging — reuse for audit entries.
- `get_audit_logger()` for security-sensitive events (Gate 3 denials) — `skill_allowed_tools_denied` should use audit logger.
- Migration chain: current head after Phase 20 is **022** (usage_count on skill_definitions) — next migration is **023**.

### Integration Points
- `backend/api/routes/admin_skills.py`: skill import endpoint calls `SecurityScanner.scan()` — no change needed; enhanced scanner is a drop-in replacement.
- `backend/skill_repos/service.py`: calls `SecurityScanner` after fetch — same integration point.
- `backend/api/routes/user_skills.py`: `run_user_skill` calls `SkillExecutor.run()` — no route change; enforcement is inside executor.
- Admin catalog frontend: needs "Update available" badge on skill cards where `status='pending_review'` and `source_url` is set — existing `ArtifactCardGrid` card component.

</code_context>

<specifics>
## Specific Ideas

- The `allowed_tools` check before Gate 3 ACL is a deliberate optimization: if the skill's own declaration prohibits the tool, there's no need to hit the DB for an ACL lookup.
- The update checker should store the `source_hash` at import time so the first run has something to compare against — don't just start hashing on the first Celery run.
- Data flow analysis: the key risk pattern is "read sensitive data → send outbound" (fetch email → HTTP post). This should score the lowest.

</specifics>

<deferred>
## Deferred Ideas

- **Importing Claude Code skills from GitHub** — The user asked about fetching skills from the Claude Code skill repo on GitHub and converting them to AgentOS SkillDefinitions. This requires a format adapter (Claude Code skill YAML → agentskills.io SKILL.md format). Best fit: **Phase 23 (Enhanced Builder)** which already has "external learning" and "searches cached external repo indexes." Add as a builder source type there.

</deferred>

---

*Phase: 21-skill-platform-c-dependency-security-hardening*
*Context gathered: 2026-03-08*
