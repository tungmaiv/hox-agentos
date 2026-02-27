"""
Tests for the execute_workflow Celery task.

Verifies:
- Missing WorkflowRun exits silently without publishing events
- Compiler failure sets run.status = 'failed' and publishes workflow_failed
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4


@pytest.mark.asyncio
async def test_execute_workflow_not_found_exits_silently():
    """Missing WorkflowRun logs error and returns without raising."""
    with patch("scheduler.tasks.workflow_execution.async_session") as mock_sf, \
         patch("scheduler.tasks.workflow_execution.publish_event") as mock_pub:

        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        from scheduler.tasks.workflow_execution import execute_workflow
        await execute_workflow(str(uuid4()))

        mock_pub.assert_not_called()


@pytest.mark.asyncio
async def test_execute_workflow_compile_failure_sets_failed_status():
    """Compiler ValueError sets run.status = 'failed'."""
    run_id = str(uuid4())

    mock_run = MagicMock()
    mock_run.id = uuid4()
    mock_run.workflow_id = uuid4()
    mock_run.owner_user_id = uuid4()
    mock_run.status = "pending"

    mock_workflow = MagicMock()
    mock_workflow.definition_json = {"schema_version": "BAD", "nodes": [], "edges": []}

    with patch("scheduler.tasks.workflow_execution.async_session") as mock_sf, \
         patch("scheduler.tasks.workflow_execution.publish_event") as mock_pub:

        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_workflow)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),
        ])
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        from scheduler.tasks.workflow_execution import execute_workflow
        await execute_workflow(run_id)

        # Status must be set to failed
        assert mock_run.status == "failed"
        # workflow_failed event must be published
        published_events = [c[0][1]["event"] for c in mock_pub.call_args_list]
        assert "workflow_failed" in published_events
