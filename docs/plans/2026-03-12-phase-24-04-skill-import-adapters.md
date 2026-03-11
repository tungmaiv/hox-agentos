# Phase 24-04: Skill Import Adapters Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace hardcoded `SkillImporter` with a pluggable adapter architecture. Adapters auto-detect their source; `UnifiedImportService` orchestrates fetch → normalize → security gate → save.

**Architecture:** `backend/skills/adapters/` module with `BaseSkillAdapter` ABC and four concrete adapters. `UnifiedImportService` chains them. The security gate pipeline (from 24-05) is stubbed here and wired in fully in 24-05. Existing `SkillImporter` methods are preserved and called from inside the adapters.

**Tech Stack:** Python 3.12, FastAPI, httpx, the existing `SkillImporter` in `backend/skills/importer.py`.

**Depends on:** Phase 24-02 (registry_entries must exist for the save step).

---

## Task 1: Base Adapter Interface

**Files:**
- Create: `backend/skills/adapters/__init__.py`
- Create: `backend/skills/adapters/base.py`

**Step 1: Write the base adapter**

```python
# backend/skills/adapters/base.py
"""
Base interface for skill import adapters.

Each adapter handles one source type. UnifiedImportService auto-detects
the right adapter by calling can_handle() on each in priority order.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawSkill:
    """Raw skill data before normalization. Source-format-specific."""
    content: str | bytes       # raw text or bytes
    source_url: str | None = None
    content_type: str = "text"  # "text" | "zip" | "yaml"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillImportCandidate:
    """Normalized skill data ready for security gate and DB save."""
    name: str
    description: str
    instruction_markdown: str | None = None
    procedure: dict[str, Any] | None = None   # merged from instructional+procedural
    allowed_tools: list[str] | None = None
    tags: list[str] = field(default_factory=list)
    category: str | None = None
    source_url: str | None = None
    license: str | None = None
    version: str = "1.0.0"
    declared_dependencies: list[str] = field(default_factory=list)
    scripts_content: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseSkillAdapter(ABC):
    """Strategy interface for importing skills from a specific source type."""

    @abstractmethod
    def can_handle(self, source: str) -> bool:
        """Return True if this adapter can handle the given source string."""
        ...

    @abstractmethod
    async def fetch(self, source: str) -> list[RawSkill]:
        """Fetch raw skill(s) from the source. Returns list (some sources yield multiple)."""
        ...

    @abstractmethod
    def normalize(self, raw: RawSkill) -> SkillImportCandidate:
        """Convert a RawSkill to a normalized SkillImportCandidate."""
        ...
```

**Step 2: Write a test for the interface**

```python
# backend/tests/skills/adapters/test_base_adapter.py
from skills.adapters.base import SkillImportCandidate, RawSkill


def test_skill_import_candidate_defaults():
    candidate = SkillImportCandidate(
        name="test", description="test desc"
    )
    assert candidate.version == "1.0.0"
    assert candidate.tags == []
    assert candidate.declared_dependencies == []
```

**Step 3: Run test**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/skills/adapters/test_base_adapter.py -v
```

**Step 4: Commit**

```bash
git add backend/skills/adapters/
git commit -m "feat(24-04): add base skill import adapter interface"
```

---

## Task 2: SkillRepoAdapter (Refactored)

**Files:**
- Create: `backend/skills/adapters/skill_repo.py`
- Test: `backend/tests/skills/adapters/test_skill_repo_adapter.py`

**Step 1: Write the adapter (wraps existing SkillImporter)**

```python
# backend/skills/adapters/skill_repo.py
"""
SkillRepoAdapter — imports from AgentSkills-format SKILL.md URLs.

Handles:
- Direct SKILL.md URL: https://example.com/skills/SKILL.md
- ZIP bundle URL: https://example.com/skills/skill.zip
- GitHub blob URL (converted to raw automatically by SkillImporter)

Does NOT handle: agentskills-index.json repository URLs (those go through
the SkillRepository flow, not this adapter).
"""
import structlog

from skills.adapters.base import BaseSkillAdapter, RawSkill, SkillImportCandidate
from skills.importer import SkillImporter

logger = structlog.get_logger(__name__)
_importer = SkillImporter()


class SkillRepoAdapter(BaseSkillAdapter):
    def can_handle(self, source: str) -> bool:
        lower = source.lower()
        return (
            lower.startswith("http")
            and (
                "skill.md" in lower
                or lower.endswith(".zip")
                or "github.com" in lower
                or "raw.githubusercontent.com" in lower
            )
        )

    async def fetch(self, source: str) -> list[RawSkill]:
        # Delegate to existing SkillImporter.import_from_url
        skill_data = await _importer.import_from_url(source)
        return [RawSkill(
            content=str(skill_data),
            source_url=source,
            content_type="parsed",
            extra=skill_data,
        )]

    def normalize(self, raw: RawSkill) -> SkillImportCandidate:
        d = raw.extra
        return SkillImportCandidate(
            name=d["name"],
            description=d.get("description", ""),
            instruction_markdown=d.get("instruction_markdown"),
            procedure=d.get("procedure_json"),
            allowed_tools=d.get("allowed_tools"),
            tags=d.get("tags") or [],
            category=d.get("category"),
            source_url=raw.source_url,
            license=d.get("license"),
            version=d.get("version", "1.0.0"),
            declared_dependencies=d.get("declared_dependencies") or [],
            scripts_content=d.get("scripts_content") or [],
            metadata=d.get("metadata_json") or {},
        )
```

**Step 2: Write tests**

```python
# backend/tests/skills/adapters/test_skill_repo_adapter.py
import pytest
from unittest.mock import AsyncMock, patch


def test_can_handle_skill_md_url():
    from skills.adapters.skill_repo import SkillRepoAdapter
    adapter = SkillRepoAdapter()
    assert adapter.can_handle("https://example.com/path/SKILL.md")
    assert adapter.can_handle("https://example.com/skill.zip")
    assert adapter.can_handle("https://github.com/user/repo/blob/main/SKILL.md")


def test_cannot_handle_non_skill_url():
    from skills.adapters.skill_repo import SkillRepoAdapter
    adapter = SkillRepoAdapter()
    assert not adapter.can_handle("https://github.com/user/repo")
    assert not adapter.can_handle("github.com/user/repo")


@pytest.mark.asyncio
async def test_fetch_delegates_to_importer():
    from skills.adapters.skill_repo import SkillRepoAdapter

    mock_data = {
        "name": "test-skill",
        "description": "A test skill",
        "instruction_markdown": "Do stuff",
    }
    with patch("skills.adapters.skill_repo._importer") as mock_importer:
        mock_importer.import_from_url = AsyncMock(return_value=mock_data)
        adapter = SkillRepoAdapter()
        results = await adapter.fetch("https://example.com/SKILL.md")
        assert len(results) == 1
        assert results[0].extra == mock_data


def test_normalize_maps_fields():
    from skills.adapters.skill_repo import SkillRepoAdapter
    from skills.adapters.base import RawSkill

    raw = RawSkill(
        content="",
        source_url="https://example.com/SKILL.md",
        content_type="parsed",
        extra={
            "name": "my-skill",
            "description": "Does things",
            "instruction_markdown": "## Instructions\nDo the thing",
            "tags": ["productivity"],
        },
    )
    adapter = SkillRepoAdapter()
    candidate = adapter.normalize(raw)
    assert candidate.name == "my-skill"
    assert candidate.tags == ["productivity"]
    assert candidate.instruction_markdown == "## Instructions\nDo the thing"
```

**Step 3: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/skills/adapters/test_skill_repo_adapter.py -v
```

**Step 4: Commit**

```bash
git add backend/skills/adapters/skill_repo.py \
        backend/tests/skills/adapters/test_skill_repo_adapter.py
git commit -m "feat(24-04): add SkillRepoAdapter wrapping existing SkillImporter"
```

---

## Task 3: ClaudeMarketAdapter

**Files:**
- Create: `backend/skills/adapters/claude_market.py`
- Test: `backend/tests/skills/adapters/test_claude_market_adapter.py`

**Step 1: Write the adapter**

```python
# backend/skills/adapters/claude_market.py
"""
ClaudeMarketAdapter — imports skills from Claude Code YAML format.

Handles:
- Raw YAML content strings (content_type="yaml")
- URLs pointing to .yaml or .yml skill files

Uses SkillImporter.import_from_claude_code_yaml() for parsing.
"""
import structlog

from skills.adapters.base import BaseSkillAdapter, RawSkill, SkillImportCandidate
from skills.importer import SkillImporter

logger = structlog.get_logger(__name__)
_importer = SkillImporter()


class ClaudeMarketAdapter(BaseSkillAdapter):
    def can_handle(self, source: str) -> bool:
        lower = source.lower()
        # Handles direct YAML content (starts with 'name:' or 'description:')
        if source.strip().startswith(("name:", "description:")):
            return True
        # Handles .yaml or .yml URLs
        if lower.startswith("http") and (lower.endswith(".yaml") or lower.endswith(".yml")):
            return True
        return False

    async def fetch(self, source: str) -> list[RawSkill]:
        if source.strip().startswith(("name:", "description:")):
            # Direct YAML content
            return [RawSkill(content=source, content_type="yaml")]

        # URL — fetch and return raw YAML
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(source)
            resp.raise_for_status()
        return [RawSkill(content=resp.text, source_url=source, content_type="yaml")]

    def normalize(self, raw: RawSkill) -> SkillImportCandidate:
        skill_data = _importer.import_from_claude_code_yaml(raw.content)
        return SkillImportCandidate(
            name=skill_data["name"],
            description=skill_data.get("description", ""),
            instruction_markdown=skill_data.get("instruction_markdown"),
            allowed_tools=skill_data.get("allowed_tools"),
            tags=skill_data.get("tags") or [],
            category=skill_data.get("category"),
            source_url=raw.source_url,
            license=skill_data.get("license"),
            version=skill_data.get("version", "1.0.0"),
        )
```

**Step 2: Write tests**

```python
# backend/tests/skills/adapters/test_claude_market_adapter.py
import pytest


def test_can_handle_yaml_content():
    from skills.adapters.claude_market import ClaudeMarketAdapter
    adapter = ClaudeMarketAdapter()
    assert adapter.can_handle("name: my-skill\ndescription: does things")


def test_can_handle_yaml_url():
    from skills.adapters.claude_market import ClaudeMarketAdapter
    adapter = ClaudeMarketAdapter()
    assert adapter.can_handle("https://raw.githubusercontent.com/user/repo/main/skill.yaml")


def test_cannot_handle_skill_md():
    from skills.adapters.claude_market import ClaudeMarketAdapter
    adapter = ClaudeMarketAdapter()
    assert not adapter.can_handle("https://example.com/SKILL.md")


@pytest.mark.asyncio
async def test_fetch_direct_yaml_content():
    from skills.adapters.claude_market import ClaudeMarketAdapter
    adapter = ClaudeMarketAdapter()
    yaml_content = "name: test\ndescription: test skill"
    results = await adapter.fetch(yaml_content)
    assert len(results) == 1
    assert results[0].content == yaml_content
    assert results[0].content_type == "yaml"


def test_normalize_yaml():
    from skills.adapters.claude_market import ClaudeMarketAdapter
    from skills.adapters.base import RawSkill

    adapter = ClaudeMarketAdapter()
    raw = RawSkill(
        content="name: email-helper\ndescription: Helps with email\ntools: [email.fetch, email.send]",
        content_type="yaml",
    )
    candidate = adapter.normalize(raw)
    assert candidate.name == "email-helper"
    assert candidate.allowed_tools == ["email.fetch", "email.send"]
```

**Step 3: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/skills/adapters/test_claude_market_adapter.py -v
```

**Step 4: Commit**

```bash
git add backend/skills/adapters/claude_market.py \
        backend/tests/skills/adapters/test_claude_market_adapter.py
git commit -m "feat(24-04): add ClaudeMarketAdapter for Claude Code YAML skills"
```

---

## Task 4: GitHubAdapter

**Files:**
- Create: `backend/skills/adapters/github.py`
- Test: `backend/tests/skills/adapters/test_github_adapter.py`

**Step 1: Write the adapter**

```python
# backend/skills/adapters/github.py
"""
GitHubAdapter — imports skills by scanning a GitHub repo for skill files.

Accepts:
- github.com/user/repo (full URL or shorthand)
- owner/repo (shorthand)

Fetches the repo file tree via GitHub API, detects skill files
(SKILL.md, *.yaml with name+description frontmatter), returns one RawSkill per file found.
"""
import re
from typing import Any

import httpx
import structlog

from skills.adapters.base import BaseSkillAdapter, RawSkill, SkillImportCandidate
from skills.importer import SkillImporter

logger = structlog.get_logger(__name__)
_importer = SkillImporter()

_GITHUB_REPO_RE = re.compile(
    r"^(?:https?://github\.com/)?([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)/?$"
)


class GitHubAdapter(BaseSkillAdapter):
    def can_handle(self, source: str) -> bool:
        return bool(_GITHUB_REPO_RE.match(source.strip()))

    async def fetch(self, source: str) -> list[RawSkill]:
        match = _GITHUB_REPO_RE.match(source.strip())
        if not match:
            return []
        owner, repo = match.group(1), match.group(2)

        # Use GitHub API to list repo contents (default branch)
        tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
        async with httpx.AsyncClient(timeout=30.0, headers={"Accept": "application/vnd.github+json"}) as client:
            resp = await client.get(tree_url)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            tree = resp.json().get("tree", [])

        raw_skills: list[RawSkill] = []
        for item in tree:
            path: str = item.get("path", "")
            if item.get("type") != "blob":
                continue
            filename = path.split("/")[-1]
            if filename in ("SKILL.md",) or (filename.endswith((".yaml", ".yml")) and "skill" in filename.lower()):
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}"
                try:
                    async with httpx.AsyncClient(timeout=15.0) as fc:
                        file_resp = await fc.get(raw_url)
                        file_resp.raise_for_status()
                    content_type = "text" if filename.endswith(".md") else "yaml"
                    raw_skills.append(RawSkill(
                        content=file_resp.text,
                        source_url=raw_url,
                        content_type=content_type,
                    ))
                except Exception as exc:
                    logger.warning("github_file_fetch_failed", path=path, error=str(exc))

        logger.info("github_repo_scanned", owner=owner, repo=repo, found=len(raw_skills))
        return raw_skills

    def normalize(self, raw: RawSkill) -> SkillImportCandidate:
        if raw.content_type == "yaml":
            skill_data = _importer.import_from_claude_code_yaml(raw.content)
        else:
            skill_data = _importer.parse_skill_md(raw.content)

        return SkillImportCandidate(
            name=skill_data["name"],
            description=skill_data.get("description", ""),
            instruction_markdown=skill_data.get("instruction_markdown"),
            procedure=skill_data.get("procedure_json"),
            allowed_tools=skill_data.get("allowed_tools"),
            tags=skill_data.get("tags") or [],
            category=skill_data.get("category"),
            source_url=raw.source_url,
            license=skill_data.get("license"),
            version=skill_data.get("version", "1.0.0"),
            declared_dependencies=skill_data.get("declared_dependencies") or [],
            scripts_content=skill_data.get("scripts_content") or [],
        )
```

**Step 2: Write tests**

```python
# backend/tests/skills/adapters/test_github_adapter.py
import pytest


def test_can_handle_github_url():
    from skills.adapters.github import GitHubAdapter
    adapter = GitHubAdapter()
    assert adapter.can_handle("github.com/user/repo")
    assert adapter.can_handle("https://github.com/user/repo")
    assert adapter.can_handle("user/repo")


def test_cannot_handle_non_github():
    from skills.adapters.github import GitHubAdapter
    adapter = GitHubAdapter()
    assert not adapter.can_handle("https://example.com/skills/SKILL.md")
    assert not adapter.can_handle("name: my-skill\ndescription: test")
```

**Step 3: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/skills/adapters/test_github_adapter.py -v
```

**Step 4: Commit**

```bash
git add backend/skills/adapters/github.py \
        backend/tests/skills/adapters/test_github_adapter.py
git commit -m "feat(24-04): add GitHubAdapter for repo-based skill discovery"
```

---

## Task 5: ZipFileAdapter (Refactored)

**Files:**
- Create: `backend/skills/adapters/zip_file.py`

**Step 1: Write the adapter**

```python
# backend/skills/adapters/zip_file.py
"""
ZipFileAdapter — imports from ZIP bundles (wraps existing SkillImporter.import_from_zip).
Handles base64-encoded ZIP strings or raw bytes.
"""
import base64

from skills.adapters.base import BaseSkillAdapter, RawSkill, SkillImportCandidate
from skills.importer import SkillImporter

_importer = SkillImporter()


class ZipFileAdapter(BaseSkillAdapter):
    def can_handle(self, source: str) -> bool:
        # ZIP bytes are passed as base64 strings prefixed with "zip:"
        return source.startswith("zip:")

    async def fetch(self, source: str) -> list[RawSkill]:
        # source format: "zip:<base64-encoded-zip-bytes>"
        b64 = source[4:]
        zip_bytes = base64.b64decode(b64)
        return [RawSkill(content=zip_bytes, content_type="zip")]

    def normalize(self, raw: RawSkill) -> SkillImportCandidate:
        skill_data = _importer.import_from_zip(raw.content)
        return SkillImportCandidate(
            name=skill_data["name"],
            description=skill_data.get("description", ""),
            instruction_markdown=skill_data.get("instruction_markdown"),
            procedure=skill_data.get("procedure_json"),
            allowed_tools=skill_data.get("allowed_tools"),
            tags=skill_data.get("tags") or [],
            category=skill_data.get("category"),
            source_url=raw.source_url,
            license=skill_data.get("license"),
            version=skill_data.get("version", "1.0.0"),
            declared_dependencies=skill_data.get("declared_dependencies") or [],
            scripts_content=skill_data.get("scripts_content") or [],
        )
```

**Step 2: Commit**

```bash
git add backend/skills/adapters/zip_file.py
git commit -m "feat(24-04): add ZipFileAdapter wrapping existing ZIP import"
```

---

## Task 6: UnifiedImportService

**Files:**
- Create: `backend/skills/adapters/unified_import.py`
- Test: `backend/tests/skills/adapters/test_unified_import.py`
- Modify: `backend/api/routes/admin_skills.py` (wire import endpoint to use UnifiedImportService)

**Step 1: Write the service**

```python
# backend/skills/adapters/unified_import.py
"""
UnifiedImportService — orchestrates skill import through:
  1. Auto-detect adapter via can_handle()
  2. Fetch raw skill(s)
  3. Normalize each to SkillImportCandidate
  4. Run security gate pipeline (stubbed here; wired in 24-05)
  5. Save to registry_entries

Security gate stub: always returns (True, None) until 24-05 wires the real scanner.
"""
import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.registry_entry import RegistryEntry
from skills.adapters.base import BaseSkillAdapter, SkillImportCandidate
from skills.adapters.claude_market import ClaudeMarketAdapter
from skills.adapters.github import GitHubAdapter
from skills.adapters.skill_repo import SkillRepoAdapter
from skills.adapters.zip_file import ZipFileAdapter

logger = structlog.get_logger(__name__)

# Adapter priority order: more specific first
_ADAPTERS: list[BaseSkillAdapter] = [
    ZipFileAdapter(),
    SkillRepoAdapter(),
    ClaudeMarketAdapter(),
    GitHubAdapter(),
]


async def _security_gate_stub(
    candidate: SkillImportCandidate,
) -> tuple[bool, str | None]:
    """Security gate stub — replaced in 24-05 with real scanner call.

    Returns:
        (allowed, rejection_reason) — stub always allows.
    """
    return True, None


class UnifiedImportService:
    """Auto-detect adapter, fetch, normalize, security-gate, and save a skill."""

    async def import_skill(
        self,
        source: str,
        session: AsyncSession,
        imported_by: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        """Import skill(s) from the given source.

        Returns list of created registry entry dicts.
        Raises ValueError if no adapter handles the source,
        or if security gate blocks the import.
        """
        adapter = self._detect_adapter(source)
        if not adapter:
            raise ValueError(
                f"No adapter found for source: {source!r}. "
                "Supported: SKILL.md URLs, ZIP files (zip:<base64>), "
                "Claude Code YAML, GitHub repos (owner/repo)."
            )

        raw_skills = await adapter.fetch(source)
        results = []

        for raw in raw_skills:
            candidate = adapter.normalize(raw)

            # Security gate (stubbed until 24-05)
            allowed, reason = await _security_gate_stub(candidate)
            if not allowed:
                logger.warning(
                    "skill_import_blocked",
                    name=candidate.name,
                    reason=reason,
                )
                raise ValueError(f"Import blocked by security gate: {reason}")

            entry = await self._save(candidate, session, imported_by)
            results.append({"id": str(entry.id), "name": entry.name, "status": entry.status})
            logger.info("skill_imported", name=candidate.name, id=str(entry.id))

        return results

    def _detect_adapter(self, source: str) -> BaseSkillAdapter | None:
        for adapter in _ADAPTERS:
            if adapter.can_handle(source):
                return adapter
        return None

    async def _save(
        self,
        candidate: SkillImportCandidate,
        session: AsyncSession,
        imported_by: uuid.UUID | None,
    ) -> RegistryEntry:
        config: dict[str, Any] = {
            "instruction_markdown": candidate.instruction_markdown,
            "allowed_tools": candidate.allowed_tools or [],
            "declared_dependencies": candidate.declared_dependencies,
        }
        if candidate.procedure:
            config["procedure"] = candidate.procedure

        metadata: dict[str, Any] = {
            "tags": candidate.tags,
            "category": candidate.category,
            "source_url": candidate.source_url,
            "license": candidate.license,
            "version": candidate.version,
            **candidate.metadata,
        }

        # Upsert by name: update if exists, create if not
        from sqlalchemy import select
        existing = await session.execute(
            select(RegistryEntry).where(
                RegistryEntry.type == "skill",
                RegistryEntry.name == candidate.name,
            )
        )
        entry = existing.scalar_one_or_none()
        if entry:
            entry.config = config
            entry.metadata_ = metadata
            entry.description = candidate.description
        else:
            entry = RegistryEntry(
                type="skill",
                name=candidate.name,
                description=candidate.description,
                status="active",
                config=config,
                metadata_=metadata,
                created_by=imported_by,
            )
            session.add(entry)

        await session.commit()
        await session.refresh(entry)
        return entry
```

**Step 2: Write tests**

```python
# backend/tests/skills/adapters/test_unified_import.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_import_raises_on_unknown_source():
    from skills.adapters.unified_import import UnifiedImportService
    service = UnifiedImportService()
    with pytest.raises(ValueError, match="No adapter found"):
        await service.import_skill("totally-unknown-source://x", session=AsyncMock())


@pytest.mark.asyncio
async def test_import_detects_skill_repo_adapter():
    from skills.adapters.unified_import import UnifiedImportService

    service = UnifiedImportService()
    adapter = service._detect_adapter("https://example.com/SKILL.md")
    from skills.adapters.skill_repo import SkillRepoAdapter
    assert isinstance(adapter, SkillRepoAdapter)


@pytest.mark.asyncio
async def test_import_detects_github_adapter():
    from skills.adapters.unified_import import UnifiedImportService

    service = UnifiedImportService()
    adapter = service._detect_adapter("user/repo")
    from skills.adapters.github import GitHubAdapter
    assert isinstance(adapter, GitHubAdapter)
```

**Step 3: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/skills/adapters/ -v
```

Expected: all PASS.

**Step 4: Wire into the admin import endpoint**

In `backend/api/routes/admin_skills.py`, find the import endpoint (the one that calls `SkillImporter`). Replace with:

```python
from skills.adapters.unified_import import UnifiedImportService

_import_service = UnifiedImportService()

@router.post("/import")
async def import_skill(
    source: str,
    session: AsyncSession = Depends(get_session),
    user=Depends(require_permission("registry:manage")),
):
    results = await _import_service.import_skill(source, session, imported_by=user.id)
    return {"imported": results}
```

**Step 5: Run full test suite**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

**Step 6: Commit**

```bash
git add backend/skills/adapters/unified_import.py \
        backend/tests/skills/adapters/test_unified_import.py \
        backend/api/routes/admin_skills.py
git commit -m "feat(24-04): add UnifiedImportService with pluggable adapter pattern"
```

---

## Completion Check

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Exit 0, same or higher test count as before.
