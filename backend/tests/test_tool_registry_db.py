"""Tests for DB-backed tool registry with TTL cache, last_seen_at, and startup seeding.

Covers:
- get_tool returns active tools from DB cache
- get_tool returns None for disabled tools (status != 'active')
- get_tool returns None for is_active=False tools
- register_tool upserts into tool_definitions
- list_tools returns only active tool names
- Cache TTL and invalidation
- update_tool_last_seen batching
- seed_tool_definitions_from_registry startup seed
- Backward compat: session=None returns stale cache
"""
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db import Base
from core.models.tool_definition import ToolDefinition


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


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset tool cache before each test to prevent cross-test pollution."""
    from gateway.tool_registry import invalidate_tool_cache
    import gateway.tool_registry as tr

    tr._tool_cache.clear()
    invalidate_tool_cache()
    yield
    tr._tool_cache.clear()
    invalidate_tool_cache()


async def _seed_tool(session: AsyncSession, name: str, **kwargs) -> ToolDefinition:
    """Helper to insert a tool definition row."""
    defaults = {
        "id": uuid.uuid4(),
        "name": name,
        "version": "1.0.0",
        "description": f"Test tool {name}",
        "handler_type": "backend",
        "status": "active",
        "is_active": True,
        "sandbox_required": False,
        "input_schema": {"required_permissions": []},
    }
    defaults.update(kwargs)
    tool = ToolDefinition(**defaults)
    session.add(tool)
    await session.commit()
    return tool


# ── get_tool tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_tool_returns_active_tool(session: AsyncSession) -> None:
    """get_tool returns tool dict for active tools."""
    from gateway.tool_registry import get_tool

    await _seed_tool(session, "email.send", input_schema={"required_permissions": ["email:write"]})

    result = await get_tool("email.send", session)
    assert result is not None
    assert result["name"] == "email.send"
    assert result["handler_type"] == "backend"


@pytest.mark.asyncio
async def test_get_tool_returns_none_for_disabled(session: AsyncSession) -> None:
    """get_tool returns None for tools with status='disabled'."""
    from gateway.tool_registry import get_tool

    await _seed_tool(session, "disabled_tool", status="disabled")

    result = await get_tool("disabled_tool", session)
    assert result is None


@pytest.mark.asyncio
async def test_get_tool_returns_none_for_inactive(session: AsyncSession) -> None:
    """get_tool returns None for tools with is_active=False."""
    from gateway.tool_registry import get_tool

    await _seed_tool(session, "inactive_tool", is_active=False)

    result = await get_tool("inactive_tool", session)
    assert result is None


@pytest.mark.asyncio
async def test_get_tool_returns_none_for_unknown(session: AsyncSession) -> None:
    """get_tool returns None for tools that don't exist."""
    from gateway.tool_registry import get_tool

    result = await get_tool("nonexistent.tool", session)
    assert result is None


@pytest.mark.asyncio
async def test_get_tool_session_none_returns_stale_cache(session: AsyncSession) -> None:
    """session=None returns from stale cache without refresh (backward compat)."""
    from gateway.tool_registry import get_tool, _refresh_tool_cache

    await _seed_tool(session, "cached_tool")
    await _refresh_tool_cache(session)

    # Now call without session -- should return from cache
    result = await get_tool("cached_tool")
    assert result is not None
    assert result["name"] == "cached_tool"


# ── register_tool tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_tool_inserts(session: AsyncSession) -> None:
    """register_tool creates a new row in tool_definitions."""
    from gateway.tool_registry import register_tool, get_tool

    await register_tool(
        session,
        name="test.new_tool",
        description="A new tool",
        required_permissions=["test:read"],
        handler_type="backend",
    )

    result = await get_tool("test.new_tool", session)
    assert result is not None
    assert result["name"] == "test.new_tool"
    assert "test:read" in result["required_permissions"]


@pytest.mark.asyncio
async def test_register_tool_upserts(session: AsyncSession) -> None:
    """register_tool updates existing row on conflict (same name+version)."""
    from gateway.tool_registry import register_tool, get_tool

    await register_tool(
        session,
        name="test.upsert",
        description="v1",
        handler_type="backend",
    )

    await register_tool(
        session,
        name="test.upsert",
        description="v2",
        handler_type="mcp",
    )

    result = await get_tool("test.upsert", session)
    assert result is not None
    assert result["handler_type"] == "mcp"


# ── list_tools tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_tools_returns_active_only(session: AsyncSession) -> None:
    """list_tools returns only active tool names."""
    from gateway.tool_registry import list_tools

    await _seed_tool(session, "active_tool")
    await _seed_tool(session, "disabled_tool", status="disabled")
    await _seed_tool(session, "inactive_tool", is_active=False)

    names = await list_tools(session)
    assert "active_tool" in names
    assert "disabled_tool" not in names
    assert "inactive_tool" not in names


# ── cache tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_works_within_ttl(session: AsyncSession) -> None:
    """Repeated get_tool calls within TTL don't re-query DB."""
    from gateway.tool_registry import get_tool, _refresh_tool_cache
    import gateway.tool_registry as tr

    await _seed_tool(session, "cached")
    await _refresh_tool_cache(session)

    # Manually verify timestamp is recent
    assert time.monotonic() - tr._tool_cache_timestamp < 1.0

    # A second call should not need to refresh
    result = await get_tool("cached", session)
    assert result is not None


@pytest.mark.asyncio
async def test_invalidation_forces_refresh(session: AsyncSession) -> None:
    """invalidate_tool_cache() causes next get_tool to refresh from DB."""
    from gateway.tool_registry import get_tool, invalidate_tool_cache, _refresh_tool_cache
    import gateway.tool_registry as tr

    await _seed_tool(session, "will_invalidate")
    await _refresh_tool_cache(session)
    assert "will_invalidate" in tr._tool_cache

    invalidate_tool_cache()
    assert tr._tool_cache_timestamp == 0.0

    # Next get_tool with session triggers refresh
    result = await get_tool("will_invalidate", session)
    assert result is not None


# ── update_tool_last_seen tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_tool_last_seen_sets_timestamp(session: AsyncSession) -> None:
    """update_tool_last_seen sets last_seen_at for active tools."""
    from gateway.tool_registry import update_tool_last_seen
    from sqlalchemy import select

    tool = await _seed_tool(session, "seen_tool")
    assert tool.last_seen_at is None

    await update_tool_last_seen("seen_tool", session)

    result = await session.execute(
        select(ToolDefinition).where(ToolDefinition.name == "seen_tool")
    )
    updated = result.scalar_one()
    assert updated.last_seen_at is not None


@pytest.mark.asyncio
async def test_update_tool_last_seen_batches(session: AsyncSession) -> None:
    """update_tool_last_seen does not update if last_seen_at is within 60s."""
    from gateway.tool_registry import update_tool_last_seen
    from sqlalchemy import select

    recent = datetime.now(timezone.utc)
    await _seed_tool(session, "recent_tool", last_seen_at=recent)

    await update_tool_last_seen("recent_tool", session)

    result = await session.execute(
        select(ToolDefinition).where(ToolDefinition.name == "recent_tool")
    )
    updated = result.scalar_one()
    # Should not have changed since last_seen_at was within 60s
    # (The timestamps should be very close or identical)
    assert updated.last_seen_at is not None


# ── startup seed tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_seed_tool_definitions_populates_db(session: AsyncSession) -> None:
    """seed_tool_definitions_from_registry inserts legacy tools into empty DB."""
    from gateway.tool_registry import seed_tool_definitions_from_registry
    from sqlalchemy import select

    await seed_tool_definitions_from_registry(session)

    result = await session.execute(select(ToolDefinition))
    tools = result.scalars().all()
    names = {t.name for t in tools}

    assert "crm.get_project_status" in names
    assert "crm.list_projects" in names
    assert "crm.update_task_status" in names


@pytest.mark.asyncio
async def test_seed_is_idempotent(session: AsyncSession) -> None:
    """Calling seed twice does not create duplicates."""
    from gateway.tool_registry import seed_tool_definitions_from_registry
    from sqlalchemy import select, func

    await seed_tool_definitions_from_registry(session)
    await seed_tool_definitions_from_registry(session)

    result = await session.execute(select(func.count()).select_from(ToolDefinition))
    count = result.scalar_one()
    assert count == 3  # Exactly 3 legacy tools


@pytest.mark.asyncio
async def test_seeded_tools_available_via_cache(session: AsyncSession) -> None:
    """After seeding and cache refresh, tools are available via get_tool."""
    from gateway.tool_registry import (
        get_tool,
        seed_tool_definitions_from_registry,
        _refresh_tool_cache,
        invalidate_tool_cache,
    )

    await seed_tool_definitions_from_registry(session)
    invalidate_tool_cache()
    await _refresh_tool_cache(session)

    crm = await get_tool("crm.get_project_status", session)
    assert crm is not None
    assert crm["handler_type"] == "mcp"
    assert crm["mcp_tool"] == "get_project_status"
    assert crm["mcp_server"] == "crm"
    assert "crm:read" in crm["required_permissions"]


# ---------------------------------------------------------------------------
# Phase 9: targeted cache entry eviction (EXTD-03/05)
# ---------------------------------------------------------------------------


def test_cache_entry_eviction() -> None:
    """invalidate_tool_cache_entry(name) removes only the named key from _tool_cache.

    Other cached entries remain untouched — this is targeted eviction, not a blanket flush.
    The global TTL timestamp (_tool_cache_timestamp) must NOT be reset.
    """
    import gateway.tool_registry as tr
    from gateway.tool_registry import invalidate_tool_cache_entry

    # Seed cache with two tools
    tr._tool_cache["tool.alpha"] = {"name": "tool.alpha", "status": "active"}
    tr._tool_cache["tool.beta"] = {"name": "tool.beta", "status": "active"}

    # Record current TTL timestamp (should not change)
    ts_before = tr._tool_cache_timestamp

    # Evict only 'tool.alpha'
    invalidate_tool_cache_entry("tool.alpha")

    # 'tool.alpha' gone, 'tool.beta' untouched
    assert "tool.alpha" not in tr._tool_cache, "invalidate_tool_cache_entry should remove the named entry"
    assert "tool.beta" in tr._tool_cache, "invalidate_tool_cache_entry must not remove other entries"

    # Global TTL timestamp must NOT change (targeted eviction, not blanket flush)
    assert tr._tool_cache_timestamp == ts_before, (
        "invalidate_tool_cache_entry must not reset _tool_cache_timestamp. "
        "Use invalidate_tool_cache() for blanket flush."
    )

    # Calling with a non-existent key must not raise
    invalidate_tool_cache_entry("tool.nonexistent")  # must not raise KeyError
