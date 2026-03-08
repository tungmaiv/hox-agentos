# Phase 21: Skill Platform C — Dependency & Security Hardening - Research

**Researched:** 2026-03-08
**Domain:** Python AST static analysis, Celery periodic tasks, SecurityScanner enhancement, SkillExecutor security gates
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Dependency declaration format (SKSEC-01)**
- Two locations supported: `dependencies:` list in SKILL.md frontmatter (primary) OR `scripts/requirements.txt` in ZIP bundle (fallback). Importer checks frontmatter first, then falls back.
- Python stdlib modules are always allowed without declaration — only third-party packages require explicit listing.
- If `scripts/` directory exists but NO dependency declaration is found in either location: import succeeds but SecurityScanner notes "no dependency declaration found" and reduces trust score. Does NOT block outright.
- SecurityScanner performs static AST scan of `.py` files in `scripts/` using Python's `ast` module: extract all import/from statements, compare against declared deps + stdlib allowlist.
- Undeclared third-party import found → skill is rejected (trust score → 0, recommendation = "reject"). Admin sees the specific undeclared module name in the security report.
- Dependency check applies to imported skills only (`source_type='imported'`). Builtin and user_created skills are not checked.

**allowed-tools enforcement (SKSEC-02)**
- `allowed_tools = null/empty` → permissive: all tools permitted that the user's ACL allows. Backwards-compatible with all existing procedural skills.
- When `allowed_tools` is set, the check runs BEFORE Gate 3 ACL check. If tool is not in `allowed_tools`, fail immediately without a DB lookup.
- Blocked by `allowed_tools` → fail the entire skill run. Return `SkillResult(success=False, failed_step=step_id)`. User sees: "Tool X not permitted by this skill."
- Audit log: structured structlog entry `skill_allowed_tools_denied` with fields: `skill_name`, `skill_id`, `tool_name`, `user_id`, `declared_allowed_tools`. Same log level as existing Gate 3 denials. Use `get_audit_logger()`.

**Update checker (SKSEC-03)**
- Celery periodic task runs daily (e.g., 2am).
- Change detection: SHA-256 hash of raw HTTP response body from `source_url`. If hash differs from stored `source_hash`, change is detected.
- `source_hash` stored in a new `source_hash TEXT` column on `skill_definitions`. Populated at import time for skills with a `source_url`, updated when a new version row is created.
- On change detected: create a new DB row with the same `name`, patch-bumped `version` (e.g., `1.0.0` → `1.0.1`), `status='pending_review'`. Original version row stays active until admin approves.
- Admin notification: visual badge/indicator on skill card in admin catalog. No email/push notification. Frontend already shows orange badge for `status='pending_review'`.
- Only skills with `source_type='imported'` and a non-null `source_url` are checked.

**SecurityScanner enhancement (SKSEC-04)**
- Author verification factor (10%) removed, replaced by two new factors.
- Final weight distribution (Claude's discretion — must sum to 100%):
  - `source_reputation`: 25%
  - `tool_scope`: 20%
  - `prompt_safety`: 20%
  - `complexity`: 5%
  - `dependency_risk`: 20%
  - `data_flow_risk`: 10%
- Dependency risk factor (three signals): dangerous module names, package count/bloat, undeclared packages detected by AST scan (= factor score 0).
- Data flow risk factor (three patterns): exfiltration paths (read sensitive → send external), credential patterns in prompt templates, tool chain risk escalation.

### Claude's Discretion
- Exact final weight percentages for the 6 SecurityScanner factors (must sum to 100%) → research recommends: 25/20/20/5/20/10
- Specific scoring thresholds within each factor
- AST-based import extraction implementation details (`sys.stdlib_module_names` in Python 3.10+)
- Celery beat schedule configuration (cron expression, task name)
- Exact patch version bump logic (semver parsing)

### Deferred Ideas (OUT OF SCOPE)
- Importing Claude Code skills from GitHub — format adapter (Claude Code skill YAML → agentskills.io SKILL.md format). Deferred to Phase 23.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SKSEC-01 | Skills with `scripts/` directory must declare dependencies explicitly; SecurityScanner blocks undeclared subprocess/socket/os.system usage | AST `ast.parse()` + `sys.stdlib_module_names` enables reliable stdlib vs third-party detection; importer extension pattern confirmed |
| SKSEC-02 | `allowed-tools` enforcement: SkillExecutor restricts tool calls to intersection of skill's declared `allowed-tools` and user's ACL; denied calls logged to audit | Inject check into `_run_tool_step()` before `check_tool_acl()` call; `get_audit_logger()` pattern established in `security/acl.py` |
| SKSEC-03 | Update checker (Celery periodic task) re-fetches `source_url`, compares hash, creates `pending_review` version if changed | Celery beat schedule pattern established in `celery_app.py`; `asyncio.run()` pattern from `embedding.py`; `pending_review` status already has orange badge in frontend |
| SKSEC-04 | SecurityScanner enhanced with dependency risk factor (20%) and data flow analysis factor (replaces author verification 10%) | All changes confined to `security_scanner.py`; drop-in via existing integration points; test file covers weighted score formula |
</phase_requirements>

---

## Summary

Phase 21 adds four security capabilities to the skill platform: dependency declaration enforcement with static AST scanning, `allowed_tools` runtime enforcement in the executor, a Celery periodic task that monitors imported skill sources for upstream changes, and an enhanced SecurityScanner with two new scoring factors.

All four features build on existing infrastructure with minimal new abstractions. The SecurityScanner changes are a pure code modification — no schema changes. The `allowed_tools` enforcement is a 15-line injection into `_run_tool_step()`. The update checker follows the exact Celery task pattern used by `embedding.py`. The only schema change is adding a single `source_hash TEXT` column (migration 024 — current head is 023).

The key technical insight is that Python 3.10+ ships `sys.stdlib_module_names` — a frozenset of all stdlib module names — making stdlib vs. third-party classification reliable without any external package. Since the backend runs Python 3.13.3 (confirmed), this is directly available.

**Primary recommendation:** Implement in four plans — one per requirement — in dependency order: SKSEC-04 (scanner), then SKSEC-01 (AST scanner which calls the enhanced scanner), then SKSEC-02 (executor), then SKSEC-03 (Celery task + migration).

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `ast` (stdlib) | Python 3.13 built-in | Parse `.py` files, extract import nodes | No dependency; `ast.parse()` is the canonical Python static analysis tool |
| `sys.stdlib_module_names` (stdlib) | Python 3.10+ | Frozenset of all stdlib module names | Official Python 3.10+ API; available on Python 3.13.3 (confirmed) |
| `hashlib` (stdlib) | Python 3.13 built-in | SHA-256 hash of HTTP response body | No dependency; used for `source_hash` |
| `celery` | 5+ (existing) | Periodic update checker task | Already in project; beat schedule pattern established |
| `httpx` | existing | Re-fetch `source_url` in Celery task | Already used in `importer.py`; `asyncio.run(async_fn())` pattern for Celery |
| `structlog` | existing | Audit logging for `skill_allowed_tools_denied` | Project standard; `get_audit_logger()` established |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `semver` (NOT needed) | n/a | Version bump | Simple string split sufficient: `"1.0.0"` → split on `.` → bump patch int |
| `re` (stdlib) | built-in | Credential patterns in data flow analysis | Already used in `security_scanner.py` for `_COMPILED_PATTERNS` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `sys.stdlib_module_names` | `isort`/`pipreqs` | External packages vs. built-in frozenset — stdlib frozenset is simpler, no dep |
| `asyncio.run()` in Celery | `sync_to_async` | asyncio.run() is established project pattern — keep consistent |

**Installation:** No new packages needed. All dependencies are stdlib or already in project.

---

## Architecture Patterns

### Recommended Project Structure

Changes are confined to existing files + one new file:

```
backend/
├── skills/
│   ├── security_scanner.py    # MODIFY: add _score_dependency_risk(), _score_data_flow_risk()
│   ├── importer.py            # MODIFY: parse dependencies: frontmatter + scripts/requirements.txt
│   └── executor.py            # MODIFY: inject allowed_tools check in _run_tool_step()
├── scheduler/
│   ├── celery_app.py          # MODIFY: add check_skill_updates task to include/beat_schedule
│   └── tasks/
│       └── check_skill_updates.py   # NEW: daily Celery task for source URL change detection
├── core/models/
│   └── skill_definition.py    # MODIFY: add source_hash TEXT column
└── alembic/versions/
    └── 024_skill_source_hash.py     # NEW: migration for source_hash column
```

### Pattern 1: AST Import Extraction

**What:** Parse `.py` files in `scripts/` to extract all imported module names, classify as stdlib vs. third-party.

**When to use:** During `SecurityScanner.scan()` when `skill_data` includes scripts content (added by importer for ZIP bundles with `scripts/` dir).

**Example:**
```python
# Source: Python stdlib ast module documentation
import ast
import sys

_STDLIB_MODULES: frozenset[str] = sys.stdlib_module_names  # Python 3.10+

def _extract_imports(source_code: str) -> set[str]:
    """Extract top-level module names from Python source using AST."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        # Unparseable file — treat as undeclared (maximum risk)
        return {"<unparseable>"}

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # Top-level name: "os.path" → "os"
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    return imported

def _is_third_party(module_name: str) -> bool:
    """Return True if module_name is not in Python stdlib."""
    return module_name not in _STDLIB_MODULES and not module_name.startswith("_")
```

### Pattern 2: allowed_tools Check Before Gate 3 ACL

**What:** Inject a skill-declared tool restriction before the DB-based ACL lookup.

**When to use:** In `_run_tool_step()`, immediately after extracting `tool_name`.

**Example:**
```python
# In skills/executor.py → _run_tool_step()
async def _run_tool_step(self, step, context, user_id, session, allowed_tools=None):
    tool_name = step["tool"]

    # Skill-declared allowed_tools check (before Gate 3 — no DB lookup needed)
    if allowed_tools is not None:
        if tool_name not in allowed_tools:
            audit_logger.info(
                "skill_allowed_tools_denied",
                skill_name=self._current_skill_name,
                skill_id=str(self._current_skill_id),
                tool_name=tool_name,
                user_id=str(user_id),
                declared_allowed_tools=allowed_tools,
            )
            raise SkillStepError(
                f"Tool '{tool_name}' not permitted by this skill. "
                f"Declared allowed tools: {allowed_tools}"
            )

    # Gate: verify tool exists and is active
    tool_def = await get_tool(tool_name, session)
    ...
    # Gate 3: Tool ACL check (existing)
    allowed = await check_tool_acl(user_id, tool_name, session)
    ...
```

Note: `allowed_tools` must be passed from `run()` into `_run_tool_step()`. The `run()` method reads `skill.allowed_tools` (already on ORM model) and passes it through. The audit logger must be imported from `core.logging`.

### Pattern 3: Celery Daily Periodic Task

**What:** Daily Celery beat task that fetches source URLs, computes SHA-256 hash, compares to stored `source_hash`, creates `pending_review` version on change.

**When to use:** New file `scheduler/tasks/check_skill_updates.py`.

**Example:**
```python
# Source: embedding.py pattern (asyncio.run inside Celery task)
import asyncio
import hashlib

import httpx
import structlog

from scheduler.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    queue="default",
    name="scheduler.tasks.check_skill_updates.check_skill_updates_task",
)
def check_skill_updates_task() -> None:
    """Daily check for upstream changes to imported skill source URLs."""
    asyncio.run(_check_all_skill_updates())


async def _check_all_skill_updates() -> None:
    from core.db import async_session
    from core.models.skill_definition import SkillDefinition
    from sqlalchemy import select

    async with async_session() as session:
        result = await session.execute(
            select(SkillDefinition).where(
                SkillDefinition.source_type == "imported",
                SkillDefinition.source_url.isnot(None),
                SkillDefinition.status == "active",
            )
        )
        skills = result.scalars().all()

    for skill in skills:
        await _check_single_skill(skill)


async def _check_single_skill(skill) -> None:
    from core.db import async_session
    from core.models.skill_definition import SkillDefinition

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(skill.source_url)
            resp.raise_for_status()
    except Exception as exc:
        logger.warning("skill_update_check_fetch_failed",
                       skill_name=skill.name, error=str(exc))
        return

    new_hash = hashlib.sha256(resp.content).hexdigest()

    if new_hash == skill.source_hash:
        return  # No change

    # Change detected — create pending_review version
    _bump_patch = _bump_version(skill.version)
    async with async_session() as session:
        new_row = SkillDefinition(
            name=skill.name,
            version=_bump_patch,
            status="pending_review",
            source_type=skill.source_type,
            source_url=skill.source_url,
            source_hash=new_hash,
            # copy other fields from parent skill...
        )
        session.add(new_row)
        await session.commit()

    logger.info("skill_update_detected",
                skill_name=skill.name, new_version=_bump_patch)


def _bump_version(version: str) -> str:
    """Bump patch segment: '1.0.0' → '1.0.1'."""
    parts = version.split(".")
    if len(parts) == 3:
        try:
            parts[2] = str(int(parts[2]) + 1)
            return ".".join(parts)
        except ValueError:
            pass
    return f"{version}.1"
```

**celery_app.py additions:**
```python
# In include list:
"scheduler.tasks.check_skill_updates",

# In task_routes:
"scheduler.tasks.check_skill_updates.check_skill_updates_task": {"queue": "default"},

# In beat_schedule:
"check-skill-updates-daily": {
    "task": "scheduler.tasks.check_skill_updates.check_skill_updates_task",
    "schedule": crontab(hour=2, minute=0),  # 2am UTC daily
},
```

Note: `crontab` requires `from celery.schedules import crontab`.

### Pattern 4: SecurityScanner Weight Rebalancing

**What:** Remove `_score_author_verification()` (always returned 50, contributing nothing meaningful). Add two new scoring methods. Update weights.

**New weights (sum = 100%):**
- `source_reputation`: 0.25
- `tool_scope`: 0.20
- `prompt_safety`: 0.20
- `complexity`: 0.05
- `dependency_risk`: 0.20
- `data_flow_risk`: 0.10

**Key note:** All existing tests in `test_security_scanner.py` that assert `report.factors["author_verification"]` or verify the old weighted formula must be updated. The `TestWeightedScoring.test_weights_sum_correctly` test references the old formula directly.

### Anti-Patterns to Avoid
- **Doing AST scanning inline in `importer.py`:** Scanner is the security gate, not the importer. Importer extracts and passes scripts content; scanner does AST analysis.
- **Checking `allowed_tools` AFTER Gate 3 ACL:** Defeats the optimization — if skill doesn't allow the tool, never hit the DB.
- **Fetching source URLs synchronously inside Celery task body:** Use `asyncio.run()` wrapping an `async def` (established pattern from `embedding.py`).
- **Storing SHA-256 as bytes:** Store as hex string (64 chars). `hashlib.sha256(b).hexdigest()` returns a hex string, stored in `TEXT` column.
- **Using `semver` package for patch bump:** Overkill — simple string split is sufficient and requires no new dependency.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Stdlib module list | Custom allowlist | `sys.stdlib_module_names` | Python 3.10+ frozenset; always current with interpreter |
| Cron scheduling | Custom timer loop | Celery beat `crontab(hour=2, minute=0)` | Already in project; reliable |
| URL fetch retry | Custom retry loop | `httpx.AsyncClient` with timeout; log and skip on failure | Simple: skip failed checks, try again tomorrow |
| Semver parsing | Full semver library | String split + int increment | Only need patch bump; no dep needed |

**Key insight:** All four SKSEC requirements are achievable with stdlib + existing project dependencies. No new packages needed.

---

## Common Pitfalls

### Pitfall 1: `sys.stdlib_module_names` Availability
**What goes wrong:** Code uses `sys.stdlib_module_names` but backend container runs Python <3.10.
**Why it happens:** Attribute added in Python 3.10. Older Pythons raise `AttributeError`.
**How to avoid:** Confirmed Python 3.13.3 in backend container. No fallback needed. Document in code with `# Python 3.10+`.
**Warning signs:** `AttributeError: module 'sys' has no attribute 'stdlib_module_names'`

### Pitfall 2: SecurityScanner Existing Tests Break on Weight Change
**What goes wrong:** `TestWeightedScoring.test_weights_sum_correctly` hardcodes old formula with `author_verification * 0.10`.
**Why it happens:** The test directly references factor names and weights.
**How to avoid:** Update test alongside code. The test must be updated in the same plan as the scanner change. Also check `test_clean_skill_high_score` — the score threshold may change with new weights.
**Warning signs:** `test_weights_sum_correctly` fails with `KeyError: 'author_verification'`

### Pitfall 3: Alembic Migration Numbering
**What goes wrong:** Developer creates migration `024` but current head is `023` — chain breaks if another migration was inserted.
**Why it happens:** Migration chain is linear. Current confirmed head is `023` (Phase 20's FTS migration).
**How to avoid:** Always run `.venv/bin/alembic heads` before creating. Next migration is `024`.
**Warning signs:** `Multiple heads` error from alembic.

### Pitfall 4: Celery Beat Not Restarted After Code Change
**What goes wrong:** New beat schedule added to `celery_app.py` but Celery beat process still running old config.
**Why it happens:** Celery beat reads schedule at startup. Code change requires worker restart.
**How to avoid:** After adding beat schedule, run `just dev-local-restart-workers`.
**Warning signs:** Task never fires on schedule.

### Pitfall 5: `source_hash` Populated at Import Time
**What goes wrong:** Celery task runs for first time, no `source_hash` stored, compares `None != new_hash`, creates spurious `pending_review` for all imported skills.
**Why it happens:** `source_hash` was null when skill was imported (before this phase).
**How to avoid:** Update checker must treat `source_hash IS NULL` as "no baseline — store hash without creating pending_review version." Only create pending_review when hash changes from a known value.
**Warning signs:** All imported skills get `pending_review` after first Celery run.

### Pitfall 6: ZIP scripts/ Content Not Passed to Scanner
**What goes wrong:** AST scan never fires because `skill_data` dict doesn't include scripts content.
**Why it happens:** `import_from_zip()` currently ignores `scripts/` directory entirely.
**How to avoid:** When extracting ZIP, collect all `.py` files from `scripts/` subdirectory and add their content to `skill_data["scripts_content"]` (list of `{"filename": str, "source": str}`). Scanner reads this field.
**Warning signs:** Dependency scan always scores 100 even for skills with `scripts/`.

### Pitfall 7: `allowed_tools` None vs Empty List Distinction
**What goes wrong:** `skill.allowed_tools = []` (empty list, not None) treated as permissive, but empty list means "no tools permitted."
**Why it happens:** Ambiguity between null (not set) and empty (explicitly zero tools).
**How to avoid:** Per CONTEXT.md decision: `null/empty` is permissive. Check `if allowed_tools is not None and len(allowed_tools) > 0:`. An explicit empty list is treated same as null (permissive). This matches the backwards-compat requirement.
**Warning signs:** Skills with no `allowed_tools` set start failing tool calls.

---

## Code Examples

### AST Scan in SecurityScanner

```python
# Source: Python docs — ast module, sys.stdlib_module_names
import ast
import sys

_STDLIB_MODULES: frozenset[str] = sys.stdlib_module_names  # Python 3.10+

# Dangerous third-party packages (signal penalty in dependency_risk)
_DANGEROUS_PACKAGES: frozenset[str] = frozenset({
    "requests", "httpx", "paramiko", "cryptography",
    "pycryptodome", "scapy", "nmap",
})

def _score_dependency_risk(self, skill_data: dict[str, Any]) -> int:
    """Score dependency risk: package count, dangerous names, undeclared imports."""
    scripts_content: list[dict[str, str]] = skill_data.get("scripts_content", [])
    declared_deps: list[str] = skill_data.get("declared_dependencies", [])

    if not scripts_content:
        return 100  # No scripts — no dependency risk

    # Extract all imported third-party modules from scripts
    all_imports: set[str] = set()
    for script in scripts_content:
        extracted = _extract_imports_from_source(script["source"])
        third_party = {m for m in extracted if _is_third_party(m)}
        all_imports.update(third_party)

    # Signal 3: Undeclared import → score = 0 (reject)
    declared_set = set(declared_deps)
    undeclared = all_imports - declared_set
    if undeclared:
        # Store undeclared for security report
        skill_data.setdefault("_undeclared_imports", list(undeclared))
        return 0

    # Signal 1: Dangerous package names in declared deps
    dangerous_found = declared_set & _DANGEROUS_PACKAGES
    danger_penalty = len(dangerous_found) * 20  # 20 per dangerous package

    # Signal 2: Package count/bloat
    count = len(declared_set)
    if count == 0:
        bloat_score = 100
    elif count <= 3:
        bloat_score = 80
    elif count <= 10:
        bloat_score = 50
    else:
        bloat_score = 20

    raw = max(0, bloat_score - danger_penalty)
    return raw
```

### Data Flow Risk Factor

```python
# Pattern: exfiltration (read sensitive → send outbound)
_OUTBOUND_TOOLS: frozenset[str] = frozenset({"http.post", "sandbox.run"})
_SENSITIVE_READ_TOOLS: frozenset[str] = frozenset({
    "email.fetch", "crm.get", "crm.list", "calendar.list"
})
# Credential patterns in prompt templates
_CREDENTIAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [r"api.?key", r"password", r"\btoken\b", r"Bearer\s+\S+"]
]

def _score_data_flow_risk(self, skill_data: dict[str, Any]) -> int:
    """Score data flow risk: exfiltration paths, credential patterns, escalation."""
    procedure = skill_data.get("procedure_json")
    if not procedure:
        return 100  # Instructional skills have no data flow

    steps = procedure.get("steps", [])
    tool_steps = [s for s in steps if isinstance(s, dict) and s.get("type") == "tool"]
    tool_names = [s.get("tool", "") for s in tool_steps]

    score = 100

    # Signal 1: Exfiltration — sensitive read before outbound call
    has_sensitive_read = any(t in _SENSITIVE_READ_TOOLS for t in tool_names)
    has_outbound = any(t in _OUTBOUND_TOOLS for t in tool_names)
    if has_sensitive_read and has_outbound:
        score -= 60  # High penalty for read-then-exfiltrate

    # Signal 2: Credential patterns in prompt templates
    all_prompts = " ".join(
        s.get("prompt_template", "") for s in steps if isinstance(s, dict)
    )
    for pattern in _CREDENTIAL_PATTERNS:
        if pattern.search(all_prompts):
            score -= 30
            break

    # Signal 3: Tool chain escalation (read → write → admin/sandbox)
    tool_scope_order = [self._classify_tool_scope(t) for t in tool_names]
    if tool_scope_order:
        min_scope = min(tool_scope_order)
        if min_scope == 0:  # admin tool
            score -= 40
        elif min_scope <= 30:  # sandbox tool
            score -= 20

    return max(0, score)
```

### importer.py — Dependency Field Parsing

```python
# In SkillImporter.parse_skill_md() — add after existing optional field parsing
if "dependencies" in frontmatter:
    raw_deps = frontmatter["dependencies"]
    if isinstance(raw_deps, list):
        skill_data["declared_dependencies"] = [str(d) for d in raw_deps]
    elif isinstance(raw_deps, str):
        skill_data["declared_dependencies"] = raw_deps.split()

# In SkillImporter.import_from_zip() — after parse_skill_md():
# Extract scripts/ content for AST scanning
scripts_content: list[dict[str, str]] = []
for name in zf.namelist():
    parts = name.replace("\\", "/").split("/")
    # Match scripts/ subdir files ending in .py
    if "scripts" in parts and name.endswith(".py"):
        try:
            source = zf.read(name).decode("utf-8")
            scripts_content.append({"filename": parts[-1], "source": source})
        except Exception:
            pass
if scripts_content:
    skill_data["scripts_content"] = scripts_content

# Fallback: scripts/requirements.txt if no frontmatter dependencies
if "declared_dependencies" not in skill_data:
    for name in zf.namelist():
        if name.replace("\\", "/").endswith("scripts/requirements.txt"):
            try:
                req_text = zf.read(name).decode("utf-8")
                deps = [
                    line.strip().split("==")[0].split(">=")[0].split("~=")[0].strip()
                    for line in req_text.splitlines()
                    if line.strip() and not line.startswith("#")
                ]
                skill_data["declared_dependencies"] = deps
            except Exception:
                pass
            break
```

### Migration 024

```python
# alembic/versions/024_skill_source_hash.py
"""add source_hash column to skill_definitions

Revision ID: 024
Revises: 023
Create Date: 2026-03-08 00:00:00.000000

Phase 21-SKSEC-03: Add source_hash TEXT for update checker.
"""
from alembic import op
import sqlalchemy as sa

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        "skill_definitions",
        sa.Column("source_hash", sa.Text, nullable=True),
    )

def downgrade() -> None:
    op.drop_column("skill_definitions", "source_hash")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Author verification (always returns 50) | Removed; replaced by dependency_risk + data_flow_risk | Phase 21 | Scores become more meaningful; factor names change |
| No `scripts/` dependency tracking | AST scan + declared dep requirement | Phase 21 | Imported skills with scripts must declare deps |
| No `source_hash` | SHA-256 stored at import + daily diff | Phase 21 | Enables upstream change detection |

**Deprecated/outdated:**
- `_score_author_verification()`: Remove entirely. MVPing as "always 50" provided no security value. Replaced by more concrete signals.
- Old test `TestWeightedScoring.test_weights_sum_correctly`: Must be rewritten with new 6-factor formula.

---

## Open Questions

1. **How to handle multiple active versions of same skill in update checker**
   - What we know: `UNIQUE(name, version)` constraint. Multiple rows with same name but different versions can exist.
   - What's unclear: Should the checker scan only the highest active version? Or all active rows?
   - Recommendation: Query only `status='active'` skills. If a skill has multiple active versions, check each independently. In practice, only one version should be `active` at a time (admin workflow).

2. **`skills_content` field in SecurityScanner when skill is imported via SKILL.md URL (not ZIP)**
   - What we know: ZIP import can extract `scripts/` dir. URL import of a plain SKILL.md has no scripts.
   - What's unclear: If a SKILL.md at a URL somehow references scripts, how are they obtained?
   - Recommendation: Only ZIP bundles can include `scripts/`. URL SKILL.md import never has `scripts_content`. Scanner checks `skill_data.get("scripts_content", [])` — empty list = no script risk (score 100 for dependency factor).

3. **Skill copy completeness in pending_review row**
   - What we know: On change detection, a new DB row is created with bumped version.
   - What's unclear: Which fields to copy from the original vs. re-parsing from the fetched content.
   - Recommendation: Re-parse the fetched content using `SkillImporter` (same as original import) + run SecurityScanner. Store all parsed fields in new row. This ensures the pending_review version reflects actual upstream content, not just a version bump of stale data.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python 3.13.3) |
| Config file | none — invoked directly |
| Quick run command | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/test_security_scanner.py tests/test_skill_executor.py tests/test_skill_importer.py -q` |
| Full suite command | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SKSEC-04 | SecurityScanner new 6-factor weighted score | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_security_scanner.py -x -q` | ✅ (needs update) |
| SKSEC-04 | dependency_risk factor: zero score when undeclared import | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_security_scanner.py::TestDependencyRisk -x` | ❌ Wave 0 |
| SKSEC-04 | data_flow_risk factor: exfiltration pattern detected | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_security_scanner.py::TestDataFlowRisk -x` | ❌ Wave 0 |
| SKSEC-01 | Importer parses `dependencies:` frontmatter | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_skill_importer.py::TestDependencyParsing -x` | ❌ Wave 0 |
| SKSEC-01 | Importer extracts scripts/ content from ZIP | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_skill_importer.py::TestZipScripts -x` | ❌ Wave 0 |
| SKSEC-01 | Undeclared third-party import → reject recommendation | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_security_scanner.py::TestDependencyRisk::test_undeclared_import_rejected -x` | ❌ Wave 0 |
| SKSEC-02 | allowed_tools enforcement blocks undeclared tool | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_skill_executor.py::TestAllowedTools -x` | ❌ Wave 0 |
| SKSEC-02 | allowed_tools=None is permissive (backwards compat) | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_skill_executor.py::TestAllowedTools::test_null_allowed_tools_permissive -x` | ❌ Wave 0 |
| SKSEC-02 | Audit log emitted on allowed_tools denial | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_skill_executor.py::TestAllowedTools::test_audit_log_on_denial -x` | ❌ Wave 0 |
| SKSEC-03 | Update checker detects hash change, creates pending_review | unit | `PYTHONPATH=. .venv/bin/pytest tests/scheduler/test_check_skill_updates.py -x` | ❌ Wave 0 |
| SKSEC-03 | Update checker skips skills with null source_hash (no baseline) | unit | `PYTHONPATH=. .venv/bin/pytest tests/scheduler/test_check_skill_updates.py::test_null_hash_stores_without_creating_review -x` | ❌ Wave 0 |
| SKSEC-03 | Update checker skips non-imported skills | unit | `PYTHONPATH=. .venv/bin/pytest tests/scheduler/test_check_skill_updates.py::test_builtin_skill_skipped -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=. .venv/bin/pytest tests/test_security_scanner.py tests/test_skill_executor.py tests/test_skill_importer.py -q`
- **Per wave merge:** `PYTHONPATH=. .venv/bin/pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_security_scanner.py::TestDependencyRisk` — new class for SKSEC-04 dependency factor
- [ ] `tests/test_security_scanner.py::TestDataFlowRisk` — new class for SKSEC-04 data flow factor
- [ ] `tests/test_security_scanner.py::TestWeightedScoring::test_weights_sum_correctly` — UPDATE to new 6-factor formula (remove `author_verification`)
- [ ] `tests/test_skill_importer.py::TestDependencyParsing` — new class for SKSEC-01 frontmatter parsing
- [ ] `tests/test_skill_importer.py::TestZipScripts` — new class for SKSEC-01 scripts/ extraction
- [ ] `tests/test_skill_executor.py::TestAllowedTools` — new class for SKSEC-02 enforcement
- [ ] `tests/scheduler/test_check_skill_updates.py` — new file for SKSEC-03 (create `tests/scheduler/` dir + `__init__.py` if not exists)

---

## Sources

### Primary (HIGH confidence)
- Python 3.13 stdlib docs — `ast` module: `ast.parse()`, `ast.walk()`, `ast.Import`, `ast.ImportFrom`
- Python 3.10 release notes — `sys.stdlib_module_names` frozenset added in 3.10
- Codebase direct read — `backend/skills/security_scanner.py`, `executor.py`, `importer.py`, `celery_app.py`, `scheduler/tasks/embedding.py`, `core/models/skill_definition.py`

### Secondary (MEDIUM confidence)
- Celery docs — `crontab` schedule, beat configuration patterns (consistent with existing celery_app.py usage)
- hashlib docs — `sha256().hexdigest()` for stable hex string output

### Tertiary (LOW confidence)
- None — all research based on direct codebase reads and stdlib documentation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stdlib; existing project libraries; no new deps needed
- Architecture: HIGH — all changes extend existing patterns; Celery task follows embedding.py exactly; AST pattern is stdlib
- Pitfalls: HIGH — identified from direct code inspection (migration numbering from alembic heads, test breakage from weight change, null source_hash first-run bug)

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (stable domain — stdlib APIs don't change; project patterns stable)
