"""
Tool registry -- DB-backed with in-process TTL cache.

All tools (backend tools, MCP wrappers, sandbox tools) are registered here.
This is the SINGLE registry for all tools -- never register tools elsewhere.

Phase 6 evolution: migrated from in-memory dict to DB-backed queries.
- get_tool()/list_tools() read from tool_definitions table via 60s TTL cache
- register_tool() upserts into tool_definitions (not in-memory dict)
- Disabled tools (status != 'active' or is_active = False) excluded
- update_tool_last_seen() tracks dispatch activity (batched to 60s)
- seed_tool_definitions_from_registry() populates DB from legacy registry on startup
- Backward compat: session=None falls back to stale cache (no refresh)
"""
import time
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# ── In-process cache (TTL = 60s) ──────────────────────────────────────────
_tool_cache: dict[str, dict[str, Any]] = {}
_tool_cache_timestamp: float = 0.0
_TOOL_CACHE_TTL: float = 60.0


def invalidate_tool_cache() -> None:
    """Force cache refresh on next get_tool/list_tools call."""
    global _tool_cache_timestamp
    _tool_cache_timestamp = 0.0


def invalidate_tool_cache_entry(name: str) -> None:
    """Evict a single tool entry from the in-process cache.

    Use when a specific tool's status changes (enable/disable/version switch).
    Does NOT reset the global TTL timestamp — other cached entries remain valid.
    """
    _tool_cache.pop(name, None)
    logger.debug("tool_cache_entry_evicted", name=name)


async def _refresh_tool_cache(session: AsyncSession) -> None:
    """Reload cache from tool_definitions table (active + is_active only)."""
    global _tool_cache, _tool_cache_timestamp
    from core.models.tool_definition import ToolDefinition

    result = await session.execute(
        select(ToolDefinition).where(
            ToolDefinition.status == "active",
            ToolDefinition.is_active == True,  # noqa: E712
        )
    )
    rows = result.scalars().all()

    new_cache: dict[str, dict[str, Any]] = {}
    for row in rows:
        new_cache[row.name] = {
            "name": row.name,
            "description": row.description or "",
            "required_permissions": [],  # populated from row metadata below
            "sandbox_required": row.sandbox_required,
            "mcp_server": None,
            "mcp_tool": row.mcp_tool_name,
            "handler_type": row.handler_type,
            "handler_module": row.handler_module,
            "handler_function": row.handler_function,
            "mcp_server_id": str(row.mcp_server_id) if row.mcp_server_id else None,
            "config_json": row.config_json,
        }
        # Derive mcp_server name from the tool name for MCP tools
        # (convention: "server.tool_name" -> mcp_server="server")
        if row.handler_type == "mcp" and "." in row.name:
            new_cache[row.name]["mcp_server"] = row.name.split(".")[0]
        # NOTE: required_permissions is currently stored inside input_schema
        # as {"required_permissions": ["crm:read", ...]}. This is a legacy
        # convention from the migration of the in-memory registry. Post-MVP,
        # consider adding a dedicated required_permissions JSON column to
        # tool_definitions to avoid overloading input_schema's purpose.
        if row.input_schema and "required_permissions" in row.input_schema:
            new_cache[row.name]["required_permissions"] = row.input_schema["required_permissions"]

    _tool_cache = new_cache
    _tool_cache_timestamp = time.monotonic()
    logger.debug("tool_cache_refreshed", tool_count=len(new_cache))


async def get_tool(
    name: str, session: AsyncSession | None = None
) -> dict[str, Any] | None:
    """
    Get a tool definition by name from DB-backed cache.

    If session is provided and cache is expired, refreshes from DB.
    If session is None, returns from stale cache (backward compat).
    Returns None if tool not found or not active.
    """
    global _tool_cache_timestamp

    if session is not None:
        elapsed = time.monotonic() - _tool_cache_timestamp
        if elapsed >= _TOOL_CACHE_TTL or not _tool_cache:
            await _refresh_tool_cache(session)

    return _tool_cache.get(name)


async def register_tool(
    session: AsyncSession,
    *,
    name: str,
    description: str = "",
    required_permissions: list[str] | None = None,
    sandbox_required: bool = False,
    mcp_server: str | None = None,
    mcp_tool: str | None = None,
    handler_type: str = "backend",
    handler_module: str | None = None,
    handler_function: str | None = None,
    mcp_server_id: Any = None,
) -> None:
    """
    Upsert a tool into tool_definitions table.

    Performs SELECT + INSERT or UPDATE (SQLite-compatible, no ON CONFLICT).
    Invalidates cache after upsert.
    """
    from core.models.tool_definition import ToolDefinition

    result = await session.execute(
        select(ToolDefinition).where(
            ToolDefinition.name == name,
            ToolDefinition.version == "1.0.0",
        )
    )
    existing = result.scalar_one_or_none()

    perms = required_permissions or []

    if existing is not None:
        existing.description = description
        existing.sandbox_required = sandbox_required
        existing.handler_type = handler_type
        existing.handler_module = handler_module
        existing.handler_function = handler_function
        existing.mcp_tool_name = mcp_tool
        existing.input_schema = {"required_permissions": perms}
        if mcp_server_id is not None:
            existing.mcp_server_id = mcp_server_id
        existing.status = "active"
        existing.is_active = True
    else:
        tool = ToolDefinition(
            name=name,
            description=description,
            version="1.0.0",
            handler_type=handler_type,
            handler_module=handler_module,
            handler_function=handler_function,
            sandbox_required=sandbox_required,
            mcp_tool_name=mcp_tool,
            mcp_server_id=mcp_server_id,
            input_schema={"required_permissions": perms},
            status="active",
            is_active=True,
        )
        session.add(tool)

    await session.commit()
    invalidate_tool_cache()


async def list_tools(session: AsyncSession | None = None) -> list[str]:
    """Return list of all active tool names from cache."""
    global _tool_cache_timestamp

    if session is not None:
        elapsed = time.monotonic() - _tool_cache_timestamp
        if elapsed >= _TOOL_CACHE_TTL or not _tool_cache:
            await _refresh_tool_cache(session)

    return list(_tool_cache.keys())


async def update_tool_last_seen(name: str, session: AsyncSession) -> None:
    """
    Update last_seen_at on a tool after successful dispatch.

    Batched: only updates if last_seen_at is older than 60s or NULL,
    to avoid excessive DB writes on high-frequency tool calls.
    """
    from core.models.tool_definition import ToolDefinition

    now = datetime.now(timezone.utc)
    cutoff = datetime.fromtimestamp(now.timestamp() - 60, tz=timezone.utc)

    result = await session.execute(
        select(ToolDefinition).where(
            ToolDefinition.name == name,
            ToolDefinition.is_active == True,  # noqa: E712
        )
    )
    tool = result.scalar_one_or_none()
    if tool is None:
        return

    # Normalize for comparison: SQLite stores offset-naive datetimes
    last = tool.last_seen_at
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    if last is None or last < cutoff:
        await session.execute(
            update(ToolDefinition)
            .where(ToolDefinition.id == tool.id)
            .values(last_seen_at=now)
        )
        await session.commit()


# ── Legacy registry snapshot (for startup seeding) ─────────────────────────
# These are the tools that were hardcoded in the old _registry dict.
# Used by seed_tool_definitions_from_registry() to populate tool_definitions
# on first boot so tool dispatch works immediately after migration 014.

_LEGACY_REGISTRY: list[dict[str, Any]] = [
    {
        "name": "crm.get_project_status",
        "description": "Get project status from CRM",
        "required_permissions": ["crm:read"],
        "sandbox_required": False,
        "handler_type": "mcp",
        "mcp_server": "crm",
        "mcp_tool": "get_project_status",
    },
    {
        "name": "crm.list_projects",
        "description": "List all CRM projects",
        "required_permissions": ["crm:read"],
        "sandbox_required": False,
        "handler_type": "mcp",
        "mcp_server": "crm",
        "mcp_tool": "list_projects",
    },
    {
        "name": "crm.update_task_status",
        "description": "Update task status in CRM kanban",
        "required_permissions": ["crm:write"],
        "sandbox_required": False,
        "handler_type": "mcp",
        "mcp_server": "crm",
        "mcp_tool": "update_task_status",
    },
]


async def seed_tool_definitions_from_registry(session: AsyncSession) -> None:
    """
    Seed tool_definitions from legacy hardcoded registry.

    Uses SELECT + conditional INSERT (no ON CONFLICT) for SQLite compat.
    Only inserts if (name, version) doesn't already exist.
    Called at startup from main.py lifespan.
    """
    from core.models.tool_definition import ToolDefinition

    seeded = 0
    for entry in _LEGACY_REGISTRY:
        result = await session.execute(
            select(ToolDefinition).where(
                ToolDefinition.name == entry["name"],
                ToolDefinition.version == "1.0.0",
            )
        )
        if result.scalar_one_or_none() is not None:
            continue  # Already exists

        tool = ToolDefinition(
            name=entry["name"],
            description=entry.get("description", ""),
            version="1.0.0",
            handler_type=entry.get("handler_type", "backend"),
            sandbox_required=entry.get("sandbox_required", False),
            mcp_tool_name=entry.get("mcp_tool"),
            input_schema={"required_permissions": entry.get("required_permissions", [])},
            status="active",
            is_active=True,
        )
        session.add(tool)
        seeded += 1

    if seeded > 0:
        await session.commit()
        logger.info("tool_definitions_seeded", count=seeded)
    else:
        logger.debug("tool_definitions_seed_skipped", reason="all tools already exist")
