# backend/gateway/runtime.py
"""
AG-UI runtime — wraps the LangGraph master agent for AG-UI streaming.

Architecture note (@copilotkitnext v1.51.4 / ag-ui-langgraph 0.0.25):
  @copilotkit/react-core v1.51.4 uses @copilotkitnext internally with
  runtimeTransport="single" (useSingleEndpoint=true). All requests go to
  POST /api/copilotkit as a JSON envelope: {"method": "<name>", "params": {...}, "body": {...}}.

  Supported methods:
    "info"       — return available agents (discovery / runtime sync)
    "agent/run"  — run an agent with RunAgentInput body, stream AG-UI events

Security architecture:
  Gate 1 (JWT): Depends(get_current_user) on the endpoint.
  Gate 2 (RBAC 'chat'): checked inline via has_permission().
  Gate 3 (Tool ACL 'agents.chat'): checked inline via check_tool_acl().
  Only after all 3 gates pass does the request reach the LangGraph agent.

Security invariant: user_id is NEVER accepted from the request body.
It is extracted from the validated JWT by get_current_user() dependency.

Frontend integration (02-03):
  The Next.js proxy (frontend/src/app/api/copilotkit/route.ts) forwards
  POST /api/copilotkit with the server-side Bearer token injected.
  Credentials never touch the browser.
"""
import time
from typing import Any
from uuid import UUID

import structlog
from ag_ui.core import RunAgentInput
from ag_ui.encoder import EventEncoder

# Import directly from submodule — copilotkit.__init__ imports CopilotKitMiddleware
# which requires langchain.agents.middleware (not available in our langchain version).
from copilotkit.langgraph_agui_agent import LangGraphAGUIAgent
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from agents.master_agent import create_master_graph
from core.context import current_conversation_id_ctx, current_user_ctx
from core.db import async_session
from core.models.user import UserContext
from security.acl import check_tool_acl, log_tool_call
from security.deps import get_current_user
from security.rbac import has_permission

logger = structlog.get_logger(__name__)

# Build graph once at module load — LangGraph compilation is expensive.
_master_graph = create_master_graph()

_agent = LangGraphAGUIAgent(
    name="blitz_master",
    description="Blitz AgentOS master conversational agent",
    graph=_master_graph,
)

# Runtime info response for the "info" method.
# Format expected by @copilotkitnext/core fetchRuntimeInfo():
#   { version, agents: { <agentId>: { description } }, audioFileTranscriptionEnabled }
_RUNTIME_INFO = {
    "version": "0.1.0",
    "agents": {
        "blitz_master": {
            "description": _agent.description,
        }
    },
    "audioFileTranscriptionEnabled": False,
}

router = APIRouter(prefix="/api", tags=["copilotkit"])


async def _check_gates(user: UserContext, start_ms: int) -> None:
    """
    Apply Gate 2 (RBAC) and Gate 3 (Tool ACL) for the CopilotKit endpoint.

    Raises HTTPException(403) if either gate denies access.
    Logs every attempt via audit logger regardless of outcome.

    Args:
        user: Authenticated UserContext from Gate 1 (get_current_user dependency).
        start_ms: Monotonic milliseconds at request start for duration tracking.
    """
    # Gate 2: RBAC — user must have 'chat' permission
    if not has_permission(user, "chat"):
        elapsed = int(time.monotonic() * 1000) - start_ms
        await log_tool_call(user["user_id"], "agents.chat", False, elapsed)
        raise HTTPException(status_code=403, detail="Permission denied")

    # Gate 3: Tool ACL — check per-user tool allowlist
    async with async_session() as session:
        allowed = await check_tool_acl(user["user_id"], "agents.chat", session)
    elapsed = int(time.monotonic() * 1000) - start_ms
    await log_tool_call(user["user_id"], "agents.chat", allowed, elapsed)

    if not allowed:
        raise HTTPException(status_code=403, detail="Permission denied by ACL")


@router.post(
    "/copilotkit",
    responses={
        401: {"description": "Missing or invalid JWT"},
        403: {"description": "Insufficient permissions"},
        400: {"description": "Invalid or missing method in request envelope"},
    },
)
async def copilotkit_endpoint(
    request: Request,
    user: UserContext = Depends(get_current_user),
) -> Any:
    """
    AG-UI single-route endpoint for @copilotkitnext v1.51.4.

    Request body format (JSON envelope):
      { "method": "info" }
        → Returns available agent registry (runtime sync / discovery).
      { "method": "agent/run", "params": {"agentId": "blitz_master"}, "body": <RunAgentInput> }
        → Streams AG-UI events (text, tool calls, state snapshots).

    Security: 3-gate chain (JWT → RBAC → Tool ACL).
    The JWT Authorization header is injected by the Next.js proxy route from
    the server-side session; credentials never touch the browser.

    Memory isolation: thread_id from RunAgentInput is mapped to conversation_id
    and injected via current_conversation_id_ctx so memory nodes scope all
    DB queries to the correct conversation without threading args through the graph.
    """
    start_ms = int(time.monotonic() * 1000)
    await _check_gates(user, start_ms)

    try:
        envelope = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    method = envelope.get("method")

    # ── info ──────────────────────────────────────────────────────────────
    if method == "info":
        return JSONResponse(content=_RUNTIME_INFO)

    # ── agent/run ─────────────────────────────────────────────────────────
    if method == "agent/run":
        params = envelope.get("params") or {}
        agent_id = params.get("agentId")
        if agent_id != _agent.name:
            raise HTTPException(
                status_code=404,
                detail=f"Agent '{agent_id}' not found. Available: ['{_agent.name}']",
            )

        body = envelope.get("body") or {}
        try:
            # Use model_validate (not **body) because the JS client sends camelCase
            # field names (threadId, runId, forwardedProps) and RunAgentInput uses
            # validate_by_alias=True with a camelCase alias generator.
            input_data = RunAgentInput.model_validate(body)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid RunAgentInput: {exc}") from exc

        # Map thread_id → UUID for conversation-scoped memory isolation.
        conversation_id: UUID | None = None
        if input_data.thread_id:
            try:
                conversation_id = UUID(str(input_data.thread_id))
            except (ValueError, AttributeError):
                logger.warning("invalid_thread_id", thread_id=input_data.thread_id)

        accept_header = request.headers.get("accept")
        encoder = EventEncoder(accept=accept_header)

        async def event_generator():
            # Set contextvars inside the generator so they're active when the
            # LangGraph nodes run (during streaming iteration by Starlette).
            user_token = current_user_ctx.set(user)
            conv_token = current_conversation_id_ctx.set(conversation_id) if conversation_id else None
            try:
                async for event in _agent.run(input_data):
                    yield encoder.encode(event)
            finally:
                current_user_ctx.reset(user_token)
                if conv_token is not None:
                    current_conversation_id_ctx.reset(conv_token)

        return StreamingResponse(
            event_generator(),
            media_type=encoder.get_content_type(),
        )

    # ── unknown method ─────────────────────────────────────────────────────
    raise HTTPException(
        status_code=400,
        detail=f"Unsupported method '{method}'. Supported: info, agent/run",
    )
