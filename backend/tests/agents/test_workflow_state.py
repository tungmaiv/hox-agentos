from uuid import uuid4
from agents.workflow_state import WorkflowState


def test_workflow_state_has_required_keys():
    """WorkflowState must have all fields used by the compiler and handlers."""
    state: WorkflowState = {
        "run_id": uuid4(),
        "user_context": {"user_id": str(uuid4()), "roles": ["employee"]},
        "node_outputs": {},
        "current_output": None,
        "hitl_result": None,
    }
    assert state["node_outputs"] == {}
    assert state["hitl_result"] is None


def test_workflow_state_node_outputs_accumulates():
    """node_outputs is a plain dict — no LangGraph reducer magic."""
    state: WorkflowState = {
        "run_id": None,
        "user_context": None,
        "node_outputs": {"n1": {"count": 3}},
        "current_output": {"count": 3},
        "hitl_result": None,
    }
    state["node_outputs"]["n2"] = {"sent": True}
    assert "n1" in state["node_outputs"]
    assert "n2" in state["node_outputs"]
