"""
OpenAPI Bridge service layer — registers OpenAPI endpoints as registry entries.

register_openapi_endpoints():
  1. Creates a RegistryEntry with type='mcp_server' for the OpenAPI server
  2. Optionally encrypts the API key and stores it as hex string in config
  3. For each selected endpoint, creates a RegistryEntry with type='tool'
     and handler_type='openapi_proxy' in config
  4. The config on each tool entry contains the routing info needed by the proxy

Security:
  - API key encrypted with AES-256-GCM via encrypt_token() before storage
  - auth_token_hex field stores iv+ciphertext as hex string (bytes not JSON-serializable)
  - Never logs the api_key value
"""
import re
import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from openapi_bridge.schemas import EndpointInfo, RegisterResponse
from registry.models import RegistryEntry
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
    Build the config for a tool RegistryEntry with handler_type='openapi_proxy'.

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
    # Optionally encrypt the API key
    auth_token_bytes: bytes | None = None
    if auth_value:
        ciphertext, iv = encrypt_token(auth_value)
        # Store as iv + ciphertext (same convention as mcp_servers route)
        auth_token_bytes = iv + ciphertext

    # Store auth_token as hex string in config (bytes not JSON-serializable)
    auth_token_hex: str | None = None
    if auth_token_bytes:
        auth_token_hex = auth_token_bytes.hex()

    # Create RegistryEntry with type='mcp_server'
    server_entry = RegistryEntry(
        type="mcp_server",
        name=server_name,
        display_name=server_name,
        description=f"OpenAPI bridge for {base_url}",
        config={
            "url": base_url,
            "openapi_spec_url": spec_url,
            "auth_type": auth_type,
            "auth_token_hex": auth_token_hex,
            "auth_header": auth_header,
        },
        status="active",
        owner_id=uuid.uuid4(),  # system-owned; no user context in service layer
    )
    session.add(server_entry)
    await session.flush()  # get server_entry.id without committing

    logger.info(
        "openapi_server_created",
        server_name=server_name,
        base_url=base_url,
        endpoint_count=len(endpoints),
    )

    # Create RegistryEntry rows with type='tool' for each endpoint
    tools_created = 0
    for endpoint in endpoints:
        tool_name = _endpoint_tool_name(server_name, endpoint)
        input_schema = _build_input_schema(endpoint)
        config_json = _build_tool_config_json(endpoint, base_url, auth_type, auth_header)

        tool_entry = RegistryEntry(
            type="tool",
            name=tool_name,
            display_name=endpoint.summary or tool_name,
            description=endpoint.description or endpoint.summary,
            config={
                "handler_type": "openapi_proxy",
                "mcp_server_entry_id": str(server_entry.id),
                "input_schema": input_schema,
                **config_json,
            },
            status="active",
            owner_id=server_entry.owner_id,
        )
        session.add(tool_entry)
        tools_created += 1

    await session.commit()

    logger.info(
        "openapi_tools_registered",
        server_name=server_name,
        tools_created=tools_created,
    )

    return RegisterResponse(
        server_id=str(server_entry.id),
        tools_created=tools_created,
    )
