"""
OpenAPI proxy — dispatches tool calls as HTTP requests to external APIs.

The proxy:
  - Builds URLs with path parameter substitution
  - Separates arguments into path/query/header/body params
  - Applies authentication (Bearer, API Key, Basic, None)
  - Executes the HTTP request via httpx
  - Returns JSON response or error dict on non-2xx status
  - Logs the call via structlog (never logs credential values)

Security note: api_key is decrypted inside the tool executor and passed
here — it never appears in logs or error responses.
"""
import base64
import time
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


def _build_url(base_url: str, path_template: str, path_params: dict[str, str]) -> str:
    """
    Build the full URL by substituting path parameters into the template.

    Example:
        base_url = "https://api.example.com/v1"
        path_template = "/users/{userId}"
        path_params = {"userId": "abc123"}
        → "https://api.example.com/v1/users/abc123"
    """
    path = path_template
    for key, value in path_params.items():
        path = path.replace(f"{{{key}}}", str(value))
    # Avoid double slash between base_url and path
    base = base_url.rstrip("/")
    return f"{base}{path}"


def _build_auth_headers(
    auth_type: str,
    api_key: str | None,
    auth_header: str | None = None,
) -> dict[str, str]:
    """
    Build authentication headers based on auth_type.

    Supported types:
      - "bearer": Authorization: Bearer <api_key>
      - "api_key": <auth_header or "X-API-Key">: <api_key>
      - "basic": Authorization: Basic base64("user:pass")  (api_key is "user:pass")
      - "none": no auth headers

    Never logs the api_key value.
    """
    if not api_key or auth_type == "none":
        return {}

    if auth_type == "bearer":
        return {"Authorization": f"Bearer {api_key}"}

    if auth_type == "api_key":
        header_name = auth_header or "X-API-Key"
        return {header_name: api_key}

    if auth_type == "basic":
        encoded = base64.b64encode(api_key.encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}

    return {}


def _separate_arguments(
    arguments: dict[str, Any],
    parameters: list[dict[str, Any]],
    method: str,
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, Any]]:
    """
    Separate tool arguments into path, query, header, and body params.

    For methods without a request body (GET, HEAD, DELETE):
      - All non-path/header args go to query params.
    For methods with a request body (POST, PUT, PATCH):
      - Non-path/header args with an explicit "body" location OR
        args not listed as any specific param → body.

    Returns:
        (path_params, query_params, header_params, body)
    """
    path_params: dict[str, str] = {}
    query_params: dict[str, str] = {}
    header_params: dict[str, str] = {}
    body: dict[str, Any] = {}

    # Build a lookup of parameter name → location
    param_locations: dict[str, str] = {}
    for p in parameters:
        if isinstance(p, dict):
            param_locations[p["name"]] = p.get("location", "query")

    has_body_method = method.upper() in {"POST", "PUT", "PATCH"}

    for arg_name, arg_value in arguments.items():
        location = param_locations.get(arg_name)

        if location == "path":
            path_params[arg_name] = str(arg_value)
        elif location == "header":
            header_params[arg_name] = str(arg_value)
        elif location == "query":
            query_params[arg_name] = str(arg_value)
        elif location is None:
            # Argument not in parameters spec — treat as body for body methods
            if has_body_method:
                body[arg_name] = arg_value
            else:
                query_params[arg_name] = str(arg_value)
        else:
            # Unknown location — treat as query
            query_params[arg_name] = str(arg_value)

    # For body methods without explicit body params, all non-path/header args → body
    # This handles the case where requestBody schema is not in parameters list
    if has_body_method and not body and not param_locations:
        for arg_name, arg_value in arguments.items():
            body[arg_name] = arg_value
        path_params = {}
        query_params = {}

    return path_params, query_params, header_params, body


async def call_openapi_tool(
    tool_config: dict[str, Any],
    arguments: dict[str, Any],
    api_key: str | None,
    auth_type: str | None = None,
    auth_header: str | None = None,
) -> dict[str, Any]:
    """
    Execute an HTTP request for an OpenAPI tool call.

    Args:
        tool_config: dict with keys:
            - method: HTTP method (GET, POST, etc.)
            - path: URL path template (may contain {param} placeholders)
            - base_url: base URL of the API
            - parameters: list of parameter dicts with name/location/required
            - auth_type: "bearer" | "api_key" | "basic" | "none"
            - auth_header: custom auth header name (for api_key type)
        arguments: dict of tool call arguments (from LLM or UI)
        api_key: decrypted API key/token (may be None for public APIs)
        auth_type: override auth_type from tool_config (optional)
        auth_header: override auth_header from tool_config (optional)

    Returns:
        On 2xx: response JSON dict (or {"text": body} if not JSON)
        On non-2xx: {"error": True, "status": <code>, "detail": <text>}
        On network error: {"error": True, "status": 0, "detail": <message>}
    """
    method = tool_config.get("method", "GET").upper()
    path_template = tool_config.get("path", "/")
    base_url = tool_config.get("base_url", "")
    parameters = tool_config.get("parameters", [])
    effective_auth_type = auth_type or tool_config.get("auth_type", "none") or "none"
    effective_auth_header = auth_header or tool_config.get("auth_header")

    start_ms = int(time.monotonic() * 1000)

    # Separate arguments by location
    path_params, query_params, header_params, body = _separate_arguments(
        arguments, parameters, method
    )

    # Build full URL
    url = _build_url(base_url, path_template, path_params)

    # Build auth headers (never log api_key value)
    auth_headers = _build_auth_headers(effective_auth_type, api_key, effective_auth_header)

    # Merge all headers
    headers = {**auth_headers, **header_params}

    # Execute the HTTP request
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            request_kwargs: dict[str, Any] = {
                "url": url,
                "headers": headers,
            }
            if query_params:
                request_kwargs["params"] = query_params
            if body and method in {"POST", "PUT", "PATCH"}:
                request_kwargs["json"] = body

            response = await client.request(method, **request_kwargs)

        duration_ms = int(time.monotonic() * 1000) - start_ms

        logger.info(
            "openapi_tool_call",
            method=method,
            url=url,
            status=response.status_code,
            duration_ms=duration_ms,
        )

        if response.status_code >= 200 and response.status_code < 300:
            # Success — return JSON or text
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    return dict(response.json())
                except Exception:
                    return {"text": response.text}
            else:
                return {"text": response.text}
        else:
            # Error response
            return {
                "error": True,
                "status": response.status_code,
                "detail": response.text[:500],
            }

    except httpx.RequestError as exc:
        duration_ms = int(time.monotonic() * 1000) - start_ms
        logger.warning(
            "openapi_tool_call_network_error",
            method=method,
            url=url,
            error=str(exc),
            duration_ms=duration_ms,
        )
        return {
            "error": True,
            "status": 0,
            "detail": f"Network error: {str(exc)[:200]}",
        }
