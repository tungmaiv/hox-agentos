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
    elif tool_def.get("handler_type") == "openapi_proxy":
        # OpenAPI proxy tool: dispatch to external HTTP API via call_openapi_tool()
        # Gates 2+3 applied here (same pattern as call_mcp_tool does internally for MCP tools)
        import time as _time
        import uuid as _uuid

        from core.logging import get_audit_logger
        from core.models.mcp_server import McpServer
        from openapi_bridge.proxy import call_openapi_tool
        from security.acl import check_tool_acl
        from security.credentials import decrypt_token
        from security.rbac import has_permission
        from sqlalchemy import select as _select

        audit_logger = get_audit_logger()
        start_ms = int(_time.monotonic() * 1000)

        # Gate 2: RBAC — check each required permission
        for permission in tool_def.get("required_permissions", []):
            if not await has_permission(user, permission, session):
                elapsed = int(_time.monotonic() * 1000) - start_ms
                audit_logger.info(
                    "tool_call",
                    tool=body.tool,
                    user_id=str(user["user_id"]),
                    allowed=False,
                    duration_ms=elapsed,
                    gate="rbac",
                )
                raise HTTPException(
                    status_code=403, detail=f"Missing permission: {permission}"
                )

        # Gate 3: ACL — check tool-level ACL for this user
        allowed = await check_tool_acl(user["user_id"], body.tool, session)
        elapsed = int(_time.monotonic() * 1000) - start_ms
        audit_logger.info(
            "tool_call",
            tool=body.tool,
            user_id=str(user["user_id"]),
            allowed=allowed,
            duration_ms=elapsed,
            gate="acl",
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="Tool call denied by ACL")

        # Load and decrypt API key from the associated McpServer
        config_json = tool_def.get("config_json") or {}
        api_key: str | None = None

        mcp_server_id = tool_def.get("mcp_server_id")
        if mcp_server_id is not None:
            server_result = await session.execute(
                _select(McpServer).where(
                    McpServer.id == _uuid.UUID(mcp_server_id)
                )
            )
            server_row = server_result.scalar_one_or_none()
            if server_row is not None and server_row.auth_token:
                raw = server_row.auth_token
                iv = raw[:12]
                ciphertext = raw[12:]
                api_key = decrypt_token(ciphertext, iv)

        result = await call_openapi_tool(
            tool_config=config_json,
            arguments=body.params,
            api_key=api_key,
        )

        # Update last_seen_at (best-effort — don't fail the request on registry error)
        try:
            from gateway.tool_registry import update_tool_last_seen
            await update_tool_last_seen(body.tool, session)
        except Exception:
            pass

        is_error = result.get("error") is True
        return ToolCallResponse(
            result=result if not is_error else None,
            success=not is_error,
            error=result.get("detail") if is_error else None,
        )
    else:
        # Backend tool direct execution — not yet implemented for other handler types
        raise HTTPException(
            status_code=501,
            detail="Backend tool direct execution not yet implemented",
        )
