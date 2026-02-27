import pytest
from uuid import uuid4
from agents.graphs import compile_workflow_to_stategraph

USER_CTX = {"user_id": str(uuid4()), "roles": ["employee"], "email": "test@blitz.local"}

SIMPLE_WORKFLOW = {
    "schema_version": "1.0",
    "nodes": [
        {"id": "n1", "type": "trigger_node", "data": {"config": {"trigger_type": "manual"}}},
        {"id": "n2", "type": "tool_node",    "data": {"config": {"tool_name": "crm.list_projects", "params": {}}}},
        {"id": "n3", "type": "channel_output_node", "data": {"config": {"channel": "web"}}},
    ],
    "edges": [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3"},
    ],
}

CONDITIONAL_WORKFLOW = {
    "schema_version": "1.0",
    "nodes": [
        {"id": "n1", "type": "trigger_node",    "data": {"config": {}}},
        {"id": "n2", "type": "tool_node",       "data": {"config": {"tool_name": "crm.list_projects", "params": {}}}},
        {"id": "n3", "type": "condition_node",  "data": {"config": {"expression": "output.count > 0"}}},
        {"id": "n4", "type": "channel_output_node", "data": {"config": {"channel": "web"}}},
    ],
    "edges": [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3"},
        {"id": "e3", "source": "n3", "target": "n4", "data": {"branch": "true"}},
    ],
}


def test_compile_simple_workflow_returns_compilable_builder():
    builder = compile_workflow_to_stategraph(SIMPLE_WORKFLOW, USER_CTX)
    assert builder is not None
    # Should be compilable without error
    from langgraph.checkpoint.memory import MemorySaver
    compiled = builder.compile(checkpointer=MemorySaver())
    assert compiled is not None


def test_compile_rejects_missing_schema_version():
    bad = {**SIMPLE_WORKFLOW, "schema_version": "9.9"}
    with pytest.raises(ValueError, match="schema_version"):
        compile_workflow_to_stategraph(bad, USER_CTX)


def test_compile_rejects_no_schema_version():
    bad = {"nodes": [], "edges": []}
    with pytest.raises(ValueError, match="schema_version"):
        compile_workflow_to_stategraph(bad, USER_CTX)


def test_compile_conditional_workflow():
    builder = compile_workflow_to_stategraph(CONDITIONAL_WORKFLOW, USER_CTX)
    from langgraph.checkpoint.memory import MemorySaver
    compiled = builder.compile(checkpointer=MemorySaver())
    assert compiled is not None


def test_compile_empty_workflow():
    """Empty workflow (no nodes) should not raise — returns a graph with no nodes."""
    empty = {"schema_version": "1.0", "nodes": [], "edges": []}
    builder = compile_workflow_to_stategraph(empty, USER_CTX)
    assert builder is not None


def test_compile_unknown_node_type_raises():
    bad_node_type = {
        "schema_version": "1.0",
        "nodes": [{"id": "n1", "type": "unknown_node", "data": {"config": {}}}],
        "edges": [],
    }
    with pytest.raises(ValueError, match="Unknown node type"):
        compile_workflow_to_stategraph(bad_node_type, USER_CTX)
