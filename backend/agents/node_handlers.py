"""
Node handler registry for workflow execution.

Each handler is an async function with signature:
    async def handler(config: dict[str, Any], state: WorkflowState) -> Any

The handler receives:
  - config: the node's config dict from definition_json (e.g. {"tool_name": "fetch_email"})
  - state:  the current WorkflowState

It returns the node's output, which the compiler wraps in a state update:
    {"node_outputs": {node_id: result}, "current_output": result}

Stubs (04-02): agent_node and tool_node return mock output.
Full wiring (04-03): replaced with real sub-agent invocation and MCP tool calls.
"""
from typing import Any, Callable

import structlog

from agents.condition_evaluator import evaluate_condition
from agents.workflow_state import WorkflowState

logger = structlog.get_logger(__name__)

# Type alias for node handler functions
NodeHandler = Callable[[dict[str, Any], WorkflowState], Any]


# ── Trigger node ───────────────────────────────────────────────────────────────

async def _handle_trigger_node(config: dict[str, Any], state: WorkflowState) -> Any:
    """
    Entry point node — no execution logic.
    Passes current_output through so webhook payloads flow into the graph.
    """
    return state.get("current_output")


# ── Agent node ────────────────────────────────────────────────────────────────

async def _handle_agent_node(config: dict[str, Any], state: WorkflowState) -> Any:
    """
    Invoke a named sub-agent.

    Config fields:
      agent:       one of "email_agent", "calendar_agent", "project_agent"
      instruction: free-text instruction passed to the sub-agent

    04-02 stub: returns a structured mock so the compiler can be tested end-to-end.
    04-03: replaced with real sub-agent dispatch.
    """
    agent_name = config.get("agent", "email_agent")
    instruction = config.get("instruction", "")
    logger.info(
        "agent_node_invoked",
        agent=agent_name,
        instruction=instruction[:80],
        user_id=str((state.get("user_context") or {}).get("user_id")),
    )
    # Stub — 04-03 wires real dispatch
    return {"agent": agent_name, "result": f"[stub] {instruction}", "success": True}


# ── Tool node ─────────────────────────────────────────────────────────────────

async def _handle_tool_node(config: dict[str, Any], state: WorkflowState) -> Any:
    """
    Call a registered tool through the tool registry.

    Config fields:
      tool_name: tool identifier (must be registered in gateway/tool_registry.py)
      params:    dict of tool parameters

    04-02 stub: looks up the tool definition and returns mock output.
    04-03: replaced with real MCP client invocation via mcp/registry.py.
    """
    from gateway.tool_registry import get_tool

    tool_name = config.get("tool_name", "")
    params = config.get("params", {})
    tool_def = get_tool(tool_name)

    if tool_def is None:
        logger.warning("tool_node_unknown_tool", tool_name=tool_name)
        return {"error": f"Tool '{tool_name}' not registered", "success": False}

    logger.info(
        "tool_node_invoked",
        tool=tool_name,
        user_id=str((state.get("user_context") or {}).get("user_id")),
    )
    # Stub — 04-03 wires real MCP invocation
    return {"tool": tool_name, "params": params, "result": "[stub]", "success": True, "count": 0}


# ── Condition node ────────────────────────────────────────────────────────────

async def _handle_condition_node(config: dict[str, Any], state: WorkflowState) -> bool:
    """
    Evaluate a sandboxed expression against current_output.

    Config fields:
      expression: e.g. "output.count > 0", "output.matched == true"

    Returns True or False. The compiler uses this return value to route
    the graph along the true_edge or false_edge.
    """
    expression = config.get("expression", "output.is_empty")
    return evaluate_condition(expression, state.get("current_output"))


# ── HITL approval node ────────────────────────────────────────────────────────

async def _handle_hitl_approval_node(config: dict[str, Any], state: WorkflowState) -> Any:
    """
    Pause graph execution and wait for human approval.

    Uses LangGraph's interrupt() mechanism. The graph state is saved to the
    AsyncPostgresSaver checkpointer. Execution resumes when
    POST /api/workflows/runs/{id}/approve is called, which sets
    hitl_result = "approved" in the state before re-invoking the graph.

    Config fields:
      message: prompt shown to the user in the canvas HITL node UI
    """
    from langgraph.types import interrupt

    message = config.get("message", "Please review and approve to continue.")

    # If resuming after approval, skip the interrupt and return the result
    if state.get("hitl_result") is not None:
        logger.info("hitl_resuming", hitl_result=state["hitl_result"])
        return {"hitl_result": state["hitl_result"], "approved": state["hitl_result"] == "approved"}

    # First pass: pause execution
    logger.info("hitl_pausing", message=message)
    result = interrupt({"message": message, "node_type": "hitl_approval"})
    return result


# ── Channel output node ───────────────────────────────────────────────────────

async def _handle_channel_output_node(config: dict[str, Any], state: WorkflowState) -> Any:
    """
    Send current_output to a delivery channel.

    Config fields:
      channel:  one of "telegram", "teams", "web"
      template: message template string, e.g. "Digest:\n{output}"

    04-02 stub: logs the send and returns success.
    04-03: wired to channels/gateway.py send_to_channel().
    """
    channel = config.get("channel", "web")
    template = config.get("template", "{output}")
    output = state.get("current_output")
    user_id = str((state.get("user_context") or {}).get("user_id", ""))

    # Render template — safe string format, not eval
    try:
        message = template.format(output=output)
    except (KeyError, ValueError):
        message = str(output)

    logger.info("channel_output_node_invoked", channel=channel, user_id=user_id)
    # Stub — 04-03 wires real channel dispatch
    return {"channel": channel, "message": message, "sent": True}


# ── Registry ──────────────────────────────────────────────────────────────────

HANDLER_REGISTRY: dict[str, NodeHandler] = {
    "trigger_node": _handle_trigger_node,
    "agent_node": _handle_agent_node,
    "tool_node": _handle_tool_node,
    "condition_node": _handle_condition_node,
    "hitl_approval_node": _handle_hitl_approval_node,
    "channel_output_node": _handle_channel_output_node,
}

# Alias for compatibility with PLAN.md which references NODE_HANDLER_REGISTRY
NODE_HANDLER_REGISTRY = HANDLER_REGISTRY


def get_handler(node_type: str) -> NodeHandler:
    """Look up a handler by node type. Raises ValueError for unknown types."""
    if node_type not in HANDLER_REGISTRY:
        raise ValueError(
            f"Unknown node type: {node_type!r}. "
            f"Registered types: {sorted(HANDLER_REGISTRY.keys())}"
        )
    return HANDLER_REGISTRY[node_type]
