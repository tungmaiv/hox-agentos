"""
Webhook trigger endpoint — public endpoint, no JWT required.

POST /api/webhooks/{webhook_id}

Security: validated via X-Webhook-Secret header (HMAC token stored in
workflow_triggers.webhook_secret). Returns 401 for both "not found" and
"secret mismatch" cases to avoid leaking trigger existence.

Execution logic is wired in plan 04-03. For now, creates a WorkflowRun row
with status=pending and returns {run_id: ..., status: "accepted"}.
"""
import hmac
import uuid

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.workflow import WorkflowRun, WorkflowTrigger
from scheduler.tasks.workflow_execution import execute_workflow_task

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/{webhook_id}", status_code=202)
async def fire_webhook(
    webhook_id: uuid.UUID,
    x_webhook_secret: str = Header(..., alias="X-Webhook-Secret"),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Fire a webhook trigger.

    Validates the webhook_id (trigger ID) and X-Webhook-Secret header.
    Returns 401 for both missing triggers and wrong secrets (no existence leaking).
    Creates a WorkflowRun row with status=pending.
    """
    result = await session.execute(
        select(WorkflowTrigger)
        .where(WorkflowTrigger.id == webhook_id)
        .where(WorkflowTrigger.trigger_type == "webhook")
        .where(WorkflowTrigger.is_active == True)  # noqa: E712
    )
    trigger = result.scalar_one_or_none()

    # Reject if not found OR secret mismatch — same 401 to avoid existence leaking
    if trigger is None or not hmac.compare_digest(
        trigger.webhook_secret or "", x_webhook_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook credentials")

    run = WorkflowRun(
        workflow_id=trigger.workflow_id,
        owner_user_id=trigger.owner_user_id,
        trigger_type="webhook",
        status="pending",
        owner_roles_json=trigger.owner_roles_json or [],
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    execute_workflow_task.delay(str(run.id))
    logger.info("webhook_fired", trigger_id=str(webhook_id), run_id=str(run.id))
    return {"run_id": str(run.id), "status": "accepted"}
