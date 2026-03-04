"""
OpenAPI spec parser — fetches and parses OpenAPI 3.x specs (JSON or YAML).

The parser:
  - Fetches specs from a URL via httpx (30s timeout, follows redirects)
  - Detects JSON or YAML format automatically
  - Validates it's an OpenAPI 3.x spec
  - Extracts endpoints (operations) as EndpointInfo objects
  - Skips deprecated operations
  - Builds tag_groups for UI grouping
  - Handles missing fields gracefully

Security note: The parser is admin-only — URL is provided by an authenticated
admin, not an end user. Input validation is handled by Pydantic in the route layer.
"""
import json
from typing import Any

import httpx
import structlog

from openapi_bridge.schemas import EndpointInfo, ParameterInfo, ParseResponse

logger = structlog.get_logger(__name__)

# HTTP methods recognized from OpenAPI path items
_HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options", "trace"}


def _detect_and_parse_spec(text: str) -> dict[str, Any]:
    """
    Auto-detect JSON or YAML and parse spec text.

    Tries JSON first (faster); falls back to YAML.
    Raises ValueError if the text is neither valid JSON nor YAML,
    or if the parsed result is not an OpenAPI 3.x spec.
    """
    # Try JSON first
    try:
        spec = json.loads(text)
    except json.JSONDecodeError:
        # Fall back to YAML
        try:
            import yaml

            spec = yaml.safe_load(text)
        except Exception as exc:
            raise ValueError(f"Could not parse spec as JSON or YAML: {exc}") from exc

    if not isinstance(spec, dict):
        raise ValueError("Spec must be a JSON/YAML object at the root level")

    openapi_version = spec.get("openapi", "")
    if not str(openapi_version).startswith("3."):
        raise ValueError(
            f"Only OpenAPI 3.x specs are supported. Got: '{openapi_version}'"
        )

    return spec


def _extract_parameter_type(schema: dict[str, Any] | None) -> str:
    """Extract the JSON Schema type string from a parameter schema object."""
    if not schema:
        return "string"
    param_type = schema.get("type", "string")
    return str(param_type) if param_type else "string"


def _extract_parameters(
    raw_params: list[dict[str, Any]] | None,
) -> list[ParameterInfo]:
    """Parse an OpenAPI parameters list into ParameterInfo objects."""
    if not raw_params:
        return []

    params: list[ParameterInfo] = []
    for p in raw_params:
        if not isinstance(p, dict):
            continue
        location = p.get("in", "query")
        # Map "in" values: path, query, header, cookie (skip cookie — not useful for proxy)
        if location == "cookie":
            continue
        params.append(
            ParameterInfo(
                name=str(p.get("name", "")),
                location=str(location),
                required=bool(p.get("required", location == "path")),
                schema_type=_extract_parameter_type(p.get("schema")),
                description=p.get("description"),
            )
        )
    return params


def _extract_request_body_schema(
    request_body: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Extract the JSON schema from requestBody.content.application/json.schema."""
    if not request_body:
        return None
    content = request_body.get("content", {})
    json_content = content.get("application/json", {})
    schema = json_content.get("schema")
    if schema and isinstance(schema, dict):
        return schema
    return None


def _parse_paths(
    paths: dict[str, Any],
) -> tuple[list[EndpointInfo], dict[str, list[int]]]:
    """
    Parse the OpenAPI 'paths' object into EndpointInfo list + tag_groups.

    Returns:
        (endpoints, tag_groups) where tag_groups maps tag name -> list of indices
        into the endpoints list. Endpoints without tags go into "default".
    """
    endpoints: list[EndpointInfo] = []
    tag_groups: dict[str, list[int]] = {}

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        for method, operation in path_item.items():
            if method.lower() not in _HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                continue

            # Skip deprecated operations
            if operation.get("deprecated", False):
                continue

            parameters = _extract_parameters(operation.get("parameters", []))
            request_body_schema = _extract_request_body_schema(
                operation.get("requestBody")
            )
            tags: list[str] = operation.get("tags") or []

            endpoint = EndpointInfo(
                operation_id=operation.get("operationId"),
                method=method.upper(),
                path=str(path),
                summary=operation.get("summary"),
                description=operation.get("description"),
                tags=tags,
                parameters=parameters,
                request_body_schema=request_body_schema,
                deprecated=False,
            )

            idx = len(endpoints)
            endpoints.append(endpoint)

            # Group by tags
            effective_tags = tags if tags else ["default"]
            for tag in effective_tags:
                tag_groups.setdefault(tag, []).append(idx)

    return endpoints, tag_groups


async def fetch_and_parse_openapi(url: str) -> ParseResponse:
    """
    Fetch an OpenAPI spec from a URL and parse it into a ParseResponse.

    Args:
        url: HTTP(S) URL pointing to an OpenAPI spec (JSON or YAML).

    Returns:
        ParseResponse with base_url, title, version, endpoints, tag_groups.

    Raises:
        ValueError: if the spec cannot be fetched, parsed, or is not OpenAPI 3.x.
        httpx.HTTPStatusError: if the HTTP fetch returns a non-2xx status.
    """
    logger.info("openapi_spec_fetch_start", url=url)

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

    spec = _detect_and_parse_spec(response.text)

    # Extract base URL from servers[0] or fall back to the spec URL origin
    servers = spec.get("servers", [])
    if servers and isinstance(servers[0], dict) and servers[0].get("url"):
        base_url = str(servers[0]["url"])
    else:
        # Derive from the spec URL: take scheme + host + path up to last slash
        from urllib.parse import urlparse

        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

    info = spec.get("info", {})
    title: str | None = info.get("title")
    version: str | None = info.get("version")

    paths = spec.get("paths", {})
    endpoints, tag_groups = _parse_paths(paths)

    logger.info(
        "openapi_spec_parsed",
        url=url,
        endpoint_count=len(endpoints),
        tag_count=len(tag_groups),
    )

    return ParseResponse(
        base_url=base_url,
        title=str(title) if title is not None else None,
        version=str(version) if version is not None else None,
        endpoints=endpoints,
        tag_groups=tag_groups,
    )
