"""
Celery beat task: fire cron-triggered workflows.

fire_cron_triggers_task(): Celery task, runs every 60 seconds via beat.
fire_cron_triggers():       Async logic — loads all active cron triggers,
                            checks if each is due within the last 60s,
                            creates a WorkflowRun and enqueues execution.

Tolerance window: 60 seconds. Celery beat fires every 60s; a trigger is
"due" if its previous scheduled run was within the last 60s.
This prevents double-firing if beat fires a few seconds late.

Security: WorkflowRun.owner_user_id is set to the trigger's owner_user_id.
The execution task (execute_workflow_task) runs as that user — full ACL applies.
"""
import asyncio
from datetime import datetime, timezone

import structlog
from croniter import croniter
from sqlalchemy import select

from core.db import async_session
from core.models.workflow import WorkflowRun, WorkflowTrigger
from scheduler.celery_app import celery_app
from scheduler.tasks.workflow_execution import execute_workflow_task

logger = structlog.get_logger(__name__)

_TOLERANCE_SECONDS = 60


@celery_app.task(
    name="scheduler.tasks.cron_trigger.fire_cron_triggers_task",
    queue="default",
)
def fire_cron_triggers_task() -> None:
    """Celery beat entry point — runs every 60 seconds."""
    asyncio.run(fire_cron_triggers())


async def fire_cron_triggers() -> None:
    """Load and fire all due cron triggers."""
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        result = await session.execute(
            select(WorkflowTrigger)
            .where(WorkflowTrigger.trigger_type == "cron")
            .where(WorkflowTrigger.is_active == True)  # noqa: E712
        )
        triggers = result.scalars().all()

        for trigger in triggers:
            if not trigger.cron_expression:
                continue

            try:
                cron = croniter(trigger.cron_expression, now)
                prev: datetime = cron.get_prev(datetime)
                # croniter returns a naive datetime — make it UTC-aware
                if prev.tzinfo is None:
                    prev = prev.replace(tzinfo=timezone.utc)
                seconds_since_last = (now - prev).total_seconds()

                if seconds_since_last > _TOLERANCE_SECONDS:
                    continue  # Not due yet

                run = WorkflowRun(
                    workflow_id=trigger.workflow_id,
                    owner_user_id=trigger.owner_user_id,
                    trigger_type="cron",
                    status="pending",
                    owner_roles_json=trigger.owner_roles_json or [],
                )
                session.add(run)
                await session.commit()
                await session.refresh(run)

                execute_workflow_task.delay(str(run.id))
                logger.info(
                    "cron_trigger_fired",
                    trigger_id=str(trigger.id),
                    run_id=str(run.id),
                    cron=trigger.cron_expression,
                )

            except Exception as exc:
                logger.error(
                    "cron_trigger_error",
                    trigger_id=str(trigger.id),
                    cron=trigger.cron_expression,
                    error=str(exc),
                )
                # Continue processing other triggers
