"""
Admin CRUD API for tool definitions — multi-version + bulk status.

GET    /api/admin/tools              — list all tool definitions (optional filters)
POST   /api/admin/tools              — create a new tool definition
GET    /api/admin/tools/{tool_id}    — get tool by UUID
PUT    /api/admin/tools/{tool_id}    — update tool fields
PATCH  /api/admin/tools/{tool_id}/status   — enable/disable with graceful removal
PATCH  /api/admin/tools/{tool_id}/activate — activate version, deactivate others
PATCH  /api/admin/tools/bulk-status  — bulk status update

Security: requires `registry:manage` permission (Gate 2 RBAC).
"""
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.tool_definition import ToolDefinition
from core.models.user import UserContext
from core.schemas.registry import (
    BulkStatusUpdate,
    StatusUpdate,
    ToolDefinitionCreate,
    ToolDefinitionResponse,
    ToolDefinitionUpdate,
)
from registry.service import invalidate_tool_cache_entry
from security.deps import get_current_user
from security.rbac import has_permission

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin/tools", tags=["admin-tools"])


async def _require_registry_manager(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2 dependency: require registry:manage permission."""
    if not await has_permission(user, "registry:manage", session):
        raise HTTPException(status_code=403, detail="Registry manage permission required")
    return user


@router.get("")
async def list_tools(
    status: str | None = Query(None, description="Filter by status"),
    version: str | None = Query(None, description="Filter by version"),
    name: str | None = Query(None, description="Filter by name substring (case-insensitive)"),
    handler_type: str | None = Query(None, description="Filter by handler_type: backend, mcp, sandbox"),
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> list[ToolDefinitionResponse]:
    """List all tool definitions with optional filters."""
    stmt = select(ToolDefinition)
    if status is not None:
        stmt = stmt.where(ToolDefinition.status == status)
    if version is not None:
        stmt = stmt.where(ToolDefinition.version == version)
    if name is not None:
        stmt = stmt.where(ToolDefinition.name.ilike(f"%{name}%"))
    if handler_type is not None:
        stmt = stmt.where(ToolDefinition.handler_type == handler_type)
    result = await session.execute(stmt)
    tools = result.scalars().all()
    logger.info("admin_tools_listed", user_id=str(user["user_id"]), count=len(tools))
    return [ToolDefinitionResponse.model_validate(t) for t in tools]


@router.post("", status_code=201)
async def create_tool(
    body: ToolDefinitionCreate,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> ToolDefinitionResponse:
    """Create a new tool definition."""
    has_stub = bool(body.handler_code)
    tool = ToolDefinition(
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        version=body.version,
        handler_type=body.handler_type,
        handler_module=body.handler_module,
        handler_function=body.handler_function,
        mcp_server_id=body.mcp_server_id,
        mcp_tool_name=body.mcp_tool_name,
        sandbox_required=body.sandbox_required,
        input_schema=body.input_schema,
        output_schema=body.output_schema,
        handler_code=body.handler_code,
        # If a handler stub was generated, hold the tool in pending_stub
        # until the admin fills and activates it via /activate-stub
        status="pending_stub" if has_stub else "active",
        is_active=not has_stub,
    )
    session.add(tool)
    await session.commit()
    await session.refresh(tool)
    logger.info(
        "admin_tool_created",
        tool_id=str(tool.id),
        name=tool.name,
        user_id=str(user["user_id"]),
    )
    return ToolDefinitionResponse.model_validate(tool)


@router.patch("/{tool_id}/activate-stub")
async def activate_tool_stub(
    tool_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> ToolDefinitionResponse:
    """
    Activate a pending_stub tool — promotes it from pending_stub to active.

    Used after the artifact builder generates a Python handler stub (SKBLD-03).
    The stub is code-reviewed by the admin, then activated to make the tool callable.

    Returns 409 if the tool is not in pending_stub status.
    """
    from core.logging import get_audit_logger
    audit = get_audit_logger()

    result = await session.execute(
        select(ToolDefinition).where(ToolDefinition.id == tool_id)
    )
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")

    if tool.status != "pending_stub":
        raise HTTPException(
            status_code=409,
            detail=f"Tool is not in pending_stub status (current: {tool.status})",
        )

    tool.status = "active"
    tool.is_active = True
    await session.commit()
    await session.refresh(tool)

    audit.info(
        "tool_stub_activated",
        tool_id=str(tool_id),
        user_id=str(user["user_id"]),
    )
    logger.info(
        "admin_tool_stub_activated",
        tool_id=str(tool_id),
        name=tool.name,
        user_id=str(user["user_id"]),
    )
    return ToolDefinitionResponse.model_validate(tool)


@router.get("/check-name")
async def check_tool_name(
    name: str = Query(..., min_length=1),
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Returns {"available": true/false} for the given tool name (case-insensitive)."""
    from registry.models import RegistryEntry
    count = await session.scalar(
        select(func.count()).where(
            RegistryEntry.type == "tool",
            func.lower(RegistryEntry.name) == name.lower(),
            RegistryEntry.deleted_at.is_(None),
        )
    )
    return {"available": (count or 0) == 0}


@router.get("/{tool_id}")
async def get_tool(
    tool_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> ToolDefinitionResponse:
    """Get a tool definition by UUID."""
    result = await session.execute(
        select(ToolDefinition).where(ToolDefinition.id == tool_id)
    )
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return ToolDefinitionResponse.model_validate(tool)


@router.put("/{tool_id}")
async def update_tool(
    tool_id: UUID,
    body: ToolDefinitionUpdate,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> ToolDefinitionResponse:
    """Update a tool definition's fields."""
    result = await session.execute(
        select(ToolDefinition).where(ToolDefinition.id == tool_id)
    )
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tool, field, value)

    await session.commit()
    await session.refresh(tool)
    logger.info(
        "admin_tool_updated",
        tool_id=str(tool_id),
        user_id=str(user["user_id"]),
    )
    return ToolDefinitionResponse.model_validate(tool)


@router.patch("/bulk-status")
async def bulk_status_update(
    body: BulkStatusUpdate,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Bulk update status for multiple tools."""
    result = await session.execute(
        update(ToolDefinition)
        .where(ToolDefinition.id.in_(body.ids))
        .values(status=body.status)
    )
    await session.commit()
    count = result.rowcount
    logger.info(
        "admin_tools_bulk_status",
        status=body.status,
        count=count,
        user_id=str(user["user_id"]),
    )
    return {"updated": count, "status": body.status}


@router.patch("/{tool_id}/status")
async def patch_tool_status(
    tool_id: UUID,
    body: StatusUpdate,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Enable/disable a tool with graceful removal.

    When disabling/deprecating, returns count of active workflow runs
    referencing this tool so the admin can assess impact.
    """
    result = await session.execute(
        select(ToolDefinition).where(ToolDefinition.id == tool_id)
    )
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")

    tool.status = body.status
    await session.commit()
    invalidate_tool_cache_entry(tool.name)

    # Graceful removal: count active workflow runs referencing this tool
    active_workflow_runs = 0
    if body.status in ("disabled", "deprecated"):
        try:
            from core.models.workflow import WorkflowRun

            run_result = await session.execute(
                select(WorkflowRun).where(WorkflowRun.status == "running")
            )
            runs = run_result.scalars().all()
            for run in runs:
                if run.initial_state and tool.name in str(run.initial_state):
                    active_workflow_runs += 1
        except Exception:
            pass

    logger.info(
        "admin_tool_status_changed",
        tool_id=str(tool_id),
        status=body.status,
        active_workflow_runs=active_workflow_runs,
        user_id=str(user["user_id"]),
    )
    return {
        "updated": True,
        "status": body.status,
        "active_workflow_runs": active_workflow_runs,
    }


@router.patch("/{tool_id}/activate")
async def activate_tool_version(
    tool_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> ToolDefinitionResponse:
    """
    Activate a specific tool version — deactivates all other versions of the same name.

    Enables version rollback: activate an older version to make it the current one.
    """
    result = await session.execute(
        select(ToolDefinition).where(ToolDefinition.id == tool_id)
    )
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")

    # Deactivate all versions of the same tool name
    await session.execute(
        update(ToolDefinition)
        .where(ToolDefinition.name == tool.name)
        .values(is_active=False)
    )

    # Activate this specific version
    tool.is_active = True
    await session.commit()
    await session.refresh(tool)
    invalidate_tool_cache_entry(tool.name)

    logger.info(
        "admin_tool_version_activated",
        tool_id=str(tool_id),
        name=tool.name,
        version=tool.version,
        user_id=str(user["user_id"]),
    )
    return ToolDefinitionResponse.model_validate(tool)
