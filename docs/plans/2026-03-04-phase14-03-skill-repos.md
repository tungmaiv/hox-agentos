# Phase 14-03: Skill Repositories Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable admins to register external skill repositories, users to browse/search skills from those repositories, and import skills into AgentOS through the existing security pipeline with `pending_review` status.

**Architecture:** New `backend/skill_repos/` module with ORM model, Pydantic schemas, service layer, and routes. New `skill_repositories` DB table via Alembic migration 019. Admin endpoints require `registry:manage`. User-facing browse/import requires `chat` permission. Frontend gets "Skill Repositories" admin tab and "Skill Store" user-facing browse page.

**Tech Stack:** FastAPI, SQLAlchemy async, httpx, Pydantic v2, structlog, Alembic

**Note:** This plan includes the Alembic migration (019) that also adds `openapi_spec_url` to `mcp_servers` from Plan 14-02. Execute this plan after Plan 14-02 Task 1 (which adds the ORM column).

---

### Task 1: Create SkillRepository ORM model

**Files:**
- Create: `backend/skill_repos/__init__.py`
- Create: `backend/skill_repos/models.py`
- Modify: `backend/core/models/__init__.py` (add import)

**Step 1: Create module init**

```python
# backend/skill_repos/__init__.py
```

**Step 2: Create the ORM model**

```python
# backend/skill_repos/models.py
"""
SkillRepository ORM model — external skill repository registry.

Stores registered repository URLs and their cached index data.
Each repository serves an agentskills-index.json at its base URL.
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, JSON, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base

_JSONB = JSON().with_variant(JSONB(), "postgresql")


class SkillRepository(Base):
    """Registry entry for an external skill repository."""

    __tablename__ = "skill_repositories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cached_index: Mapped[dict[str, Any] | None] = mapped_column(
        _JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

**Step 3: Register model in `core/models/__init__.py`**

Add after the existing imports:

```python
from skill_repos.models import SkillRepository  # noqa: F401
```

**Step 4: Commit**

```bash
git add backend/skill_repos/__init__.py backend/skill_repos/models.py backend/core/models/__init__.py
git commit -m "feat(14-03): add SkillRepository ORM model"
```

---

### Task 2: Create Alembic migration 019

**Files:**
- Create: `backend/alembic/versions/019_ecosystem_capabilities.py`

**Step 1: Generate migration**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
.venv/bin/alembic revision --autogenerate -m "ecosystem_capabilities"
```

**Step 2: Review the generated migration**

It should contain:
1. `op.create_table('skill_repositories', ...)` — all columns from the ORM model
2. `op.add_column('mcp_servers', sa.Column('openapi_spec_url', sa.Text(), nullable=True))` — from Plan 14-02

If the `openapi_spec_url` column isn't detected (because Plan 14-02 Task 1 hasn't been applied yet), add it manually to the upgrade function:

```python
op.add_column('mcp_servers', sa.Column('openapi_spec_url', sa.Text(), nullable=True))
```

And to downgrade:

```python
op.drop_column('mcp_servers', 'openapi_spec_url')
```

**Step 3: Commit**

```bash
git add backend/alembic/versions/019_*.py
git commit -m "feat(14-03): add migration 019 — skill_repositories table + openapi_spec_url column"
```

---

### Task 3: Create Pydantic schemas

**Files:**
- Create: `backend/skill_repos/schemas.py`

**Step 1: Write schemas**

```python
# backend/skill_repos/schemas.py
"""Pydantic schemas for skill repository management."""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


# ── Repository Index Format ────────────────────────────────────────────

class IndexSkillEntry(BaseModel):
    """Single skill entry in a repository index."""
    name: str
    description: str
    version: str = "1.0"
    skill_url: str
    directory_url: str | None = None
    metadata: dict[str, Any] | None = None


class IndexRepository(BaseModel):
    """Repository metadata from the index."""
    name: str
    description: str | None = None
    url: str | None = None
    version: str | None = None


class RepositoryIndex(BaseModel):
    """Schema for agentskills-index.json."""
    repository: IndexRepository
    skills: list[IndexSkillEntry]


# ── Admin API schemas ──────────────────────────────────────────────────

class RepoCreate(BaseModel):
    url: str  # base URL — will fetch /agentskills-index.json


class RepoResponse(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    description: str | None
    is_active: bool
    last_synced_at: datetime | None
    skill_count: int  # computed from cached_index
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── User-facing browse/import schemas ──────────────────────────────────

class SkillBrowseItem(BaseModel):
    """Skill entry for browsing external repositories."""
    name: str
    description: str
    version: str
    repository_name: str
    repository_id: uuid.UUID
    skill_url: str
    metadata: dict[str, Any] | None = None


class SkillImportFromRepoRequest(BaseModel):
    repository_id: uuid.UUID
    skill_name: str
```

**Step 2: Commit**

```bash
git add backend/skill_repos/schemas.py
git commit -m "feat(14-03): add skill repository Pydantic schemas"
```

---

### Task 4: Create service layer

**Files:**
- Create: `backend/skill_repos/service.py`

**Step 1: Write the service**

```python
# backend/skill_repos/service.py
"""
Service layer for skill repository management.

Handles: index fetching, validation, syncing, browsing, and importing.
"""
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from skill_repos.models import SkillRepository
from skill_repos.schemas import (
    IndexSkillEntry,
    RepoResponse,
    RepositoryIndex,
    SkillBrowseItem,
)
from skills.importer import SkillImportError, SkillImporter
from skills.security_scanner import SecurityScanner

logger = structlog.get_logger(__name__)


async def fetch_repo_index(url: str) -> RepositoryIndex:
    """Fetch and validate a repository's agentskills-index.json.

    Args:
        url: Base URL of the repository (we append /agentskills-index.json).

    Returns:
        Validated RepositoryIndex.

    Raises:
        ValueError: If the index is invalid or unreachable.
    """
    index_url = url.rstrip("/") + "/agentskills-index.json"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(index_url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ValueError(f"Failed to fetch index from {index_url}: {exc}")

    try:
        data = resp.json()
        return RepositoryIndex.model_validate(data)
    except Exception as exc:
        raise ValueError(f"Invalid repository index format: {exc}")


async def add_repository(url: str, session: AsyncSession) -> SkillRepository:
    """Register a new skill repository.

    Fetches the index, validates it, and creates the DB row.
    """
    index = await fetch_repo_index(url)

    # Check for duplicate name
    existing = await session.execute(
        select(SkillRepository).where(SkillRepository.name == index.repository.name)
    )
    if existing.scalar_one_or_none():
        raise ValueError(f"Repository '{index.repository.name}' already registered")

    repo = SkillRepository(
        name=index.repository.name,
        url=url.rstrip("/"),
        description=index.repository.description,
        is_active=True,
        last_synced_at=datetime.now(timezone.utc),
        cached_index=index.model_dump(),
    )
    session.add(repo)
    await session.commit()
    await session.refresh(repo)

    logger.info(
        "skill_repo_added",
        name=repo.name,
        url=repo.url,
        skills_count=len(index.skills),
    )
    return repo


async def sync_repository(repo_id: UUID, session: AsyncSession) -> SkillRepository:
    """Re-fetch and update a repository's cached index."""
    result = await session.execute(
        select(SkillRepository).where(SkillRepository.id == repo_id)
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        raise ValueError(f"Repository {repo_id} not found")

    index = await fetch_repo_index(repo.url)
    repo.cached_index = index.model_dump()
    repo.last_synced_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(repo)

    logger.info(
        "skill_repo_synced",
        name=repo.name,
        skills_count=len(index.skills),
    )
    return repo


async def list_repositories(session: AsyncSession) -> list[RepoResponse]:
    """List all registered repositories with skill counts."""
    result = await session.execute(select(SkillRepository))
    repos = result.scalars().all()

    responses = []
    for repo in repos:
        skill_count = 0
        if repo.cached_index and "skills" in repo.cached_index:
            skill_count = len(repo.cached_index["skills"])

        responses.append(RepoResponse(
            id=repo.id,
            name=repo.name,
            url=repo.url,
            description=repo.description,
            is_active=repo.is_active,
            last_synced_at=repo.last_synced_at,
            skill_count=skill_count,
            created_at=repo.created_at,
            updated_at=repo.updated_at,
        ))

    return responses


async def delete_repository(repo_id: UUID, session: AsyncSession) -> None:
    """Delete a repository (imported skills remain)."""
    result = await session.execute(
        select(SkillRepository).where(SkillRepository.id == repo_id)
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        raise ValueError(f"Repository {repo_id} not found")

    await session.delete(repo)
    await session.commit()

    logger.info("skill_repo_deleted", name=repo.name)


async def browse_skills(
    session: AsyncSession, query: str | None = None
) -> list[SkillBrowseItem]:
    """Browse skills from all active repositories, optionally filtered by keyword."""
    result = await session.execute(
        select(SkillRepository).where(
            SkillRepository.is_active == True,  # noqa: E712
        )
    )
    repos = result.scalars().all()

    items: list[SkillBrowseItem] = []
    for repo in repos:
        if not repo.cached_index or "skills" not in repo.cached_index:
            continue

        for skill_data in repo.cached_index["skills"]:
            try:
                skill = IndexSkillEntry.model_validate(skill_data)
            except Exception:
                continue

            # Filter by query if provided
            if query:
                q_lower = query.lower()
                if (
                    q_lower not in skill.name.lower()
                    and q_lower not in skill.description.lower()
                ):
                    continue

            items.append(SkillBrowseItem(
                name=skill.name,
                description=skill.description,
                version=skill.version,
                repository_name=repo.name,
                repository_id=repo.id,
                skill_url=skill.skill_url,
                metadata=skill.metadata,
            ))

    return items


async def import_skill_from_repo(
    repository_id: UUID,
    skill_name: str,
    user_id: UUID,
    session: AsyncSession,
) -> dict[str, Any]:
    """Import a skill from an external repository.

    1. Look up skill in repo's cached index
    2. Fetch SKILL.md from skill_url
    3. Parse via SkillImporter
    4. Security scan
    5. Create skill_definitions row with status='pending_review'

    Returns dict with skill_id and security_score.
    """
    from core.models.skill_definition import SkillDefinition

    # Find repo
    result = await session.execute(
        select(SkillRepository).where(SkillRepository.id == repository_id)
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        raise ValueError(f"Repository {repository_id} not found")

    # Find skill in cached index
    if not repo.cached_index or "skills" not in repo.cached_index:
        raise ValueError(f"Repository '{repo.name}' has no cached index")

    skill_entry = None
    for entry in repo.cached_index["skills"]:
        if entry.get("name") == skill_name:
            skill_entry = IndexSkillEntry.model_validate(entry)
            break

    if skill_entry is None:
        raise ValueError(f"Skill '{skill_name}' not found in repository '{repo.name}'")

    # Fetch and parse SKILL.md
    importer = SkillImporter()
    try:
        parsed = await importer.import_from_url(skill_entry.skill_url)
    except SkillImportError as exc:
        raise ValueError(f"Failed to import skill: {exc}")

    # Security scan
    scanner = SecurityScanner()
    report = scanner.scan(
        procedure_json=parsed.get("procedure_json"),
        source_url=skill_entry.skill_url,
        instruction_markdown=parsed.get("instruction_markdown"),
    )

    # Create skill definition with pending_review status
    skill = SkillDefinition(
        name=parsed["name"],
        display_name=parsed.get("display_name"),
        description=parsed.get("description"),
        version=parsed.get("version", "1.0.0"),
        skill_type=parsed.get("skill_type", "instructional"),
        slash_command=parsed.get("slash_command"),
        source_type="imported",
        instruction_markdown=parsed.get("instruction_markdown"),
        procedure_json=parsed.get("procedure_json"),
        input_schema=parsed.get("input_schema"),
        output_schema=parsed.get("output_schema"),
        security_score=report.score,
        security_report=report.factors,
        status="pending_review",
        is_active=False,
        created_by=user_id,
    )
    session.add(skill)
    await session.commit()
    await session.refresh(skill)

    logger.info(
        "skill_imported_from_repo",
        skill_name=skill.name,
        repo_name=repo.name,
        security_score=report.score,
        recommendation=report.recommendation,
    )

    return {
        "skill_id": str(skill.id),
        "name": skill.name,
        "security_score": report.score,
        "recommendation": report.recommendation,
        "status": "pending_review",
    }
```

**Step 2: Commit**

```bash
git add backend/skill_repos/service.py
git commit -m "feat(14-03): add skill repository service layer"
```

---

### Task 5: Create routes

**Files:**
- Create: `backend/skill_repos/routes.py`
- Modify: `backend/main.py` (register routes)

**Step 1: Write the routes**

```python
# backend/skill_repos/routes.py
"""
API routes for skill repository management.

Admin endpoints (registry:manage):
  GET    /api/admin/skill-repos              — list repositories
  POST   /api/admin/skill-repos              — add repository
  DELETE /api/admin/skill-repos/{id}         — remove repository
  POST   /api/admin/skill-repos/{id}/sync    — re-fetch index

User-facing endpoints (chat permission):
  GET    /api/skill-repos/browse             — browse/search skills
  POST   /api/skill-repos/import             — import skill from repo
"""
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.user import UserContext
from security.deps import get_current_user, get_user_db
from security.rbac import has_permission
from skill_repos.schemas import (
    RepoCreate,
    RepoResponse,
    SkillBrowseItem,
    SkillImportFromRepoRequest,
)
from skill_repos.service import (
    add_repository,
    browse_skills,
    delete_repository,
    import_skill_from_repo,
    list_repositories,
    sync_repository,
)

logger = structlog.get_logger(__name__)

# ── Admin routes ─────────────────────────────────────────────────────────

admin_router = APIRouter(prefix="/api/admin/skill-repos", tags=["admin-skill-repos"])


async def _require_registry_manager(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    if not await has_permission(user, "registry:manage", session):
        raise HTTPException(status_code=403, detail="Registry manage permission required")
    return user


@admin_router.get("")
async def list_repos(
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> list[RepoResponse]:
    return await list_repositories(session)


@admin_router.post("", status_code=201)
async def create_repo(
    body: RepoCreate,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> RepoResponse:
    try:
        repo = await add_repository(body.url, session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Build response with skill count
    skill_count = 0
    if repo.cached_index and "skills" in repo.cached_index:
        skill_count = len(repo.cached_index["skills"])

    return RepoResponse(
        id=repo.id,
        name=repo.name,
        url=repo.url,
        description=repo.description,
        is_active=repo.is_active,
        last_synced_at=repo.last_synced_at,
        skill_count=skill_count,
        created_at=repo.created_at,
        updated_at=repo.updated_at,
    )


@admin_router.delete("/{repo_id}", status_code=204)
async def remove_repo(
    repo_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_repository(repo_id, session)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@admin_router.post("/{repo_id}/sync")
async def sync_repo(
    repo_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> RepoResponse:
    try:
        repo = await sync_repository(repo_id, session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    skill_count = 0
    if repo.cached_index and "skills" in repo.cached_index:
        skill_count = len(repo.cached_index["skills"])

    return RepoResponse(
        id=repo.id,
        name=repo.name,
        url=repo.url,
        description=repo.description,
        is_active=repo.is_active,
        last_synced_at=repo.last_synced_at,
        skill_count=skill_count,
        created_at=repo.created_at,
        updated_at=repo.updated_at,
    )


# ── User-facing routes ──────────────────────────────────────────────────

user_router = APIRouter(prefix="/api/skill-repos", tags=["skill-repos"])


async def _require_chat(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> UserContext:
    if not await has_permission(user, "chat", session):
        raise HTTPException(status_code=403, detail="Chat permission required")
    return user


@user_router.get("/browse")
async def browse_repo_skills(
    q: str | None = Query(None, description="Search keyword"),
    user: UserContext = Depends(_require_chat),
    session: AsyncSession = Depends(get_user_db),
) -> list[SkillBrowseItem]:
    return await browse_skills(session, query=q)


@user_router.post("/import")
async def import_from_repo(
    body: SkillImportFromRepoRequest,
    user: UserContext = Depends(_require_chat),
    session: AsyncSession = Depends(get_user_db),
) -> dict:
    try:
        result = await import_skill_from_repo(
            repository_id=body.repository_id,
            skill_name=body.skill_name,
            user_id=user["user_id"],
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return result
```

**Step 2: Register routes in main.py**

In `backend/main.py`, add the import after the openapi_bridge import:

```python
from skill_repos.routes import admin_router as skill_repos_admin_router, user_router as skill_repos_user_router
```

Add after the openapi_bridge router include:

```python
    # Skill repository admin — /api/admin/skill-repos (registry:manage)
    app.include_router(skill_repos_admin_router)

    # Skill repository browsing — /api/skill-repos/browse, /api/skill-repos/import (chat)
    app.include_router(skill_repos_user_router)
```

**Step 3: Commit**

```bash
git add backend/skill_repos/routes.py backend/main.py
git commit -m "feat(14-03): add skill repository routes and register in main.py"
```

---

### Task 6: Write tests

**Files:**
- Create: `backend/tests/test_skill_repos.py`

**Step 1: Write service + route tests**

```python
# backend/tests/test_skill_repos.py
"""Tests for skill repository management."""
import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db import Base, get_db
from core.models.agent_definition import AgentDefinition  # noqa: F401
from core.models.artifact_permission import ArtifactPermission  # noqa: F401
from core.models.mcp_server import McpServer  # noqa: F401
from core.models.role_permission import RolePermission  # noqa: F401
from core.models.skill_definition import SkillDefinition  # noqa: F401
from core.models.tool_definition import ToolDefinition  # noqa: F401
from core.models.user_artifact_permission import UserArtifactPermission  # noqa: F401
from core.models.user import UserContext
from main import app
from security.deps import get_current_user
from skill_repos.models import SkillRepository  # noqa: F401
from skill_repos.schemas import RepositoryIndex, IndexRepository, IndexSkillEntry


SAMPLE_INDEX = RepositoryIndex(
    repository=IndexRepository(
        name="test-repo",
        description="Test skill repository",
        url="https://skills.example.com",
    ),
    skills=[
        IndexSkillEntry(
            name="pdf-processing",
            description="Extract text from PDFs",
            version="1.0",
            skill_url="https://skills.example.com/skills/pdf-processing/SKILL.md",
            directory_url="https://skills.example.com/skills/pdf-processing/",
            metadata={"author": "test"},
        ),
        IndexSkillEntry(
            name="data-analysis",
            description="Analyze CSV data files",
            version="1.0",
            skill_url="https://skills.example.com/skills/data-analysis/SKILL.md",
        ),
    ],
)


def make_admin_ctx() -> UserContext:
    return UserContext(
        user_id=uuid4(), email="admin@blitz.local",
        username="admin", roles=["it-admin"], groups=["/it"],
    )


def make_user_ctx() -> UserContext:
    return UserContext(
        user_id=uuid4(), email="user@blitz.local",
        username="user", roles=["employee"], groups=[],
    )


@pytest.fixture
def sqlite_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_setup())
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield factory
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def admin_client(sqlite_db) -> TestClient:
    app.dependency_overrides[get_current_user] = make_admin_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def user_client(sqlite_db) -> TestClient:
    app.dependency_overrides[get_current_user] = make_user_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


# ── Admin endpoint tests ────────────────────────────────────────────────

@patch("skill_repos.service.fetch_repo_index")
def test_add_repo(mock_fetch, admin_client):
    """Admin can add a repository."""
    mock_fetch.return_value = SAMPLE_INDEX
    resp = admin_client.post("/api/admin/skill-repos", json={"url": "https://skills.example.com"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-repo"
    assert data["skill_count"] == 2


@patch("skill_repos.service.fetch_repo_index")
def test_add_duplicate_repo(mock_fetch, admin_client):
    """Cannot add a repo with the same name twice."""
    mock_fetch.return_value = SAMPLE_INDEX
    admin_client.post("/api/admin/skill-repos", json={"url": "https://skills.example.com"})
    resp = admin_client.post("/api/admin/skill-repos", json={"url": "https://skills.example.com"})
    assert resp.status_code == 422
    assert "already registered" in resp.json()["detail"]


@patch("skill_repos.service.fetch_repo_index")
def test_list_repos(mock_fetch, admin_client):
    """Admin can list repos."""
    mock_fetch.return_value = SAMPLE_INDEX
    admin_client.post("/api/admin/skill-repos", json={"url": "https://skills.example.com"})
    resp = admin_client.get("/api/admin/skill-repos")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@patch("skill_repos.service.fetch_repo_index")
def test_delete_repo(mock_fetch, admin_client):
    """Admin can delete a repo."""
    mock_fetch.return_value = SAMPLE_INDEX
    create_resp = admin_client.post("/api/admin/skill-repos", json={"url": "https://skills.example.com"})
    repo_id = create_resp.json()["id"]
    resp = admin_client.delete(f"/api/admin/skill-repos/{repo_id}")
    assert resp.status_code == 204


def test_add_repo_requires_admin(user_client):
    """Employee cannot add repos."""
    resp = user_client.post("/api/admin/skill-repos", json={"url": "https://example.com"})
    assert resp.status_code == 403


# ── User-facing browse/import tests ────────────────────────────────────

@patch("skill_repos.service.fetch_repo_index")
def test_browse_skills(mock_fetch, admin_client, user_client):
    """User can browse skills from all active repos."""
    mock_fetch.return_value = SAMPLE_INDEX
    admin_client.post("/api/admin/skill-repos", json={"url": "https://skills.example.com"})

    resp = user_client.get("/api/skill-repos/browse")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2


@patch("skill_repos.service.fetch_repo_index")
def test_browse_with_search(mock_fetch, admin_client, user_client):
    """Browse with q= filters by keyword."""
    mock_fetch.return_value = SAMPLE_INDEX
    admin_client.post("/api/admin/skill-repos", json={"url": "https://skills.example.com"})

    resp = user_client.get("/api/skill-repos/browse?q=pdf")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["name"] == "pdf-processing"
```

**Step 2: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_skill_repos.py -v
```

Expected: 7 PASSED

**Step 3: Commit**

```bash
git add backend/tests/test_skill_repos.py
git commit -m "test(14-03): add skill repository service and route tests"
```

---

### Task 7: Add frontend admin "Skill Repositories" tab and proxy routes

**Files:**
- Create: `frontend/src/app/admin/skill-repos/page.tsx`
- Create: `frontend/src/app/api/skill-repos/browse/route.ts`
- Create: `frontend/src/app/api/skill-repos/import/route.ts`
- Modify: `frontend/src/app/admin/layout.tsx` (add tab)

The page should:
1. List registered repos (name, URL, skill count, last synced) with "Sync" and "Remove" buttons
2. "Add Repository" dialog with URL input
3. Below the repo list, show a "Skill Store" browse section with search box
4. Each browse result shows name, description, version, source repo
5. "Import" button per skill — triggers import, shows status

The catch-all admin proxy at `frontend/src/app/api/admin/[...path]/route.ts` handles admin skill-repo endpoints. User-facing browse/import need dedicated proxy routes.

**Step 1: Create user-facing proxy routes**

Follow the pattern in existing Next.js API routes — inject Bearer token from next-auth session, forward to backend.

**Step 2: Create the admin page**

Follow the Users page pattern (`"use client"`, direct `fetch()`, `useState`).

**Step 3: Add tab to layout.tsx**

```typescript
{ label: "Skill Repos", href: "/admin/skill-repos" },
```

**Step 4: Run frontend build**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build
```

Expected: 0 errors

**Step 5: Commit**

```bash
git add frontend/src/app/admin/skill-repos/ frontend/src/app/api/skill-repos/ frontend/src/app/admin/layout.tsx
git commit -m "feat(14-03): add Skill Repositories admin tab and Skill Store browse UI"
```

---

### Task 8: Run full test suite and verify

**Step 1: Run backend tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: baseline + new tests pass

**Step 2: Run frontend build**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build
```

Expected: 0 errors
