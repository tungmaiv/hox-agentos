"""
UnifiedRegistryService — single service for all registry_entries CRUD operations.

Replaces the 4 separate registries (tool_registry, mcp/registry, admin_agents route,
admin_skills/tools routes) with a single strategy-pattern service.

Design:
- _handlers dict maps type strings to RegistryHandler instances
- list_entries: filter by type/status, exclude soft-deleted
- get_entry: fetch by id, exclude soft-deleted
- create_entry: validate_config → INSERT → on_create hook
- update_entry: validate_config → UPDATE
- delete_entry: on_delete hook → SET deleted_at = now()
- get_tools_for_user: returns active tools in format compatible with old tool_registry
"""
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.schemas.registry import RegistryEntryCreate, RegistryEntryUpdate
from registry.handlers.agent_handler import AgentHandler
from registry.handlers.base import RegistryHandler
from registry.handlers.mcp_handler import MCPHandler
from registry.handlers.skill_handler import SkillHandler
from registry.handlers.tool_handler import ToolHandler
from registry.models import RegistryEntry

logger = structlog.get_logger(__name__)

_VALID_TYPES = {"agent", "skill", "tool", "mcp_server"}
_VALID_STATUSES = {"draft", "active", "archived"}


class UnifiedRegistryService:
    """Strategy-pattern service for all registry_entries operations."""

    def __init__(self) -> None:
        self._handlers: dict[str, RegistryHandler] = {
            "agent": AgentHandler(),
            "skill": SkillHandler(),
            "tool": ToolHandler(),
            "mcp_server": MCPHandler(),
        }

    def _get_handler(self, entry_type: str) -> RegistryHandler:
        handler = self._handlers.get(entry_type)
        if handler is None:
            raise ValueError(f"Unknown registry entry type: '{entry_type}'")
        return handler

    async def list_entries(
        self,
        session: AsyncSession,
        type: str | None = None,
        status: str | None = None,
        include_deleted: bool = False,
    ) -> list[RegistryEntry]:
        """
        List registry entries with optional type/status filters.

        By default excludes soft-deleted entries (deleted_at IS NOT NULL).
        """
        query = select(RegistryEntry)

        if not include_deleted:
            query = query.where(RegistryEntry.deleted_at.is_(None))

        if type is not None:
            query = query.where(RegistryEntry.type == type)

        if status is not None:
            query = query.where(RegistryEntry.status == status)

        query = query.order_by(RegistryEntry.created_at.desc())
        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_entry(
        self,
        session: AsyncSession,
        entry_id: UUID,
    ) -> RegistryEntry | None:
        """Fetch a single entry by id. Returns None if not found or soft-deleted."""
        result = await session.execute(
            select(RegistryEntry).where(
                RegistryEntry.id == entry_id,
                RegistryEntry.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create_entry(
        self,
        session: AsyncSession,
        data: RegistryEntryCreate,
        owner_id: UUID | None = None,
    ) -> RegistryEntry:
        """
        Create a new registry entry.

        Steps:
        1. Validate type-specific config via handler
        2. INSERT into registry_entries
        3. Call on_create hook
        4. Return created entry
        """
        handler = self._get_handler(data.type)
        handler.validate_config(data.config)

        # Use provided owner or fall back to system sentinel
        from uuid import UUID as _UUID
        effective_owner = owner_id or _UUID("00000000-0000-0000-0000-000000000001")

        entry = RegistryEntry(
            type=data.type,
            name=data.name,
            display_name=data.display_name,
            description=data.description,
            config=data.config or {},
            status=data.status or "draft",
            owner_id=effective_owner,
        )
        session.add(entry)
        await session.flush()  # Populate id without committing

        await handler.on_create(entry, session)

        logger.info(
            "registry_entry_created",
            entry_id=str(entry.id),
            type=entry.type,
            name=entry.name,
        )
        return entry

    async def update_entry(
        self,
        session: AsyncSession,
        entry_id: UUID,
        data: RegistryEntryUpdate,
    ) -> RegistryEntry | None:
        """
        Update an existing registry entry.

        Returns None if not found or soft-deleted.
        Validates config if provided.
        """
        entry = await self.get_entry(session, entry_id)
        if entry is None:
            return None

        handler = self._get_handler(entry.type)

        if data.config is not None:
            # Merge with existing config and validate merged result
            merged_config = {**(entry.config or {}), **data.config}
            handler.validate_config(merged_config)
            entry.config = merged_config

        if data.display_name is not None:
            entry.display_name = data.display_name

        if data.description is not None:
            entry.description = data.description

        if data.status is not None:
            if data.status not in _VALID_STATUSES:
                raise ValueError(
                    f"Invalid status '{data.status}'. Must be one of: {_VALID_STATUSES}"
                )
            entry.status = data.status

        entry.updated_at = datetime.now(timezone.utc)

        logger.info(
            "registry_entry_updated",
            entry_id=str(entry_id),
            type=entry.type,
            name=entry.name,
        )
        return entry

    async def delete_entry(
        self,
        session: AsyncSession,
        entry_id: UUID,
    ) -> bool:
        """
        Soft-delete an entry by setting deleted_at timestamp.

        Returns True if deleted, False if not found.
        """
        entry = await self.get_entry(session, entry_id)
        if entry is None:
            return False

        handler = self._get_handler(entry.type)
        await handler.on_delete(entry, session)

        entry.deleted_at = datetime.now(timezone.utc)

        logger.info(
            "registry_entry_deleted",
            entry_id=str(entry_id),
            type=entry.type,
            name=entry.name,
        )
        return True

    async def get_tools_for_user(
        self,
        session: AsyncSession,
        user_id: UUID,
        roles: list[str],
    ) -> list[dict]:
        """
        Return active tool entries in format compatible with old tool_registry.

        Returns list[dict] with keys:
            name, description, handler_type, handler_function, handler_module,
            handler_code, sandbox_required, mcp_server_id, mcp_tool,
            mcp_server, required_permissions, config_json

        This method replaces ToolRegistry.get_tools_for_user() / _refresh_tool_cache().
        """
        entries = await self.list_entries(session, type="tool", status="active")

        tools = []
        for entry in entries:
            cfg = entry.config or {}

            # Derive mcp_server name from entry name (convention: "server.tool_name")
            mcp_server: str | None = None
            if cfg.get("handler_type") == "mcp" and "." in entry.name:
                mcp_server = entry.name.split(".")[0]

            # required_permissions may be stored in input_schema (legacy) or config directly
            required_permissions: list[str] = cfg.get("required_permissions", [])
            input_schema = cfg.get("input_schema") or {}
            if not required_permissions and isinstance(input_schema, dict):
                required_permissions = input_schema.get("required_permissions", [])

            tools.append(
                {
                    "name": entry.name,
                    "description": entry.description or "",
                    "handler_type": cfg.get("handler_type", "backend"),
                    "handler_module": cfg.get("handler_module"),
                    "handler_function": cfg.get("handler_function"),
                    "handler_code": cfg.get("handler_code"),
                    "sandbox_required": cfg.get("sandbox_required", False),
                    "mcp_server_id": cfg.get("mcp_server_id"),
                    "mcp_tool": cfg.get("mcp_tool_name"),
                    "mcp_server": mcp_server,
                    "required_permissions": required_permissions,
                    "config_json": cfg.get("config_json"),
                }
            )

        logger.debug(
            "get_tools_for_user",
            user_id=str(user_id),
            tool_count=len(tools),
        )
        return tools
