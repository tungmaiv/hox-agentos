"""
Tests for the cron trigger Celery beat task.

Verifies:
- Due cron trigger creates a WorkflowRun and enqueues execute_workflow_task
- Trigger with null cron_expression is skipped silently
- Invalid cron expression logs and continues without crashing
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_fire_cron_triggers_creates_run_for_due_trigger():
    """A trigger due within the last 60s creates a WorkflowRun and enqueues execution."""
    trigger = MagicMock()
    trigger.id = uuid4()
    trigger.workflow_id = uuid4()
    trigger.owner_user_id = uuid4()
    trigger.cron_expression = "* * * * *"  # every minute — always due

    mock_run = MagicMock()
    mock_run.id = uuid4()

    with patch("scheduler.tasks.cron_trigger.async_session") as mock_sf, \
         patch("scheduler.tasks.cron_trigger.execute_workflow_task") as mock_exec:

        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[trigger]))
                )
            )
        )
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", uuid4()))

        from scheduler.tasks.cron_trigger import fire_cron_triggers
        await fire_cron_triggers()

        mock_session.add.assert_called_once()
        mock_exec.delay.assert_called_once()


@pytest.mark.asyncio
async def test_fire_cron_triggers_skips_trigger_with_no_expression():
    """Triggers with null cron_expression are skipped silently."""
    trigger = MagicMock()
    trigger.id = uuid4()
    trigger.workflow_id = uuid4()
    trigger.owner_user_id = uuid4()
    trigger.cron_expression = None  # No expression

    with patch("scheduler.tasks.cron_trigger.async_session") as mock_sf, \
         patch("scheduler.tasks.cron_trigger.execute_workflow_task") as mock_exec:

        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[trigger]))
                )
            )
        )

        from scheduler.tasks.cron_trigger import fire_cron_triggers
        await fire_cron_triggers()

        mock_exec.delay.assert_not_called()


@pytest.mark.asyncio
async def test_fire_cron_triggers_bad_expression_logs_and_continues():
    """Invalid cron expressions are logged and do not crash the scheduler."""
    trigger = MagicMock()
    trigger.id = uuid4()
    trigger.workflow_id = uuid4()
    trigger.owner_user_id = uuid4()
    trigger.cron_expression = "not-a-cron"

    with patch("scheduler.tasks.cron_trigger.async_session") as mock_sf, \
         patch("scheduler.tasks.cron_trigger.execute_workflow_task") as mock_exec:

        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[trigger]))
                )
            )
        )

        from scheduler.tasks.cron_trigger import fire_cron_triggers
        await fire_cron_triggers()  # must not raise

        mock_exec.delay.assert_not_called()
