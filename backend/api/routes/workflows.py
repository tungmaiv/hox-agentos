"""
Workflow CRUD API — full lifecycle management for canvas workflows.

Endpoints:
  GET    /api/workflows                           — list user's workflows
  POST   /api/workflows                           — create new workflow
  GET    /api/workflows/templates                 — list template workflows (requires JWT)
  POST   /api/workflows/templates/{id}/copy       — copy template to user's workflows
  GET    /api/workflows/runs/pending-hitl         — count of paused HITL runs
  GET    /api/workflows/runs/{run_id}             — get a specific run
  POST   /api/workflows/runs/{run_id}/approve     — approve a paused HITL run
  POST   /api/workflows/runs/{run_id}/reject      — reject a paused HITL run
  GET    /api/workflows/{id}                      — get workflow by ID
  PUT    /api/workflows/{id}                      — update workflow definition
  DELETE /api/workflows/{id}                      — delete workflow
  POST   /api/workflows/{id}/run                  — trigger manual execution (stub — wired in 04-03)
  GET    /api/workflows/{id}/triggers             — list triggers
  POST   /api/workflows/{id}/triggers             — create trigger
  DELETE /api/workflows/{id}/triggers/{trigger_id} — delete trigger

Security: all endpoints require JWT via get_current_user (Gate 1).
Memory isolation: all queries parameterized on owner_user_id from JWT — never from request body.

Note on route ordering: specific paths (/templates, /runs/...) MUST be declared
BEFORE parameterized paths (/{id}) to prevent FastAPI from matching "templates"
or "runs" as {id} values.
"""
import json
import secrets
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import async_session as _async_session
from core.models.user import UserContext
from core.models.workflow import Workflow, WorkflowRun, WorkflowTrigger
from core.schemas.workflow import (
    PendingHitlResponse,
    WorkflowCreate,
    WorkflowListItem,
    WorkflowResponse,
    WorkflowRunResponse,
    WorkflowTriggerCreate,
    WorkflowTriggerListResponse,
    WorkflowTriggerResponse,
    WorkflowUpdate,
)
from scheduler.tasks.workflow_execution import execute_workflow_task
from security.deps import get_current_user, get_user_db
from workflow_events import publish_event, subscribe_events

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/workflows", tags=["workflows"])


# ── Workflow CRUD ─────────────────────────────────────────────────────────────


@router.get("", response_model=list[WorkflowListItem])
async def list_workflows(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> list[WorkflowListItem]:
    """List the current user's non-template workflows, newest first."""
    result = await session.execute(
        select(Workflow)
        .where(Workflow.owner_user_id == user["user_id"])
        .where(Workflow.is_template == False)  # noqa: E712
        .order_by(Workflow.updated_at.desc())
    )
    return [WorkflowListItem.model_validate(w) for w in result.scalars().all()]


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    body: WorkflowCreate,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> WorkflowResponse:
    """Create a new workflow for the current user."""
    workflow = Workflow(
        owner_user_id=user["user_id"],
        name=body.name,
        description=body.description,
        definition_json=body.definition_json,
    )
    session.add(workflow)
    await session.commit()
    await session.refresh(workflow)
    logger.info("workflow_created", workflow_id=str(workflow.id), user_id=str(user["user_id"]))
    return WorkflowResponse.model_validate(workflow)


# NOTE: /templates, /runs/pending-hitl, /runs/{run_id} MUST come before /{workflow_id}
# to prevent FastAPI route matching treating "templates" or "runs" as {workflow_id}.


@router.get("/templates", response_model=list[WorkflowResponse])
async def list_templates(
    session: AsyncSession = Depends(get_user_db),
) -> list[WorkflowResponse]:
    """List all template workflows. Requires JWT — authenticated users only."""
    result = await session.execute(
        select(Workflow).where(Workflow.is_template == True)  # noqa: E712
    )
    return [WorkflowResponse.model_validate(t) for t in result.scalars().all()]


@router.post(
    "/templates/{template_id}/copy",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def copy_template(
    template_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> WorkflowResponse:
    """Copy a template workflow into the current user's workspace."""
    result = await session.execute(
        select(Workflow)
        .where(Workflow.id == template_id)
        .where(Workflow.is_template == True)  # noqa: E712
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    copy = Workflow(
        owner_user_id=user["user_id"],
        name=template.name,
        description=template.description,
        definition_json=template.definition_json,
        is_template=False,
        template_source_id=template.id,
    )
    session.add(copy)
    await session.commit()
    await session.refresh(copy)
    logger.info(
        "template_copied",
        template_id=str(template_id),
        copy_id=str(copy.id),
        user_id=str(user["user_id"]),
    )
    return WorkflowResponse.model_validate(copy)


@router.get("/runs/pending-hitl", response_model=PendingHitlResponse)
async def pending_hitl_count(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> PendingHitlResponse:
    """Return count of workflow runs paused waiting for human approval."""
    result = await session.execute(
        select(func.count())
        .select_from(WorkflowRun)
        .where(WorkflowRun.owner_user_id == user["user_id"])
        .where(WorkflowRun.status == "paused_hitl")
    )
    return PendingHitlResponse(count=result.scalar_one())


@router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
async def get_run(
    run_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> WorkflowRunResponse:
    """Get a specific workflow run by ID."""
    run = await _get_user_run(run_id, user["user_id"], session)
    return WorkflowRunResponse.model_validate(run)


@router.post("/runs/{run_id}/approve", response_model=WorkflowRunResponse)
async def approve_hitl(
    run_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> WorkflowRunResponse:
    """Resume a paused_hitl workflow run with approval."""
    run = await _get_user_run(run_id, user["user_id"], session)
    if run.status != "paused_hitl":
        raise HTTPException(
            status_code=409,
            detail=f"Run status is '{run.status}', expected 'paused_hitl'",
        )
    run.status = "running"
    await session.commit()
    await session.refresh(run)
    execute_workflow_task.delay(str(run.id), hitl_result="approved")
    logger.info("hitl_approved", run_id=str(run_id), user_id=str(user["user_id"]))
    return WorkflowRunResponse.model_validate(run)


@router.post("/runs/{run_id}/reject", response_model=WorkflowRunResponse)
async def reject_hitl(
    run_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> WorkflowRunResponse:
    """Reject a paused_hitl workflow run — marks it failed."""
    run = await _get_user_run(run_id, user["user_id"], session)
    if run.status != "paused_hitl":
        raise HTTPException(
            status_code=409,
            detail=f"Run status is '{run.status}', expected 'paused_hitl'",
        )
    run.status = "failed"
    run.result_json = {"rejected_by": str(user["user_id"])}
    await session.commit()
    await session.refresh(run)
    publish_event(str(run_id), {"event": "workflow_rejected"})
    logger.info("hitl_rejected", run_id=str(run_id), user_id=str(user["user_id"]))
    return WorkflowRunResponse.model_validate(run)


# ── Per-workflow endpoints ─────────────────────────────────────────────────────


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> WorkflowResponse:
    """Get a specific workflow by ID (must be owned by caller)."""
    workflow = await _get_user_workflow(workflow_id, user["user_id"], session)
    return WorkflowResponse.model_validate(workflow)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID,
    body: WorkflowUpdate,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> WorkflowResponse:
    """Update workflow name, description, or definition_json."""
    workflow = await _get_user_workflow(workflow_id, user["user_id"], session)
    if body.name is not None:
        workflow.name = body.name
    if body.description is not None:
        workflow.description = body.description
    if body.definition_json is not None:
        workflow.definition_json = body.definition_json
    await session.commit()
    await session.refresh(workflow)
    logger.info("workflow_updated", workflow_id=str(workflow_id), user_id=str(user["user_id"]))
    return WorkflowResponse.model_validate(workflow)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> None:
    """Delete a workflow and all its runs and triggers."""
    workflow = await _get_user_workflow(workflow_id, user["user_id"], session)
    await session.delete(workflow)
    await session.commit()
    logger.info("workflow_deleted", workflow_id=str(workflow_id), user_id=str(user["user_id"]))


@router.post(
    "/{workflow_id}/run",
    response_model=WorkflowRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def run_workflow(
    workflow_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> WorkflowRunResponse:
    """
    Trigger manual execution of a workflow.

    Creates a WorkflowRun row with status=pending, enqueues the execution Celery
    task, and returns the run record. The client can then subscribe to
    GET /api/workflows/runs/{run_id}/events for real-time node-level SSE events.
    """
    workflow = await _get_user_workflow(workflow_id, user["user_id"], session)
    run = WorkflowRun(
        workflow_id=workflow.id,
        owner_user_id=user["user_id"],
        trigger_type="manual",
        status="pending",
        owner_roles_json=user.get("roles", []),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    execute_workflow_task.delay(str(run.id))
    logger.info(
        "workflow_run_enqueued",
        workflow_id=str(workflow_id),
        run_id=str(run.id),
        user_id=str(user["user_id"]),
    )
    return WorkflowRunResponse.model_validate(run)


@router.get("/{workflow_id}/triggers", response_model=list[WorkflowTriggerListResponse])
async def list_triggers(
    workflow_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> list[WorkflowTriggerListResponse]:
    """List all triggers for a workflow."""
    await _get_user_workflow(workflow_id, user["user_id"], session)
    result = await session.execute(
        select(WorkflowTrigger).where(WorkflowTrigger.workflow_id == workflow_id)
    )
    return [WorkflowTriggerListResponse.model_validate(t) for t in result.scalars().all()]


@router.post(
    "/{workflow_id}/triggers",
    response_model=WorkflowTriggerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_trigger(
    workflow_id: uuid.UUID,
    body: WorkflowTriggerCreate,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> WorkflowTriggerResponse:
    """Create a new trigger (cron or webhook) for a workflow."""
    await _get_user_workflow(workflow_id, user["user_id"], session)
    webhook_secret = secrets.token_urlsafe(32) if body.trigger_type == "webhook" else None
    trigger = WorkflowTrigger(
        workflow_id=workflow_id,
        owner_user_id=user["user_id"],
        trigger_type=body.trigger_type,
        cron_expression=body.cron_expression,
        webhook_secret=webhook_secret,
        is_active=body.is_active,
        owner_roles_json=user.get("roles", []),
    )
    session.add(trigger)
    await session.commit()
    await session.refresh(trigger)
    logger.info(
        "trigger_created",
        workflow_id=str(workflow_id),
        trigger_id=str(trigger.id),
        trigger_type=body.trigger_type,
        user_id=str(user["user_id"]),
    )
    return WorkflowTriggerResponse.model_validate(trigger)


@router.delete(
    "/{workflow_id}/triggers/{trigger_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_trigger(
    workflow_id: uuid.UUID,
    trigger_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> None:
    """Delete a specific trigger from a workflow."""
    await _get_user_workflow(workflow_id, user["user_id"], session)
    result = await session.execute(
        select(WorkflowTrigger)
        .where(WorkflowTrigger.id == trigger_id)
        .where(WorkflowTrigger.workflow_id == workflow_id)
    )
    trigger = result.scalar_one_or_none()
    if trigger is None:
        raise HTTPException(status_code=404, detail="Trigger not found")
    await session.delete(trigger)
    await session.commit()


# ── SSE Events ────────────────────────────────────────────────────────────────

@router.get("/runs/{run_id}/events")
async def get_run_events(
    run_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> StreamingResponse:
    """
    SSE stream of workflow run events.

    Subscribes to the Redis pub/sub channel for this run and streams
    node-level events (node_started, node_completed, hitl_paused,
    workflow_completed, workflow_failed) to the browser.

    Stops when a terminal event (workflow_completed, workflow_failed,
    workflow_rejected) is received or after 300 seconds.

    Fast-path: if the run already reached a terminal state before the SSE
    subscriber connected (common for sub-second workflows), the terminal event
    is emitted immediately from the DB instead of waiting for pub/sub.
    """
    # Verify run exists and belongs to caller
    await _get_user_run(run_id, user["user_id"], session)
    run_id_str = str(run_id)

    async def _check_run_status() -> tuple[str, dict[str, Any] | None]:
        """Re-fetch run status from DB (used by subscribe_events fast-path)."""
        async with _async_session() as s:
            result = await s.execute(
                select(WorkflowRun).where(WorkflowRun.id == run_id)
            )
            fresh_run = result.scalar_one_or_none()
            if fresh_run is None:
                return ("failed", {"error": "Run not found"})
            return (fresh_run.status, fresh_run.result_json)

    async def _event_generator():
        async for event in subscribe_events(run_id_str, get_run_status=_check_run_status):
            if event.get("event") == "keepalive":
                yield ": keepalive\n\n"
            else:
                yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Internal helpers ──────────────────────────────────────────────────────────


async def _get_user_workflow(
    workflow_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> Workflow:
    """Fetch a workflow, enforcing ownership (user_id from JWT)."""
    result = await session.execute(
        select(Workflow)
        .where(Workflow.id == workflow_id)
        .where(Workflow.owner_user_id == user_id)
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


async def _get_user_run(
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> WorkflowRun:
    """Fetch a workflow run, enforcing ownership (user_id from JWT)."""
    result = await session.execute(
        select(WorkflowRun)
        .where(WorkflowRun.id == run_id)
        .where(WorkflowRun.owner_user_id == user_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
