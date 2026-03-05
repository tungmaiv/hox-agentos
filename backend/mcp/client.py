"""
HTTP+SSE MCP client.

One instance per server URL. Implements tools/list (discovery) and
tools/call (invocation) using MCP JSON-RPC over HTTP.

Note: The mock CRM server returns JSON directly (not SSE stream) —
both response modes are handled transparently since we just read
response.json().
"""
from typing import Any

import httpx
import structlog

from core.logging import timed

logger = structlog.get_logger(__name__)


class MCPClient:
    """
    HTTP+SSE MCP client. One instance per server URL.
    Implements tools/list + tools/call JSON-RPC.
    """

    def __init__(self, server_url: str, auth_token: str | None = None) -> None:
        self._base_url = server_url.rstrip("/")
        self._headers: dict[str, str] = {}
        if auth_token:
            self._headers["Authorization"] = f"Bearer {auth_token}"

    async def list_tools(self) -> list[dict[str, Any]]:
        """Call tools/list JSON-RPC. Returns list of tool definitions."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._base_url}/sse",
                json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json().get("result", {}).get("tools", [])

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Call tools/call JSON-RPC. Returns structured result."""
        server_name = self._base_url.split("://")[-1].split("/")[0]
        with timed(logger, "mcp_call", tool=tool_name, server=server_name):
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._base_url}/sse",
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {"name": tool_name, "arguments": arguments},
                        "id": 2,
                    },
                    headers=self._headers,
                )
                response.raise_for_status()
                result = response.json()
                if "error" in result:
                    logger.warning(
                        "mcp_tool_error", tool=tool_name, error=result["error"]
                    )
                    return {"error": result["error"]["message"], "success": False}
                return {"result": result.get("result"), "success": True}
