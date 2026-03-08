# Phase 21: Skill Platform C — Security Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add defense-in-depth security to the skill ecosystem: dependency scanning at import, tool gate enforcement at runtime, and upstream change detection in the background.

**Architecture:** Three independent layers — SecurityScanner v2 (AST analysis at import), SkillToolGate (intersection enforcement at execution), UpdateChecker (Celery Beat daily task). All build on existing infrastructure with no new services.

**Tech Stack:** Python `ast` module (static analysis), existing `SecurityScanner`, `SkillExecutor`, `check_tool_acl_cached`, Celery Beat, structlog audit logger, Alembic migrations.

**Baseline:** 794 tests passing. Every task ends with full suite passing.

**Canonical test command:**
```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

---

## Task 1: DB Migration 024 — New Columns

**Files:**
- Create: `backend/alembic/versions/024_skill_security.py`
- Modify: `backend/core/models/skill_definition.py`
- Modify: `backend/core/models/platform_config.py`

### Step 1: Write failing tests for new model fields

```python
# backend/tests/test_migration_024.py
import pytest
from sqlalchemy import inspect
from core.db import engine

@pytest.mark.asyncio
async def test_skill_definitions_has_new_columns():
    async with engine.connect() as conn:
        def get_cols(sync_conn):
            inspector = inspect(sync_conn)
            return {c["name"] for c in inspector.get_columns("skill_definitions")}
        cols = await conn.run_sync(get_cols)
    assert "source_hash" in cols
    assert "source_etag" in cols
    assert "last_checked_at" in cols

@pytest.mark.asyncio
async def test_platform_config_has_skill_gate_columns():
    async with engine.connect() as conn:
        def get_cols(sync_conn):
            inspector = inspect(sync_conn)
            return {c["name"] for c in inspector.get_columns("platform_config")}
        cols = await conn.run_sync(get_cols)
    assert "skill_tool_gate_mode" in cols
    assert "skill_update_check_schedule" in cols
```

### Step 2: Run to verify it fails

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_migration_024.py -v
```
Expected: FAIL — columns don't exist yet.

### Step 3: Write the migration

```python
# backend/alembic/versions/024_skill_security.py
"""024 skill security columns

Revision ID: 024_skill_security
Revises: 023_skill_catalog_fts
Create Date: 2026-03-08

"""
from alembic import op
import sqlalchemy as sa

revision = "024_skill_security"
down_revision = "023_skill_catalog_fts"  # confirm actual ID of 023 before running
branch_labels = None
depends_on = None


def upgrade() -> None:
    # skill_definitions: source tracking for update checker
    op.add_column(
        "skill_definitions",
        sa.Column("source_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "skill_definitions",
        sa.Column("source_etag", sa.String(255), nullable=True),
    )
    op.add_column(
        "skill_definitions",
        sa.Column(
            "last_checked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # platform_config: skill security settings
    op.add_column(
        "platform_config",
        sa.Column(
            "skill_tool_gate_mode",
            sa.String(20),
            nullable=False,
            server_default="permissive",
        ),
    )
    op.add_column(
        "platform_config",
        sa.Column(
            "skill_update_check_schedule",
            sa.String(100),
            nullable=False,
            server_default="0 2 * * *",
        ),
    )


def downgrade() -> None:
    op.drop_column("skill_definitions", "source_hash")
    op.drop_column("skill_definitions", "source_etag")
    op.drop_column("skill_definitions", "last_checked_at")
    op.drop_column("platform_config", "skill_tool_gate_mode")
    op.drop_column("platform_config", "skill_update_check_schedule")
```

> **Important:** Before writing the migration, verify the exact revision ID of migration 023:
> ```bash
> cd /home/tungmv/Projects/hox-agentos/backend
> .venv/bin/alembic heads
> ```
> Use the actual ID as `down_revision`, not the literal string "023_skill_catalog_fts".

### Step 4: Update SkillDefinition model

Add to `backend/core/models/skill_definition.py` after the `usage_count` column:

```python
# Source integrity — for UpdateChecker (SKSEC-03)
source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
source_etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
last_checked_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

Ensure `datetime` is imported from `datetime` at top of file.

### Step 5: Update PlatformConfig model

Add to `backend/core/models/platform_config.py` at end of column list:

```python
# Skill security settings (SKSEC-02, SKSEC-03)
skill_tool_gate_mode: Mapped[str] = mapped_column(
    String(20), nullable=False, server_default="permissive"
)
skill_update_check_schedule: Mapped[str] = mapped_column(
    String(100), nullable=False, server_default="0 2 * * *"
)
```

### Step 6: Apply migration (via docker exec)

```bash
docker exec -it blitz-postgres psql -U blitz blitz -c "
ALTER TABLE skill_definitions ADD COLUMN IF NOT EXISTS source_hash VARCHAR(64);
ALTER TABLE skill_definitions ADD COLUMN IF NOT EXISTS source_etag VARCHAR(255);
ALTER TABLE skill_definitions ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMPTZ;
ALTER TABLE platform_config ADD COLUMN IF NOT EXISTS skill_tool_gate_mode VARCHAR(20) NOT NULL DEFAULT 'permissive';
ALTER TABLE platform_config ADD COLUMN IF NOT EXISTS skill_update_check_schedule VARCHAR(100) NOT NULL DEFAULT '0 2 * * *';
"
```

Then stamp the migration as applied:
```bash
.venv/bin/alembic stamp 024_skill_security
```

### Step 7: Run tests to verify they pass

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_migration_024.py -v
```
Expected: PASS.

### Step 8: Run full suite — no regressions

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
Expected: 794+ passing, 0 failures.

### Step 9: Commit

```bash
git add backend/alembic/versions/024_skill_security.py \
        backend/core/models/skill_definition.py \
        backend/core/models/platform_config.py \
        backend/tests/test_migration_024.py
git commit -m "feat(21-01): migration 024 — skill security columns"
```

---

## Task 2: Importer — Parse Dependencies Key

**Files:**
- Modify: `backend/skills/importer.py`
- Modify: `backend/tests/test_skill_importer.py` (or create if missing)

Skills declare Python package dependencies and allowed file paths in `SKILL.md` YAML frontmatter:

```yaml
---
name: My Skill
description: Does stuff
dependencies:
  python: [requests, pydantic]
  allowed_paths: ["./data/"]
---
```

The importer needs to extract this and pass it in `skill_data` so the scanner can read it.

### Step 1: Write failing tests

```python
# backend/tests/test_skill_importer.py (add to existing file)

class TestDependenciesParsing:
    def test_parses_python_dependencies(self):
        importer = SkillImporter()
        content = """---
name: dep-skill
description: Has deps
dependencies:
  python: [requests, pydantic]
  allowed_paths: ["./data/"]
---
Does things.
"""
        data = importer.parse_skill_md(content)
        assert data["dependencies"] == {
            "python": ["requests", "pydantic"],
            "allowed_paths": ["./data/"],
        }

    def test_missing_dependencies_defaults_to_empty(self):
        importer = SkillImporter()
        content = "---\nname: simple\ndescription: No deps\n---\nBody."
        data = importer.parse_skill_md(content)
        assert data.get("dependencies") == {}

    def test_dependencies_stored_in_metadata_json(self):
        importer = SkillImporter()
        content = """---
name: dep-skill
description: Has deps
dependencies:
  python: [httpx]
---
Body.
"""
        data = importer.parse_skill_md(content)
        # dependencies also mirrored into metadata_json for DB storage
        assert data["metadata_json"].get("dependencies") == data["dependencies"]
```

### Step 2: Run to verify it fails

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_skill_importer.py::TestDependenciesParsing -v
```
Expected: FAIL — `dependencies` key not extracted yet.

### Step 3: Update `parse_skill_md` in `backend/skills/importer.py`

In the section that extracts YAML frontmatter fields, add:

```python
# Extract dependencies (optional, defaults to empty dict)
dependencies: dict[str, list[str]] = frontmatter.get("dependencies") or {}
skill_data["dependencies"] = dependencies

# Mirror into metadata_json for DB storage
if "metadata_json" not in skill_data:
    skill_data["metadata_json"] = {}
skill_data["metadata_json"]["dependencies"] = dependencies
```

Also update `import_from_zip` to call `parse_skill_md` after extracting the SKILL.md content, then additionally extract and store any Python files from a `scripts/` directory:

```python
def import_from_zip(self, zip_bytes: bytes) -> dict[str, Any]:
    import zipfile, io, ast as ast_mod
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # Find SKILL.md (existing logic)
        skill_md_content = ...  # existing extraction
        skill_data = self.parse_skill_md(skill_md_content)

        # NEW: extract scripts/*.py for scanner
        embedded_scripts: dict[str, str] = {}
        for name in zf.namelist():
            if name.startswith("scripts/") and name.endswith(".py"):
                embedded_scripts[name] = zf.read(name).decode("utf-8", errors="replace")
        if embedded_scripts:
            skill_data["metadata_json"]["embedded_scripts"] = embedded_scripts

    return skill_data
```

### Step 4: Run tests to verify they pass

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_skill_importer.py::TestDependenciesParsing -v
```
Expected: PASS.

### Step 5: Run full suite

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
Expected: 794+ passing.

### Step 6: Commit

```bash
git add backend/skills/importer.py backend/tests/test_skill_importer.py
git commit -m "feat(21-02): importer — parse dependencies and embedded scripts"
```

---

## Task 3: SecurityScanner v2 — 5 Factors

**Files:**
- Modify: `backend/skills/security_scanner.py`
- Modify: `backend/tests/test_security_scanner.py` (or create if missing)

Replace the existing 5 factors with new ones. **Keep all existing `INJECTION_PATTERNS` and prompt safety logic** — move it into the new `_score_code_safety` factor.

New factor map (weights must sum to 100):

| Factor method | Weight | What it checks |
|---------------|--------|----------------|
| `_score_code_safety` | 30 | Dangerous builtins in scripts + existing injection patterns in prompts |
| `_score_dependency_risk` | 20 | Undeclared Python imports in embedded scripts vs `dependencies.python` |
| `_score_data_flow_file` | 15 | File I/O builtins (`open`, `pathlib.Path`) outside `allowed_paths` |
| `_score_data_flow_network` | 15 | Network builtins (`urllib`, `requests`, `httpx`, `socket`) |
| `_score_metadata_completeness` | 20 | `name`, `description`, `version`, `license`, `author` present |

### Step 1: Write failing tests

```python
# backend/tests/test_security_scanner.py (add class)

import ast
import pytest
from skills.security_scanner import SecurityScanner

CLEAN_SKILL: dict = {
    "name": "clean-skill",
    "description": "Does nothing dangerous",
    "version": "1.0.0",
    "license": "MIT",
    "metadata_json": {
        "author": "Test Author",
        "dependencies": {"python": ["requests"], "allowed_paths": ["./data/"]},
    },
}

class TestSecurityScannerV2:
    def test_dangerous_builtin_subprocess_rejected(self):
        scanner = SecurityScanner()
        skill = dict(CLEAN_SKILL)
        skill["metadata_json"] = dict(skill["metadata_json"])
        skill["metadata_json"]["embedded_scripts"] = {
            "scripts/run.py": "import subprocess\nsubprocess.run(['ls'])"
        }
        report = scanner.scan(skill)
        assert report.recommendation == "reject"
        assert any("subprocess" in r for r in report.injection_matches)

    def test_undeclared_import_lowers_score(self):
        scanner = SecurityScanner()
        skill = dict(CLEAN_SKILL)
        skill["metadata_json"] = {
            "author": "Test",
            "dependencies": {"python": []},  # requests not declared
            "embedded_scripts": {
                "scripts/run.py": "import requests\nrequests.get('http://example.com')"
            },
        }
        report = scanner.scan(skill)
        assert report.factors["dependency_risk"] < 80

    def test_declared_import_scores_full(self):
        scanner = SecurityScanner()
        skill = dict(CLEAN_SKILL)  # requests is declared in CLEAN_SKILL deps
        skill["metadata_json"] = {
            "author": "Test",
            "dependencies": {"python": ["requests"], "allowed_paths": []},
            "embedded_scripts": {
                "scripts/run.py": "import requests\nrequests.get('http://example.com')"
            },
        }
        report = scanner.scan(skill)
        assert report.factors["dependency_risk"] >= 80

    def test_network_egress_lowers_data_flow_score(self):
        scanner = SecurityScanner()
        skill = dict(CLEAN_SKILL)
        skill["metadata_json"] = dict(skill["metadata_json"])
        skill["metadata_json"]["embedded_scripts"] = {
            "scripts/run.py": "import socket\ns = socket.socket()"
        }
        report = scanner.scan(skill)
        assert report.factors["data_flow_network"] < 80

    def test_missing_metadata_lowers_score(self):
        scanner = SecurityScanner()
        skill = {"name": "no-meta", "description": "bare"}
        report = scanner.scan(skill)
        assert report.factors["metadata_completeness"] < 60

    def test_clean_skill_scores_high(self):
        scanner = SecurityScanner()
        report = scanner.scan(CLEAN_SKILL)
        assert report.score >= 70
        assert report.recommendation == "approve"

    def test_factors_weights_sum_to_100(self):
        from skills.security_scanner import FACTOR_WEIGHTS
        assert sum(FACTOR_WEIGHTS.values()) == 100
```

### Step 2: Run to verify it fails

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_security_scanner.py::TestSecurityScannerV2 -v
```
Expected: FAIL — new factor methods not implemented.

### Step 3: Rewrite `backend/skills/security_scanner.py`

Key structural changes (preserve the `SecurityReport` dataclass and `INJECTION_PATTERNS`):

```python
import ast
import re
import stdlib_list  # pip: stdlib-list — or use sys.stdlib_module_names (Python 3.10+)
from dataclasses import dataclass, field
from typing import Any

# --- Factor weights (must sum to 100) ---
FACTOR_WEIGHTS: dict[str, int] = {
    "code_safety": 30,
    "dependency_risk": 20,
    "data_flow_file": 15,
    "data_flow_network": 15,
    "metadata_completeness": 20,
}

# Dangerous builtins — always block (score = 0 for code_safety)
_DANGEROUS_BUILTINS = {
    "subprocess", "os.system", "os.popen", "socket",
    "eval", "exec", "__import__",
}

# Network egress patterns
_NETWORK_MODULES = {"urllib", "urllib3", "requests", "httpx", "socket", "aiohttp"}

# File I/O patterns
_FILE_IO_BUILTINS = {"open", "pathlib"}

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

# Python stdlib module names (Python 3.10+)
import sys
_STDLIB_MODULES = sys.stdlib_module_names  # frozenset


@dataclass
class SecurityReport:
    score: int
    factors: dict[str, int]
    recommendation: str
    injection_matches: list[str] = field(default_factory=list)


class SecurityScanner:
    def scan(
        self,
        skill_data: dict[str, Any],
        source_url: str | None = None,
    ) -> SecurityReport:
        meta = skill_data.get("metadata_json") or {}
        scripts: dict[str, str] = meta.get("embedded_scripts") or {}
        deps: dict[str, Any] = meta.get("dependencies") or {}
        declared_python: set[str] = set(deps.get("python") or [])

        injection_matches: list[str] = []

        factors = {
            "code_safety": self._score_code_safety(skill_data, scripts, injection_matches),
            "dependency_risk": self._score_dependency_risk(scripts, declared_python),
            "data_flow_file": self._score_data_flow_file(scripts),
            "data_flow_network": self._score_data_flow_network(scripts),
            "metadata_completeness": self._score_metadata_completeness(skill_data, meta),
        }

        weighted = sum(
            factors[name] * weight
            for name, weight in FACTOR_WEIGHTS.items()
        ) // 100

        score = max(0, min(100, weighted))

        if score >= 80:
            recommendation = "approve"
        elif score >= 60:
            recommendation = "review"
        else:
            recommendation = "reject"

        return SecurityReport(
            score=score,
            factors=factors,
            recommendation=recommendation,
            injection_matches=injection_matches,
        )

    def _score_code_safety(
        self,
        skill_data: dict[str, Any],
        scripts: dict[str, str],
        injection_matches: list[str],
    ) -> int:
        """30% — dangerous builtins in scripts + injection patterns in prompts."""
        # Check embedded Python scripts for dangerous builtins
        for fname, source in scripts.items():
            try:
                tree = ast.parse(source)
            except SyntaxError:
                injection_matches.append(f"syntax_error:{fname}")
                return 0

            for node in ast.walk(tree):
                # import subprocess / import os
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    mods = (
                        [alias.name for alias in node.names]
                        if isinstance(node, ast.Import)
                        else [node.module or ""]
                    )
                    for mod in mods:
                        base = mod.split(".")[0]
                        if base in {"subprocess", "socket"}:
                            injection_matches.append(f"undeclared_dangerous_builtin:{base} in {fname}")
                            return 0
                # os.system / os.popen via attribute access
                if isinstance(node, ast.Attribute):
                    if (
                        isinstance(node.value, ast.Name)
                        and node.value.id == "os"
                        and node.attr in {"system", "popen"}
                    ):
                        injection_matches.append(f"undeclared_dangerous_builtin:os.{node.attr} in {fname}")
                        return 0

        # Check prompt templates for injection patterns (existing logic)
        text_to_check = " ".join([
            skill_data.get("instruction_markdown") or "",
            str(skill_data.get("procedure_json") or ""),
        ])
        for pattern in INJECTION_PATTERNS:
            matches = re.findall(pattern, text_to_check, re.IGNORECASE)
            if matches:
                injection_matches.extend(matches)

        # Penalise 10 points per injection match in prompts, floor 0
        prompt_penalty = len([m for m in injection_matches]) * 10
        return max(0, 100 - prompt_penalty)

    def _score_dependency_risk(
        self,
        scripts: dict[str, str],
        declared: set[str],
    ) -> int:
        """20% — imported third-party packages vs declared list."""
        if not scripts:
            return 100  # no scripts = no dependency risk

        imported: set[str] = set()
        for source in scripts.values():
            try:
                tree = ast.parse(source)
            except SyntaxError:
                return 0
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])

        # Only check third-party (not stdlib)
        third_party = imported - _STDLIB_MODULES
        undeclared = third_party - declared

        if not third_party:
            return 100
        if not undeclared:
            return 100

        # Penalise proportionally — each undeclared package -25 points
        penalty = min(len(undeclared) * 25, 100)
        return max(0, 100 - penalty)

    def _score_data_flow_file(self, scripts: dict[str, str]) -> int:
        """15% — file I/O builtins detected."""
        if not scripts:
            return 100

        for source in scripts.values():
            try:
                tree = ast.parse(source)
            except SyntaxError:
                return 0
            for node in ast.walk(tree):
                # open() builtin
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == "open":
                        return 50  # file I/O present but not necessarily dangerous
                # pathlib.Path
                if isinstance(node, ast.Attribute):
                    if (
                        isinstance(node.value, ast.Name)
                        and node.value.id in {"Path", "pathlib"}
                    ):
                        return 50
        return 100

    def _score_data_flow_network(self, scripts: dict[str, str]) -> int:
        """15% — network egress imports detected."""
        if not scripts:
            return 100

        for source in scripts.values():
            try:
                tree = ast.parse(source)
            except SyntaxError:
                return 0
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    mods = (
                        [alias.name for alias in node.names]
                        if isinstance(node, ast.Import)
                        else [node.module or ""]
                    )
                    for mod in mods:
                        if mod.split(".")[0] in _NETWORK_MODULES:
                            return 40  # network import present
        return 100

    def _score_metadata_completeness(
        self,
        skill_data: dict[str, Any],
        meta: dict[str, Any],
    ) -> int:
        """20% — presence of required metadata fields."""
        required = ["name", "description", "version", "license"]
        present = sum(1 for f in required if skill_data.get(f) or meta.get(f))
        # author in metadata
        if meta.get("author"):
            present += 1
        total = len(required) + 1  # +1 for author
        return int((present / total) * 100)
```

> **Note on stdlib detection:** `sys.stdlib_module_names` is available from Python 3.10+. Confirm version with `python --version` in the venv. If needed, fall back to a hardcoded set of common stdlib modules.

### Step 4: Run tests to verify they pass

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_security_scanner.py::TestSecurityScannerV2 -v
```
Expected: PASS.

### Step 5: Check existing scanner tests still pass

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_security_scanner.py -v
```
If existing tests reference old factor names (`source_reputation`, `tool_scope`, etc.), update them to use the new factor names. The report shape (`score`, `factors`, `recommendation`, `injection_matches`) is unchanged.

### Step 6: Run full suite

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
Expected: 794+ passing.

### Step 7: Commit

```bash
git add backend/skills/security_scanner.py backend/tests/test_security_scanner.py
git commit -m "feat(21-03): SecurityScanner v2 — 5-factor trust score + dependency scan"
```

---

## Task 4: SkillToolGate — Runtime Enforcement

**Files:**
- Create: `backend/skills/tool_gate.py`
- Modify: `backend/agents/master_agent.py` (lines ~647–751)
- Create: `backend/tests/test_skill_tool_gate.py`

### Step 1: Write failing tests

```python
# backend/tests/test_skill_tool_gate.py
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import pytest
from skills.tool_gate import SkillToolGate, ToolAccessDenied


@dataclass
class FakeSkill:
    id: object = None
    name: str = "test-skill"
    allowed_tools: list[str] | None = None

    def __post_init__(self):
        if self.id is None:
            self.id = uuid4()


class TestSkillToolGate:
    @pytest.mark.asyncio
    async def test_allowed_tool_passes(self):
        gate = SkillToolGate(gate_mode="strict")
        skill = FakeSkill(allowed_tools=["email.read"])

        async def fake_acl(user_id, tool_name, session):
            return True

        session = AsyncMock()
        # Should not raise
        await gate.check(
            skill=skill,
            tool_name="email.read",
            user_id=uuid4(),
            session=session,
            acl_fn=fake_acl,
        )

    @pytest.mark.asyncio
    async def test_undeclared_tool_denied_in_strict_mode(self):
        gate = SkillToolGate(gate_mode="strict")
        skill = FakeSkill(allowed_tools=["email.read"])

        async def fake_acl(user_id, tool_name, session):
            return True

        session = AsyncMock()
        with pytest.raises(ToolAccessDenied) as exc:
            await gate.check(
                skill=skill,
                tool_name="email.send",
                user_id=uuid4(),
                session=session,
                acl_fn=fake_acl,
            )
        assert "email.send" in str(exc.value)

    @pytest.mark.asyncio
    async def test_empty_allowed_tools_denies_all_in_strict_mode(self):
        gate = SkillToolGate(gate_mode="strict")
        skill = FakeSkill(allowed_tools=[])

        async def fake_acl(user_id, tool_name, session):
            return True

        session = AsyncMock()
        with pytest.raises(ToolAccessDenied):
            await gate.check(
                skill=skill,
                tool_name="email.read",
                user_id=uuid4(),
                session=session,
                acl_fn=fake_acl,
            )

    @pytest.mark.asyncio
    async def test_empty_allowed_tools_uses_acl_in_permissive_mode(self):
        gate = SkillToolGate(gate_mode="permissive")
        skill = FakeSkill(allowed_tools=None)  # not declared

        async def fake_acl(user_id, tool_name, session):
            return True  # user allowed

        session = AsyncMock()
        # Should not raise
        await gate.check(
            skill=skill,
            tool_name="email.read",
            user_id=uuid4(),
            session=session,
            acl_fn=fake_acl,
        )

    @pytest.mark.asyncio
    async def test_user_acl_denial_blocks_even_declared_tool(self):
        gate = SkillToolGate(gate_mode="permissive")
        skill = FakeSkill(allowed_tools=["email.send"])

        async def fake_acl(user_id, tool_name, session):
            return False  # user not allowed

        session = AsyncMock()
        with pytest.raises(ToolAccessDenied):
            await gate.check(
                skill=skill,
                tool_name="email.send",
                user_id=uuid4(),
                session=session,
                acl_fn=fake_acl,
            )
```

### Step 2: Run to verify it fails

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_skill_tool_gate.py -v
```
Expected: FAIL — module doesn't exist.

### Step 3: Create `backend/skills/tool_gate.py`

```python
"""
SkillToolGate — runtime enforcement of skill allowed_tools vs user ACL.

SKSEC-02: tool calls restricted to (skill.allowed_tools ∩ user_acl).
Gate mode (strict | permissive) controls behaviour when allowed_tools is empty/None.
"""
from __future__ import annotations

import structlog
from typing import Any, Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)
audit = structlog.get_logger("audit")


class ToolAccessDenied(Exception):
    """Raised when SkillToolGate blocks a tool call."""

    def __init__(self, tool_name: str, skill_name: str, reason: str) -> None:
        self.tool_name = tool_name
        self.skill_name = skill_name
        self.reason = reason
        super().__init__(f"Tool '{tool_name}' denied for skill '{skill_name}': {reason}")


AclFn = Callable[[UUID, str, AsyncSession], Awaitable[bool]]


class SkillToolGate:
    """Enforce skill-level tool access control at runtime."""

    def __init__(self, gate_mode: str = "permissive") -> None:
        if gate_mode not in {"strict", "permissive"}:
            raise ValueError(f"gate_mode must be 'strict' or 'permissive', got {gate_mode!r}")
        self.gate_mode = gate_mode

    async def check(
        self,
        skill: Any,  # SkillDefinition ORM or dataclass with .id, .name, .allowed_tools
        tool_name: str,
        user_id: UUID,
        session: AsyncSession,
        acl_fn: AclFn,
    ) -> None:
        """
        Assert the tool call is allowed. Raises ToolAccessDenied if not.

        Logic:
          - If skill.allowed_tools is None or empty AND mode is strict → deny all.
          - If skill.allowed_tools is None or empty AND mode is permissive → use user ACL only.
          - If skill.allowed_tools is set → effective = allowed_tools ∩ user_acl.
        """
        allowed_tools: list[str] | None = getattr(skill, "allowed_tools", None) or None

        if not allowed_tools:
            if self.gate_mode == "strict":
                self._deny(skill, tool_name, user_id, "no_declared_tools_strict_mode")
            # permissive: fall through to ACL check only
            user_allowed = await acl_fn(user_id, tool_name, session)
            if not user_allowed:
                self._deny(skill, tool_name, user_id, "user_acl_denied")
            return

        # Skill declared tools: check intersection
        if tool_name not in allowed_tools:
            self._deny(skill, tool_name, user_id, "not_in_skill_allowed_tools")

        user_allowed = await acl_fn(user_id, tool_name, session)
        if not user_allowed:
            self._deny(skill, tool_name, user_id, "user_acl_denied")

    def _deny(
        self,
        skill: Any,
        tool_name: str,
        user_id: UUID,
        reason: str,
    ) -> None:
        audit.warning(
            "skill_tool_denied",
            skill_id=str(getattr(skill, "id", None)),
            skill_name=getattr(skill, "name", "unknown"),
            tool_name=tool_name,
            user_id=str(user_id),
            gate_mode=self.gate_mode,
            reason=reason,
        )
        raise ToolAccessDenied(
            tool_name=tool_name,
            skill_name=getattr(skill, "name", "unknown"),
            reason=reason,
        )
```

### Step 4: Run tests to verify they pass

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_skill_tool_gate.py -v
```
Expected: PASS.

### Step 5: Wire SkillToolGate into `_skill_executor_node`

Open `backend/agents/master_agent.py`. In `_skill_executor_node`, find where tool steps are dispatched inside the `SkillExecutor.run()` call.

The gate needs to wrap individual tool calls. The cleanest insertion point is in `SkillExecutor.run()` in `backend/skills/executor.py`, where each `tool` step is dispatched.

In `backend/skills/executor.py`, find the section that handles `tool` step type and add the gate check before the tool invocation:

```python
# At top of executor.py, add import:
from skills.tool_gate import SkillToolGate, ToolAccessDenied
from core.config import settings  # to read gate mode later (use a default for now)

# In the tool step handler, before calling the tool handler:
async def _run_tool_step(self, step, skill, user_context, session, ...):
    tool_name = step["tool"]

    # SkillToolGate check
    gate_mode = await _get_gate_mode(session)  # see helper below
    gate = SkillToolGate(gate_mode=gate_mode)
    user_id = user_context["user_id"]

    from security.acl import check_tool_acl_cached
    try:
        await gate.check(
            skill=skill,
            tool_name=tool_name,
            user_id=user_id,
            session=session,
            acl_fn=check_tool_acl_cached,
        )
    except ToolAccessDenied as exc:
        return SkillResult(
            success=False,
            output=f"Tool access denied: {exc.reason}",
            failed_step=step.get("id"),
        )

    # ... existing tool invocation continues ...
```

Add the `_get_gate_mode` helper at module level in `executor.py`:

```python
import asyncio
from functools import lru_cache

_gate_mode_cache: tuple[str, float] | None = None
_GATE_MODE_TTL = 60.0  # seconds

async def _get_gate_mode(session) -> str:
    """Read skill_tool_gate_mode from platform_config with 60s TTL."""
    global _gate_mode_cache
    import time
    now = time.monotonic()
    if _gate_mode_cache and (now - _gate_mode_cache[1]) < _GATE_MODE_TTL:
        return _gate_mode_cache[0]

    from sqlalchemy import select, text
    from core.models.platform_config import PlatformConfig
    result = await session.execute(select(PlatformConfig).where(PlatformConfig.id == 1))
    cfg = result.scalar_one_or_none()
    mode = (cfg.skill_tool_gate_mode if cfg else None) or "permissive"
    _gate_mode_cache = (mode, now)
    return mode
```

### Step 6: Add integration test for executor gate

```python
# backend/tests/test_skill_executor.py (add to existing)

class TestSkillToolGateIntegration:
    @pytest.mark.asyncio
    async def test_tool_step_blocked_by_gate(self, executor, user_context, mock_session):
        """Skill with allowed_tools=[] in strict mode blocks tool calls."""
        skill = FakeSkill(
            name="restricted",
            allowed_tools=[],
            procedure_json={
                "schema_version": "1.0",
                "steps": [
                    {"id": "s1", "type": "tool", "tool": "email.read", "params": {}}
                ],
                "output": "{{s1.output}}",
            },
        )
        with patch("skills.executor._get_gate_mode", return_value="strict"):
            result = await executor.run(skill, user_context, mock_session)
        assert result.success is False
        assert "denied" in result.output.lower()
```

### Step 7: Run full suite

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
Expected: 794+ passing.

### Step 8: Commit

```bash
git add backend/skills/tool_gate.py \
        backend/skills/executor.py \
        backend/tests/test_skill_tool_gate.py \
        backend/tests/test_skill_executor.py
git commit -m "feat(21-04): SkillToolGate — runtime allowed_tools enforcement"
```

---

## Task 5: Gate Mode Config — Backend API + Admin UI

**Files:**
- Modify: `backend/api/routes/admin_keycloak.py` (add gate mode read/write endpoints)
- Modify: `frontend/src/app/(authenticated)/admin/identity/page.tsx` (or wherever platform config UI lives — search for the component that renders Keycloak config settings)

### Step 1: Write failing test for API endpoint

```python
# backend/tests/api/test_admin_platform_config.py
import pytest
from httpx import AsyncClient

class TestSkillGateModeEndpoint:
    @pytest.mark.asyncio
    async def test_get_skill_gate_mode_returns_default(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/admin/platform-config/skill-gate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["skill_tool_gate_mode"] in {"strict", "permissive"}
        assert "skill_update_check_schedule" in data

    @pytest.mark.asyncio
    async def test_update_gate_mode_to_strict(self, auth_client: AsyncClient):
        resp = await auth_client.patch(
            "/api/admin/platform-config/skill-gate",
            json={"skill_tool_gate_mode": "strict"},
        )
        assert resp.status_code == 200
        assert resp.json()["skill_tool_gate_mode"] == "strict"

    @pytest.mark.asyncio
    async def test_invalid_gate_mode_rejected(self, auth_client: AsyncClient):
        resp = await auth_client.patch(
            "/api/admin/platform-config/skill-gate",
            json={"skill_tool_gate_mode": "unknown"},
        )
        assert resp.status_code == 422
```

### Step 2: Run to verify it fails

```bash
PYTHONPATH=. .venv/bin/pytest tests/api/test_admin_platform_config.py -v
```
Expected: FAIL — endpoints don't exist.

### Step 3: Add endpoints to `backend/api/routes/admin_keycloak.py`

Add these two routes to the existing router (near the existing Keycloak config endpoints):

```python
from pydantic import BaseModel, field_validator

class SkillGateModeUpdate(BaseModel):
    skill_tool_gate_mode: str | None = None
    skill_update_check_schedule: str | None = None

    @field_validator("skill_tool_gate_mode")
    @classmethod
    def validate_mode(cls, v: str | None) -> str | None:
        if v is not None and v not in {"strict", "permissive"}:
            raise ValueError("skill_tool_gate_mode must be 'strict' or 'permissive'")
        return v


@router.get("/skill-gate")
async def get_skill_gate_config(
    current_user: CurrentUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    result = await session.execute(
        select(PlatformConfig).where(PlatformConfig.id == 1)
    )
    cfg = result.scalar_one_or_none()
    return {
        "skill_tool_gate_mode": (cfg.skill_tool_gate_mode if cfg else "permissive"),
        "skill_update_check_schedule": (
            cfg.skill_update_check_schedule if cfg else "0 2 * * *"
        ),
    }


@router.patch("/skill-gate")
async def update_skill_gate_config(
    body: SkillGateModeUpdate,
    current_user: CurrentUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    result = await session.execute(
        select(PlatformConfig).where(PlatformConfig.id == 1)
    )
    cfg = result.scalar_one_or_none()
    if cfg is None:
        cfg = PlatformConfig(id=1)
        session.add(cfg)

    if body.skill_tool_gate_mode is not None:
        cfg.skill_tool_gate_mode = body.skill_tool_gate_mode
    if body.skill_update_check_schedule is not None:
        cfg.skill_update_check_schedule = body.skill_update_check_schedule

    await session.commit()
    await session.refresh(cfg)
    return {
        "skill_tool_gate_mode": cfg.skill_tool_gate_mode,
        "skill_update_check_schedule": cfg.skill_update_check_schedule,
    }
```

Note: The router prefix for this file is likely `/api/admin/platform-config` — confirm by checking the router registration in `backend/main.py`.

### Step 4: Add admin UI toggle

Find the platform config admin page in the frontend. Run:
```bash
grep -r "platform.config\|platformConfig\|keycloak_url\|KeycloakConfig" \
  /home/tungmv/Projects/hox-agentos/frontend/src --include="*.tsx" -l
```

In that page component, add a "Skill Security" section after the existing Keycloak config section:

```tsx
// Add to the admin platform config page

const [gateMode, setGateMode] = useState<"strict" | "permissive">("permissive")

// Fetch on mount
useEffect(() => {
  fetch("/api/admin/platform-config/skill-gate", { headers: authHeaders })
    .then(r => r.json())
    .then(d => setGateMode(d.skill_tool_gate_mode))
}, [])

// In JSX:
<div className="border rounded p-4 space-y-3">
  <h3 className="font-semibold text-sm">Skill Tool Gate</h3>
  <p className="text-xs text-muted-foreground">
    Controls what happens when a skill has no declared tools.
  </p>
  <div className="flex items-center gap-3">
    <label className="text-sm">Mode:</label>
    <select
      value={gateMode}
      onChange={async e => {
        const mode = e.target.value as "strict" | "permissive"
        setGateMode(mode)
        await fetch("/api/admin/platform-config/skill-gate", {
          method: "PATCH",
          headers: { ...authHeaders, "Content-Type": "application/json" },
          body: JSON.stringify({ skill_tool_gate_mode: mode }),
        })
      }}
      className="border rounded px-2 py-1 text-sm"
    >
      <option value="permissive">Permissive (inherit user ACL)</option>
      <option value="strict">Strict (deny all undeclared tools)</option>
    </select>
  </div>
</div>
```

### Step 5: Run backend tests

```bash
PYTHONPATH=. .venv/bin/pytest tests/api/test_admin_platform_config.py -v
```
Expected: PASS.

### Step 6: Run full suite

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
Expected: 794+ passing.

### Step 7: Frontend build check

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
```
Expected: 0 errors.

### Step 8: Commit

```bash
git add backend/api/routes/admin_keycloak.py \
        backend/tests/api/test_admin_platform_config.py \
        frontend/src/...  # the modified admin page
git commit -m "feat(21-05): gate mode config — API endpoint + admin UI toggle"
```

---

## Task 6: UpdateChecker — Celery Periodic Task

**Files:**
- Create: `backend/scheduler/tasks/skill_update_checker.py`
- Modify: `backend/scheduler/celery_app.py`
- Create: `backend/tests/test_skill_update_checker.py`

### Step 1: Write failing tests

```python
# backend/tests/test_skill_update_checker.py
import hashlib
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import pytest
from scheduler.tasks.skill_update_checker import (
    _compute_sha256,
    _check_single_skill,
    CheckResult,
)


def test_compute_sha256_is_deterministic():
    data = b"hello world"
    h1 = _compute_sha256(data)
    h2 = _compute_sha256(data)
    assert h1 == h2
    assert h1 == hashlib.sha256(data).hexdigest()


@dataclass
class FakeSkill:
    id: object = None
    source_url: str = "https://example.com/skill.zip"
    source_hash: str | None = None
    source_etag: str | None = None
    last_checked_at: object = None

    def __post_init__(self):
        if self.id is None:
            self.id = uuid4()


class TestCheckSingleSkill:
    @pytest.mark.asyncio
    async def test_no_change_when_etag_matches(self):
        skill = FakeSkill(source_etag="abc123", source_hash="deadbeef")

        async def fake_head(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.headers = {"ETag": "abc123"}
            return resp

        result = await _check_single_skill(skill, head_fn=fake_head, get_fn=None)
        assert result == CheckResult.NO_CHANGE

    @pytest.mark.asyncio
    async def test_change_detected_when_hash_differs(self):
        original_hash = hashlib.sha256(b"old content").hexdigest()
        skill = FakeSkill(source_hash=original_hash)

        async def fake_head(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.headers = {}  # No ETag
            return resp

        async def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.content = b"new content"  # Different from original
            return resp

        result = await _check_single_skill(skill, head_fn=fake_head, get_fn=fake_get)
        assert result == CheckResult.CHANGED

    @pytest.mark.asyncio
    async def test_no_change_when_hash_same(self):
        content = b"same content"
        current_hash = hashlib.sha256(content).hexdigest()
        skill = FakeSkill(source_hash=current_hash)

        async def fake_head(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.headers = {}
            return resp

        async def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.content = content  # Same as stored hash
            return resp

        result = await _check_single_skill(skill, head_fn=fake_head, get_fn=fake_get)
        assert result == CheckResult.NO_CHANGE
```

### Step 2: Run to verify it fails

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_skill_update_checker.py -v
```
Expected: FAIL — module doesn't exist.

### Step 3: Create `backend/scheduler/tasks/skill_update_checker.py`

```python
"""
Celery task: check_skill_updates

Daily task that polls source_url for each approved skill.
If the content has changed (ETag or SHA-256), creates a pending_review version.

SKSEC-03
"""
from __future__ import annotations

import asyncio
import hashlib
from enum import Enum
from typing import Any, Callable, Awaitable
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)
audit = structlog.get_logger("audit")


class CheckResult(str, Enum):
    NO_CHANGE = "no_change"
    CHANGED = "changed"
    ERROR = "error"


def _compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def _check_single_skill(
    skill: Any,
    head_fn: Callable[..., Awaitable[Any]],
    get_fn: Callable[..., Awaitable[Any]] | None,
) -> CheckResult:
    """
    Check if skill source has changed.

    1. HTTP HEAD → check ETag / Last-Modified
    2. If headers match stored → NO_CHANGE
    3. If headers differ or absent → HTTP GET → SHA-256 → compare
    4. Return CHANGED or NO_CHANGE
    """
    url = skill.source_url
    if not url:
        return CheckResult.NO_CHANGE

    try:
        head_resp = await head_fn(url, timeout=10)
    except Exception as exc:
        logger.warning("skill_update_head_failed", skill_id=str(skill.id), error=str(exc))
        return CheckResult.ERROR

    # Try ETag match
    new_etag = head_resp.headers.get("ETag") or head_resp.headers.get("etag")
    if new_etag and skill.source_etag and new_etag == skill.source_etag:
        return CheckResult.NO_CHANGE

    # Try Last-Modified (less reliable — skip for now, ETag is preferred)

    # Fall back to full download + SHA-256
    if get_fn is None:
        return CheckResult.NO_CHANGE

    try:
        get_resp = await get_fn(url, timeout=30)
    except Exception as exc:
        logger.warning("skill_update_get_failed", skill_id=str(skill.id), error=str(exc))
        return CheckResult.ERROR

    new_hash = _compute_sha256(get_resp.content)

    if skill.source_hash and new_hash == skill.source_hash:
        return CheckResult.NO_CHANGE

    return CheckResult.CHANGED


async def _run_update_check() -> dict[str, int]:
    """Async body for the Celery task."""
    import httpx
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from core.db import async_session
    from core.models.skill_definition import SkillDefinition
    from datetime import datetime, timezone

    stats = {"checked": 0, "changed": 0, "errors": 0}

    async with httpx.AsyncClient() as client:
        async with async_session() as session:
            # Load all approved skills with source_url
            result = await session.execute(
                select(SkillDefinition).where(
                    SkillDefinition.status == "active",
                    SkillDefinition.source_url.isnot(None),
                )
            )
            skills = result.scalars().all()

            for skill in skills:
                stats["checked"] += 1
                check_result = await _check_single_skill(
                    skill,
                    head_fn=client.head,
                    get_fn=client.get,
                )

                now = datetime.now(timezone.utc)

                if check_result == CheckResult.NO_CHANGE:
                    # Update last_checked_at and etag
                    skill.last_checked_at = now
                    await session.commit()

                elif check_result == CheckResult.CHANGED:
                    stats["changed"] += 1
                    audit.info(
                        "skill_update_detected",
                        skill_id=str(skill.id),
                        skill_name=skill.name,
                        source_url=skill.source_url,
                    )

                    # Create a pending_review copy
                    new_skill = SkillDefinition(
                        name=skill.name,
                        display_name=skill.display_name,
                        description=skill.description,
                        version=skill.version,
                        skill_type=skill.skill_type,
                        slash_command=None,  # avoid unique constraint collision
                        source_type=skill.source_type,
                        source_url=skill.source_url,
                        instruction_markdown=skill.instruction_markdown,
                        procedure_json=skill.procedure_json,
                        allowed_tools=skill.allowed_tools,
                        metadata_json={
                            **(skill.metadata_json or {}),
                            "parent_skill_id": str(skill.id),
                            "change_detected_at": now.isoformat(),
                        },
                        status="pending_review",
                        is_active=False,
                    )
                    session.add(new_skill)
                    skill.last_checked_at = now
                    await session.commit()

                else:
                    stats["errors"] += 1

    logger.info("skill_update_check_complete", **stats)
    return stats


def check_skill_updates() -> dict[str, int]:
    """Celery task entry point — wraps async body."""
    return asyncio.run(_run_update_check())
```

### Step 4: Run tests to verify they pass

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_skill_update_checker.py -v
```
Expected: PASS.

### Step 5: Register task in `backend/scheduler/celery_app.py`

Add to the `include` list:
```python
include=[
    "scheduler.tasks.embedding",
    "scheduler.tasks.workflow_execution",
    "scheduler.tasks.cron_trigger",
    "scheduler.tasks.skill_update_checker",  # NEW
],
```

Add to `beat_schedule`:
```python
"check-skill-updates-daily": {
    "task": "scheduler.tasks.skill_update_checker.check_skill_updates",
    "schedule": crontab(hour=2, minute=0),  # daily at 02:00 UTC
},
```

Import `crontab` at top of `celery_app.py`:
```python
from celery.schedules import crontab
```

Make `check_skill_updates` a proper Celery task by decorating it:

```python
# In skill_update_checker.py, at the end:
from scheduler.celery_app import celery_app

check_skill_updates = celery_app.task(
    name="scheduler.tasks.skill_update_checker.check_skill_updates",
    bind=False,
)(check_skill_updates)
```

> **Note:** Celery task registration requires careful import ordering to avoid circular imports. Follow the same pattern as `scheduler/tasks/embedding.py` — check that file for how it imports and registers tasks.

### Step 6: Run full suite

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
Expected: 794+ passing.

### Step 7: Commit

```bash
git add backend/scheduler/tasks/skill_update_checker.py \
        backend/scheduler/celery_app.py \
        backend/tests/test_skill_update_checker.py
git commit -m "feat(21-06): UpdateChecker Celery task — daily source URL monitoring"
```

---

## Task 7: Verification

### Step 1: Run full test suite

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
Expected: ≥794 tests passing (net new tests added), 0 failures.

### Step 2: TypeScript check

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
```
Expected: 0 errors.

### Step 3: Manual smoke test (optional — requires running stack)

```bash
# 1. Verify scanner rejects dangerous skill
curl -X POST http://localhost:8000/api/admin/skills/import \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "---\nname: bad-skill\ndescription: dangerous\n---\n", "embedded_scripts": {"scripts/run.py": "import subprocess\nsubprocess.run([\"ls\"])"}}'
# Expect: security_report.recommendation == "reject"

# 2. Verify gate mode endpoint
curl http://localhost:8000/api/admin/platform-config/skill-gate \
  -H "Authorization: Bearer $TOKEN"
# Expect: {"skill_tool_gate_mode": "permissive", ...}
```

### Step 4: Final commit (if any cleanup needed)

```bash
git add -A
git commit -m "chore(phase-21): final verification — all tests passing"
```

---

## Summary

| Task | SKSEC | Key files |
|------|-------|-----------|
| 1: Migration 024 | — | `alembic/versions/024_*.py`, models |
| 2: Importer deps | SKSEC-01 | `skills/importer.py` |
| 3: Scanner v2 | SKSEC-01 + SKSEC-04 | `skills/security_scanner.py` |
| 4: SkillToolGate | SKSEC-02 | `skills/tool_gate.py`, `skills/executor.py` |
| 5: Gate config | SKSEC-02 | `api/routes/admin_keycloak.py`, frontend admin page |
| 6: UpdateChecker | SKSEC-03 | `scheduler/tasks/skill_update_checker.py` |
| 7: Verification | all | full test suite |
