# backend/tests/test_workflow_schemas.py
"""
Tests for Pydantic workflow schemas — schema_version validation, trigger type validation.
"""
import pytest
from core.schemas.workflow import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowListItem,
    WorkflowRunResponse,
    WorkflowTriggerCreate,
    WorkflowTriggerResponse,
    PendingHitlResponse,
)


def test_workflow_create_valid():
    data = WorkflowCreate(
        name="Test",
        definition_json={"schema_version": "1.0", "nodes": [], "edges": []},
    )
    assert data.name == "Test"


def test_workflow_create_rejects_missing_schema_version():
    with pytest.raises(Exception):
        WorkflowCreate(name="Bad", definition_json={"nodes": [], "edges": []})


def test_workflow_create_rejects_wrong_schema_version():
    with pytest.raises(Exception):
        WorkflowCreate(
            name="Bad",
            definition_json={"schema_version": "2.0", "nodes": [], "edges": []},
        )


def test_trigger_create_cron():
    t = WorkflowTriggerCreate(trigger_type="cron", cron_expression="0 8 * * 1-5")
    assert t.cron_expression == "0 8 * * 1-5"


def test_trigger_create_rejects_unknown_type():
    with pytest.raises(Exception):
        WorkflowTriggerCreate(trigger_type="email")


def test_pending_hitl_response():
    r = PendingHitlResponse(count=3)
    assert r.count == 3
