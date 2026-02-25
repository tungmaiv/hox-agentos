# backend/gateway/runtime.py
"""
CopilotKit runtime — wraps the LangGraph master agent for AG-UI streaming.

Architecture note (CopilotKit 0.1.54+):
  CopilotKitSDK is deprecated in favor of CopilotKitRemoteEndpoint.
  The integration uses add_fastapi_endpoint() from copilotkit.integrations.fastapi,
  but we need to enforce 3-gate security BEFORE CopilotKit handles the request.

Security architecture:
  The /api/copilotkit router enforces Gate 1 (JWT) via Depends(get_current_user).
  Gate 2 (RBAC 'chat') and Gate 3 (Tool ACL 'agents.chat') are checked inline.
  Only after all 3 gates pass does the request reach the CopilotKit handler.

Security invariant: user_id is NEVER accepted from the request body.
It is extracted from the validated JWT by get_current_user() dependency.

Frontend integration (02-03):
  The Next.js proxy route (frontend/src/app/api/copilotkit/route.ts) forwards
  requests to POST /api/copilotkit with the server-side Bearer token injected.
  Sub-paths (e.g. /api/copilotkit/agent/blitz_master) are handled by the
  catch-all route registered via add_fastapi_endpoint() on the secured sub-router.
"""
import json
import time
from typing import Any
from uuid import UUID

import structlog
from copilotkit import CopilotKitRemoteEndpoint, LangGraphAgent
from copilotkit.integrations.fastapi import handler as copilotkit_handler
from fastapi import APIRouter, Depends, HTTPException, Request

from agents.master_agent import create_master_graph
from core.context import current_conversation_id_ctx, current_user_ctx
from core.db import async_session
from core.models.user import UserContext
from security.acl import check_tool_acl, log_tool_call
from security.deps import get_current_user
from security.rbac import has_permission

logger = structlog.get_logger(__name__)

# Build graph once at module load — LangGraph compilation is expensive.
# CopilotKit holds a reference; the same compiled graph handles all requests.
_master_graph = create_master_graph()

_sdk = CopilotKitRemoteEndpoint(
    agents=[
        LangGraphAgent(
            name="blitz_master",
            description="Blitz AgentOS master conversational agent",
            graph=_master_graph,
        )
    ]
)

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
    },
)
async def copilotkit_endpoint(
    request: Request,
    user: UserContext = Depends(get_current_user),
) -> Any:
    """
    AG-UI entry point for CopilotKit (root endpoint).

    Security: identical 3-gate chain as /api/agents/chat.
    The JWT Authorization header is injected by the Next.js proxy route
    (frontend/src/app/api/copilotkit/route.ts) from the server-side session.
    Credentials never touch the browser.

    Extracts threadId from the CopilotKit request body and sets
    current_conversation_id_ctx so that memory nodes can scope DB operations
    to the correct conversation without arg threading.
    """
    start_ms = int(time.monotonic() * 1000)
    await _check_gates(user, start_ms)

    # Read body once — body stream can only be consumed once per request.
    body_bytes = await request.body()
    body: dict = {}
    if body_bytes:
        try:
            body = json.loads(body_bytes)
        except (json.JSONDecodeError, ValueError):
            body = {}

    # Extract threadId (conversation UUID) from CopilotKit AG-UI request body.
    # CopilotKit sends threadId as the conversation identifier for memory isolation.
    thread_id_raw = body.get("threadId") or body.get("thread_id")
    conversation_id: UUID | None = None
    if thread_id_raw:
        try:
            conversation_id = UUID(str(thread_id_raw))
        except (ValueError, AttributeError):
            logger.warning("invalid_thread_id", thread_id=thread_id_raw)

    # Set both contextvars before graph invocation; reset in finally block.
    user_token = current_user_ctx.set(user)
    conv_token = current_conversation_id_ctx.set(conversation_id) if conversation_id else None
    try:
        return await copilotkit_handler(request, _sdk)
    finally:
        current_user_ctx.reset(user_token)
        if conv_token is not None:
            current_conversation_id_ctx.reset(conv_token)


@router.api_route(
    "/copilotkit/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    responses={
        401: {"description": "Missing or invalid JWT"},
        403: {"description": "Insufficient permissions"},
    },
)
async def copilotkit_subpath_endpoint(
    request: Request,
    path: str,  # noqa: ARG001 — path is captured by FastAPI, used internally
    user: UserContext = Depends(get_current_user),
) -> Any:
    """
    AG-UI sub-path endpoints for CopilotKit (agent execution, state, etc.).

    CopilotKit routes:
      POST /api/copilotkit/agent/{name}         — execute agent (streaming)
      POST /api/copilotkit/agent/{name}/state   — get agent state
      POST /api/copilotkit/info                 — list available agents/actions
      POST /api/copilotkit/actions/execute      — execute action
      POST /api/copilotkit/agents/execute       — execute agent (v1 compat)

    All sub-paths enforce the same 3-gate security as the root endpoint.
    Also extracts threadId for conversation_id contextvar injection.
    """
    start_ms = int(time.monotonic() * 1000)
    await _check_gates(user, start_ms)

    # Read body once for threadId extraction.
    body_bytes = await request.body()
    body: dict = {}
    if body_bytes:
        try:
            body = json.loads(body_bytes)
        except (json.JSONDecodeError, ValueError):
            body = {}

    thread_id_raw = body.get("threadId") or body.get("thread_id")
    conversation_id: UUID | None = None
    if thread_id_raw:
        try:
            conversation_id = UUID(str(thread_id_raw))
        except (ValueError, AttributeError):
            logger.warning("invalid_thread_id", thread_id=thread_id_raw)

    user_token = current_user_ctx.set(user)
    conv_token = current_conversation_id_ctx.set(conversation_id) if conversation_id else None
    try:
        return await copilotkit_handler(request, _sdk)
    finally:
        current_user_ctx.reset(user_token)
        if conv_token is not None:
            current_conversation_id_ctx.reset(conv_token)
