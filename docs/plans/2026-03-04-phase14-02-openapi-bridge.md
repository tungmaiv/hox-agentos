# Phase 14-02: OpenAPI Bridge Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable admins to connect any OpenAPI-described API as tools — parse the spec, select endpoints, register them as callable tools with an in-process HTTP proxy. All through the admin panel.

**Architecture:** New `backend/openapi_bridge/` module with four files: parser (fetches and parses OpenAPI 3.x), proxy (runtime HTTP dispatcher), service (registration logic), and routes (admin endpoints). Frontend gets a "Connect API" section in the admin panel. The `mcp_servers` table gets a new nullable `openapi_spec_url` column.

**Tech Stack:** FastAPI, httpx, PyYAML, SQLAlchemy async, Pydantic v2, structlog

---

### Task 1: Add openapi_spec_url column to mcp_servers

**Files:**
- Create: `backend/alembic/versions/019_ecosystem_capabilities.py`
- Modify: `backend/core/models/mcp_server.py` (add column)

**Step 1: Add column to ORM model**

In `backend/core/models/mcp_server.py`, after the `last_seen_at` column (around line 45), add:

```python
    openapi_spec_url: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Also add `Text` to the sqlalchemy imports if not already present.

**Step 2: Create migration 019**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
.venv/bin/alembic revision --autogenerate -m "ecosystem_capabilities"
```

Review the generated migration. It should contain:
- `op.add_column('mcp_servers', sa.Column('openapi_spec_url', sa.Text(), nullable=True))`

**Step 3: Commit**

```bash
git add backend/core/models/mcp_server.py backend/alembic/versions/019_*.py
git commit -m "feat(14-02): add openapi_spec_url column to mcp_servers"
```

---

### Task 2: Create OpenAPI parser

**Files:**
- Create: `backend/openapi_bridge/__init__.py`
- Create: `backend/openapi_bridge/schemas.py`
- Create: `backend/openapi_bridge/parser.py`

**Step 1: Create module init**

```python
# backend/openapi_bridge/__init__.py
```

**Step 2: Create schemas**

```python
# backend/openapi_bridge/schemas.py
"""Pydantic schemas for OpenAPI bridge."""
import uuid
from typing import Any

from pydantic import BaseModel


class ParameterInfo(BaseModel):
    """Describes a single OpenAPI parameter."""
    name: str
    location: str  # "path" | "query" | "header"
    required: bool
    schema_type: str  # "string" | "integer" | "boolean" | etc.
    description: str | None = None


class EndpointInfo(BaseModel):
    """Describes a single OpenAPI operation."""
    operation_id: str
    method: str  # "GET" | "POST" | "PUT" | "DELETE" | "PATCH"
    path: str
    summary: str | None = None
    description: str | None = None
    parameters: list[ParameterInfo] = []
    request_body_schema: dict[str, Any] | None = None
    deprecated: bool = False


class OpenAPIParseRequest(BaseModel):
    url: str


class OpenAPIParseResponse(BaseModel):
    title: str | None = None
    version: str | None = None
    base_url: str
    endpoints: list[EndpointInfo]


class EndpointSelection(BaseModel):
    """One endpoint the admin selected for registration."""
    operation_id: str
    method: str
    path: str


class OpenAPIRegisterRequest(BaseModel):
    spec_url: str
    base_url: str
    server_name: str
    display_name: str | None = None
    api_key: str | None = None
    endpoints: list[EndpointSelection]


class OpenAPIRegisterResponse(BaseModel):
    server_id: uuid.UUID
    tools_created: int
```

**Step 3: Create the parser**

```python
# backend/openapi_bridge/parser.py
"""Fetch and parse OpenAPI 3.x specifications."""
import re
from typing import Any

import httpx
import structlog
import yaml

from openapi_bridge.schemas import EndpointInfo, OpenAPIParseResponse, ParameterInfo

logger = structlog.get_logger(__name__)

_HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}


def _extract_schema_type(schema: dict[str, Any]) -> str:
    """Extract a human-readable type from a JSON Schema object."""
    if "type" in schema:
        return str(schema["type"])
    if "anyOf" in schema or "oneOf" in schema:
        return "union"
    if "$ref" in schema:
        ref = schema["$ref"]
        return ref.rsplit("/", 1)[-1] if "/" in ref else ref
    return "object"


def _resolve_ref(ref: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Resolve a $ref pointer within the spec (one level only)."""
    parts = ref.lstrip("#/").split("/")
    node = spec
    for part in parts:
        node = node.get(part, {})
    return node if isinstance(node, dict) else {}


def _extract_parameters(
    params: list[dict[str, Any]], spec: dict[str, Any]
) -> list[ParameterInfo]:
    """Convert OpenAPI parameter objects to ParameterInfo."""
    result = []
    for p in params:
        if "$ref" in p:
            p = _resolve_ref(p["$ref"], spec)
        schema = p.get("schema", {})
        result.append(ParameterInfo(
            name=p.get("name", ""),
            location=p.get("in", "query"),
            required=p.get("required", False),
            schema_type=_extract_schema_type(schema),
            description=p.get("description"),
        ))
    return result


def _make_operation_id(method: str, path: str) -> str:
    """Generate a fallback operationId from method + path."""
    clean = re.sub(r"[{}]", "", path)
    clean = re.sub(r"[^a-zA-Z0-9/]", "", clean)
    parts = [p for p in clean.split("/") if p]
    return f"{method}_{'_'.join(parts)}" if parts else f"{method}_root"


async def fetch_and_parse_openapi(url: str) -> OpenAPIParseResponse:
    """Fetch an OpenAPI spec URL and parse it into EndpointInfo list.

    Supports OpenAPI 3.0.x and 3.1.x in JSON or YAML format.
    Ignores deprecated operations.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    raw = resp.text

    # Parse as JSON first, fall back to YAML
    spec: dict[str, Any]
    if "json" in content_type or raw.lstrip().startswith("{"):
        import json
        spec = json.loads(raw)
    else:
        spec = yaml.safe_load(raw)

    if not isinstance(spec, dict):
        raise ValueError("Invalid OpenAPI spec: root must be an object")

    openapi_version = spec.get("openapi", "")
    if not openapi_version.startswith("3."):
        raise ValueError(f"Only OpenAPI 3.x is supported, got: {openapi_version}")

    info = spec.get("info", {})
    title = info.get("title")
    version = info.get("version")

    # Determine base URL from servers array
    servers = spec.get("servers", [])
    base_url = servers[0]["url"] if servers else ""

    # Extract endpoints from paths
    endpoints: list[EndpointInfo] = []
    paths = spec.get("paths", {})

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        # Path-level parameters (inherited by all operations)
        path_params = path_item.get("parameters", [])

        for method in _HTTP_METHODS:
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue

            if operation.get("deprecated", False):
                continue

            operation_id = operation.get("operationId") or _make_operation_id(method, path)

            # Merge path-level + operation-level parameters
            op_params = path_params + operation.get("parameters", [])
            parameters = _extract_parameters(op_params, spec)

            # Extract request body schema
            request_body_schema = None
            req_body = operation.get("requestBody", {})
            if isinstance(req_body, dict):
                content = req_body.get("content", {})
                json_content = content.get("application/json", {})
                schema = json_content.get("schema", {})
                if "$ref" in schema:
                    schema = _resolve_ref(schema["$ref"], spec)
                if schema:
                    request_body_schema = schema

            endpoints.append(EndpointInfo(
                operation_id=operation_id,
                method=method.upper(),
                path=path,
                summary=operation.get("summary"),
                description=operation.get("description"),
                parameters=parameters,
                request_body_schema=request_body_schema,
            ))

    logger.info(
        "openapi_spec_parsed",
        url=url,
        title=title,
        endpoints_count=len(endpoints),
    )

    return OpenAPIParseResponse(
        title=title,
        version=version,
        base_url=base_url,
        endpoints=endpoints,
    )
```

**Step 4: Commit**

```bash
git add backend/openapi_bridge/
git commit -m "feat(14-02): add OpenAPI parser with schema extraction"
```

---

### Task 3: Write parser tests

**Files:**
- Create: `backend/tests/test_openapi_parser.py`

**Step 1: Write tests**

```python
# backend/tests/test_openapi_parser.py
"""Tests for OpenAPI spec parser."""
import json

import pytest
import httpx
from unittest.mock import AsyncMock, patch

from openapi_bridge.parser import fetch_and_parse_openapi, _make_operation_id


# ── Sample OpenAPI 3.0 spec ────────────────────────────────────────────

SAMPLE_SPEC_30 = {
    "openapi": "3.0.3",
    "info": {"title": "Pet Store", "version": "1.0.0"},
    "servers": [{"url": "https://api.petstore.io/v1"}],
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                    }
                ],
            },
            "post": {
                "operationId": "createPet",
                "summary": "Create a pet",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                },
                            }
                        }
                    }
                },
            },
        },
        "/pets/{petId}": {
            "get": {
                "operationId": "showPetById",
                "summary": "Info for a specific pet",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
            },
            "delete": {
                "operationId": "deletePet",
                "summary": "Delete a pet",
                "deprecated": True,
            },
        },
    },
}


def _mock_response(spec: dict) -> httpx.Response:
    """Build a mock httpx.Response with JSON content."""
    return httpx.Response(
        200,
        json=spec,
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "https://example.com/spec"),
    )


@pytest.mark.asyncio
async def test_parse_openapi_30():
    """Parses a standard OpenAPI 3.0 spec correctly."""
    with patch("openapi_bridge.parser.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.get.return_value = _mock_response(SAMPLE_SPEC_30)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await fetch_and_parse_openapi("https://example.com/spec.json")

    assert result.title == "Pet Store"
    assert result.base_url == "https://api.petstore.io/v1"
    # 3 endpoints: listPets, createPet, showPetById (deletePet is deprecated)
    assert len(result.endpoints) == 3

    list_pets = next(e for e in result.endpoints if e.operation_id == "listPets")
    assert list_pets.method == "GET"
    assert list_pets.path == "/pets"
    assert len(list_pets.parameters) == 1
    assert list_pets.parameters[0].name == "limit"
    assert list_pets.parameters[0].location == "query"

    create_pet = next(e for e in result.endpoints if e.operation_id == "createPet")
    assert create_pet.request_body_schema is not None
    assert create_pet.request_body_schema["type"] == "object"


@pytest.mark.asyncio
async def test_parse_rejects_openapi_2():
    """Rejects OpenAPI 2.x (Swagger) specs."""
    spec = {"swagger": "2.0", "info": {"title": "Old"}, "paths": {}}
    with patch("openapi_bridge.parser.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.get.return_value = _mock_response(spec)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        with pytest.raises(ValueError, match="Only OpenAPI 3.x"):
            await fetch_and_parse_openapi("https://example.com/old.json")


@pytest.mark.asyncio
async def test_deprecated_endpoints_excluded():
    """Deprecated operations are skipped."""
    with patch("openapi_bridge.parser.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.get.return_value = _mock_response(SAMPLE_SPEC_30)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await fetch_and_parse_openapi("https://example.com/spec.json")

    op_ids = [e.operation_id for e in result.endpoints]
    assert "deletePet" not in op_ids


def test_make_operation_id():
    """Fallback operationId generation from method + path."""
    assert _make_operation_id("get", "/pets") == "get_pets"
    assert _make_operation_id("post", "/pets/{petId}/toys") == "post_pets_petId_toys"
    assert _make_operation_id("get", "/") == "get_root"
```

**Step 2: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_openapi_parser.py -v
```

Expected: 4 PASSED

**Step 3: Commit**

```bash
git add backend/tests/test_openapi_parser.py
git commit -m "test(14-02): add OpenAPI parser unit tests"
```

---

### Task 4: Create the runtime proxy

**Files:**
- Create: `backend/openapi_bridge/proxy.py`

**Step 1: Write the proxy module**

```python
# backend/openapi_bridge/proxy.py
"""
Runtime HTTP proxy for OpenAPI-bridged tools.

When a tool with handler_type='openapi_proxy' is dispatched, this module
builds and executes the actual HTTP request against the external API.
"""
import re
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


async def call_openapi_tool(
    config: dict[str, Any],
    arguments: dict[str, Any],
    api_key: str | None = None,
) -> dict[str, Any]:
    """Execute an OpenAPI tool call by proxying to the external API.

    Args:
        config: Tool's config_json containing method, path, base_url, parameters.
        arguments: Tool call arguments from the agent.
        api_key: Decrypted API key (or None for unauthenticated APIs).

    Returns:
        dict with "success" bool and "result" or "error" key.
    """
    method = config["method"]
    path_template = config["path"]
    base_url = config["base_url"].rstrip("/")
    parameters = config.get("parameters", [])

    # Substitute path parameters
    path = path_template
    for param in parameters:
        if param.get("location") == "path" and param["name"] in arguments:
            path = path.replace(f"{{{param['name']}}}", str(arguments[param["name"]]))

    url = f"{base_url}{path}"

    # Build query params
    query_params: dict[str, str] = {}
    for param in parameters:
        if param.get("location") == "query" and param["name"] in arguments:
            query_params[param["name"]] = str(arguments[param["name"]])

    # Build headers
    headers: dict[str, str] = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    for param in parameters:
        if param.get("location") == "header" and param["name"] in arguments:
            headers[param["name"]] = str(arguments[param["name"]])

    # Build request body (everything not consumed by path/query/header params)
    param_names = {p["name"] for p in parameters}
    body_args = {k: v for k, v in arguments.items() if k not in param_names}
    json_body = body_args if body_args and method in ("POST", "PUT", "PATCH") else None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method=method,
                url=url,
                params=query_params or None,
                headers=headers,
                json=json_body,
            )

        if resp.status_code >= 400:
            logger.warning(
                "openapi_proxy_error",
                url=url,
                status=resp.status_code,
                body=resp.text[:500],
            )
            return {
                "success": False,
                "error": f"HTTP {resp.status_code}: {resp.text[:500]}",
            }

        # Try to parse as JSON, fall back to text
        try:
            result = resp.json()
        except Exception:
            result = resp.text

        return {"success": True, "result": result}

    except httpx.TimeoutException:
        return {"success": False, "error": f"Timeout calling {url}"}
    except httpx.HTTPError as exc:
        return {"success": False, "error": f"HTTP error: {exc}"}
```

**Step 2: Commit**

```bash
git add backend/openapi_bridge/proxy.py
git commit -m "feat(14-02): add OpenAPI runtime proxy for tool dispatch"
```

---

### Task 5: Write proxy tests

**Files:**
- Create: `backend/tests/test_openapi_proxy.py`

**Step 1: Write tests**

```python
# backend/tests/test_openapi_proxy.py
"""Tests for OpenAPI runtime proxy."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from openapi_bridge.proxy import call_openapi_tool


def _make_config(method: str = "GET", path: str = "/pets", base_url: str = "https://api.example.com", parameters: list | None = None):
    return {
        "method": method,
        "path": path,
        "base_url": base_url,
        "parameters": parameters or [],
    }


def _mock_response(status: int = 200, json_data: dict | None = None, text: str = ""):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.text = text or ""
    if json_data is not None:
        resp.json.return_value = json_data
        resp.text = str(json_data)
    else:
        resp.json.side_effect = ValueError("Not JSON")
    return resp


@pytest.mark.asyncio
async def test_simple_get():
    """GET with no parameters."""
    config = _make_config()
    with patch("openapi_bridge.proxy.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request.return_value = _mock_response(200, {"pets": []})
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await call_openapi_tool(config, {})

    assert result["success"] is True
    assert result["result"] == {"pets": []}
    instance.request.assert_called_once()
    call_kwargs = instance.request.call_args
    assert call_kwargs.kwargs["method"] == "GET"
    assert call_kwargs.kwargs["url"] == "https://api.example.com/pets"


@pytest.mark.asyncio
async def test_path_param_substitution():
    """Path parameters are substituted into the URL."""
    config = _make_config(
        path="/pets/{petId}",
        parameters=[{"name": "petId", "location": "path"}],
    )
    with patch("openapi_bridge.proxy.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request.return_value = _mock_response(200, {"name": "Fido"})
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await call_openapi_tool(config, {"petId": "abc-123"})

    assert result["success"] is True
    assert "pets/abc-123" in instance.request.call_args.kwargs["url"]


@pytest.mark.asyncio
async def test_query_params():
    """Query parameters are passed correctly."""
    config = _make_config(
        parameters=[{"name": "limit", "location": "query"}],
    )
    with patch("openapi_bridge.proxy.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request.return_value = _mock_response(200, [])
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await call_openapi_tool(config, {"limit": "10"})

    call_kwargs = instance.request.call_args.kwargs
    assert call_kwargs["params"] == {"limit": "10"}


@pytest.mark.asyncio
async def test_post_with_body():
    """POST sends remaining args as JSON body."""
    config = _make_config(method="POST")
    with patch("openapi_bridge.proxy.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request.return_value = _mock_response(201, {"id": "new"})
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await call_openapi_tool(config, {"name": "Fido", "breed": "Lab"})

    call_kwargs = instance.request.call_args.kwargs
    assert call_kwargs["json"] == {"name": "Fido", "breed": "Lab"}


@pytest.mark.asyncio
async def test_api_key_header():
    """API key is sent as Bearer token."""
    config = _make_config()
    with patch("openapi_bridge.proxy.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request.return_value = _mock_response(200, {})
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        await call_openapi_tool(config, {}, api_key="secret-key")

    headers = instance.request.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer secret-key"


@pytest.mark.asyncio
async def test_error_response():
    """Non-2xx responses return error."""
    config = _make_config()
    with patch("openapi_bridge.proxy.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request.return_value = _mock_response(404, text="Not Found")
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await call_openapi_tool(config, {})

    assert result["success"] is False
    assert "404" in result["error"]
```

**Step 2: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_openapi_proxy.py -v
```

Expected: 6 PASSED

**Step 3: Commit**

```bash
git add backend/tests/test_openapi_proxy.py
git commit -m "test(14-02): add OpenAPI proxy unit tests"
```

---

### Task 6: Create service and admin routes

**Files:**
- Create: `backend/openapi_bridge/service.py`
- Create: `backend/openapi_bridge/routes.py`

**Step 1: Write the service**

```python
# backend/openapi_bridge/service.py
"""
Business logic for registering OpenAPI endpoints as tools.
"""
import os
import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.mcp_server import McpServer
from core.models.tool_definition import ToolDefinition
from gateway.tool_registry import invalidate_tool_cache
from openapi_bridge.schemas import EndpointSelection, OpenAPIParseResponse

logger = structlog.get_logger(__name__)


def _build_tool_config(
    base_url: str, endpoint: EndpointSelection, parsed: OpenAPIParseResponse
) -> dict[str, Any]:
    """Build config_json for a tool from the parsed spec endpoint."""
    # Find the full EndpointInfo from parsed response
    full_ep = next(
        (e for e in parsed.endpoints if e.operation_id == endpoint.operation_id),
        None,
    )

    parameters = []
    if full_ep:
        parameters = [
            {
                "name": p.name,
                "location": p.location,
                "required": p.required,
                "schema_type": p.schema_type,
                "description": p.description,
            }
            for p in full_ep.parameters
        ]

    return {
        "method": endpoint.method,
        "path": endpoint.path,
        "base_url": base_url,
        "parameters": parameters,
        "request_body_schema": full_ep.request_body_schema if full_ep else None,
    }


def _build_input_schema(
    config: dict[str, Any],
) -> dict[str, Any]:
    """Build JSON Schema for the tool's input from OpenAPI parameters."""
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param in config.get("parameters", []):
        properties[param["name"]] = {
            "type": param.get("schema_type", "string"),
            "description": param.get("description", ""),
        }
        if param.get("required"):
            required.append(param["name"])

    # Add request body properties if present
    body_schema = config.get("request_body_schema")
    if body_schema and "properties" in body_schema:
        for name, prop in body_schema["properties"].items():
            properties[name] = prop
        if "required" in body_schema:
            required.extend(body_schema["required"])

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required_permissions": ["chat"],
    }
    if required:
        schema["required"] = required

    return schema


async def register_openapi_endpoints(
    server_name: str,
    display_name: str | None,
    spec_url: str,
    base_url: str,
    api_key: str | None,
    endpoints: list[EndpointSelection],
    parsed: OpenAPIParseResponse,
    session: AsyncSession,
) -> tuple[uuid.UUID, int]:
    """Register selected OpenAPI endpoints as callable tools.

    Creates an mcp_servers row and tool_definitions rows.
    Returns (server_id, tools_created).
    """
    # Encrypt API key if provided (same pattern as mcp_servers.py route)
    encrypted_token: bytes | None = None
    if api_key:
        from security.credentials import encrypt_token
        encrypted_token = encrypt_token(api_key)

    # Create MCP server entry
    server = McpServer(
        name=server_name,
        display_name=display_name,
        url=base_url,
        openapi_spec_url=spec_url,
        auth_token=encrypted_token,
        status="active",
        is_active=True,
    )
    session.add(server)
    await session.flush()  # Get server.id

    # Create tool definitions
    tools_created = 0
    for ep in endpoints:
        config = _build_tool_config(base_url, ep, parsed)
        input_schema = _build_input_schema(config)

        # Tool name: server_name.operation_id
        tool_name = f"{server_name}.{ep.operation_id}"

        # Find summary from parsed endpoints
        full_ep = next(
            (e for e in parsed.endpoints if e.operation_id == ep.operation_id),
            None,
        )
        description = (full_ep.summary or full_ep.description or ep.operation_id) if full_ep else ep.operation_id

        tool = ToolDefinition(
            name=tool_name,
            display_name=f"{server_name}: {ep.operation_id}",
            description=description,
            version="1.0.0",
            handler_type="openapi_proxy",
            handler_module="openapi_bridge.proxy",
            handler_function="call_openapi_tool",
            mcp_server_id=server.id,
            sandbox_required=False,
            input_schema=input_schema,
            output_schema=None,
            status="active",
            is_active=True,
        )
        session.add(tool)
        tools_created += 1

    await session.commit()
    invalidate_tool_cache()

    logger.info(
        "openapi_endpoints_registered",
        server_name=server_name,
        server_id=str(server.id),
        tools_created=tools_created,
    )

    return server.id, tools_created
```

**Step 2: Write the routes**

```python
# backend/openapi_bridge/routes.py
"""
Admin API routes for OpenAPI bridge.

POST /api/admin/openapi/parse     — fetch and parse an OpenAPI spec
POST /api/admin/openapi/register  — register selected endpoints as tools
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.user import UserContext
from openapi_bridge.parser import fetch_and_parse_openapi
from openapi_bridge.schemas import (
    OpenAPIParseRequest,
    OpenAPIParseResponse,
    OpenAPIRegisterRequest,
    OpenAPIRegisterResponse,
)
from openapi_bridge.service import register_openapi_endpoints
from security.deps import get_current_user
from security.rbac import has_permission

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin/openapi", tags=["admin-openapi"])


async def _require_registry_manager(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2: require registry:manage permission."""
    if not await has_permission(user, "registry:manage", session):
        raise HTTPException(status_code=403, detail="Registry manage permission required")
    return user


@router.post("/parse", response_model=OpenAPIParseResponse)
async def parse_openapi_spec(
    body: OpenAPIParseRequest,
    user: UserContext = Depends(_require_registry_manager),
) -> OpenAPIParseResponse:
    """Fetch and parse an OpenAPI spec URL, returning available endpoints."""
    try:
        result = await fetch_and_parse_openapi(body.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("openapi_parse_failed", url=body.url, error=str(exc))
        raise HTTPException(status_code=502, detail=f"Failed to fetch or parse spec: {exc}")

    return result


@router.post("/register", response_model=OpenAPIRegisterResponse, status_code=201)
async def register_openapi(
    body: OpenAPIRegisterRequest,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> OpenAPIRegisterResponse:
    """Register selected OpenAPI endpoints as callable tools."""
    # Re-parse spec to get full endpoint details
    try:
        parsed = await fetch_and_parse_openapi(body.spec_url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to re-fetch spec: {exc}")

    # Validate selected endpoints exist in parsed spec
    parsed_ops = {e.operation_id for e in parsed.endpoints}
    for ep in body.endpoints:
        if ep.operation_id not in parsed_ops:
            raise HTTPException(
                status_code=422,
                detail=f"Operation '{ep.operation_id}' not found in spec",
            )

    try:
        server_id, tools_created = await register_openapi_endpoints(
            server_name=body.server_name,
            display_name=body.display_name,
            spec_url=body.spec_url,
            base_url=body.base_url,
            api_key=body.api_key,
            endpoints=body.endpoints,
            parsed=parsed,
            session=session,
        )
    except Exception as exc:
        logger.error("openapi_register_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Registration failed: {exc}")

    return OpenAPIRegisterResponse(server_id=server_id, tools_created=tools_created)
```

**Step 3: Register routes in main.py**

In `backend/main.py`, add the import and router registration:

After line 40 (`from gateway import runtime`), add:

```python
from openapi_bridge.routes import router as openapi_bridge_router
```

After the admin_credentials router include (around line 168), add:

```python
    # OpenAPI bridge — parse + register OpenAPI endpoints as tools (registry:manage)
    app.include_router(openapi_bridge_router)
```

**Step 4: Commit**

```bash
git add backend/openapi_bridge/service.py backend/openapi_bridge/routes.py backend/main.py
git commit -m "feat(14-02): add OpenAPI bridge service, routes, and main.py registration"
```

---

### Task 7: Integrate openapi_proxy dispatch into tool registry

**Files:**
- Modify: `backend/gateway/tool_registry.py` (the `_refresh_tool_cache` function, around line 60-87)

**Step 1: Update the cache builder to handle openapi_proxy handler_type**

The existing cache builder already reads `handler_type` into the cache dict (line 69). The `openapi_proxy` type needs the same treatment as `mcp` for server name derivation. In `_refresh_tool_cache`, the line:

```python
        if row.handler_type == "mcp" and "." in row.name:
```

Should become:

```python
        if row.handler_type in ("mcp", "openapi_proxy") and "." in row.name:
```

This ensures that openapi_proxy tools also get `mcp_server` populated for server-name lookup.

**Step 2: Also update the ToolDefinitionCreate schema to accept `openapi_proxy`**

In `backend/core/schemas/registry.py`, line 71, update the handler_type literal:

```python
    handler_type: Literal["backend", "mcp", "sandbox", "openapi_proxy"] = "backend"
```

And in the update schema (line 85):

```python
    handler_type: Literal["backend", "mcp", "sandbox", "openapi_proxy"] | None = None
```

**Step 3: Run full test suite**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: all tests pass

**Step 4: Commit**

```bash
git add backend/gateway/tool_registry.py backend/core/schemas/registry.py
git commit -m "feat(14-02): integrate openapi_proxy handler type into tool registry"
```

---

### Task 8: Write route-level tests

**Files:**
- Create: `backend/tests/api/test_openapi_bridge.py`

**Step 1: Write tests**

```python
# backend/tests/api/test_openapi_bridge.py
"""Route-level tests for OpenAPI bridge admin endpoints."""
import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db import Base, get_db
from core.models.mcp_server import McpServer  # noqa: F401
from core.models.tool_definition import ToolDefinition  # noqa: F401
from core.models.agent_definition import AgentDefinition  # noqa: F401
from core.models.artifact_permission import ArtifactPermission  # noqa: F401
from core.models.role_permission import RolePermission  # noqa: F401
from core.models.skill_definition import SkillDefinition  # noqa: F401
from core.models.user_artifact_permission import UserArtifactPermission  # noqa: F401
from core.models.user import UserContext
from main import app
from security.deps import get_current_user


def make_admin_ctx() -> UserContext:
    return UserContext(
        user_id=uuid4(),
        email="admin@blitz.local",
        username="admin_user",
        roles=["it-admin"],
        groups=["/it"],
    )


def make_employee_ctx() -> UserContext:
    return UserContext(
        user_id=uuid4(),
        email="user@blitz.local",
        username="user",
        roles=["employee"],
        groups=[],
    )


@pytest.fixture
def sqlite_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_setup())
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield factory
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def admin_client(sqlite_db) -> TestClient:
    app.dependency_overrides[get_current_user] = make_admin_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def employee_client(sqlite_db) -> TestClient:
    app.dependency_overrides[get_current_user] = make_employee_ctx
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


MOCK_PARSE_RESULT = {
    "title": "Test API",
    "version": "1.0",
    "base_url": "https://api.test.com",
    "endpoints": [
        {
            "operation_id": "listItems",
            "method": "GET",
            "path": "/items",
            "summary": "List items",
            "parameters": [],
            "request_body_schema": None,
            "deprecated": False,
        }
    ],
}


def test_parse_requires_admin(employee_client):
    """Employee cannot parse OpenAPI specs."""
    resp = employee_client.post("/api/admin/openapi/parse", json={"url": "https://example.com"})
    assert resp.status_code == 403


@patch("openapi_bridge.routes.fetch_and_parse_openapi")
def test_parse_success(mock_parse, admin_client):
    """Admin can parse an OpenAPI spec."""
    from openapi_bridge.schemas import OpenAPIParseResponse, EndpointInfo
    mock_parse.return_value = OpenAPIParseResponse(**MOCK_PARSE_RESULT)

    resp = admin_client.post("/api/admin/openapi/parse", json={"url": "https://example.com/spec"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Test API"
    assert len(data["endpoints"]) == 1


def test_register_requires_admin(employee_client):
    """Employee cannot register OpenAPI endpoints."""
    resp = employee_client.post("/api/admin/openapi/register", json={
        "spec_url": "https://example.com",
        "base_url": "https://api.test.com",
        "server_name": "test",
        "endpoints": [],
    })
    assert resp.status_code == 403


@patch("openapi_bridge.routes.fetch_and_parse_openapi")
@patch("openapi_bridge.service.encrypt_token", return_value=b"encrypted")
def test_register_creates_server_and_tools(mock_encrypt, mock_parse, admin_client, sqlite_db):
    """Register creates mcp_servers row + tool_definitions rows."""
    from openapi_bridge.schemas import OpenAPIParseResponse
    mock_parse.return_value = OpenAPIParseResponse(**MOCK_PARSE_RESULT)

    resp = admin_client.post("/api/admin/openapi/register", json={
        "spec_url": "https://example.com/spec",
        "base_url": "https://api.test.com",
        "server_name": "test_api",
        "api_key": "sk-123",
        "endpoints": [{"operation_id": "listItems", "method": "GET", "path": "/items"}],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["tools_created"] == 1
    assert "server_id" in data
```

**Step 2: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/api/test_openapi_bridge.py -v
```

Expected: 4 PASSED

**Step 3: Commit**

```bash
git add backend/tests/api/test_openapi_bridge.py
git commit -m "test(14-02): add OpenAPI bridge route-level tests"
```

---

### Task 9: Add frontend admin "Connect API" UI and proxy routes

**Files:**
- Create: `frontend/src/app/api/admin/openapi/parse/route.ts`
- Create: `frontend/src/app/api/admin/openapi/register/route.ts`
- Create: `frontend/src/app/admin/connect-api/page.tsx`
- Modify: `frontend/src/app/admin/layout.tsx` (add tab)

This task creates the admin UI for the OpenAPI bridge. The implementation should follow the patterns in existing admin pages — the catch-all proxy at `frontend/src/app/api/admin/[...path]/route.ts` should already handle `/api/admin/openapi/*` requests without needing dedicated proxy routes. Verify first by checking if the catch-all handles POST with JSON body correctly.

If the catch-all works, only the page component and layout tab need to be created. The page component should:

1. Have an input field for the OpenAPI spec URL and a "Parse" button
2. On parse success, display a table of endpoints with checkboxes
3. Have fields for server name, display name, and API key
4. A "Register" button that sends selected endpoints to the register endpoint
5. On success, show the number of tools created and redirect to MCP Servers tab

Follow the existing admin page patterns (use `"use client"`, direct `fetch()` calls to `/api/admin/openapi/*`).

**Step 1: Create the Connect API page**

The page should be at `frontend/src/app/admin/connect-api/page.tsx`. Follow the Users page pattern (direct fetch, no `useAdminArtifacts`).

**Step 2: Add tab to layout.tsx**

In `frontend/src/app/admin/layout.tsx`, add to the `ADMIN_TABS` array:

```typescript
{ label: "Connect API", href: "/admin/connect-api" },
```

**Step 3: Run frontend build**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build
```

Expected: 0 errors

**Step 4: Commit**

```bash
git add frontend/src/app/admin/connect-api/ frontend/src/app/admin/layout.tsx
git commit -m "feat(14-02): add Connect API admin page and tab"
```

---

### Task 10: Run full test suite and verify

**Step 1: Run backend tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: baseline + new tests pass

**Step 2: Run frontend build**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm run build
```

Expected: 0 errors
