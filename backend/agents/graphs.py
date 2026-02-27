"""
Workflow compiler — converts React Flow definition_json to a LangGraph StateGraph.

Entry point: compile_workflow_to_stategraph(definition_json, user_context)

The returned builder has no checkpointer attached. Callers must call:
    compiled = builder.compile(checkpointer=AsyncPostgresSaver(...))

This separation lets tests use MemorySaver while production uses AsyncPostgresSaver.

Compilation steps:
  1. Validate schema_version == "1.0"
  2. Topological sort nodes via edges (Kahn's algorithm)
  3. Look up each node type in node_handlers.HANDLER_REGISTRY
  4. Build StateGraph[WorkflowState]:
       - Regular nodes: add_node() + add_edge()
       - condition_node: add_conditional_edges() with true/false branches
       - Terminal nodes (no outgoing edges): add_edge(node_id, END)
  5. Set entry point from the first topologically sorted node
  6. Return the builder (not yet compiled)
"""
from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from agents.node_handlers import get_handler
from agents.workflow_state import WorkflowState

logger = structlog.get_logger(__name__)


def _extract_branch(edge: dict[str, Any]) -> str | None:
    """Return the branch label ("true"/"false") from either format:
    - data.branch   — legacy format used in tests and direct API callers
    - sourceHandle  — React Flow native format used by canvas and template JSON files
    Returns None for plain (non-conditional) edges.
    """
    return edge.get("data", {}).get("branch") or edge.get("sourceHandle") or None


def _topological_sort(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Return nodes in topological order using Kahn's algorithm.
    Nodes with no incoming edges come first (entry points / triggers).
    """
    node_map = {n["id"]: n for n in nodes}
    in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
    adj: dict[str, list[str]] = {n["id"]: [] for n in nodes}

    for edge in edges:
        src, tgt = edge["source"], edge["target"]
        adj.setdefault(src, []).append(tgt)
        in_degree[tgt] = in_degree.get(tgt, 0) + 1

    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    order: list[dict[str, Any]] = []

    while queue:
        nid = queue.pop(0)
        order.append(node_map[nid])
        for neighbor in adj.get(nid, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return order


def compile_workflow_to_stategraph(
    definition_json: dict[str, Any],
    user_context: dict[str, Any],
) -> StateGraph:
    """
    Compile a React Flow definition_json into a LangGraph StateGraph builder.

    Args:
        definition_json: React Flow-native workflow definition.
                         Must have schema_version: "1.0", nodes: [...], edges: [...].
        user_context:    Owner's identity dict (user_id, roles, etc).
                         Injected into WorkflowState at execution time.

    Returns:
        An uncompiled StateGraph builder. Call .compile(checkpointer=...) to get
        an executable graph.

    Raises:
        ValueError: If schema_version is wrong or a node type is unknown.
    """
    if definition_json.get("schema_version") != "1.0":
        raise ValueError(
            f"Unsupported schema_version: {definition_json.get('schema_version')!r}. "
            "Expected '1.0'."
        )

    nodes: list[dict[str, Any]] = definition_json.get("nodes", [])
    edges: list[dict[str, Any]] = definition_json.get("edges", [])

    if not nodes:
        # Empty workflow — return a no-op graph
        builder: StateGraph = StateGraph(WorkflowState)
        return builder

    # Validate all node types before building
    for node in nodes:
        get_handler(node["type"])  # raises ValueError for unknown types

    sorted_nodes = _topological_sort(nodes, edges)

    # Build adjacency: source_node_id → list of outgoing edges
    outgoing: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        outgoing.setdefault(edge["source"], []).append(edge)

    builder = StateGraph(WorkflowState)

    for node in sorted_nodes:
        node_id: str = node["id"]
        node_type: str = node["type"]
        node_config: dict[str, Any] = node.get("data", {}).get("config", {})

        # Build the LangGraph node function for this node.
        # Uses default argument capture to avoid closure-over-loop-variable bugs.
        def _make_node_fn(
            nid: str = node_id,
            ntype: str = node_type,
            cfg: dict[str, Any] = node_config,
        ):
            async def _node_fn(state: WorkflowState) -> dict[str, Any]:
                handler = get_handler(ntype)
                result = await handler(cfg, state)
                # Accumulate outputs — copy to avoid mutating shared state
                outputs = dict(state.get("node_outputs") or {})
                outputs[nid] = result
                return {"node_outputs": outputs, "current_output": result}

            _node_fn.__name__ = nid  # LangGraph uses __name__ for tracing
            return _node_fn

        builder.add_node(node_id, _make_node_fn())

    # Add edges
    for node in sorted_nodes:
        node_id = node["id"]
        node_type = node["type"]
        node_edges = outgoing.get(node_id, [])

        if not node_edges:
            # Terminal node — connect to END
            builder.add_edge(node_id, END)
            continue

        # Separate edges by branch label (supports both data.branch and sourceHandle formats)
        true_edges = [e for e in node_edges if _extract_branch(e) == "true"]
        false_edges = [e for e in node_edges if _extract_branch(e) == "false"]
        plain_edges = [e for e in node_edges if _extract_branch(e) not in ("true", "false")]

        if node_type == "condition_node" and (true_edges or false_edges):
            # Conditional routing based on current_output (bool result from condition handler)
            true_target = true_edges[0]["target"] if true_edges else END
            false_target = false_edges[0]["target"] if false_edges else END

            def _make_router(tt: str = true_target, ft: str = false_target):
                def _router(state: WorkflowState) -> str:
                    # current_output is the bool returned by _handle_condition_node
                    return tt if state.get("current_output") else ft
                return _router

            branch_map = {}
            if true_edges:
                branch_map[true_target] = true_target
            if false_edges:
                branch_map[false_target] = false_target
            if not true_edges:
                branch_map[END] = END
            if not false_edges:
                branch_map[END] = END

            builder.add_conditional_edges(node_id, _make_router(), branch_map)
        else:
            for edge in plain_edges:
                builder.add_edge(node_id, edge["target"])

    # Entry point: first node in topological order
    builder.set_entry_point(sorted_nodes[0]["id"])

    logger.info(
        "workflow_compiled",
        node_count=len(nodes),
        edge_count=len(edges),
    )
    return builder
