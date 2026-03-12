"""Stdio-transport MCP client for CLI-installed servers (Context7, Fetch, Filesystem).

Implements MCP JSON-RPC 2.0 over stdio transport using asyncio subprocess directly,
without depending on the installed mcp SDK. This avoids the package naming conflict
between backend/mcp/ (local package) and the installed mcp SDK.

Protocol:
- Launch subprocess with command + args
- Write JSON-RPC requests to stdin (newline-delimited)
- Read JSON-RPC responses from stdout
- tools/list → returns tools array
- tools/call → returns content array
"""
import asyncio
import json
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class StdioMCPError(Exception):
    """Raised when the MCP server returns an error response."""


class StdioMCPClient:
    """Subprocess-based MCP client using JSON-RPC 2.0 over stdio transport.

    Connects to an MCP server running as a subprocess (e.g., npx, python -m).
    Each method opens a fresh subprocess connection and closes it when done.
    Compatible with the MCP protocol spec — identical to what the mcp SDK provides.
    """

    def __init__(
        self,
        command: str,
        args: list[str],
        env: dict[str, str] | None = None,
    ) -> None:
        self._command = command
        self._args = args
        self._env = env

    async def _send_rpc(
        self,
        proc: asyncio.subprocess.Process,
        method: str,
        params: dict[str, Any] | None = None,
        request_id: int = 1,
    ) -> dict[str, Any]:
        """Send a JSON-RPC request and return the result dict."""
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        line = json.dumps(payload) + "\n"
        assert proc.stdin is not None
        proc.stdin.write(line.encode())
        await proc.stdin.drain()

        assert proc.stdout is not None
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                raise StdioMCPError("MCP server closed stdout unexpectedly")
            text = raw.decode().strip()
            if not text:
                continue
            resp = json.loads(text)
            # Skip notifications (no 'id') and match our request id
            if "id" in resp and resp["id"] == request_id:
                if "error" in resp:
                    raise StdioMCPError(f"MCP error: {resp['error']}")
                return resp.get("result", {})

    async def _run_session(
        self,
        coro_fn: Any,
    ) -> Any:
        """Launch subprocess, run coro_fn(proc), clean up."""
        proc = await asyncio.create_subprocess_exec(
            self._command,
            *self._args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
        )
        try:
            # MCP initialize handshake
            await self._send_rpc(proc, "initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "blitz-agent", "version": "1.0"},
            })
            # Send initialized notification
            notif = json.dumps({
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }) + "\n"
            assert proc.stdin is not None
            proc.stdin.write(notif.encode())
            await proc.stdin.drain()

            return await coro_fn(proc)
        finally:
            try:
                if proc.stdin and not proc.stdin.is_closing():
                    proc.stdin.close()
                proc.kill()
                await proc.wait()
            except Exception:
                pass

    async def list_tools(self) -> list[dict[str, Any]]:
        """Connect to the stdio MCP server and return its tool list as dicts."""

        async def _fetch(proc: asyncio.subprocess.Process) -> list[dict[str, Any]]:
            result = await self._send_rpc(proc, "tools/list", request_id=2)
            return result.get("tools", [])

        return await self._run_session(_fetch)

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Call a tool on the stdio MCP server.

        Raises asyncio.TimeoutError if the subprocess does not respond within
        the given timeout (default 30 seconds). Never hangs indefinitely.
        """

        async def _invoke(proc: asyncio.subprocess.Process) -> dict[str, Any]:
            return await self._send_rpc(
                proc,
                "tools/call",
                params={"name": tool_name, "arguments": arguments},
                request_id=2,
            )

        async def _timed_call() -> dict[str, Any]:
            return await self._run_session(_invoke)

        try:
            return await asyncio.wait_for(_timed_call(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                "stdio_mcp_timeout",
                command=self._command,
                tool=tool_name,
                timeout=timeout,
            )
            raise
