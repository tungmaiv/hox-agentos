# backend/agents/master_agent.py
"""
Master agent — Phase 2 conversational ReAct graph.

Single master_agent node in Phase 2: receives messages, calls blitz/master LLM,
returns response. The routing conditional stub is included now so Phase 3 can
add sub-agent edges without restructuring the graph.

Evolution path (no rewrite required between phases):
  Phase 2: master_agent → [_route_after_master returns END]
  Phase 3: add load_memory + save_memory nodes wrapping master_agent;
           update _route_after_master to return sub-agent node names
  Phase 4: canvas workflows compile to separate StateGraphs (independent module)

Security: This module never reads user_id from args — it is set via contextvars
by gateway/runtime.py after all 3 security gates pass.
"""
from langchain_core.messages import BaseMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.state.types import BlitzState
from core.config import get_llm

import structlog

logger = structlog.get_logger(__name__)


async def _master_node(state: BlitzState) -> dict[str, list[BaseMessage]]:
    """
    Call blitz/master LLM with current conversation messages and return response.

    Uses get_llm() — never a direct provider SDK. The LiteLLM proxy routes
    'blitz/master' to the configured primary (Ollama/Qwen2.5) or fallback (Claude Sonnet).
    """
    llm = get_llm("blitz/master")
    response = await llm.ainvoke(state["messages"])
    logger.info("master_agent_response", content_length=len(str(response.content)))
    return {"messages": [response]}


def _route_after_master(state: BlitzState) -> str:
    """
    Routing conditional after master_agent node.

    Phase 2: always routes to END (no sub-agents yet).
    Phase 3: inspect state['route_to'] field to delegate to sub-agent nodes
             (e.g., 'email_agent', 'calendar_agent'). Add those edges to the
             graph in create_master_graph() when sub-agents are implemented.

    Returns the name of the next node (or END).
    """
    # Phase 2 stub — always terminate. Phase 3 replaces this logic.
    route_to = state.get("route_to")  # type: ignore[attr-defined]
    if route_to:
        logger.debug("master_agent_routing", route_to=route_to)
        # Phase 3 sub-agent edges will be wired here; return route_to once added.
        # For now, fall through to END even if route_to is set.
    return END


def create_master_graph() -> CompiledStateGraph:
    """
    Build and compile the master agent StateGraph.

    Returns a compiled graph ready for CopilotKit streaming or direct invocation.
    Call once at startup and reuse — LangGraph compilation is expensive.

    Phase 2 graph topology:
        START → master_agent → [_route_after_master] → END

    The routing conditional is a stub in Phase 2 (always → END).
    Phase 3 adds sub-agent edges from master_agent without restructuring this graph.
    """
    graph = StateGraph(BlitzState)
    graph.add_node("master_agent", _master_node)
    graph.set_entry_point("master_agent")
    # Routing conditional: always END in Phase 2; Phase 3 adds sub-agent branches
    graph.add_conditional_edges(
        "master_agent",
        _route_after_master,
        {END: END},  # Phase 3: extend this dict with sub-agent node names
    )
    return graph.compile()
