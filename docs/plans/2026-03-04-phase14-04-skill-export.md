# Phase 14-04: Skill Export Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Admin can export any skill definition as an agentskills.io-compliant zip directory from the admin panel.

**Architecture:** New `backend/skill_export/` module with an exporter that builds a zip in-memory from a `SkillDefinition` row, a FastAPI route that streams the zip response, and an "Export" button added to the existing admin Skills page. The existing catch-all admin proxy handles forwarding but needs a binary-aware path for zip streaming.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, structlog, Python `zipfile` + `io.BytesIO`, PyYAML

---

### Task 1: Create skill_export module with schemas

**Files:**
- Create: `backend/skill_export/__init__.py`
- Create: `backend/skill_export/schemas.py`

**Step 1: Create the module init**

```python
# backend/skill_export/__init__.py
```

(Empty file — makes it a package.)

**Step 2: Write the schemas**

```python
# backend/skill_export/schemas.py
"""Pydantic schemas for skill export metadata."""
from datetime import datetime

from pydantic import BaseModel


class ExportMetadata(BaseModel):
    """Metadata embedded in SKILL.md frontmatter during export."""
    author: str = "blitz-agentos"
    version: str
    skill_type: str
    slash_command: str | None
    source_type: str
    exported_at: str
```

**Step 3: Commit**

```bash
git add backend/skill_export/__init__.py backend/skill_export/schemas.py
git commit -m "feat(14-04): add skill_export module with schemas"
```

---

### Task 2: Write the exporter function

**Files:**
- Create: `backend/skill_export/exporter.py`

**Step 1: Write the exporter**

This builds an in-memory zip with the agentskills.io directory structure: `skill-name/SKILL.md` + optional `scripts/procedure.json` and `references/schemas.json`.

```python
# backend/skill_export/exporter.py
"""Build agentskills.io-compliant zip from a SkillDefinition row."""
import io
import json
import zipfile
from datetime import datetime, timezone

import structlog
import yaml

from core.models.skill_definition import SkillDefinition

logger = structlog.get_logger(__name__)


def build_skill_zip(skill: SkillDefinition) -> io.BytesIO:
    """Build a zip archive from a SkillDefinition ORM row.

    Returns:
        BytesIO buffer containing the zip archive.
    """
    buf = io.BytesIO()
    dir_name = skill.name  # top-level directory in zip

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # ── SKILL.md ─────────────────────────────────────────
        frontmatter: dict = {
            "name": skill.name,
            "description": skill.description or "",
        }

        # Optional standard fields
        if skill.display_name:
            frontmatter["display_name"] = skill.display_name
        if skill.slash_command:
            frontmatter["slash_command"] = skill.slash_command

        # License (not stored in DB — default to Proprietary)
        frontmatter["license"] = "Proprietary"

        # Metadata block
        frontmatter["metadata"] = {
            "author": "blitz-agentos",
            "version": skill.version,
            "skill_type": skill.skill_type,
            "source_type": skill.source_type,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

        yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
        body = skill.instruction_markdown or ""

        skill_md = f"---\n{yaml_str}---\n\n{body}\n"
        zf.writestr(f"{dir_name}/SKILL.md", skill_md)

        # ── scripts/procedure.json (procedural skills only) ──
        if skill.procedure_json:
            zf.writestr(
                f"{dir_name}/scripts/procedure.json",
                json.dumps(skill.procedure_json, indent=2, ensure_ascii=False),
            )

        # ── references/schemas.json (if schemas defined) ─────
        schemas: dict = {}
        if skill.input_schema:
            schemas["input_schema"] = skill.input_schema
        if skill.output_schema:
            schemas["output_schema"] = skill.output_schema
        if schemas:
            zf.writestr(
                f"{dir_name}/references/schemas.json",
                json.dumps(schemas, indent=2, ensure_ascii=False),
            )

    buf.seek(0)

    logger.info(
        "skill_zip_built",
        skill_name=skill.name,
        zip_size=buf.getbuffer().nbytes,
    )
    return buf
```

**Step 2: Commit**

```bash
git add backend/skill_export/exporter.py
git commit -m "feat(14-04): add build_skill_zip exporter function"
```

---

### Task 3: Write tests for the exporter

**Files:**
- Create: `backend/tests/test_skill_export.py`

**Step 1: Write the test file**

```python
# backend/tests/test_skill_export.py
"""Tests for the skill_export module."""
import io
import json
import zipfile
from unittest.mock import MagicMock
from uuid import uuid4

import yaml

from skill_export.exporter import build_skill_zip


def _make_skill(**overrides) -> MagicMock:
    """Create a mock SkillDefinition with defaults."""
    defaults = {
        "id": uuid4(),
        "name": "test-skill",
        "display_name": "Test Skill",
        "description": "A test skill for export",
        "version": "1.0.0",
        "skill_type": "instructional",
        "slash_command": "/test",
        "source_type": "user_created",
        "instruction_markdown": "# Instructions\n\nDo the thing.",
        "procedure_json": None,
        "input_schema": None,
        "output_schema": None,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def test_export_instructional_skill():
    """Instructional skill produces SKILL.md with correct frontmatter."""
    skill = _make_skill()
    buf = build_skill_zip(skill)

    with zipfile.ZipFile(buf) as zf:
        names = zf.namelist()
        assert "test-skill/SKILL.md" in names
        # No procedure file for instructional
        assert "test-skill/scripts/procedure.json" not in names

        content = zf.read("test-skill/SKILL.md").decode("utf-8")

        # Parse frontmatter
        assert content.startswith("---\n")
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        assert frontmatter["name"] == "test-skill"
        assert frontmatter["description"] == "A test skill for export"
        assert frontmatter["slash_command"] == "/test"
        assert frontmatter["license"] == "Proprietary"
        assert frontmatter["metadata"]["skill_type"] == "instructional"
        assert frontmatter["metadata"]["version"] == "1.0.0"
        assert "exported_at" in frontmatter["metadata"]

        # Body after second ---
        body = parts[2].strip()
        assert "# Instructions" in body
        assert "Do the thing." in body


def test_export_procedural_skill_includes_procedure():
    """Procedural skill includes scripts/procedure.json."""
    procedure = {"steps": [{"tool": "email.fetch", "params": {}}]}
    skill = _make_skill(
        skill_type="procedural",
        procedure_json=procedure,
    )
    buf = build_skill_zip(skill)

    with zipfile.ZipFile(buf) as zf:
        assert "test-skill/scripts/procedure.json" in zf.namelist()
        proc = json.loads(zf.read("test-skill/scripts/procedure.json"))
        assert proc == procedure


def test_export_includes_schemas():
    """Skills with schemas include references/schemas.json."""
    in_schema = {"type": "object", "properties": {"query": {"type": "string"}}}
    out_schema = {"type": "object", "properties": {"result": {"type": "string"}}}
    skill = _make_skill(input_schema=in_schema, output_schema=out_schema)
    buf = build_skill_zip(skill)

    with zipfile.ZipFile(buf) as zf:
        assert "test-skill/references/schemas.json" in zf.namelist()
        schemas = json.loads(zf.read("test-skill/references/schemas.json"))
        assert schemas["input_schema"] == in_schema
        assert schemas["output_schema"] == out_schema


def test_export_no_schemas_omits_references():
    """No schemas → no references/ directory."""
    skill = _make_skill(input_schema=None, output_schema=None)
    buf = build_skill_zip(skill)

    with zipfile.ZipFile(buf) as zf:
        assert "test-skill/references/schemas.json" not in zf.namelist()


def test_export_empty_body():
    """Skill with no instruction_markdown still produces valid SKILL.md."""
    skill = _make_skill(instruction_markdown=None)
    buf = build_skill_zip(skill)

    with zipfile.ZipFile(buf) as zf:
        content = zf.read("test-skill/SKILL.md").decode("utf-8")
        assert content.startswith("---\n")
        # Should still be valid YAML frontmatter
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])
        assert frontmatter["name"] == "test-skill"


def test_zip_is_valid():
    """Returned BytesIO is a valid zip file."""
    skill = _make_skill()
    buf = build_skill_zip(skill)
    assert isinstance(buf, io.BytesIO)
    assert buf.getbuffer().nbytes > 0
    assert zipfile.is_zipfile(buf)
```

**Step 2: Run tests to verify they pass**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_skill_export.py -v
```

Expected: 6 PASSED

**Step 3: Commit**

```bash
git add backend/tests/test_skill_export.py
git commit -m "test(14-04): add skill export unit tests"
```

---

### Task 4: Add the export route

**Files:**
- Create: `backend/skill_export/routes.py`

**Step 1: Write the route**

```python
# backend/skill_export/routes.py
"""Admin route for exporting a skill as agentskills.io zip."""
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.skill_definition import SkillDefinition
from core.models.user import UserContext
from security.deps import get_current_user
from security.rbac import has_permission
from skill_export.exporter import build_skill_zip

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin/skills", tags=["admin-skill-export"])


async def _require_registry_manager(
    user: UserContext = Depends(get_current_user),
) -> UserContext:
    """Gate: require registry:manage permission."""
    if not has_permission(user["roles"], "registry:manage"):
        raise HTTPException(status_code=403, detail="registry:manage required")
    return user


@router.get("/{skill_id}/export")
async def export_skill(
    skill_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export a skill as agentskills.io-compliant zip archive."""
    result = await session.execute(
        select(SkillDefinition).where(SkillDefinition.id == skill_id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    buf = build_skill_zip(skill)
    filename = f"{skill.name}.zip"

    logger.info(
        "skill_exported",
        skill_id=str(skill_id),
        skill_name=skill.name,
        user_id=str(user["user_id"]),
    )

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
```

**Step 2: Register the router in main.py**

In `backend/main.py`, add the import and include the router. Find the router registration block (around line 127-200) and add:

```python
from skill_export.routes import router as skill_export_router
```

And in the `include_router` section (after the admin_skills router):

```python
app.include_router(skill_export_router)
```

**Important:** The skill_export router uses prefix `/api/admin/skills` same as admin_skills — FastAPI merges routes from both routers. The `/{skill_id}/export` path won't conflict because admin_skills has `/{skill_id}` for GET/PUT and `/{skill_id}/status`, `/{skill_id}/activate`, etc. The export route's `/{skill_id}/export` literal segment is distinct.

**Step 3: Commit**

```bash
git add backend/skill_export/routes.py backend/main.py
git commit -m "feat(14-04): add skill export admin route with StreamingResponse"
```

---

### Task 5: Write route tests

**Files:**
- Modify: `backend/tests/test_skill_export.py` (append route tests)

**Step 1: Add route tests to the existing test file**

Append to `backend/tests/test_skill_export.py`:

```python
# ── Route tests ──────────────────────────────────────────────

import asyncio
import zipfile as zf_mod

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db import Base, get_db
from core.models.skill_definition import SkillDefinition
from core.models.user import UserContext
from security.deps import get_current_user

# Import all models so Base.metadata has all tables
from core.models.agent_definition import AgentDefinition  # noqa: F401
from core.models.artifact_permission import ArtifactPermission  # noqa: F401
from core.models.mcp_server import McpServer  # noqa: F401
from core.models.role_permission import RolePermission  # noqa: F401
from core.models.tool_definition import ToolDefinition  # noqa: F401
from core.models.user_artifact_permission import UserArtifactPermission  # noqa: F401


@pytest.fixture
def route_db():
    """In-memory SQLite for route tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(_setup())
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def admin_user() -> UserContext:
    return {
        "user_id": uuid4(),
        "username": "admin",
        "email": "admin@blitz.local",
        "roles": ["admin"],
        "permissions": ["registry:manage", "chat"],
    }


@pytest.fixture
def app_client(route_db, admin_user):
    """FastAPI test client with dependency overrides."""
    from main import app

    async def _override_db():
        async with route_db() as session:
            yield session

    async def _override_user():
        return admin_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_export_route_returns_zip(app_client, route_db):
    """GET /api/admin/skills/{id}/export returns a valid zip."""
    # Seed a skill
    async with route_db() as session:
        skill = SkillDefinition(
            name="export-me",
            description="A skill to export",
            skill_type="instructional",
            instruction_markdown="# Export Test",
            status="active",
            is_active=True,
        )
        session.add(skill)
        await session.commit()
        skill_id = skill.id

    async with AsyncClient(
        transport=ASGITransport(app=app_client),
        base_url="http://test",
    ) as client:
        resp = await client.get(f"/api/admin/skills/{skill_id}/export")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert "export-me.zip" in resp.headers.get("content-disposition", "")

    # Validate zip contents
    buf = io.BytesIO(resp.content)
    assert zf_mod.is_zipfile(buf)
    with zf_mod.ZipFile(buf) as z:
        assert "export-me/SKILL.md" in z.namelist()


@pytest.mark.asyncio
async def test_export_route_404_for_missing_skill(app_client):
    """GET /api/admin/skills/{id}/export returns 404 for unknown skill."""
    fake_id = uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app_client),
        base_url="http://test",
    ) as client:
        resp = await client.get(f"/api/admin/skills/{fake_id}/export")
    assert resp.status_code == 404
```

**Step 2: Run tests to verify they pass**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_skill_export.py -v
```

Expected: 8 PASSED (6 exporter + 2 route)

**Step 3: Commit**

```bash
git add backend/tests/test_skill_export.py
git commit -m "test(14-04): add skill export route tests"
```

---

### Task 6: Update frontend admin proxy for binary responses

**Files:**
- Modify: `frontend/src/app/api/admin/[...path]/route.ts`

**Step 1: Update the proxy to handle binary responses**

The current catch-all proxy reads `await backendResponse.text()` which corrupts binary zip data. Update it to detect binary content types and stream the raw response.

In `frontend/src/app/api/admin/[...path]/route.ts`, replace the try/catch block in `proxyRequest` (around lines 69-85) with:

```typescript
  try {
    const backendResponse = await fetch(url.toString(), fetchInit);
    const contentType =
      backendResponse.headers.get("Content-Type") ?? "application/json";

    // Binary responses (zip, octet-stream, images) — stream raw bytes
    const isBinary =
      contentType.includes("application/zip") ||
      contentType.includes("application/octet-stream") ||
      contentType.includes("image/");

    if (isBinary) {
      const arrayBuffer = await backendResponse.arrayBuffer();
      const responseHeaders: Record<string, string> = {
        "Content-Type": contentType,
      };
      const disposition = backendResponse.headers.get("Content-Disposition");
      if (disposition) {
        responseHeaders["Content-Disposition"] = disposition;
      }
      return new NextResponse(arrayBuffer, {
        status: backendResponse.status,
        headers: responseHeaders,
      });
    }

    // Text/JSON responses — existing behavior
    const responseBody = await backendResponse.text();
    return new NextResponse(responseBody, {
      status: backendResponse.status,
      headers: { "Content-Type": contentType },
    });
  } catch {
    return NextResponse.json(
      { error: "Backend unreachable" },
      { status: 502 }
    );
  }
```

**Step 2: Build to verify no TypeScript errors**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build
```

Expected: 0 errors

**Step 3: Commit**

```bash
git add frontend/src/app/api/admin/\[...path\]/route.ts
git commit -m "feat(14-04): admin proxy handles binary responses for zip export"
```

---

### Task 7: Add Export button to admin Skills page

**Files:**
- Modify: `frontend/src/app/admin/skills/page.tsx`

**Step 1: Add the export handler and button**

In `frontend/src/app/admin/skills/page.tsx`, add an export handler after `handleReview` (around line 48):

```typescript
  const handleExport = async (skillId: string, skillName: string) => {
    try {
      const resp = await fetch(`/api/admin/skills/${skillId}/export`);
      if (!resp.ok) {
        throw new Error(`Export failed: ${resp.status}`);
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${skillName}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // Silently fail — user sees no download
    }
  };
```

Then add an "Export" column to the `extraColumns` array (after the securityScore column, before the closing `]`):

```typescript
    {
      key: "export",
      label: "",
      render: (item: SkillDefinition) => (
        <button
          onClick={() => handleExport(item.id, item.name)}
          className="text-xs px-1.5 py-0.5 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
          title="Export as agentskills.io zip"
        >
          Export
        </button>
      ),
    },
```

Also add an Export button in the card grid's `renderExtra` callback (after the Review buttons block, before the closing `</div>`):

```typescript
              <button
                onClick={() => handleExport(item.id, item.name)}
                className="text-xs px-1.5 py-0.5 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors ml-auto"
                title="Export as agentskills.io zip"
              >
                Export
              </button>
```

**Step 2: Build to verify no TypeScript errors**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build
```

Expected: 0 errors

**Step 3: Commit**

```bash
git add frontend/src/app/admin/skills/page.tsx
git commit -m "feat(14-04): add Export button to admin Skills page"
```

---

### Task 8: Run full test suite and verify

**Step 1: Run backend tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: baseline + 8 new = 266+ tests pass (assuming baseline ~258)

**Step 2: Run frontend build**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build
```

Expected: 0 errors

**Step 3: Verify the export endpoint manually (optional)**

```bash
# If backend is running:
# 1. Get a skill ID from the admin page
# 2. curl -H "Authorization: Bearer <token>" http://localhost:8000/api/admin/skills/<id>/export -o skill.zip
# 3. unzip -l skill.zip  # verify structure
```
