# backend/tests/test_workflow_models.py
"""
RED: Failing tests for Workflow, WorkflowRun, WorkflowTrigger ORM models.
These tests fail until backend/core/models/workflow.py is created.
"""
from core.models.workflow import Workflow, WorkflowRun, WorkflowTrigger


def test_workflow_tablename():
    assert Workflow.__tablename__ == "workflows"


def test_workflow_run_tablename():
    assert WorkflowRun.__tablename__ == "workflow_runs"


def test_workflow_trigger_tablename():
    assert WorkflowTrigger.__tablename__ == "workflow_triggers"
