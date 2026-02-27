# backend/tests/test_webhooks_api.py
"""
Tests for POST /api/webhooks/{webhook_id} endpoint.

The webhook endpoint is public — no JWT required. It validates X-Webhook-Secret
against the stored webhook_secret in workflow_triggers.

Security: 401 for both "trigger not found" and "wrong secret" to avoid
leaking trigger existence.
"""
import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.db import Base, get_db
from core.models.workflow import Workflow, WorkflowTrigger
from main import app


@pytest.fixture
def sqlite_webhook_db():
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


def test_webhook_route_exists():
    """POST /api/webhooks/{id} is registered (not 404)."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        f"/api/webhooks/{uuid4()}",
        headers={"X-Webhook-Secret": "any"},
        json={},
    )
    assert response.status_code != 404


def test_webhook_with_wrong_secret_returns_401(sqlite_webhook_db: None):
    """POST /api/webhooks/{id} with wrong secret returns 401."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        f"/api/webhooks/{uuid4()}",
        headers={"X-Webhook-Secret": "wrong-secret"},
        json={},
    )
    assert response.status_code == 401


def test_webhook_missing_secret_header_returns_422(sqlite_webhook_db: None):
    """POST /api/webhooks/{id} without X-Webhook-Secret returns 422."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        f"/api/webhooks/{uuid4()}",
        json={},
    )
    # Missing required header → 422 Unprocessable Entity
    assert response.status_code == 422


def test_valid_webhook_enqueues_execution(sqlite_webhook_db: None):
    """POST /api/webhooks/{id} with correct secret enqueues execute_workflow_task."""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def _seed():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as s:
            wf = Workflow(
                name="Test WF",
                owner_user_id=uuid4(),
                definition_json={"schema_version": "1.0", "nodes": [], "edges": []},
            )
            s.add(wf)
            await s.flush()
            trigger = WorkflowTrigger(
                workflow_id=wf.id,
                owner_user_id=wf.owner_user_id,
                trigger_type="webhook",
                is_active=True,
                webhook_secret="secret-abc",
            )
            s.add(trigger)
            await s.commit()
            return trigger.id

    loop = asyncio.new_event_loop()
    trigger_id = loop.run_until_complete(_seed())
    factory2 = async_sessionmaker(engine, expire_on_commit=False)

    async def override():
        async with factory2() as s:
            yield s

    app.dependency_overrides[get_db] = override

    with patch(
        "api.routes.webhooks.execute_workflow_task.delay"
    ) as mock_delay:
        client = TestClient(app, raise_server_exceptions=True)
        response = client.post(
            f"/api/webhooks/{trigger_id}",
            headers={"X-Webhook-Secret": "secret-abc"},
        )

    app.dependency_overrides.pop(get_db, None)
    loop.run_until_complete(engine.dispose())
    loop.close()

    assert response.status_code == 202
    mock_delay.assert_called_once()
