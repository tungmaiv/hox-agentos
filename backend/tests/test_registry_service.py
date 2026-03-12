"""
Tests for UnifiedRegistryService and strategy handlers.

Covers:
  - test_get_tools_for_user: returns only active tool entries
  - test_handler_validate_config_tool: ToolHandler validates handler_function required
  - test_handler_validate_config_mcp_http: MCPHandler validates url for http_sse
"""
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db import Base
from core.schemas.registry import RegistryEntryCreate
from registry.handlers.mcp_handler import MCPHandler
from registry.handlers.tool_handler import ToolHandler
from registry.models import RegistryEntry  # noqa: F401 — registers table in Base.metadata
from registry.service import UnifiedRegistryService


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_sess = async_sessionmaker(engine, expire_on_commit=False)
    async with async_sess() as s:
        yield s
    await engine.dispose()


@pytest.fixture
def registry_service() -> UnifiedRegistryService:
    return UnifiedRegistryService()


@pytest.mark.asyncio
async def test_get_tools_for_user(session: AsyncSession, registry_service: UnifiedRegistryService):
    """get_tools_for_user returns only entries with type='tool' and status='active'."""
    owner = uuid.uuid4()

    # Insert active tool
    active_tool = RegistryEntry(
        type="tool",
        name="email.send",
        description="Send email",
        config={
            "handler_type": "backend",
            "handler_function": "tools.email.send",
            "required_permissions": ["email:write"],
        },
        status="active",
        owner_id=owner,
    )
    # Insert draft tool (should NOT appear)
    draft_tool = RegistryEntry(
        type="tool",
        name="email.draft",
        description="Draft email",
        config={"handler_type": "backend", "handler_function": "tools.email.draft"},
        status="draft",
        owner_id=owner,
    )
    # Insert active skill (should NOT appear)
    active_skill = RegistryEntry(
        type="skill",
        name="brainstorming",
        config={"skill_type": "instructional"},
        status="active",
        owner_id=owner,
    )

    session.add_all([active_tool, draft_tool, active_skill])
    await session.commit()

    tools = await registry_service.get_tools_for_user(
        session,
        user_id=owner,
        roles=["employee"],
    )

    assert len(tools) == 1
    assert tools[0]["name"] == "email.send"
    assert tools[0]["handler_type"] == "backend"
    assert tools[0]["handler_function"] == "tools.email.send"
    assert "email:write" in tools[0]["required_permissions"]


@pytest.mark.asyncio
async def test_get_tools_for_user_empty(session: AsyncSession, registry_service: UnifiedRegistryService):
    """get_tools_for_user returns empty list when no active tools exist."""
    tools = await registry_service.get_tools_for_user(
        session,
        user_id=uuid.uuid4(),
        roles=[],
    )
    assert tools == []


def test_handler_validate_config_tool():
    """ToolHandler.validate_config passes with handler_function; raises ValueError without."""
    handler = ToolHandler()

    # Valid: has handler_function
    handler.validate_config({"handler_function": "tools.test", "handler_type": "backend"})

    # Invalid: missing handler_function and handler_code
    with pytest.raises(ValueError, match="handler_function"):
        handler.validate_config({"handler_type": "backend"})

    # MCP tool: requires mcp_tool_name instead
    handler.validate_config({"handler_type": "mcp", "mcp_tool_name": "search"})

    with pytest.raises(ValueError, match="mcp_tool_name"):
        handler.validate_config({"handler_type": "mcp"})


def test_handler_validate_config_mcp_http():
    """MCPHandler.validate_config passes for http_sse with url; raises without url."""
    handler = MCPHandler()

    # Valid: http_sse with url
    handler.validate_config({"server_type": "http_sse", "url": "http://example.com"})

    # Valid: default server_type (http_sse) with url
    handler.validate_config({"url": "http://example.com"})

    # Invalid: http_sse without url
    with pytest.raises(ValueError, match="url"):
        handler.validate_config({"server_type": "http_sse"})

    # Valid: openapi_bridge with openapi_url (plan 24-03 spec)
    handler.validate_config({
        "server_type": "openapi_bridge",
        "openapi_url": "http://example.com/openapi.json",
    })
