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

Sandbox routing (07-01): tools with sandbox_required=True are executed in
Docker containers via SandboxExecutor instead of MCP dispatch.
"""
import asyncio
import uuid
from collections.abc import Awaitable
from typing import Any, Callable

import structlog

from agents.condition_evaluator import evaluate_condition
from agents.workflow_state import WorkflowState
from core.db import async_session
from gateway.tool_registry import get_tool
from mcp.registry import call_mcp_tool
from sandbox.executor import SandboxExecutor
from sandbox.policies import DEFAULT_TIMEOUT

logger = structlog.get_logger(__name__)

# Module-level singleton — Docker client is created once at import time,
# not on every tool call. This avoids repeated socket connections and the
# overhead of constructing a new client for each sandbox execution.
_sandbox_executor = SandboxExecutor()

# Type alias for node handler functions
NodeHandler = Callable[[dict[str, Any], WorkflowState], Awaitable[Any]]


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
    Invoke a named sub-agent and return formatted text output.

    Config fields:
      agent:       one of "email_agent", "calendar_agent", "project_agent"
      instruction: free-text instruction passed to the sub-agent

    Dispatches to the real sub-agent function, extracts the AIMessage content,
    and formats it for human-readable channel output via format_for_channel().
    """
    # Lazy imports to avoid circular deps when node_handlers is loaded before subagents
    from agents.subagents.email_agent import email_agent_node
    from agents.subagents.calendar_agent import calendar_agent_node
    from agents.subagents.project_agent import project_agent_node
    from channels.gateway import format_for_channel
    from langchain_core.messages import AIMessage, HumanMessage

    AGENT_DISPATCH: dict[str, Any] = {
        "email_agent": email_agent_node,
        "calendar_agent": calendar_agent_node,
        "project_agent": project_agent_node,
    }

    agent_name = config.get("agent", "email_agent")
    instruction = config.get("instruction", "")
    logger.info(
        "agent_node_invoked",
        agent=agent_name,
        instruction=instruction[:80],
        user_id=str((state.get("user_context") or {}).get("user_id")),
    )

    agent_fn = AGENT_DISPATCH.get(agent_name)
    if not agent_fn:
        return {"agent": agent_name, "error": f"Unknown agent: {agent_name}", "success": False}

    try:
        # Build minimal BlitzState for sub-agent invocation
        mini_state: dict[str, Any] = {
            "messages": [HumanMessage(content=instruction or "Please provide a summary.")],
        }
        result = await agent_fn(mini_state)

        # Extract AI response content
        messages = result.get("messages", [])
        ai_content = next(
            (str(m.content) for m in messages if isinstance(m, AIMessage)),
            f"No response from {agent_name}",
        )

        # Format structured JSON for human-readable channel output
        formatted = format_for_channel(ai_content)
        return {"agent": agent_name, "result": formatted, "success": True}
    except Exception as exc:
        logger.error("agent_node_error", agent=agent_name, error=str(exc))
        return {"agent": agent_name, "error": str(exc), "success": False}


# ── Tool node ─────────────────────────────────────────────────────────────────

async def _handle_tool_node(config: dict[str, Any], state: WorkflowState) -> Any:
    """
    Call a registered MCP tool through all 3 security gates.

    Config fields:
      tool_name: tool identifier registered in gateway/tool_registry.py
      params:    dict of tool parameters passed as MCP arguments

    Security: delegates to mcp.registry.call_mcp_tool which enforces
    Gate 2 (RBAC) and Gate 3 (ACL). Gate 1 is satisfied because user_context
    was already validated by the workflow's owner JWT before execution.

    Returns the MCP tool result dict, or an error dict if the call fails.
    """
    from fastapi import HTTPException
    from core.models.user import UserContext

    tool_name = config.get("tool_name", "")
    params = config.get("params", {})

    # Open a DB session early so get_tool() can refresh the cache from the DB.
    # Passing an active session bypasses the 60s stale cache — critical for
    # sandbox routing decisions where a revoked sandbox permission must take
    # effect immediately rather than up to 60 seconds later.
    async with async_session() as session:
        async with session.begin():
            tool_meta = await get_tool(tool_name, session=session)
        if tool_meta is None:
            logger.warning("tool_node_unknown_tool", tool_name=tool_name)
            return {"error": f"Tool '{tool_name}' not registered", "success": False}

        # Sandbox routing: tools with sandbox_required=True are executed in Docker containers.
        # This applies to Canvas "Code Execution" nodes and any tool registered with
        # sandbox_required=True in gateway/tool_registry.py.
        if tool_meta.get("sandbox_required", False):
            code = params.get("code", "")
            language = params.get("language", "python")
            timeout = int(params.get("timeout", DEFAULT_TIMEOUT))
            # SandboxExecutor.execute() is synchronous (Docker SDK blocks).
            # Offload to the default thread-pool executor so the async event
            # loop is not blocked while the container runs.
            loop = asyncio.get_event_loop()
            sandbox_result = await loop.run_in_executor(
                None,
                lambda: _sandbox_executor.execute(code=code, language=language, timeout=timeout),
            )
            logger.info(
                "sandbox_dispatch",
                tool=tool_name,
                language=language,
                timed_out=sandbox_result.timed_out,
            )
            return {
                "stdout": sandbox_result.stdout,
                "stderr": sandbox_result.stderr,
                "exit_code": sandbox_result.exit_code,
                "timed_out": sandbox_result.timed_out,
                "success": not sandbox_result.timed_out and sandbox_result.exit_code == 0,
            }

        # Build UserContext from workflow state — user_id must be UUID
        raw_ctx = state.get("user_context") or {}
        try:
            user_uuid = uuid.UUID(str(raw_ctx.get("user_id", "")))
        except ValueError:
            return {"error": "Invalid user_id in workflow state", "success": False}

        user_ctx: UserContext = {
            "user_id": user_uuid,
            "email": str(raw_ctx.get("email", "")),
            "username": str(raw_ctx.get("username", "")),
            "roles": list(raw_ctx.get("roles", [])),
            "groups": list(raw_ctx.get("groups", [])),
        }

        try:
            result = await call_mcp_tool(
                tool_name=tool_name,
                arguments=params,
                user=user_ctx,
                db_session=session,
            )
            logger.info("tool_node_success", tool=tool_name, user_id=str(user_uuid))
            return result
        except HTTPException as exc:
            await session.rollback()
            logger.warning(
                "tool_node_denied",
                tool=tool_name,
                status_code=exc.status_code,
                detail=exc.detail,
            )
            return {"error": f"{exc.status_code}: {exc.detail}", "success": False}
        except Exception as exc:
            await session.rollback()
            logger.error("tool_node_error", tool=tool_name, error=str(exc))
            return {"error": str(exc), "success": False}


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
    Send current_output to a delivery channel via ChannelGateway.

    Config fields:
      channel:  one of "telegram", "whatsapp", "ms_teams", "web"
      template: message template string, e.g. "Digest:\n{output}"

    Web channel: returns result without sending (AG-UI handles web delivery).
    Other channels: resolves external_chat_id from channel_accounts table,
    then sends outbound via ChannelGateway.send_outbound().

    Raises ValueError if:
      - No user_id in workflow context
      - No linked channel account for the target channel type
    """
    from core.models.channel import ChannelAccount
    from sqlalchemy import and_, select

    channel = config.get("channel", "web")
    template = config.get("template", "{output}")
    output = state.get("current_output")
    user_context = state.get("user_context") or {}
    workflow_name = state.get("workflow_name", "")

    # Render template -- safe string format, not eval
    try:
        message = template.format(output=output)
    except (KeyError, ValueError):
        message = str(output)

    # Prefix with workflow name per locked decision
    if workflow_name:
        message = f"[{workflow_name}] {message}"

    logger.info(
        "channel_output_node_invoked",
        channel=channel,
        user_id=str(user_context.get("user_id", "")),
    )

    if channel == "web":
        return {"channel": channel, "message": message, "sent": True}

    # Resolve delivery target from channel_accounts table
    owner_user_id = user_context.get("user_id")
    if not owner_user_id:
        raise ValueError("No user_id in workflow context")

    uid = uuid.UUID(str(owner_user_id))
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(ChannelAccount).where(
                    and_(
                        ChannelAccount.user_id == uid,
                        ChannelAccount.channel == channel,
                        ChannelAccount.is_paired == True,  # noqa: E712
                    )
                )
            )
            account = result.scalar_one_or_none()

    if not account:
        raise ValueError(f"No linked {channel} account for user {owner_user_id}")

    # Build outbound message with resolved external_chat_id
    from api.routes.channels import get_channel_gateway
    from channels.models import InternalMessage

    gateway = get_channel_gateway()
    msg = InternalMessage(
        direction="outbound",
        channel=channel,
        external_user_id=account.external_user_id,
        external_chat_id=account.external_user_id,  # DM: chat_id == user_id
        text=message,
    )
    await gateway.send_outbound(msg)

    logger.info(
        "channel_output_delivered",
        channel=channel,
        user_id=str(owner_user_id),
        external_chat_id=account.external_user_id,
    )
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
