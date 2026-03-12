"""
Tests for admin LLM config API — GET/POST/DELETE /api/admin/llm/models.

Covers:
  - test_get_models_success: admin can fetch model list from LiteLLM
  - test_get_models_litellm_unavailable: ConnectError returns graceful empty state
  - test_add_model_success: admin can add a model via POST
  - test_add_model_requires_admin: non-admin (employee) gets 403
  - test_delete_model_success: admin can delete a model via DELETE
"""
import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
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


# ---------------------------------------------------------------------------
# User context helpers
# ---------------------------------------------------------------------------


def make_admin_ctx() -> UserContext:
    """it-admin role has tool:admin permission."""
    return UserContext(
        user_id=uuid4(),
        email="admin@blitz.local",
        username="admin_user",
        roles=["it-admin"],
        groups=["/it"],
    )


def make_employee_ctx() -> UserContext:
    """employee role lacks tool:admin permission."""
    return UserContext(
        user_id=uuid4(),
        email="employee@blitz.local",
        username="emp_user",
        roles=["employee"],
        groups=["/tech"],
    )


# ---------------------------------------------------------------------------
# SQLite in-memory fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_db():
    """Override get_db with an in-memory SQLite async session."""
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


@pytest.fixture
def admin_client(sqlite_db: None) -> TestClient:
    """TestClient with admin auth + SQLite DB."""
    app.dependency_overrides[get_current_user] = make_admin_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def employee_client(sqlite_db: None) -> TestClient:
    """TestClient with employee auth + SQLite DB."""
    app.dependency_overrides[get_current_user] = make_employee_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_get_models_success(admin_client: TestClient) -> None:
    """GET /api/admin/llm/models with admin JWT → returns LLMConfigResponse with models list."""
    litellm_response = {
        "data": [
            {
                "model_name": "blitz/master",
                "litellm_params": {
                    "model": "ollama/qwen2.5:7b",
                    "api_base": "http://host.docker.internal:11434",
                },
            },
            {
                "model_name": "blitz/fast",
                "litellm_params": {
                    "model": "ollama/qwen2.5:7b",
                    "api_base": None,
                },
            },
        ]
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = litellm_response
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("api.routes.admin_llm.httpx.AsyncClient", return_value=mock_client):
        resp = admin_client.get("/api/admin/llm/models")

    assert resp.status_code == 200
    data = resp.json()
    assert data["litellm_available"] is True
    assert len(data["models"]) == 2
    assert data["models"][0]["model_alias"] == "blitz/master"
    assert data["models"][0]["provider_model"] == "ollama/qwen2.5:7b"
    assert data["models"][0]["api_base"] == "http://host.docker.internal:11434"
    assert data["models"][1]["model_alias"] == "blitz/fast"


def test_get_models_litellm_unavailable(admin_client: TestClient) -> None:
    """ConnectError → returns LLMConfigResponse with litellm_available=False and empty models."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("api.routes.admin_llm.httpx.AsyncClient", return_value=mock_client):
        resp = admin_client.get("/api/admin/llm/models")

    assert resp.status_code == 200
    data = resp.json()
    assert data["litellm_available"] is False
    assert data["models"] == []


def test_add_model_success(admin_client: TestClient) -> None:
    """POST /api/admin/llm/models with admin → calls LiteLLM /model/new → returns 201."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"status": "success"}'

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("api.routes.admin_llm.httpx.AsyncClient", return_value=mock_client):
        resp = admin_client.post(
            "/api/admin/llm/models",
            json={
                "model_alias": "blitz/custom",
                "provider_model": "gpt-4o-mini",
            },
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "added"
    assert data["model_alias"] == "blitz/custom"


def test_add_model_requires_admin(employee_client: TestClient) -> None:
    """POST /api/admin/llm/models with non-admin JWT → returns 403."""
    resp = employee_client.post(
        "/api/admin/llm/models",
        json={
            "model_alias": "blitz/custom",
            "provider_model": "gpt-4o-mini",
        },
    )
    assert resp.status_code == 403


def test_delete_model_success(admin_client: TestClient) -> None:
    """DELETE /api/admin/llm/models/{alias} → calls LiteLLM /model/delete → returns 204."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"status": "success"}'

    mock_client = AsyncMock()
    mock_client.delete = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("api.routes.admin_llm.httpx.AsyncClient", return_value=mock_client):
        resp = admin_client.delete("/api/admin/llm/models/blitz-master")

    assert resp.status_code == 204
