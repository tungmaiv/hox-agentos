# Phase 24-03: MCP Gateway Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone `mcp-gateway` Docker service that manages stdio-based MCP server processes via a pool, exposing them as HTTP+SSE endpoints. Also add OpenAPI-to-MCP auto-generation. Backend MCPClient routes stdio tool calls through the gateway.

**Architecture:** `infra/mcp-gateway/` is a FastAPI service. `ProcessPoolManager` maintains N worker processes per registered stdio server. `MCPInstaller` runs npm/uv installs at registration time. The backend's `MCPClient` gains a `GatewayMCPClient` for stdio-type servers. Builtin HTTP+SSE servers (crm, docs) are unaffected.

**Tech Stack:** Python 3.12, FastAPI, asyncio subprocess management, npm/uv as install backends, docker-compose.yml addition.

**Depends on:** Phase 24-02 (registry_entries table must exist — mcp_server entries drive pool config).

---

## Task 1: Create `infra/mcp-gateway/` Skeleton

**Files:**
- Create: `infra/mcp-gateway/main.py`
- Create: `infra/mcp-gateway/config.py`
- Create: `infra/mcp-gateway/pyproject.toml`
- Create: `infra/mcp-gateway/Dockerfile`

**Step 1: Create pyproject.toml**

```toml
# infra/mcp-gateway/pyproject.toml
[project]
name = "mcp-gateway"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "httpx>=0.27",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "structlog>=24.0",
    "asyncpg>=0.29",
    "sqlalchemy[asyncio]>=2.0",
]
```

**Step 2: Create config.py**

```python
# infra/mcp-gateway/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://blitz:blitz@postgres/blitz"
    default_pool_size: int = 2
    process_restart_delay_seconds: float = 5.0
    log_level: str = "info"

    model_config = {"env_file": ".env"}


settings = Settings()
```

**Step 3: Create main.py**

```python
# infra/mcp-gateway/main.py
"""
MCP Gateway — manages stdio MCP server processes and exposes them as HTTP+SSE.

Each registered stdio MCP server gets a pool of N worker processes.
Tool calls are dispatched round-robin to healthy processes in the pool.

Routes:
  GET  /health                     — liveness
  GET  /servers                    — list managed servers
  POST /servers/{name}/install     — install server (npm/uv)
  GET  /servers/{name}/sse         — HTTP+SSE endpoint (MCP protocol)
  POST /servers/{name}/pool/resize — resize process pool
"""
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from config import settings
from installer import MCPInstaller
from process_pool import ProcessPoolManager

logger = structlog.get_logger(__name__)

pool_manager = ProcessPoolManager(
    default_pool_size=settings.default_pool_size,
    restart_delay=settings.process_restart_delay_seconds,
)
installer = MCPInstaller()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start pool manager, load servers from DB on startup."""
    await pool_manager.start()
    yield
    await pool_manager.stop()


app = FastAPI(title="MCP Gateway", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy", "servers": list(pool_manager.servers.keys())}


@app.get("/servers")
async def list_servers() -> dict:
    return {
        "servers": [
            {
                "name": name,
                "pool_size": len(pool),
                "healthy": sum(1 for p in pool if p.is_alive),
            }
            for name, pool in pool_manager.servers.items()
        ]
    }


@app.post("/servers/{name}/install")
async def install_server(name: str, source: str, install_type: str = "npm") -> dict:
    """Install an MCP server package. install_type: 'npm' | 'pip'"""
    success, message = await installer.install(source, install_type)
    return {"name": name, "success": success, "message": message}


@app.get("/servers/{name}/sse")
async def server_sse(name: str, request_body: dict | None = None):
    """Proxy an MCP JSON-RPC call to a pooled stdio process."""
    process = await pool_manager.get_process(name)
    if not process:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"Server {name!r} not available")

    async def generate():
        response = await process.call(request_body or {})
        yield f"data: {response}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/servers/{name}/pool/resize")
async def resize_pool(name: str, size: int) -> dict:
    await pool_manager.resize(name, size)
    return {"name": name, "new_size": size}
```

**Step 4: Create Dockerfile**

```dockerfile
# infra/mcp-gateway/Dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Install uv for Python package management
RUN pip install uv --no-cache-dir

WORKDIR /app
COPY pyproject.toml .
RUN uv pip install --system -r pyproject.toml 2>/dev/null || pip install fastapi uvicorn httpx pydantic pydantic-settings structlog

COPY . .

EXPOSE 8010
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]
```

**Step 5: Commit**

```bash
git add infra/mcp-gateway/
git commit -m "feat(24-03): add mcp-gateway service skeleton"
```

---

## Task 2: Process Pool Manager

**Files:**
- Create: `infra/mcp-gateway/process_pool.py`

**Step 1: Write the process pool**

```python
# infra/mcp-gateway/process_pool.py
"""
ProcessPoolManager — manages pools of stdio MCP server processes.

Each server has a pool of N subprocess workers. Calls are dispatched
round-robin. Crashed processes are auto-restarted after restart_delay seconds.
"""
import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class StdioProcess:
    """A single stdio MCP server subprocess."""
    name: str
    command: list[str]
    process: asyncio.subprocess.Process | None = None
    is_alive: bool = False
    call_count: int = 0

    async def start(self) -> None:
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.is_alive = True
        logger.info("stdio_process_started", name=self.name, pid=self.process.pid)

    async def stop(self) -> None:
        if self.process and self.is_alive:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
            self.is_alive = False

    async def call(self, request: dict[str, Any]) -> str:
        """Send a JSON-RPC request and read the response."""
        if not self.process or not self.is_alive:
            raise RuntimeError(f"Process {self.name} is not alive")

        payload = json.dumps(request) + "\n"
        self.process.stdin.write(payload.encode())
        await self.process.stdin.drain()

        response_line = await asyncio.wait_for(
            self.process.stdout.readline(), timeout=30.0
        )
        self.call_count += 1
        return response_line.decode().strip()


class ProcessPoolManager:
    """Manages pools of stdio processes per server name."""

    def __init__(self, default_pool_size: int = 2, restart_delay: float = 5.0):
        self.default_pool_size = default_pool_size
        self.restart_delay = restart_delay
        # name -> list of StdioProcess
        self.servers: dict[str, list[StdioProcess]] = {}
        # name -> command template
        self._commands: dict[str, list[str]] = {}
        # round-robin cursor per server
        self._cursors: dict[str, int] = {}

    async def start(self) -> None:
        """Load server definitions and start all pools."""
        # Built-in catalog: Context7, Fetch, Filesystem
        builtin_servers = {
            "context7": ["npx", "-y", "@upstash/context7-mcp"],
            "fetch": ["uvx", "mcp-server-fetch"],
            "filesystem": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        }
        for name, command in builtin_servers.items():
            await self.register(name, command)

    async def stop(self) -> None:
        for pool in self.servers.values():
            for process in pool:
                await process.stop()

    async def register(self, name: str, command: list[str], pool_size: int | None = None) -> None:
        """Register a server and start its process pool."""
        size = pool_size or self.default_pool_size
        self._commands[name] = command
        self._cursors[name] = 0
        pool = []
        for _ in range(size):
            proc = StdioProcess(name=name, command=command)
            try:
                await proc.start()
                pool.append(proc)
            except Exception as exc:
                logger.warning("process_start_failed", name=name, error=str(exc))
        self.servers[name] = pool
        logger.info("pool_registered", name=name, size=len(pool))

    async def get_process(self, name: str) -> StdioProcess | None:
        """Return next healthy process (round-robin)."""
        pool = self.servers.get(name, [])
        alive = [p for p in pool if p.is_alive]
        if not alive:
            return None
        cursor = self._cursors.get(name, 0)
        process = alive[cursor % len(alive)]
        self._cursors[name] = (cursor + 1) % len(alive)
        return process

    async def resize(self, name: str, new_size: int) -> None:
        """Grow or shrink a server's pool."""
        pool = self.servers.get(name, [])
        command = self._commands.get(name)
        if not command:
            raise ValueError(f"Unknown server: {name!r}")

        current_size = len([p for p in pool if p.is_alive])
        if new_size > current_size:
            for _ in range(new_size - current_size):
                proc = StdioProcess(name=name, command=command)
                await proc.start()
                pool.append(proc)
        elif new_size < current_size:
            to_stop = [p for p in pool if p.is_alive][new_size:]
            for proc in to_stop:
                await proc.stop()
        logger.info("pool_resized", name=name, new_size=new_size)
```

**Step 2: Commit**

```bash
git add infra/mcp-gateway/process_pool.py
git commit -m "feat(24-03): add ProcessPoolManager for stdio MCP server processes"
```

---

## Task 3: MCPInstaller

**Files:**
- Create: `infra/mcp-gateway/installer.py`

**Step 1: Write the installer**

```python
# infra/mcp-gateway/installer.py
"""
MCPInstaller — installs MCP server packages at registration time.

Supports:
- npm (Node-based servers): installs globally via `npm install -g <package>`
- pip/uv (Python-based servers): installs via `uv tool install <package>`
"""
import asyncio

import structlog

logger = structlog.get_logger(__name__)


class MCPInstaller:
    async def install(self, source: str, install_type: str) -> tuple[bool, str]:
        """Install an MCP server package.

        Args:
            source: Package identifier (e.g. '@upstash/context7-mcp', 'mcp-server-fetch')
            install_type: 'npm' or 'pip'

        Returns:
            (success, message) tuple
        """
        if install_type == "npm":
            return await self._install_npm(source)
        elif install_type in ("pip", "uv"):
            return await self._install_pip(source)
        else:
            return False, f"Unknown install_type: {install_type!r}"

    async def _install_npm(self, package: str) -> tuple[bool, str]:
        return await self._run_command(["npm", "install", "-g", package])

    async def _install_pip(self, package: str) -> tuple[bool, str]:
        return await self._run_command(["uv", "tool", "install", package])

    async def _run_command(self, cmd: list[str]) -> tuple[bool, str]:
        logger.info("installing_package", command=cmd)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120.0)
            if proc.returncode == 0:
                logger.info("install_success", command=cmd)
                return True, stdout.decode().strip()
            else:
                msg = stderr.decode().strip()
                logger.warning("install_failed", command=cmd, stderr=msg)
                return False, msg
        except asyncio.TimeoutError:
            return False, "Installation timed out after 120 seconds"
        except Exception as exc:
            return False, str(exc)
```

**Step 2: Commit**

```bash
git add infra/mcp-gateway/installer.py
git commit -m "feat(24-03): add MCPInstaller for npm/pip MCP server packages"
```

---

## Task 4: Add to docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`
- Modify: `docker-compose.local.yml` (if exists for local overrides)

**Step 1: Add the service**

Open `docker-compose.yml`. Add the `mcp-gateway` service after the existing MCP services:

```yaml
  mcp-gateway:
    build: ./infra/mcp-gateway
    ports:
      - "8010:8010"
    environment:
      - DATABASE_URL=postgresql+asyncpg://blitz:${POSTGRES_PASSWORD}@postgres/blitz
      - DEFAULT_POOL_SIZE=2
      - LOG_LEVEL=info
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - blitz-net
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8010/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
```

**Step 2: Build and verify**

```bash
just build mcp-gateway
just up mcp-gateway
just logs mcp-gateway
```

Expected: service starts, `/health` returns `{"status": "healthy"}`.

```bash
curl http://localhost:8010/health
```

**Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(24-03): add mcp-gateway to docker-compose"
```

---

## Task 5: Backend `GatewayMCPClient`

**Files:**
- Create: `backend/mcp/gateway_client.py`
- Modify: `backend/mcp/client.py`

**Step 1: Write the gateway client**

```python
# backend/mcp/gateway_client.py
"""
GatewayMCPClient — routes tool calls to stdio-based MCP servers via mcp-gateway.

Builtin HTTP+SSE servers (crm, docs) still use the existing MCPClient directly.
Stdio servers registered in registry_entries use this client.
"""
import json
from typing import Any

import httpx
import structlog

from core.config import settings

logger = structlog.get_logger(__name__)

GATEWAY_URL = "http://mcp-gateway:8010"


class GatewayMCPClient:
    """Client for calling stdio MCP servers via the mcp-gateway service."""

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Call a tool on a stdio MCP server via the gateway.

        Args:
            server_name: Name of the registered server (e.g. 'context7')
            tool_name: MCP tool name (e.g. 'resolve-library-id')
            arguments: Tool arguments dict

        Returns:
            Tool result dict

        Raises:
            httpx.HTTPError: On network failure
            ValueError: On error response from gateway
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
            "id": 1,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(
                f"{GATEWAY_URL}/servers/{server_name}/sse",
                params={"request_body": json.dumps(payload)},
            )
            resp.raise_for_status()

        # Parse SSE response
        for line in resp.text.splitlines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if "error" in data:
                    raise ValueError(f"MCP error: {data['error']}")
                return data.get("result", {})

        raise ValueError("No data in gateway SSE response")
```

**Step 2: Update `backend/mcp/client.py` to route stdio servers through gateway**

Find where tool calls are dispatched in the existing MCP client. Add a check:

```python
# In the tool dispatch logic, before calling the HTTP+SSE server:
from core.models.registry_entry import RegistryEntry
from sqlalchemy import select

# Check if this server is a stdio-type (registered in registry as mcp_server with transport=stdio)
entry = await session.execute(
    select(RegistryEntry).where(
        RegistryEntry.type == "mcp_server",
        RegistryEntry.name == server_name,
    )
)
entry = entry.scalar_one_or_none()

if entry and entry.config.get("transport") == "stdio":
    from mcp.gateway_client import GatewayMCPClient
    gateway = GatewayMCPClient()
    return await gateway.call_tool(server_name, tool_name, arguments)
# else: use existing HTTP+SSE MCPClient as before
```

**Step 3: Write a test**

```python
# backend/tests/mcp/test_gateway_client.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_gateway_client_routes_to_gateway():
    from mcp.gateway_client import GatewayMCPClient

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_resp = AsyncMock()
        mock_resp.text = 'data: {"result": {"content": "ok"}}\n'
        mock_resp.raise_for_status = AsyncMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(
            return_value=AsyncMock(get=AsyncMock(return_value=mock_resp))
        )
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        client = GatewayMCPClient()
        result = await client.call_tool("context7", "resolve-library-id", {"libraryName": "react"})
        assert result == {"content": "ok"}
```

**Step 4: Run test**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/mcp/test_gateway_client.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/mcp/gateway_client.py backend/mcp/client.py \
        backend/tests/mcp/test_gateway_client.py
git commit -m "feat(24-03): add GatewayMCPClient for stdio MCP server routing"
```

---

## Task 6: OpenAPI-to-MCP Auto-Generation

**Files:**
- Modify: `infra/mcp-gateway/main.py`
- Create: `infra/mcp-gateway/openapi_bridge.py`

**Step 1: Write the OpenAPI bridge**

```python
# infra/mcp-gateway/openapi_bridge.py
"""
OpenAPI bridge — auto-generates MCP tool definitions from an OpenAPI spec URL.

Given a URL pointing to an OpenAPI 3.x spec, fetches and parses it, then
creates one MCP tool per operation. Tool calls are proxied to the REST API.
"""
import json
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


async def fetch_openapi_spec(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


def spec_to_mcp_tools(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert OpenAPI paths/operations to a list of MCP tool definitions."""
    tools = []
    base_url = ""
    if "servers" in spec and spec["servers"]:
        base_url = spec["servers"][0].get("url", "")

    for path, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            op_id = operation.get("operationId") or f"{method}_{path.replace('/', '_')}"
            tool = {
                "name": op_id,
                "description": operation.get("summary") or operation.get("description", ""),
                "method": method.upper(),
                "path": path,
                "base_url": base_url,
                "parameters": operation.get("parameters", []),
            }
            tools.append(tool)
    return tools


async def call_openapi_tool(
    tool_def: dict[str, Any],
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Execute an OpenAPI-backed MCP tool call."""
    url = tool_def["base_url"] + tool_def["path"]
    method = tool_def["method"]

    # Substitute path parameters
    for param in tool_def.get("parameters", []):
        if param.get("in") == "path":
            name = param["name"]
            if name in arguments:
                url = url.replace(f"{{{name}}}", str(arguments.pop(name)))

    async with httpx.AsyncClient(timeout=30.0) as client:
        if method in ("GET", "DELETE"):
            resp = await client.request(method, url, params=arguments)
        else:
            resp = await client.request(method, url, json=arguments)
        resp.raise_for_status()
        return resp.json()
```

**Step 2: Add registration endpoint to `main.py`**

```python
# Add to infra/mcp-gateway/main.py:
from openapi_bridge import fetch_openapi_spec, spec_to_mcp_tools

# In-memory store for OpenAPI bridge servers
_openapi_servers: dict[str, dict] = {}

@app.post("/servers/{name}/register-openapi")
async def register_openapi_server(name: str, spec_url: str) -> dict:
    """Register a new OpenAPI-backed MCP server from a spec URL."""
    spec = await fetch_openapi_spec(spec_url)
    tools = spec_to_mcp_tools(spec)
    _openapi_servers[name] = {"spec_url": spec_url, "tools": tools}
    return {"name": name, "tool_count": len(tools), "status": "registered"}
```

**Step 3: Write a test for spec parsing**

```python
# infra/mcp-gateway/tests/test_openapi_bridge.py
from openapi_bridge import spec_to_mcp_tools


def test_spec_to_mcp_tools_extracts_operations():
    spec = {
        "servers": [{"url": "https://api.example.com"}],
        "paths": {
            "/users": {
                "get": {
                    "operationId": "list_users",
                    "summary": "List all users",
                }
            },
            "/users/{id}": {
                "get": {
                    "operationId": "get_user",
                    "summary": "Get a user by ID",
                    "parameters": [{"in": "path", "name": "id"}],
                }
            },
        },
    }
    tools = spec_to_mcp_tools(spec)
    assert len(tools) == 2
    names = {t["name"] for t in tools}
    assert "list_users" in names
    assert "get_user" in names


def test_spec_to_mcp_tools_sets_base_url():
    spec = {
        "servers": [{"url": "https://api.example.com/v1"}],
        "paths": {"/ping": {"get": {"operationId": "ping"}}},
    }
    tools = spec_to_mcp_tools(spec)
    assert tools[0]["base_url"] == "https://api.example.com/v1"
```

**Step 4: Run tests from the gateway directory**

```bash
cd /home/tungmv/Projects/hox-agentos/infra/mcp-gateway
python -m pytest tests/ -v 2>/dev/null || python -m pytest tests/test_openapi_bridge.py -v
```

**Step 5: Commit**

```bash
git add infra/mcp-gateway/openapi_bridge.py infra/mcp-gateway/tests/
git commit -m "feat(24-03): add OpenAPI-to-MCP auto-generation bridge"
```

---

## Completion Check

```bash
# Gateway service is healthy
curl http://localhost:8010/health
# → {"status": "healthy", "servers": ["context7", "fetch", "filesystem"]}

# Backend tests still pass
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
