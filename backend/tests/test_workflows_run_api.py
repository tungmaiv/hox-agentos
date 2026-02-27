"""
Tests for workflow run + approve/reject API endpoints.

Security pattern: dependency_overrides for get_current_user + SQLite for get_db.
Uses TestClient (sync) following existing codebase patterns.

Verifies:
- Run non-existent workflow returns 404
- Approve non-existent run returns 404
- Reject non-existent run returns 404
- Approve run with wrong status returns 409
"""
import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import patch, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.db import Base, get_db
from core.models.user import UserContext
from main import app
from security.deps import get_current_user


def make_user_ctx() -> UserContext:
    return UserContext(
        user_id=uuid4(),
        email="test@blitz.local",
        username="testuser",
        roles=["employee"],
        groups=[],
    )


@pytest.fixture
def sqlite_run_db():
    """SQLite in-memory DB with workflow tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_setup())

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    loop.run_until_complete(engine.dispose())
    loop.close()


def test_run_workflow_not_found(sqlite_run_db: None):
    """Running a non-existent workflow returns 404."""
    app.dependency_overrides[get_current_user] = make_user_ctx
    with patch("api.routes.workflows.execute_workflow_task") as mock_task:
        mock_task.delay = MagicMock()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(f"/api/workflows/{uuid4()}/run")
    app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 404


def test_approve_run_not_found(sqlite_run_db: None):
    """Approving a non-existent run returns 404."""
    app.dependency_overrides[get_current_user] = make_user_ctx
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(f"/api/workflows/runs/{uuid4()}/approve")
    app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 404


def test_reject_run_not_found(sqlite_run_db: None):
    """Rejecting a non-existent run returns 404."""
    app.dependency_overrides[get_current_user] = make_user_ctx
    with patch("api.routes.workflows.publish_event") as mock_pub:
        mock_pub.return_value = None
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(f"/api/workflows/runs/{uuid4()}/reject")
    app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 404


def test_approve_run_wrong_status_returns_409(sqlite_run_db: None):
    """Approving a run that is not paused_hitl returns 409."""
    import asyncio
    from core.models.workflow import Workflow, WorkflowRun
    from core.db import get_db as real_get_db

    # Create a workflow + run in the in-memory DB first
    user_ctx = make_user_ctx()
    user_id = user_ctx["user_id"]

    # Override to get a session for setup
    session_factory = None
    for dep_fn in app.dependency_overrides.values():
        session_factory = dep_fn
        break

    app.dependency_overrides[get_current_user] = lambda: user_ctx

    # Create workflow and run via API, then test approve
    with patch("api.routes.workflows.execute_workflow_task") as mock_task:
        mock_task.delay = MagicMock()
        client = TestClient(app, raise_server_exceptions=False)

        # Create a workflow
        resp = client.post(
            "/api/workflows",
            json={
                "name": "Test WF",
                "definition_json": {"schema_version": "1.0", "nodes": [], "edges": []},
            },
        )
        assert resp.status_code == 201, resp.text
        wf_id = resp.json()["id"]

        # Create a run (POST /{id}/run)
        run_resp = client.post(f"/api/workflows/{wf_id}/run")
        assert run_resp.status_code in (200, 201, 202), run_resp.text
        run_id = run_resp.json()["id"]

        # Run is in "pending" status (execute_workflow_task.delay is mocked)
        # Trying to approve a non-paused_hitl run should return 409
        approve_resp = client.post(f"/api/workflows/runs/{run_id}/approve")

    app.dependency_overrides.pop(get_current_user, None)
    assert approve_resp.status_code == 409
