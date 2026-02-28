"""Tests for MCP server evolution: health-check, status patch, disabled server handling.

Covers:
- Health-check endpoint returns reachability status and latency
- Status patch updates DB and evicts client on disable
- MCPToolRegistry.refresh() skips disabled servers
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db import Base
from core.models.mcp_server import McpServer


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    async_sess = async_sessionmaker(engine, expire_on_commit=False)
    async with async_sess() as s:
        yield s


async def _seed_server(
    session: AsyncSession,
    name: str = "test-server",
    url: str = "http://mcp-test:9000",
    status: str = "active",
) -> McpServer:
    """Insert an MCP server row."""
    server = McpServer(
        id=uuid.uuid4(),
        name=name,
        url=url,
        status=status,
        is_active=status == "active",
    )
    session.add(server)
    await session.commit()
    await session.refresh(server)
    return server


# ── Health-check endpoint ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_check_reachable(session: AsyncSession) -> None:
    """Health-check returns reachable=True when server responds with 200."""
    from api.routes.mcp_servers import check_mcp_server_health

    server = await _seed_server(session, url="http://mcp-test:9000")

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        admin = MagicMock()
        result = await check_mcp_server_health(
            server_id=server.id,
            user=admin,
            session=session,
        )

    assert result["reachable"] is True
    assert "latency_ms" in result
    assert result["name"] == "test-server"


@pytest.mark.asyncio
async def test_health_check_unreachable(session: AsyncSession) -> None:
    """Health-check returns reachable=False when server is unreachable."""
    from api.routes.mcp_servers import check_mcp_server_health

    server = await _seed_server(session, url="http://mcp-test:9000")

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        admin = MagicMock()
        result = await check_mcp_server_health(
            server_id=server.id,
            user=admin,
            session=session,
        )

    assert result["reachable"] is False
    assert "latency_ms" in result


@pytest.mark.asyncio
async def test_health_check_not_found(session: AsyncSession) -> None:
    """Health-check returns 404 for unknown server ID."""
    from api.routes.mcp_servers import check_mcp_server_health

    with pytest.raises(HTTPException) as exc_info:
        await check_mcp_server_health(
            server_id=uuid.uuid4(),
            user=MagicMock(),
            session=session,
        )
    assert exc_info.value.status_code == 404


# ── Status patch endpoint ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_patch_updates_db(session: AsyncSession) -> None:
    """Patching status updates the DB row."""
    from api.routes.mcp_servers import StatusPatch, patch_mcp_server_status
    from sqlalchemy import select

    server = await _seed_server(session, status="active")

    with (
        patch("api.routes.mcp_servers.MCPToolRegistry") as mock_registry,
        patch("gateway.tool_registry.invalidate_tool_cache"),
    ):
        mock_registry.evict_client = MagicMock()

        result = await patch_mcp_server_status(
            server_id=server.id,
            body=StatusPatch(status="disabled"),
            user=MagicMock(),
            session=session,
        )

    assert result["status"] == "disabled"

    # Verify DB was updated
    db_result = await session.execute(
        select(McpServer).where(McpServer.id == server.id)
    )
    updated = db_result.scalar_one()
    assert updated.status == "disabled"


@pytest.mark.asyncio
async def test_status_patch_evicts_client_on_disable(session: AsyncSession) -> None:
    """Disabling a server evicts its client from MCPToolRegistry cache."""
    from api.routes.mcp_servers import StatusPatch, patch_mcp_server_status

    server = await _seed_server(session, name="evict-me")

    with (
        patch("api.routes.mcp_servers.MCPToolRegistry") as mock_registry,
        patch("gateway.tool_registry.invalidate_tool_cache") as mock_invalidate,
    ):
        mock_registry.evict_client = MagicMock()

        await patch_mcp_server_status(
            server_id=server.id,
            body=StatusPatch(status="disabled"),
            user=MagicMock(),
            session=session,
        )

        mock_registry.evict_client.assert_called_once_with("evict-me")
        mock_invalidate.assert_called_once()


@pytest.mark.asyncio
async def test_status_patch_invalid_status(session: AsyncSession) -> None:
    """Invalid status value returns 400."""
    from api.routes.mcp_servers import StatusPatch, patch_mcp_server_status

    server = await _seed_server(session)

    with pytest.raises(HTTPException) as exc_info:
        await patch_mcp_server_status(
            server_id=server.id,
            body=StatusPatch(status="invalid"),
            user=MagicMock(),
            session=session,
        )
    assert exc_info.value.status_code == 400


# ── MCPToolRegistry.refresh() status filtering ──────────────────────────


@pytest.mark.asyncio
async def test_refresh_skips_disabled_servers() -> None:
    """refresh() only processes servers with status='active'."""
    from mcp.registry import MCPToolRegistry, _clients

    disabled_server = MagicMock()
    disabled_server.name = "disabled-server"
    disabled_server.status = "disabled"
    disabled_server.auth_token = None

    active_server = MagicMock()
    active_server.name = "active-server"
    active_server.url = "http://active:8000"
    active_server.status = "active"
    active_server.auth_token = None
    active_server.id = uuid.uuid4()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [disabled_server, active_server]
    mock_session.execute = AsyncMock(return_value=mock_result)

    # async_session() returns a context manager; mock it as MagicMock with
    # __aenter__/__aexit__ so `async with async_session() as session:` works
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_session_factory = MagicMock(return_value=mock_cm)

    mock_client = MagicMock()
    mock_client.list_tools = AsyncMock(return_value=[])

    with (
        patch("core.db.async_session", mock_session_factory),
        patch("mcp.registry.MCPClient", return_value=mock_client),
        patch("mcp.registry.register_tool", new_callable=AsyncMock),
    ):
        # Pre-populate disabled server in cache to test eviction
        _clients["disabled-server"] = MagicMock()

        await MCPToolRegistry.refresh()

        # Disabled server should be evicted
        assert "disabled-server" not in _clients
        # Active server should be connected
        assert "active-server" in _clients

    # Cleanup
    _clients.pop("active-server", None)
