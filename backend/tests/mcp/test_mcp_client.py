"""TDD tests for MCPClient — httpx mock, no real server needed."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from mcp.client import MCPClient


@pytest.fixture
def client() -> MCPClient:
    return MCPClient(server_url="http://test-server:8001", auth_token="test-token")


@pytest.mark.asyncio
async def test_list_tools_returns_tool_definitions(client: MCPClient) -> None:
    """httpx mock returns valid tools/list response; client returns list."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "tools": [
                {"name": "get_project_status", "description": "Get project info"},
                {"name": "list_projects", "description": "List all projects"},
            ]
        },
    }

    with patch("mcp.client.httpx.AsyncClient") as mock_http_cls:
        mock_http = MagicMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http_cls.return_value = mock_http

        tools = await client.list_tools()

    assert len(tools) == 2
    assert tools[0]["name"] == "get_project_status"


@pytest.mark.asyncio
async def test_call_tool_returns_success_result(client: MCPClient) -> None:
    """Mock tools/call response; client returns {'result': ..., 'success': True}."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "project_name": "Project Alpha",
            "status": "active",
            "progress_pct": 65,
        },
    }

    with patch("mcp.client.httpx.AsyncClient") as mock_http_cls:
        mock_http = MagicMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http_cls.return_value = mock_http

        result = await client.call_tool(
            "get_project_status", {"project_name": "Project Alpha"}
        )

    assert result["success"] is True
    assert result["result"]["status"] == "active"


@pytest.mark.asyncio
async def test_call_tool_returns_error_on_mcp_error(client: MCPClient) -> None:
    """MCP error response; client returns {'error': ..., 'success': False}."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "id": 2,
        "error": {"code": -32602, "message": "Project not found"},
    }

    with patch("mcp.client.httpx.AsyncClient") as mock_http_cls:
        mock_http = MagicMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http_cls.return_value = mock_http

        result = await client.call_tool(
            "get_project_status", {"project_name": "Unknown"}
        )

    assert result["success"] is False
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_call_tool_raises_on_http_error(client: MCPClient) -> None:
    """Server returns 500; HTTPStatusError propagates."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server error", request=MagicMock(), response=MagicMock()
    )

    with patch("mcp.client.httpx.AsyncClient") as mock_http_cls:
        mock_http = MagicMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http_cls.return_value = mock_http

        with pytest.raises(httpx.HTTPStatusError):
            await client.call_tool("get_project_status", {})
