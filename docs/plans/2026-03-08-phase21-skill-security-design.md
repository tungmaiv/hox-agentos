# Phase 21 Design: Skill Platform C — Security

**Date:** 2026-03-08
**Phase:** 21 of v1.3
**Depends on:** Phase 19 (allowed_tools column, SecurityScanner v1, source_hash), Phase 20 (catalog UIs, quarantine flow)

---

## Goal

Skills with scripts declare their dependencies explicitly, tool access is restricted to declared permissions, and imported skills are monitored for upstream changes.

## Requirements

| ID | Requirement |
|----|-------------|
| SKSEC-01 | SecurityScanner blocks skills using undeclared `subprocess`, `socket`, `os.system`, etc. |
| SKSEC-02 | Runtime enforcement: tool calls restricted to `allowed_tools ∩ user_acl`; configurable strict/permissive mode |
| SKSEC-03 | Update checker (Celery periodic task) detects upstream source URL changes → `pending_review` |
| SKSEC-04 | Trust score includes dependency risk (20%) + data flow analysis (file I/O + network egress) |

---

## Architecture: Defense in Depth

Three independent security layers, all building on existing infrastructure:

```
IMPORT TIME                    RUNTIME                    BACKGROUND
──────────────────             ──────────────────         ──────────────────
skill ZIP uploaded             skill execution request    Celery beat (daily)
       ↓                              ↓                          ↓
SecurityScanner v2             SkillToolGate              UpdateChecker task
  - dangerous builtins           - load allowed_tools         - HEAD / SHA-256
  - package manifest check       - intersect with user ACL    - detect change
  - file I/O scope               - admin mode (strict/perm)   - create pending_review
  - network egress               - log denial to audit        - notify admin (log)
  - trust score (5 factors)            ↓
       ↓                       allow or raise 403
quarantine / approved
```

**What's new vs what already exists:**
- `SecurityScanner` — extends existing (phase 19) with 2 new trust score factors
- `SkillToolGate` — new class, inserted into `_skill_executor_node` in `master_agent.py`
- `UpdateChecker` — new Celery periodic task in `scheduler/jobs.py`
- Admin mode config — new `platform_config` key: `skill_tool_gate_mode: strict|permissive`

No new services. No new DB tables beyond two columns on `skill_definitions` and one config key.

---

## Section 1: Dependency Scanner (SKSEC-01 + SKSEC-04)

### Two-Tier Scanning

**Tier 1 — Dangerous builtins (always blocked, zero tolerance)**

Static AST parse of all `.py` files in `scripts/`. Block if any of the following appear:
- `subprocess`, `os.system`, `os.popen`, `socket`, `eval`, `exec`, `__import__`

Rejection reason included in scanner output:
```
"undeclared_dangerous_builtin: subprocess.run at scripts/run.py:14"
```

**Tier 2 — Package imports vs manifest allowlist**

Parse `import X` / `from X import` statements. Compare against packages declared in `SKILL.md` under a new `dependencies.python` key. Undeclared third-party packages (not stdlib, not in manifest) → rejection.

### SKILL.md Manifest Addition

```yaml
dependencies:
  python: [requests, pydantic]   # declared third-party packages
  allowed_paths: [./data/]       # declared file I/O scope (relative to skill dir)
```

### Trust Score — 5 Factors (SKSEC-04)

| Factor | Weight | What it measures |
|--------|--------|-----------------|
| Code safety | 30% | Dangerous builtins, obfuscation |
| Dependency risk | 20% | Undeclared imports, known-bad package names |
| Data flow — file I/O | 15% | Reads/writes outside `allowed_paths` |
| Data flow — network egress | 15% | `urllib`, `requests`, `httpx`, `socket` usage detected |
| Metadata completeness | 20% | Author, version, description, license present in SKILL.md |

**Score 0–100. Existing thresholds unchanged:**
- < 40 → rejected
- 40–69 → quarantine (admin review required)
- 70+ → approved

### Implementation

- Extend `backend/security/skill_scanner.py` (or equivalent phase-19 scanner module)
- AST parsing via Python `ast` module — no external dependencies
- Data flow analysis: detect import usage patterns statically (not dynamic execution)
- Scanner runs synchronously at import time (acceptable at ~100-user scale)

---

## Section 2: Runtime Tool Gate (SKSEC-02)

### SkillToolGate Class

New class inserted into `_skill_executor_node` in `master_agent.py`, called before any tool dispatch.

**Decision logic:**

```
load skill.allowed_tools from DB (list[str] or empty)
load user's permitted tools from BlitzState (already populated by Gate 3)

if allowed_tools is empty:
    check platform_config["skill_tool_gate_mode"]
    → "strict":     effective_tools = {}          # deny all tool calls
    → "permissive": effective_tools = user_acl_tools  # inherit user ACL
else:
    effective_tools = set(allowed_tools) ∩ set(user_acl_tools)

tool call attempted:
    → in effective_tools → allow
    → not in effective_tools → deny + audit log + raise ToolAccessDenied
```

### Audit Log Entry on Denial

```json
{
  "event": "skill_tool_denied",
  "skill_id": "uuid",
  "skill_name": "string",
  "tool_name": "email.send",
  "allowed_by_skill": false,
  "allowed_by_acl": true,
  "gate_mode": "strict",
  "user_id": "uuid",
  "timestamp": "ISO8601"
}
```

### Admin Configuration

New toggle on existing **Admin → Platform Config** page:

- **Skill Tool Gate Mode**: `Strict` / `Permissive`
- Stored in `platform_config` table (key: `skill_tool_gate_mode`, value: `"strict"` or `"permissive"`)
- Default: `"permissive"` (non-breaking for existing installed skills)
- `platform_config` table already exists from phase 18

**No new DB columns** — `allowed_tools` column already added in phase 19.

---

## Section 3: Update Checker (SKSEC-03)

### Celery Periodic Task

New task `check_skill_updates` in `scheduler/jobs.py`, scheduled via Celery Beat.

**Algorithm per skill (with source_url set and status = approved):**

```
1. HTTP HEAD request to source_url
   → check Last-Modified and ETag headers vs stored values
   → if headers match stored values → no change, update last_checked_at

2. if headers absent OR values differ:
   → download full ZIP
   → compute SHA-256
   → compare vs stored source_hash

3. if SHA-256 changed:
   → create new SkillDefinition row:
       status = "pending_review"
       source_url = same
       source_hash = new hash
       parent_skill_id = current approved skill id
       change_detected_at = now()
   → emit audit log event: skill_update_detected
   → admin sees new pending_review entry in existing Admin → Skills page

4. if SHA-256 unchanged:
   → update source_etag, last_checked_at
   → no version created
```

### DB Changes — Two New Columns on `skill_definitions`

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `source_etag` | `VARCHAR(255)` | `NULL` | ETag from last successful HEAD check |
| `last_checked_at` | `TIMESTAMP WITH TIME ZONE` | `NULL` | When update checker last ran for this skill |

`source_url` and `source_hash` already exist (phase 19).

### Schedule

- Default: daily at 02:00 UTC
- Configurable via `platform_config["skill_update_check_schedule"]` (cron string)
- Frequency key stored in same `platform_config` table

### Admin Visibility

No new UI needed. Admins see new `pending_review` versions appear in the existing Admin → Skills catalog. The `change_detected_at` timestamp and `parent_skill_id` reference distinguish update-triggered reviews from fresh imports.

---

## Data Flow Summary

```
SKILL IMPORT
User uploads ZIP
    → SecurityScanner v2 (AST parse, dependency check, trust score)
    → status: rejected | quarantine | approved
    → stored in skill_definitions with source_hash, source_etag

SKILL EXECUTION
User triggers skill (chat or workflow)
    → SkillToolGate: load allowed_tools, intersect with user ACL, apply gate mode
    → allowed: tool call proceeds through existing Gate 3 path
    → denied: 403 + audit log event

BACKGROUND (daily)
UpdateChecker iterates approved skills with source_url
    → HEAD → SHA-256 comparison
    → change detected: new pending_review row, admin notified via audit log
```

---

## Out of Scope (Phase 21)

- npm/Go/Rust dependency scanning (Python only for MVP)
- Email/push notifications for update alerts (audit log is sufficient for ~100 users)
- Automatic application of updates (always requires admin approval)
- Dynamic import detection (static AST only — YAGNI)

---

## Success Criteria

1. A procedural skill using `subprocess.run` is rejected at import with specific reason in scanner output
2. A skill with `allowed_tools: [email.read]` cannot call `email.send` at runtime; denial appears in audit log
3. An approved skill whose source ZIP changes at `source_url` gains a `pending_review` sibling within 24 hours
4. Trust score breakdown (5 factors) visible in skill detail view / scanner output
5. Admin can toggle strict/permissive mode and the change takes effect on next skill execution (no restart required)
