# backend/tests/test_workflows_api.py
"""
Tests for workflow CRUD API routes.

Security pattern: dependency_overrides for get_current_user + SQLite for get_db.
Tests are synchronous (TestClient) following existing codebase patterns.
"""
import asyncio
from collections.abc import AsyncGenerator
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
def sqlite_workflow_db():
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


def test_list_workflows_requires_jwt():
    """GET /api/workflows returns 401 without Authorization header."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/workflows")
    assert response.status_code == 401


def test_list_workflows_route_exists():
    """GET /api/workflows is registered (not 404)."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/workflows")
    assert response.status_code != 404


def test_list_workflows_returns_empty_list(sqlite_workflow_db: None):
    """Authenticated user with no workflows gets empty list."""
    app.dependency_overrides[get_current_user] = make_user_ctx
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/workflows")
    app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 0


def test_create_workflow_returns_201(sqlite_workflow_db: None):
    """POST /api/workflows creates a workflow and returns 201."""
    app.dependency_overrides[get_current_user] = make_user_ctx
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/workflows",
        json={
            "name": "My Workflow",
            "definition_json": {
                "schema_version": "1.0",
                "nodes": [],
                "edges": [],
            },
        },
    )
    app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Workflow"
    assert data["is_template"] is False


def test_create_workflow_rejects_bad_schema_version(sqlite_workflow_db: None):
    """POST /api/workflows with missing schema_version returns 422."""
    app.dependency_overrides[get_current_user] = make_user_ctx
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/workflows",
        json={"name": "Bad", "definition_json": {"nodes": [], "edges": []}},
    )
    app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 422


def test_get_workflow_not_found(sqlite_workflow_db: None):
    """GET /api/workflows/{id} with nonexistent id returns 404."""
    app.dependency_overrides[get_current_user] = make_user_ctx
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(f"/api/workflows/{uuid4()}")
    app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 404


def test_delete_workflow_not_found(sqlite_workflow_db: None):
    """DELETE /api/workflows/{id} with nonexistent id returns 404."""
    app.dependency_overrides[get_current_user] = make_user_ctx
    client = TestClient(app, raise_server_exceptions=False)
    response = client.delete(f"/api/workflows/{uuid4()}")
    app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 404
