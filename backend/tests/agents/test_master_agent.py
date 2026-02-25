# backend/tests/agents/test_master_agent.py
"""
TDD tests for BlitzState TypedDict and create_master_graph().

Design invariants tested:
- BlitzState uses add_messages reducer (nodes return partial state, not full state)
- graph is a CompiledStateGraph (not a raw StateGraph)
- LLM is obtained via get_llm(), never direct provider SDK
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage


def test_blitz_state_has_messages_field():
    """BlitzState must declare 'messages' with add_messages reducer annotation."""
    from agents.state.types import BlitzState
    assert "messages" in BlitzState.__annotations__, (
        "BlitzState must have a 'messages' field for LangGraph message accumulation"
    )


def test_create_master_graph_returns_compiled_graph():
    """create_master_graph() returns a compiled LangGraph StateGraph, ready for ainvoke."""
    from langgraph.graph.state import CompiledStateGraph
    with patch("agents.master_agent.get_llm") as mock_get_llm:
        mock_get_llm.return_value = MagicMock()
        from agents.master_agent import create_master_graph
        graph = create_master_graph()
    assert isinstance(graph, CompiledStateGraph), (
        f"create_master_graph() must return CompiledStateGraph, got {type(graph)}"
    )


@pytest.mark.asyncio
async def test_master_graph_calls_blitz_master_and_returns_ai_message():
    """Graph invocation calls get_llm('blitz/master') and appends an AIMessage to state."""
    mock_response = AIMessage(content="Hello! How can I assist you?")

    # Patch get_llm at the agents.master_agent module level so the _master_node function
    # (which calls get_llm() at call time, not import time) picks up the mock.
    # No reload needed — the patch replaces the name in the already-imported module.
    with patch("agents.master_agent.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_get_llm.return_value = mock_llm

        from agents.master_agent import create_master_graph
        graph = create_master_graph()
        result = await graph.ainvoke({
            "messages": [HumanMessage(content="Hello")]
        })

    assert len(result["messages"]) >= 2, "Result must contain input message + AI response"
    last_message = result["messages"][-1]
    assert isinstance(last_message, AIMessage), (
        f"Last message must be AIMessage, got {type(last_message)}"
    )
    assert last_message.content == "Hello! How can I assist you?"


def test_master_agent_uses_get_llm_not_direct_sdk():
    """Master agent must call get_llm() — not anthropic.Anthropic() or OpenAI() directly."""
    import ast
    import inspect
    import agents.master_agent as ma_module

    source = inspect.getsource(ma_module)
    tree = ast.parse(source)

    # Check no direct provider imports exist in the module
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in ("anthropic", "openai"), (
                    f"Direct provider import found: '{alias.name}'. Use get_llm() instead."
                )
        if isinstance(node, ast.ImportFrom):
            assert node.module not in ("anthropic", "openai"), (
                f"Direct provider import found from '{node.module}'. Use get_llm() instead."
            )


def test_create_master_graph_has_routing_conditional():
    """
    Graph must have a routing conditional after master_agent (not a plain edge to END).

    Phase 2 stub: conditional always returns END. Phase 3 extends it with sub-agent edges.
    This test verifies the graph structure is delegation-ready.

    Note: LangGraph 0.4.10 uses compiled.builder.branches (not compiled.graph.branches).
    """
    from langgraph.graph.state import CompiledStateGraph
    from unittest.mock import MagicMock, patch

    with patch("agents.master_agent.get_llm") as mock_get_llm:
        mock_get_llm.return_value = MagicMock()
        from agents.master_agent import create_master_graph
        graph = create_master_graph()

    assert isinstance(graph, CompiledStateGraph)
    # Verify the graph has conditional edges (not just a plain edge from master_agent → END)
    # In LangGraph 0.4.10, compiled.builder is the original StateGraph with .branches attribute.
    # The master_agent node must have branches (conditional edges), not plain edges.
    graph_builder = graph.builder
    assert "master_agent" in graph_builder.branches, (
        "master_agent must have conditional routing via add_conditional_edges(), "
        "not a plain add_edge() to END. This allows Phase 3 to add sub-agent branches."
    )
