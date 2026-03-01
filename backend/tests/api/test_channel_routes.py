"""Tests for channel API routes."""
import asyncio
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db import Base, get_db
from main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_user():
    return {
        "user_id": uuid.uuid4(),
        "email": "test@blitz.com",
        "username": "testuser",
        "roles": ["employee"],
        "groups": [],
    }


@pytest.fixture
def sqlite_db_override():
    """Override get_db with SQLite in-memory so get_user_db can connect."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def _init() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_init())
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as s:
            yield s

    yield _override
    loop.run_until_complete(engine.dispose())
    loop.close()


def _override_auth(mock_user, db_override=None):
    """Return dependency overrides for get_current_user (and optionally get_db)."""
    from security.deps import get_current_user

    async def _fake():
        return mock_user

    overrides = {get_current_user: _fake}
    if db_override is not None:
        overrides[get_db] = db_override
    return overrides


# -- POST /api/channels/incoming ---------------------------------------------


def test_incoming_forwards_to_gateway(client: TestClient):
    with patch("api.routes.channels.get_channel_gateway") as mock_gw_fn:
        mock_gw = AsyncMock()
        mock_gw.handle_inbound.return_value = None
        mock_gw_fn.return_value = mock_gw

        resp = client.post(
            "/api/channels/incoming",
            json={
                "direction": "inbound",
                "channel": "telegram",
                "external_user_id": "12345",
                "text": "Hello",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_gw.handle_inbound.assert_called_once()


# -- POST /api/channels/pair ------------------------------------------------


def test_pair_requires_auth(client: TestClient):
    resp = client.post("/api/channels/pair", json={"channel": "telegram"})
    assert resp.status_code == 401


def test_pair_generates_code(client: TestClient, mock_user, sqlite_db_override):
    app = client.app
    app.dependency_overrides = _override_auth(mock_user, db_override=sqlite_db_override)

    with patch("api.routes.channels.get_channel_gateway") as mock_gw_fn:
        mock_gw = AsyncMock()
        mock_gw.generate_pairing_code.return_value = "ABC123"
        mock_gw_fn.return_value = mock_gw

        resp = client.post("/api/channels/pair", json={"channel": "telegram"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "ABC123"
        assert data["expires_in"] == 600

    app.dependency_overrides = {}


# -- GET /api/channels/accounts ----------------------------------------------


def test_list_accounts_requires_auth(client: TestClient):
    resp = client.get("/api/channels/accounts")
    assert resp.status_code == 401
