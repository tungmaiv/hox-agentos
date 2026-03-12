"""TDD tests for StdioMCPClient — mock asyncio subprocess, no real server needed."""
import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_rpc_response(
    result: dict[str, Any],
    request_id: int = 1,
) -> bytes:
    """Build a JSON-RPC response line."""
    resp = {"jsonrpc": "2.0", "id": request_id, "result": result}
    return (json.dumps(resp) + "\n").encode()


def _build_rpc_error(message: str, request_id: int = 1) -> bytes:
    """Build a JSON-RPC error response line."""
    resp = {"jsonrpc": "2.0", "id": request_id, "error": {"message": message}}
    return (json.dumps(resp) + "\n").encode()


def _make_fake_process(responses: list[bytes]) -> MagicMock:
    """Create a mock subprocess that returns given responses in order.

    Each call to stdout.readline() returns the next response in the list.
    After responses are exhausted, returns b'' (EOF).
    """
    proc = MagicMock()
    proc.kill = MagicMock()
    proc.wait = AsyncMock()

    # stdin
    stdin = MagicMock()
    stdin.write = MagicMock()
    stdin.drain = AsyncMock()
    stdin.is_closing = MagicMock(return_value=False)
    stdin.close = MagicMock()
    proc.stdin = stdin

    # stdout — readline() returns responses in order
    stdout = MagicMock()
    response_iter = iter(responses + [b""])
    stdout.readline = AsyncMock(side_effect=lambda: next(response_iter))
    proc.stdout = stdout

    return proc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tools_returns_dicts() -> None:
    """list_tools() returns list of tool dicts from MCP server response."""
    from mcp.stdio_client import StdioMCPClient

    client = StdioMCPClient(command="npx", args=["-y", "@upstash/context7-mcp@latest"])

    # MCP initialize response (id=1), then tools/list response (id=2)
    init_resp = _build_rpc_response(
        {"protocolVersion": "2024-11-05", "capabilities": {}}, request_id=1
    )
    tools_resp = _build_rpc_response(
        {
            "tools": [
                {"name": "get_context", "description": "Get library docs"},
                {"name": "list_docs", "description": "List available docs"},
            ]
        },
        request_id=2,
    )
    fake_proc = _make_fake_process([init_resp, tools_resp])

    with patch("mcp.stdio_client.asyncio.create_subprocess_exec", AsyncMock(return_value=fake_proc)):
        result = await client.list_tools()

    assert len(result) == 2
    assert result[0]["name"] == "get_context"
    assert result[1]["name"] == "list_docs"


@pytest.mark.asyncio
async def test_call_tool_timeout() -> None:
    """call_tool with timeout=0.1 raises asyncio.TimeoutError when server hangs."""
    from mcp.stdio_client import StdioMCPClient

    client = StdioMCPClient(command="npx", args=["-y", "@upstash/context7-mcp@latest"])

    # Make readline hang forever
    async def _slow_readline() -> bytes:
        await asyncio.sleep(10)
        return b""

    fake_proc = MagicMock()
    fake_proc.kill = MagicMock()
    fake_proc.wait = AsyncMock()
    stdin = MagicMock()
    stdin.write = MagicMock()
    stdin.drain = AsyncMock()
    stdin.is_closing = MagicMock(return_value=False)
    stdin.close = MagicMock()
    fake_proc.stdin = stdin
    fake_proc.stdout = MagicMock()
    fake_proc.stdout.readline = AsyncMock(side_effect=_slow_readline)

    with patch("mcp.stdio_client.asyncio.create_subprocess_exec", AsyncMock(return_value=fake_proc)):
        with pytest.raises(asyncio.TimeoutError):
            await client.call_tool("get_context", {"query": "test"}, timeout=0.1)


@pytest.mark.asyncio
async def test_call_tool_returns_result() -> None:
    """call_tool() returns dict containing 'content' key from MCP server."""
    from mcp.stdio_client import StdioMCPClient

    client = StdioMCPClient(command="npx", args=["-y", "@upstash/context7-mcp@latest"])

    init_resp = _build_rpc_response(
        {"protocolVersion": "2024-11-05", "capabilities": {}}, request_id=1
    )
    call_resp = _build_rpc_response(
        {"content": [{"type": "text", "text": "Library documentation for requests"}]},
        request_id=2,
    )
    fake_proc = _make_fake_process([init_resp, call_resp])

    with patch("mcp.stdio_client.asyncio.create_subprocess_exec", AsyncMock(return_value=fake_proc)):
        result = await client.call_tool("get_context", {"query": "test"})

    assert "content" in result
    assert result["content"][0]["text"] == "Library documentation for requests"
