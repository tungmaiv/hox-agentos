"""
Project sub-agent node. Calls CRM via MCP — real data from mcp-crm mock server.
Uses call_mcp_tool() which enforces all 3 security gates.
"""
import re

import structlog
from langchain_core.messages import AIMessage, HumanMessage

from agents.state.types import BlitzState
from core.context import current_user_ctx
from core.db import get_session
from core.schemas.agent_outputs import ProjectStatusResult
from mcp.registry import call_mcp_tool

logger = structlog.get_logger(__name__)

_DEFAULT_PROJECT = "Project Alpha"


async def project_agent_node(state: BlitzState) -> dict:
    """
    Project sub-agent. Calls crm.get_project_status via MCP tool registry.
    Extracts project name from user message (falls back to default).
    On MCP failure: returns friendly error message.
    """
    # Extract project name from last user message
    last_user_msg = next(
        (m.content for m in reversed(state.get("messages", [])) if isinstance(m, HumanMessage)),
        "",
    )
    # Simple extraction: look for "Project X" pattern
    match = re.search(r"project\s+(\w+(?:\s+\w+)?)", str(last_user_msg), re.IGNORECASE)
    project_name = match.group(0).title() if match else _DEFAULT_PROJECT

    user = current_user_ctx.get(None)
    if user is None:
        logger.error("project_agent_no_user_context")
        ai_message = AIMessage(content="I couldn't access project data — authentication required.")
        return {"messages": [ai_message]}

    try:
        async with get_session() as session:
            try:
                result = await call_mcp_tool(
                    "crm.get_project_status",
                    {"project_name": project_name},
                    user,
                    session,
                )
            except Exception:
                await session.rollback()
                raise

        if not result.get("success"):
            error_msg = result.get("error", "Unknown error from CRM")
            logger.warning("project_agent_mcp_error", error=error_msg)
            ai_message = AIMessage(
                content=f"I couldn't reach the CRM for project data: {error_msg}"
            )
            return {"messages": [ai_message]}

        mcp_data = result["result"]
        output = ProjectStatusResult(
            project_name=mcp_data.get("project_name", project_name),
            status=mcp_data.get("status", "unknown"),
            owner=mcp_data.get("owner", "unknown"),
            progress_pct=int(mcp_data.get("progress_pct", 0)),
            last_update=mcp_data.get("last_update", ""),
        )
        ai_message = AIMessage(content=output.model_dump_json())
        return {"messages": [ai_message]}

    except Exception as exc:
        logger.error("project_agent_exception", error=str(exc))
        ai_message = AIMessage(
            content=(
                "I couldn't reach the CRM, but here's what I know: "
                "please try again or contact your admin."
            )
        )
        return {"messages": [ai_message]}
