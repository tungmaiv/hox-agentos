"""
OpenAPI Bridge service layer — registers OpenAPI endpoints as tool definitions.

register_openapi_endpoints():
  1. Creates a McpServer row for the OpenAPI server
  2. Optionally encrypts the API key and stores it in auth_token
  3. For each selected endpoint, creates a ToolDefinition with handler_type='openapi_proxy'
  4. The config_json on each tool contains the routing info needed by the proxy
  5. Invalidates the tool cache so new tools are immediately discoverable

Security:
  - API key encrypted with AES-256-GCM via encrypt_token() before storage
  - auth_token field stores iv + ciphertext (same convention as mcp_servers route)
  - Never logs the api_key value
"""
import re
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from openapi_bridge.schemas import EndpointInfo, RegisterResponse
from security.credentials import encrypt_token

logger = structlog.get_logger(__name__)


def _sanitize_tool_name(name: str) -> str:
    """
    Convert arbitrary string to a valid tool name.

    Rules:
      - Lowercase
      - Replace any non-alphanumeric character with underscore
      - Collapse multiple underscores into one
      - Strip leading/trailing underscores
    """
    name = name.lower()
    name = re.sub(r"[^a-z0-9]", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_")
    return name


def _endpoint_tool_name(server_name: str, endpoint: EndpointInfo) -> str:
    """
    Generate a tool name for an endpoint: {server_name}.{operation_or_method_path}.

    Uses operation_id if available (sanitized), otherwise derives from method + path.
    """
    server_slug = _sanitize_tool_name(server_name)

    if endpoint.operation_id:
        operation_slug = _sanitize_tool_name(endpoint.operation_id)
    else:
        # Derive from method + path: GET /users/{id} → get_users_id
        method_part = endpoint.method.lower()
        path_part = _sanitize_tool_name(endpoint.path)
        operation_slug = f"{method_part}_{path_part}"

    return f"{server_slug}.{operation_slug}"


def _build_input_schema(endpoint: EndpointInfo) -> dict[str, Any]:
    """
    Build a JSON Schema-compatible input_schema for the tool from endpoint parameters.

    Includes:
      - Path, query, and header parameters
      - Request body fields (from request_body_schema if present)
    """
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param in endpoint.parameters:
        properties[param.name] = {
            "type": param.schema_type,
            "description": param.description or f"{param.location} parameter",
        }
        if param.required:
            required.append(param.name)

    # If there's a request body schema, add its properties too
    if endpoint.request_body_schema:
        body_props = endpoint.request_body_schema.get("properties", {})
        body_required = endpoint.request_body_schema.get("required", [])
        for prop_name, prop_schema in body_props.items():
            properties[prop_name] = prop_schema
        required.extend([r for r in body_required if r not in required])

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema


def _build_tool_config_json(
    endpoint: EndpointInfo,
    base_url: str,
    auth_type: str,
    auth_header: str | None,
) -> dict[str, Any]:
    """
    Build the config_json for a ToolDefinition with handler_type='openapi_proxy'.

    The proxy runtime reads this to know how to build the HTTP request.
    """
    return {
        "method": endpoint.method,
        "path": endpoint.path,
        "base_url": base_url,
        "parameters": [
            {
                "name": p.name,
                "location": p.location,
                "required": p.required,
            }
            for p in endpoint.parameters
        ],
        "auth_type": auth_type,
        "auth_header": auth_header,
    }


async def register_openapi_endpoints(
    server_name: str,
    base_url: str,
    spec_url: str,
    endpoints: list[EndpointInfo],
    auth_type: str,
    auth_value: str | None,
    auth_header: str | None,
    session: AsyncSession,
) -> RegisterResponse:
    """
    Register selected OpenAPI endpoints as tool definitions in the database.

    Args:
        server_name: Human-readable name for the server (used in tool names)
        base_url: Base URL of the API (from ParseResponse)
        spec_url: URL where the OpenAPI spec was fetched (for reference)
        endpoints: List of selected endpoints to register
        auth_type: Authentication type ("bearer" | "api_key" | "basic" | "none")
        auth_value: Raw API key/token (will be encrypted before storage)
        auth_header: Custom auth header name (for api_key type)
        session: Async database session

    Returns:
        RegisterResponse with server_id and tools_created count.

    Raises:
        sqlalchemy.exc.IntegrityError: if server_name already exists
    """
    from core.models.mcp_server import McpServer
    from core.models.tool_definition import ToolDefinition
    from gateway.tool_registry import invalidate_tool_cache

    # Optionally encrypt the API key
    auth_token_bytes: bytes | None = None
    if auth_value:
        ciphertext, iv = encrypt_token(auth_value)
        # Store as iv + ciphertext (same convention as mcp_servers route)
        auth_token_bytes = iv + ciphertext

    # Create the McpServer row
    server = McpServer(
        name=server_name,
        url=base_url,
        openapi_spec_url=spec_url,
        auth_token=auth_token_bytes,
        is_active=True,
        status="active",
    )
    session.add(server)
    await session.flush()  # Get the server.id without committing

    logger.info(
        "openapi_server_created",
        server_name=server_name,
        base_url=base_url,
        endpoint_count=len(endpoints),
    )

    # Create ToolDefinition rows for each endpoint
    tools_created = 0
    for endpoint in endpoints:
        tool_name = _endpoint_tool_name(server_name, endpoint)
        input_schema = _build_input_schema(endpoint)
        config_json = _build_tool_config_json(endpoint, base_url, auth_type, auth_header)

        tool = ToolDefinition(
            name=tool_name,
            display_name=endpoint.summary or tool_name,
            description=endpoint.description or endpoint.summary,
            version="1.0.0",
            handler_type="openapi_proxy",
            mcp_server_id=server.id,
            input_schema=input_schema,
            config_json=config_json,
            is_active=True,
            status="active",
        )
        session.add(tool)
        tools_created += 1

    await session.commit()

    # Refresh tool cache so new tools are immediately callable
    invalidate_tool_cache()

    logger.info(
        "openapi_tools_registered",
        server_name=server_name,
        tools_created=tools_created,
    )

    return RegisterResponse(
        server_id=str(server.id),
        tools_created=tools_created,
    )
