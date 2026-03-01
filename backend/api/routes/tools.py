"""
POST /api/tools/call — Universal tool execution endpoint for UI-initiated calls.
Enforces all 3 security gates (JWT via Depends, RBAC, Tool ACL).
Executes tool via mcp.registry.call_mcp_tool() for MCP tools — no LangGraph, no SSE streaming.
This is the backend counterpart of the useMcpTool frontend hook.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from core.models.user import UserContext
from security.deps import get_current_user, get_user_db

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolCallRequest(BaseModel):
    tool: str
    params: dict[str, Any] = {}


class ToolCallResponse(BaseModel):
    result: Any
    success: bool
    error: str | None = None


@router.post("/call")
async def call_tool(
    body: ToolCallRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> ToolCallResponse:
    """
    Execute a registered tool (backend or MCP) via the tool registry.

    Gate 1: JWT validated by Depends(get_current_user).
    Gate 2 + Gate 3: enforced inside call_mcp_tool() for MCP tools.

    Only MCP tools are supported in Phase 3. Backend tool direct execution
    is not yet implemented (returns 501).
    """
    from gateway.tool_registry import get_tool
    from mcp.registry import call_mcp_tool

    tool_def = await get_tool(body.tool, session)
    if tool_def is None:
        raise HTTPException(
            status_code=404, detail=f"Tool '{body.tool}' not registered"
        )

    logger.info(
        "tool_call_request",
        tool=body.tool,
        user_id=str(user["user_id"]),
    )

    # Route to appropriate executor
    if tool_def.get("mcp_server"):
        # MCP tool: call_mcp_tool enforces Gate 2 (RBAC) + Gate 3 (ACL) internally
        result = await call_mcp_tool(body.tool, body.params, user, session)
        return ToolCallResponse(
            result=result.get("result"),
            success=result.get("success", True),
            error=result.get("error"),
        )
    else:
        # Backend tool direct execution — not yet implemented in Phase 3
        raise HTTPException(
            status_code=501,
            detail="Backend tool direct execution not yet implemented",
        )
