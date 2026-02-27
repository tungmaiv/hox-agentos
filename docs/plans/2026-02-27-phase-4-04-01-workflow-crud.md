# Phase 4 — Plan 04-01: Workflow CRUD + DB Migration + Canvas Shell

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create DB tables for workflows, a full CRUD API, webhook endpoint, and the frontend workflow list + canvas editor shell (no execution yet).

**Architecture:** Three new PostgreSQL tables (workflows, workflow_runs, workflow_triggers) via Alembic migration. FastAPI routes follow existing patterns (security/deps.py, get_db). Frontend uses Next.js Server Components for the list page and a Client Component shell for the canvas editor. React Flow is installed but rendering is minimal — execution wired in 04-03.

**Tech Stack:** SQLAlchemy async ORM, Alembic, FastAPI, Pydantic v2, Next.js 15 App Router, @xyflow/react, pnpm.

---

## Task 1: SQLAlchemy ORM Models

**Files:**
- Create: `backend/core/models/workflow.py`
- Modify: `backend/core/models/__init__.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_workflow_models.py
from core.models.workflow import Workflow, WorkflowRun, WorkflowTrigger

def test_workflow_tablename():
    assert Workflow.__tablename__ == "workflows"

def test_workflow_run_tablename():
    assert WorkflowRun.__tablename__ == "workflow_runs"

def test_workflow_trigger_tablename():
    assert WorkflowTrigger.__tablename__ == "workflow_triggers"
```

**Step 2: Run to verify it fails**

```bash
cd backend && .venv/bin/pytest tests/test_workflow_models.py -v
```
Expected: `ImportError: cannot import name 'Workflow'`

**Step 3: Create `backend/core/models/workflow.py`**

```python
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    template_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False, index=True
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # pending | running | paused_hitl | completed | failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    checkpoint_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class WorkflowTrigger(Base):
    __tablename__ = "workflow_triggers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False, index=True
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)  # cron | webhook
    cron_expression: Mapped[str | None] = mapped_column(String(100), nullable=True)
    webhook_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

**Step 4: Register models in `backend/core/models/__init__.py`**

Find the existing import block and add:
```python
from core.models.workflow import Workflow, WorkflowRun, WorkflowTrigger  # noqa: F401
```

**Step 5: Run test to verify it passes**

```bash
cd backend && .venv/bin/pytest tests/test_workflow_models.py -v
```
Expected: 3 tests PASS

**Step 6: Commit**

```bash
git add backend/core/models/workflow.py backend/core/models/__init__.py backend/tests/test_workflow_models.py
git commit -m "feat(04-01): add Workflow, WorkflowRun, WorkflowTrigger ORM models"
```

---

## Task 2: Alembic Migration

**Files:**
- Create: `backend/alembic/versions/010_phase4_workflows.py` (autogenerated)

**Step 1: Generate migration**

```bash
cd backend && .venv/bin/alembic revision --autogenerate -m "phase4_workflows"
```

This creates a new file in `backend/alembic/versions/`. Open it and verify `upgrade()` contains `create_table` calls for `workflows`, `workflow_runs`, `workflow_triggers`.

**Step 2: Run the migration**

```bash
just migrate
```
Expected output contains: `Running upgrade ... -> <hash>, phase4_workflows`

**Step 3: Verify tables exist**

```bash
just db
```
In the psql shell:
```sql
\dt workflows
\dt workflow_runs
\dt workflow_triggers
\q
```
Expected: All three tables listed.

**Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(04-01): add Alembic migration for workflow tables"
```

---

## Task 3: Pydantic Schemas

**Files:**
- Create: `backend/core/schemas/workflow.py`
- Test: `backend/tests/test_workflow_schemas.py`

**Step 1: Write failing tests**

```python
# backend/tests/test_workflow_schemas.py
import pytest
from core.schemas.workflow import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowListItem,
    WorkflowRunResponse,
    WorkflowTriggerCreate,
    WorkflowTriggerResponse,
    PendingHitlResponse,
)


def test_workflow_create_valid():
    data = WorkflowCreate(
        name="Test",
        definition_json={"schema_version": "1.0", "nodes": [], "edges": []},
    )
    assert data.name == "Test"


def test_workflow_create_rejects_missing_schema_version():
    with pytest.raises(Exception):
        WorkflowCreate(name="Bad", definition_json={"nodes": [], "edges": []})


def test_workflow_create_rejects_wrong_schema_version():
    with pytest.raises(Exception):
        WorkflowCreate(
            name="Bad",
            definition_json={"schema_version": "2.0", "nodes": [], "edges": []},
        )


def test_trigger_create_cron():
    t = WorkflowTriggerCreate(trigger_type="cron", cron_expression="0 8 * * 1-5")
    assert t.cron_expression == "0 8 * * 1-5"


def test_trigger_create_rejects_unknown_type():
    with pytest.raises(Exception):
        WorkflowTriggerCreate(trigger_type="email")


def test_pending_hitl_response():
    r = PendingHitlResponse(count=3)
    assert r.count == 3
```

**Step 2: Run to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_workflow_schemas.py -v
```
Expected: `ImportError`

**Step 3: Create `backend/core/schemas/workflow.py`**

```python
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    definition_json: dict[str, Any]

    @field_validator("definition_json")
    @classmethod
    def require_schema_version(cls, v: dict[str, Any]) -> dict[str, Any]:
        if v.get("schema_version") != "1.0":
            raise ValueError("definition_json must have schema_version: '1.0'")
        return v


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    definition_json: dict[str, Any] | None = None

    @field_validator("definition_json")
    @classmethod
    def require_schema_version(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is not None and v.get("schema_version") != "1.0":
            raise ValueError("definition_json must have schema_version: '1.0'")
        return v


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    owner_user_id: uuid.UUID | None
    name: str
    description: str | None
    definition_json: dict[str, Any]
    is_template: bool
    template_source_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowListItem(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_template: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowRunResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    owner_user_id: uuid.UUID
    trigger_type: str
    status: str
    checkpoint_id: str | None
    started_at: datetime
    completed_at: datetime | None
    result_json: dict[str, Any] | None

    model_config = {"from_attributes": True}


class PendingHitlResponse(BaseModel):
    count: int


class WorkflowTriggerCreate(BaseModel):
    trigger_type: str  # cron | webhook
    cron_expression: str | None = None
    is_active: bool = True

    @field_validator("trigger_type")
    @classmethod
    def validate_trigger_type(cls, v: str) -> str:
        if v not in ("cron", "webhook"):
            raise ValueError("trigger_type must be 'cron' or 'webhook'")
        return v


class WorkflowTriggerResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    trigger_type: str
    cron_expression: str | None
    webhook_secret: str | None
    is_active: bool

    model_config = {"from_attributes": True}
```

**Step 4: Run tests**

```bash
cd backend && .venv/bin/pytest tests/test_workflow_schemas.py -v
```
Expected: 6 tests PASS

**Step 5: Commit**

```bash
git add backend/core/schemas/workflow.py backend/tests/test_workflow_schemas.py
git commit -m "feat(04-01): add Pydantic schemas for workflow CRUD"
```

---

## Task 4: Workflow CRUD API Routes

**Files:**
- Create: `backend/api/routes/workflows.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_workflows_api.py`

**Step 1: Write failing tests**

```python
# backend/tests/test_workflows_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
from uuid import uuid4

MOCK_USER = {
    "user_id": str(uuid4()),
    "email": "test@blitz.local",
    "username": "testuser",
    "roles": ["employee"],
    "groups": [],
}


@pytest.fixture
def mock_auth(monkeypatch):
    monkeypatch.setattr("security.deps.get_current_user", lambda: MOCK_USER)


@pytest.mark.asyncio
async def test_list_workflows_returns_empty_list():
    from main import app
    with patch("security.deps.get_current_user", return_value=MOCK_USER):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/workflows",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_create_workflow_returns_201():
    from main import app
    with patch("security.deps.get_current_user", return_value=MOCK_USER):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/workflows",
                json={
                    "name": "My Workflow",
                    "definition_json": {
                        "schema_version": "1.0",
                        "nodes": [],
                        "edges": [],
                    },
                },
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 201
    assert response.json()["name"] == "My Workflow"
    assert response.json()["is_template"] is False


@pytest.mark.asyncio
async def test_create_workflow_rejects_bad_schema_version():
    from main import app
    with patch("security.deps.get_current_user", return_value=MOCK_USER):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/workflows",
                json={"name": "Bad", "definition_json": {"nodes": [], "edges": []}},
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_workflow_not_found():
    from main import app
    with patch("security.deps.get_current_user", return_value=MOCK_USER):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/workflows/{uuid4()}",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_workflow_not_found():
    from main import app
    with patch("security.deps.get_current_user", return_value=MOCK_USER):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.delete(
                f"/api/workflows/{uuid4()}",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 404
```

**Step 2: Run to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_workflows_api.py -v
```
Expected: All fail with 404 (route not registered)

**Step 3: Create `backend/api/routes/workflows.py`**

```python
import secrets
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.workflow import Workflow, WorkflowRun, WorkflowTrigger
from core.models.user import UserContext
from core.schemas.workflow import (
    PendingHitlResponse,
    WorkflowCreate,
    WorkflowListItem,
    WorkflowResponse,
    WorkflowRunResponse,
    WorkflowTriggerCreate,
    WorkflowTriggerResponse,
    WorkflowUpdate,
)
from security.deps import get_current_user

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/workflows", tags=["workflows"])


# ── Workflow CRUD ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[WorkflowListItem])
async def list_workflows(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[WorkflowListItem]:
    result = await session.execute(
        select(Workflow)
        .where(Workflow.owner_user_id == uuid.UUID(user["user_id"]))
        .where(Workflow.is_template == False)  # noqa: E712
        .order_by(Workflow.updated_at.desc())
    )
    return [WorkflowListItem.model_validate(w) for w in result.scalars().all()]


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    body: WorkflowCreate,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    workflow = Workflow(
        owner_user_id=uuid.UUID(user["user_id"]),
        name=body.name,
        description=body.description,
        definition_json=body.definition_json,
    )
    session.add(workflow)
    await session.commit()
    await session.refresh(workflow)
    logger.info("workflow_created", workflow_id=str(workflow.id), user_id=user["user_id"])
    return WorkflowResponse.model_validate(workflow)


@router.get("/runs/pending-hitl", response_model=PendingHitlResponse)
async def pending_hitl_count(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PendingHitlResponse:
    result = await session.execute(
        select(WorkflowRun)
        .where(WorkflowRun.owner_user_id == uuid.UUID(user["user_id"]))
        .where(WorkflowRun.status == "paused_hitl")
    )
    return PendingHitlResponse(count=len(result.scalars().all()))


@router.get("/templates", response_model=list[WorkflowResponse])
async def list_templates(
    session: AsyncSession = Depends(get_db),
) -> list[WorkflowResponse]:
    result = await session.execute(
        select(Workflow).where(Workflow.is_template == True)  # noqa: E712
    )
    return [WorkflowResponse.model_validate(t) for t in result.scalars().all()]


@router.post(
    "/templates/{template_id}/copy",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def copy_template(
    template_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    result = await session.execute(
        select(Workflow)
        .where(Workflow.id == template_id)
        .where(Workflow.is_template == True)  # noqa: E712
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    copy = Workflow(
        owner_user_id=uuid.UUID(user["user_id"]),
        name=template.name,
        description=template.description,
        definition_json=template.definition_json,
        is_template=False,
        template_source_id=template.id,
    )
    session.add(copy)
    await session.commit()
    await session.refresh(copy)
    return WorkflowResponse.model_validate(copy)


@router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
async def get_run(
    run_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkflowRunResponse:
    run = await _get_user_run(run_id, uuid.UUID(user["user_id"]), session)
    return WorkflowRunResponse.model_validate(run)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    workflow = await _get_user_workflow(workflow_id, uuid.UUID(user["user_id"]), session)
    return WorkflowResponse.model_validate(workflow)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID,
    body: WorkflowUpdate,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    workflow = await _get_user_workflow(workflow_id, uuid.UUID(user["user_id"]), session)
    if body.name is not None:
        workflow.name = body.name
    if body.description is not None:
        workflow.description = body.description
    if body.definition_json is not None:
        workflow.definition_json = body.definition_json
    await session.commit()
    await session.refresh(workflow)
    return WorkflowResponse.model_validate(workflow)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    workflow = await _get_user_workflow(workflow_id, uuid.UUID(user["user_id"]), session)
    await session.delete(workflow)
    await session.commit()


# ── Triggers ──────────────────────────────────────────────────────────────────

@router.get("/{workflow_id}/triggers", response_model=list[WorkflowTriggerResponse])
async def list_triggers(
    workflow_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[WorkflowTriggerResponse]:
    await _get_user_workflow(workflow_id, uuid.UUID(user["user_id"]), session)
    result = await session.execute(
        select(WorkflowTrigger).where(WorkflowTrigger.workflow_id == workflow_id)
    )
    return [WorkflowTriggerResponse.model_validate(t) for t in result.scalars().all()]


@router.post(
    "/{workflow_id}/triggers",
    response_model=WorkflowTriggerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_trigger(
    workflow_id: uuid.UUID,
    body: WorkflowTriggerCreate,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkflowTriggerResponse:
    await _get_user_workflow(workflow_id, uuid.UUID(user["user_id"]), session)
    webhook_secret = secrets.token_urlsafe(32) if body.trigger_type == "webhook" else None
    trigger = WorkflowTrigger(
        workflow_id=workflow_id,
        owner_user_id=uuid.UUID(user["user_id"]),
        trigger_type=body.trigger_type,
        cron_expression=body.cron_expression,
        webhook_secret=webhook_secret,
        is_active=body.is_active,
    )
    session.add(trigger)
    await session.commit()
    await session.refresh(trigger)
    return WorkflowTriggerResponse.model_validate(trigger)


@router.delete("/{workflow_id}/triggers/{trigger_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trigger(
    workflow_id: uuid.UUID,
    trigger_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    await _get_user_workflow(workflow_id, uuid.UUID(user["user_id"]), session)
    result = await session.execute(
        select(WorkflowTrigger)
        .where(WorkflowTrigger.id == trigger_id)
        .where(WorkflowTrigger.workflow_id == workflow_id)
    )
    trigger = result.scalar_one_or_none()
    if trigger is None:
        raise HTTPException(status_code=404, detail="Trigger not found")
    await session.delete(trigger)
    await session.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_user_workflow(
    workflow_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> Workflow:
    result = await session.execute(
        select(Workflow)
        .where(Workflow.id == workflow_id)
        .where(Workflow.owner_user_id == user_id)
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


async def _get_user_run(
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> WorkflowRun:
    result = await session.execute(
        select(WorkflowRun)
        .where(WorkflowRun.id == run_id)
        .where(WorkflowRun.owner_user_id == user_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
```

**Step 4: Register router in `backend/main.py`**

Find where other routers are registered (look for `app.include_router`) and add:
```python
from api.routes.workflows import router as workflows_router
# ...
app.include_router(workflows_router)
```

**Step 5: Run tests**

```bash
cd backend && .venv/bin/pytest tests/test_workflows_api.py -v
```
Expected: 5 tests PASS

**Step 6: Commit**

```bash
git add backend/api/routes/workflows.py backend/main.py backend/tests/test_workflows_api.py
git commit -m "feat(04-01): add workflow CRUD API routes"
```

---

## Task 5: Webhook Endpoint

**Files:**
- Create: `backend/api/routes/webhooks.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_webhooks_api.py`

**Step 1: Write failing tests**

```python
# backend/tests/test_webhooks_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from uuid import uuid4


@pytest.mark.asyncio
async def test_webhook_with_wrong_secret_returns_401():
    from main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/webhooks/{uuid4()}",
            headers={"X-Webhook-Secret": "wrong"},
            json={},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_missing_secret_header_returns_422():
    from main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/webhooks/{uuid4()}",
            json={},
        )
    # Missing required header → 422 Unprocessable Entity
    assert response.status_code == 422
```

**Step 2: Run to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_webhooks_api.py -v
```
Expected: Both fail (route not found)

**Step 3: Create `backend/api/routes/webhooks.py`**

```python
import uuid

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.workflow import WorkflowRun, WorkflowTrigger

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/{webhook_id}", status_code=202)
async def fire_webhook(
    webhook_id: uuid.UUID,
    x_webhook_secret: str = Header(..., alias="X-Webhook-Secret"),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    result = await session.execute(
        select(WorkflowTrigger)
        .where(WorkflowTrigger.id == webhook_id)
        .where(WorkflowTrigger.trigger_type == "webhook")
        .where(WorkflowTrigger.is_active == True)  # noqa: E712
    )
    trigger = result.scalar_one_or_none()

    # Reject if not found OR secret mismatch (same 401 — no leaking existence)
    if trigger is None or trigger.webhook_secret != x_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook credentials")

    run = WorkflowRun(
        workflow_id=trigger.workflow_id,
        owner_user_id=trigger.owner_user_id,
        trigger_type="webhook",
        status="pending",
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    logger.info("webhook_fired", trigger_id=str(webhook_id), run_id=str(run.id))
    # Execution is wired in plan 04-03
    return {"run_id": str(run.id), "status": "accepted"}
```

**Step 4: Register in `backend/main.py`**

```python
from api.routes.webhooks import router as webhooks_router
# ...
app.include_router(webhooks_router)
```

**Step 5: Run tests**

```bash
cd backend && .venv/bin/pytest tests/test_webhooks_api.py -v
```
Expected: 2 tests PASS

**Step 6: Commit**

```bash
git add backend/api/routes/webhooks.py backend/main.py backend/tests/test_webhooks_api.py
git commit -m "feat(04-01): add webhook trigger endpoint"
```

---

## Task 6: Frontend — API Proxies

**Files:** Create all under `frontend/src/app/api/workflows/`

**Step 1: Install React Flow**

```bash
cd frontend && pnpm add @xyflow/react
```

**Step 2: Create proxy routes**

`frontend/src/app/api/workflows/route.ts`:
```typescript
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET() {
  const session = await auth();
  if (!session?.accessToken) return NextResponse.json([], { status: 401 });
  const res = await fetch(`${BACKEND}/api/workflows`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
  });
  return NextResponse.json(await res.json(), { status: res.status });
}

export async function POST(req: NextRequest) {
  const session = await auth();
  if (!session?.accessToken) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const res = await fetch(`${BACKEND}/api/workflows`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${session.accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(await req.json()),
  });
  return NextResponse.json(await res.json(), { status: res.status });
}
```

`frontend/src/app/api/workflows/[id]/route.ts`:
```typescript
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET(_: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session?.accessToken) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const res = await fetch(`${BACKEND}/api/workflows/${params.id}`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
  });
  return NextResponse.json(await res.json(), { status: res.status });
}

export async function PUT(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session?.accessToken) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const res = await fetch(`${BACKEND}/api/workflows/${params.id}`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${session.accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(await req.json()),
  });
  return NextResponse.json(await res.json(), { status: res.status });
}

export async function DELETE(_: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session?.accessToken) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const res = await fetch(`${BACKEND}/api/workflows/${params.id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${session.accessToken}` },
  });
  return new NextResponse(null, { status: res.status });
}
```

`frontend/src/app/api/workflows/[id]/run/route.ts`:
```typescript
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function POST(_: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session?.accessToken) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const res = await fetch(`${BACKEND}/api/workflows/${params.id}/run`, {
    method: "POST",
    headers: { Authorization: `Bearer ${session.accessToken}` },
  });
  return NextResponse.json(await res.json(), { status: res.status });
}
```

`frontend/src/app/api/workflows/runs/[run_id]/events/route.ts`:
```typescript
import { auth } from "@/auth";
import { NextRequest } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET(_: NextRequest, { params }: { params: { run_id: string } }) {
  const session = await auth();
  if (!session?.accessToken) return new Response("Unauthorized", { status: 401 });
  const backendRes = await fetch(
    `${BACKEND}/api/workflows/runs/${params.run_id}/events`,
    {
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
        Accept: "text/event-stream",
      },
    }
  );
  return new Response(backendRes.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
```

`frontend/src/app/api/workflows/runs/[run_id]/approve/route.ts`:
```typescript
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function POST(_: NextRequest, { params }: { params: { run_id: string } }) {
  const session = await auth();
  if (!session?.accessToken) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const res = await fetch(`${BACKEND}/api/workflows/runs/${params.run_id}/approve`, {
    method: "POST",
    headers: { Authorization: `Bearer ${session.accessToken}` },
  });
  return NextResponse.json(await res.json(), { status: res.status });
}
```

`frontend/src/app/api/workflows/runs/[run_id]/reject/route.ts` — identical to approve, substitute `reject`.

`frontend/src/app/api/workflows/runs/pending-hitl/route.ts`:
```typescript
import { auth } from "@/auth";
import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET() {
  const session = await auth();
  if (!session?.accessToken) return NextResponse.json({ count: 0 });
  const res = await fetch(`${BACKEND}/api/workflows/runs/pending-hitl`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
  });
  return NextResponse.json(await res.json(), { status: res.status });
}
```

`frontend/src/app/api/workflows/templates/route.ts`:
```typescript
import { auth } from "@/auth";
import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET() {
  const session = await auth();
  if (!session?.accessToken) return NextResponse.json([], { status: 401 });
  const res = await fetch(`${BACKEND}/api/workflows/templates`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
  });
  return NextResponse.json(await res.json(), { status: res.status });
}
```

`frontend/src/app/api/workflows/templates/[id]/copy/route.ts`:
```typescript
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function POST(_: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session?.accessToken) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const res = await fetch(`${BACKEND}/api/workflows/templates/${params.id}/copy`, {
    method: "POST",
    headers: { Authorization: `Bearer ${session.accessToken}` },
  });
  return NextResponse.json(await res.json(), { status: res.status });
}
```

**Step 3: Commit**

```bash
git add frontend/src/app/api/workflows/
git commit -m "feat(04-01): add frontend API proxy routes for workflows"
```

---

## Task 7: Frontend — Workflow List Page + Canvas Shell

**Files:**
- Create: `frontend/src/app/workflows/page.tsx`
- Create: `frontend/src/app/workflows/[id]/page.tsx`
- Create: `frontend/src/app/workflows/[id]/canvas-editor.tsx`

**Step 1: Create workflow list page**

`frontend/src/app/workflows/page.tsx`:
```typescript
import { auth } from "@/auth";
import { redirect } from "next/navigation";
import Link from "next/link";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface WorkflowListItem {
  id: string;
  name: string;
  description: string | null;
  updated_at: string;
}

interface WorkflowTemplate {
  id: string;
  name: string;
  description: string | null;
}

async function fetchJson<T>(url: string, token: string): Promise<T> {
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) return [] as unknown as T;
  return res.json();
}

export default async function WorkflowsPage() {
  const session = await auth();
  if (!session?.accessToken) redirect("/login");

  const [workflows, templates] = await Promise.all([
    fetchJson<WorkflowListItem[]>(`${BACKEND}/api/workflows`, session.accessToken),
    fetchJson<WorkflowTemplate[]>(`${BACKEND}/api/workflows/templates`, session.accessToken),
  ]);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Workflows</h1>
        <Link
          href="/workflows/new"
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
        >
          + New Workflow
        </Link>
      </div>

      {templates.length > 0 && (
        <section className="mb-8">
          <h2 className="text-lg font-semibold mb-3 text-gray-700">Start from a template</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {templates.map((t) => (
              <div key={t.id} className="border rounded-lg p-4 bg-gray-50">
                <h3 className="font-medium">{t.name}</h3>
                {t.description && (
                  <p className="text-sm text-gray-500 mt-1">{t.description}</p>
                )}
                <form action={`/api/workflows/templates/${t.id}/copy`} method="POST" className="mt-3">
                  <button
                    type="submit"
                    className="text-sm px-3 py-1 bg-white border rounded hover:bg-gray-100"
                  >
                    Use template →
                  </button>
                </form>
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="text-lg font-semibold mb-3 text-gray-700">Your workflows</h2>
        {workflows.length === 0 ? (
          <p className="text-gray-400 text-sm">No workflows yet. Start from a template or create a new one.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {workflows.map((w) => (
              <Link
                key={w.id}
                href={`/workflows/${w.id}`}
                className="border rounded-lg p-4 hover:border-blue-400 transition-colors"
              >
                <h3 className="font-medium">{w.name}</h3>
                {w.description && (
                  <p className="text-sm text-gray-500 mt-1">{w.description}</p>
                )}
                <p className="text-xs text-gray-400 mt-2">
                  Updated {new Date(w.updated_at).toLocaleDateString()}
                </p>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
```

**Step 2: Create canvas editor shell**

`frontend/src/app/workflows/[id]/page.tsx` (Server Component):
```typescript
import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { CanvasEditor } from "./canvas-editor";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default async function WorkflowEditorPage({
  params,
}: {
  params: { id: string };
}) {
  const session = await auth();
  if (!session?.accessToken) redirect("/login");

  const res = await fetch(`${BACKEND}/api/workflows/${params.id}`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
    cache: "no-store",
  });
  if (!res.ok) redirect("/workflows");

  const workflow = await res.json();
  return <CanvasEditor workflow={workflow} />;
}
```

`frontend/src/app/workflows/[id]/canvas-editor.tsx` (Client Component — canvas wired in 04-03):
```typescript
"use client";

interface WorkflowDefinition {
  schema_version: "1.0";
  nodes: unknown[];
  edges: unknown[];
}

interface Workflow {
  id: string;
  name: string;
  definition_json: WorkflowDefinition;
}

export function CanvasEditor({ workflow }: { workflow: Workflow }) {
  return (
    <div className="flex flex-col h-screen">
      <div className="flex items-center justify-between px-4 py-2 border-b">
        <h1 className="font-semibold">{workflow.name}</h1>
        <span className="text-xs text-gray-400">Canvas coming in 04-03</span>
      </div>
      <div className="flex-1 flex items-center justify-center text-gray-300 text-sm">
        {workflow.definition_json.nodes.length} nodes · {workflow.definition_json.edges.length} edges
      </div>
    </div>
  );
}
```

**Step 3: Build check**

```bash
cd frontend && pnpm run build 2>&1 | tail -20
```
Expected: Build succeeds (0 errors).

**Step 4: Commit**

```bash
git add frontend/src/app/workflows/
git commit -m "feat(04-01): add workflow list page and canvas editor shell"
```

---

## Task 8: Full Test Run

**Step 1: Run all backend tests**

```bash
cd backend && .venv/bin/pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: All existing tests pass + new tests pass, 0 failures.

**Step 2: Frontend build**

```bash
cd frontend && pnpm run build 2>&1 | tail -10
```
Expected: ✓ Compiled successfully

**Step 3: Commit (if any fixes were needed)**

```bash
git add -A
git status  # verify only expected files
git commit -m "fix(04-01): address any issues found during full test run"
```

---

**Plan 04-01 complete.** Delivers:
- DB tables: `workflows`, `workflow_runs`, `workflow_triggers`
- Full CRUD API + webhook endpoint + trigger management
- Frontend workflow list page + canvas shell
- 13 new tests passing

**Next: Plan 04-02** — Compiler (WorkflowState + node handlers + canvas-to-StateGraph).
