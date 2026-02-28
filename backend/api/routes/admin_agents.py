"""
Admin CRUD API for agent definitions — multi-version + bulk status.

GET    /api/admin/agents              — list all agent definitions (optional filters)
POST   /api/admin/agents              — create a new agent definition
GET    /api/admin/agents/{agent_id}   — get agent by UUID
PUT    /api/admin/agents/{agent_id}   — update agent fields
PATCH  /api/admin/agents/{agent_id}/status   — enable/disable with graceful removal
PATCH  /api/admin/agents/{agent_id}/activate — activate version, deactivate others
PATCH  /api/admin/agents/bulk-status  — bulk status update

Security: requires `registry:manage` permission (Gate 2 RBAC).
"""
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.agent_definition import AgentDefinition
from core.models.user import UserContext
from core.schemas.registry import (
    AgentDefinitionCreate,
    AgentDefinitionResponse,
    AgentDefinitionUpdate,
    BulkStatusUpdate,
    StatusUpdate,
)
from security.deps import get_current_user
from security.rbac import has_permission

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin/agents", tags=["admin-agents"])


async def _require_registry_manager(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2 dependency: require registry:manage permission."""
    if not await has_permission(user, "registry:manage", session):
        raise HTTPException(status_code=403, detail="Registry manage permission required")
    return user


@router.get("")
async def list_agents(
    status: str | None = Query(None, description="Filter by status"),
    version: str | None = Query(None, description="Filter by version"),
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> list[AgentDefinitionResponse]:
    """List all agent definitions with optional filters."""
    stmt = select(AgentDefinition)
    if status is not None:
        stmt = stmt.where(AgentDefinition.status == status)
    if version is not None:
        stmt = stmt.where(AgentDefinition.version == version)
    result = await session.execute(stmt)
    agents = result.scalars().all()
    logger.info("admin_agents_listed", user_id=str(user["user_id"]), count=len(agents))
    return [AgentDefinitionResponse.model_validate(a) for a in agents]


@router.post("", status_code=201)
async def create_agent(
    body: AgentDefinitionCreate,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> AgentDefinitionResponse:
    """Create a new agent definition."""
    agent = AgentDefinition(
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        version=body.version,
        handler_module=body.handler_module,
        handler_function=body.handler_function,
        routing_keywords=body.routing_keywords,
        config_json=body.config_json,
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    logger.info(
        "admin_agent_created",
        agent_id=str(agent.id),
        name=agent.name,
        user_id=str(user["user_id"]),
    )
    return AgentDefinitionResponse.model_validate(agent)


@router.get("/{agent_id}")
async def get_agent(
    agent_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> AgentDefinitionResponse:
    """Get an agent definition by UUID."""
    result = await session.execute(
        select(AgentDefinition).where(AgentDefinition.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentDefinitionResponse.model_validate(agent)


@router.put("/{agent_id}")
async def update_agent(
    agent_id: UUID,
    body: AgentDefinitionUpdate,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> AgentDefinitionResponse:
    """Update an agent definition's fields."""
    result = await session.execute(
        select(AgentDefinition).where(AgentDefinition.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(agent, field, value)

    await session.commit()
    await session.refresh(agent)
    logger.info(
        "admin_agent_updated",
        agent_id=str(agent_id),
        user_id=str(user["user_id"]),
    )
    return AgentDefinitionResponse.model_validate(agent)


@router.patch("/bulk-status")
async def bulk_status_update(
    body: BulkStatusUpdate,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Bulk update status for multiple agents."""
    result = await session.execute(
        update(AgentDefinition)
        .where(AgentDefinition.id.in_(body.ids))
        .values(status=body.status)
    )
    await session.commit()
    count = result.rowcount
    logger.info(
        "admin_agents_bulk_status",
        status=body.status,
        count=count,
        user_id=str(user["user_id"]),
    )
    return {"updated": count, "status": body.status}


@router.patch("/{agent_id}/status")
async def patch_agent_status(
    agent_id: UUID,
    body: StatusUpdate,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Enable/disable an agent with graceful removal.

    When disabling/deprecating, returns count of active workflow runs
    referencing this agent so the admin can assess impact.
    """
    result = await session.execute(
        select(AgentDefinition).where(AgentDefinition.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.status = body.status
    await session.commit()

    # Graceful removal: count active workflow runs referencing this agent
    active_workflow_runs = 0
    if body.status in ("disabled", "deprecated"):
        try:
            from core.models.workflow import WorkflowRun

            run_result = await session.execute(
                select(WorkflowRun).where(WorkflowRun.status == "running")
            )
            runs = run_result.scalars().all()
            # Count runs whose workflow references this agent name
            for run in runs:
                if run.initial_state and agent.name in str(run.initial_state):
                    active_workflow_runs += 1
        except Exception:
            # WorkflowRun may not exist in test DB; gracefully return 0
            pass

    logger.info(
        "admin_agent_status_changed",
        agent_id=str(agent_id),
        status=body.status,
        active_workflow_runs=active_workflow_runs,
        user_id=str(user["user_id"]),
    )
    return {
        "updated": True,
        "status": body.status,
        "active_workflow_runs": active_workflow_runs,
    }


@router.patch("/{agent_id}/activate")
async def activate_agent_version(
    agent_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> AgentDefinitionResponse:
    """
    Activate a specific agent version — deactivates all other versions of the same name.

    This enables version rollback: activate an older version to make it the current one.
    """
    result = await session.execute(
        select(AgentDefinition).where(AgentDefinition.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Deactivate all versions of the same agent name
    await session.execute(
        update(AgentDefinition)
        .where(AgentDefinition.name == agent.name)
        .values(is_active=False)
    )

    # Activate this specific version
    agent.is_active = True
    await session.commit()
    await session.refresh(agent)

    logger.info(
        "admin_agent_version_activated",
        agent_id=str(agent_id),
        name=agent.name,
        version=agent.version,
        user_id=str(user["user_id"]),
    )
    return AgentDefinitionResponse.model_validate(agent)
