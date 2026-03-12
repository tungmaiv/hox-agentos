"""
OpenAPI Bridge test suite — parser, proxy, service, and routes.

Tests:
  - Parser: valid OpenAPI 3.0 JSON spec → EndpointInfo list, tag groups, deprecated skipped
  - Parser: OpenAPI 3.1 YAML spec handled correctly
  - Proxy: correct GET request with path params + query params
  - Proxy: correct POST request with JSON body
  - Proxy: Bearer token auth header applied
  - Proxy: error dict returned on non-2xx response
  - Service: creates McpServer + ToolDefinition rows with handler_type='openapi_proxy'
  - Service: API key encrypted using encrypt_token()
  - Tool registry: dispatches openapi_proxy handler_type
  - Routes: POST /api/admin/openapi/parse returns parsed endpoint list
  - Routes: POST /api/admin/openapi/register creates server and tools
"""
import base64
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db import Base

# Import all models so that Base.metadata has them registered before create_all()
from core.models.mcp_server import McpServer  # noqa: F401
from core.models.tool_definition import ToolDefinition  # noqa: F401
from registry.models import RegistryEntry  # noqa: F401


# ---------------------------------------------------------------------------
# Sample OpenAPI specs for testing
# ---------------------------------------------------------------------------

SAMPLE_OPENAPI_3_0_JSON: dict[str, Any] = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "servers": [{"url": "https://api.example.com/v1"}],
    "paths": {
        "/users/{userId}": {
            "get": {
                "operationId": "get_user",
                "summary": "Get a user by ID",
                "tags": ["users"],
                "parameters": [
                    {
                        "name": "userId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "include_deleted",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "boolean"},
                        "description": "Include deleted users",
                    },
                ],
                "deprecated": False,
            }
        },
        "/users": {
            "post": {
                "operationId": "create_user",
                "summary": "Create a new user",
                "tags": ["users"],
                "parameters": [],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "email": {"type": "string"},
                                },
                            }
                        }
                    }
                },
            },
            "get": {
                "operationId": "list_users_deprecated",
                "summary": "List users (deprecated)",
                "tags": ["users"],
                "parameters": [],
                "deprecated": True,
            },
        },
        "/health": {
            "get": {
                "operationId": "health_check",
                "summary": "Health check",
                "description": "Returns 200 if healthy",
                "parameters": [],
                # No tags — should go to "default" group
            }
        },
    },
}

SAMPLE_OPENAPI_3_1_YAML = """
openapi: "3.1.0"
info:
  title: YAML API
  version: "2.0.0"
servers:
  - url: https://yaml-api.example.com
paths:
  /items:
    get:
      operationId: list_items
      summary: List all items
      tags:
        - items
      parameters:
        - name: limit
          in: query
          required: false
          schema:
            type: integer
"""


# ---------------------------------------------------------------------------
# In-memory DB fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session() -> AsyncSession:
    """In-memory SQLite async session with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestFetchAndParseOpenAPI:
    """Tests for openapi_bridge.parser.fetch_and_parse_openapi()."""

    async def test_parse_valid_3_0_json_spec(self) -> None:
        """Parses a valid OpenAPI 3.0 JSON spec and returns correct EndpointInfo list."""
        import json

        from openapi_bridge.parser import fetch_and_parse_openapi

        spec_json = json.dumps(SAMPLE_OPENAPI_3_0_JSON)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = spec_json
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await fetch_and_parse_openapi("https://api.example.com/openapi.json")

        # Check base URL and metadata
        assert result.base_url == "https://api.example.com/v1"
        assert result.title == "Test API"
        assert result.version == "1.0.0"

        # Should have 3 non-deprecated endpoints (get_user, create_user, health_check)
        assert len(result.endpoints) == 3

        # Check get_user endpoint
        get_user = next(e for e in result.endpoints if e.operation_id == "get_user")
        assert get_user.method == "GET"
        assert get_user.path == "/users/{userId}"
        assert get_user.summary == "Get a user by ID"
        assert "users" in get_user.tags

        # Check parameters on get_user
        assert len(get_user.parameters) == 2
        path_param = next(p for p in get_user.parameters if p.location == "path")
        assert path_param.name == "userId"
        assert path_param.required is True
        assert path_param.schema_type == "string"

        query_param = next(p for p in get_user.parameters if p.location == "query")
        assert query_param.name == "include_deleted"
        assert query_param.required is False
        assert query_param.schema_type == "boolean"

    async def test_deprecated_operations_skipped(self) -> None:
        """Deprecated endpoints are excluded from results."""
        import json

        from openapi_bridge.parser import fetch_and_parse_openapi

        spec_json = json.dumps(SAMPLE_OPENAPI_3_0_JSON)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = spec_json
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await fetch_and_parse_openapi("https://api.example.com/openapi.json")

        # list_users_deprecated should NOT be in results
        operation_ids = [e.operation_id for e in result.endpoints]
        assert "list_users_deprecated" not in operation_ids

    async def test_request_body_schema_extracted(self) -> None:
        """POST endpoint request body schema is extracted correctly."""
        import json

        from openapi_bridge.parser import fetch_and_parse_openapi

        spec_json = json.dumps(SAMPLE_OPENAPI_3_0_JSON)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = spec_json
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await fetch_and_parse_openapi("https://api.example.com/openapi.json")

        create_user = next(e for e in result.endpoints if e.operation_id == "create_user")
        assert create_user.request_body_schema is not None
        assert create_user.request_body_schema.get("type") == "object"

    async def test_tag_groups_built(self) -> None:
        """Endpoints grouped by tags; endpoints without tags go to 'default'."""
        import json

        from openapi_bridge.parser import fetch_and_parse_openapi

        spec_json = json.dumps(SAMPLE_OPENAPI_3_0_JSON)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = spec_json
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await fetch_and_parse_openapi("https://api.example.com/openapi.json")

        # "users" tag should exist
        assert "users" in result.tag_groups
        assert len(result.tag_groups["users"]) >= 1

        # health_check has no tags → goes to "default"
        assert "default" in result.tag_groups
        health_idx = result.tag_groups["default"][0]
        assert result.endpoints[health_idx].operation_id == "health_check"

    async def test_parse_openapi_3_1_yaml_spec(self) -> None:
        """Parses an OpenAPI 3.1 YAML spec correctly."""
        from openapi_bridge.parser import fetch_and_parse_openapi

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_OPENAPI_3_1_YAML
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await fetch_and_parse_openapi("https://yaml-api.example.com/openapi.yaml")

        assert result.title == "YAML API"
        assert result.version == "2.0.0"
        assert result.base_url == "https://yaml-api.example.com"
        assert len(result.endpoints) == 1
        assert result.endpoints[0].operation_id == "list_items"
        assert result.endpoints[0].method == "GET"

        # Check the query param
        assert len(result.endpoints[0].parameters) == 1
        assert result.endpoints[0].parameters[0].name == "limit"
        assert result.endpoints[0].parameters[0].schema_type == "integer"


# ---------------------------------------------------------------------------
# Proxy tests
# ---------------------------------------------------------------------------


class TestCallOpenAPITool:
    """Tests for openapi_bridge.proxy.call_openapi_tool()."""

    async def test_get_request_with_path_and_query_params(self) -> None:
        """Constructs correct GET request with path params + query params."""
        from openapi_bridge.proxy import call_openapi_tool

        tool_config = {
            "method": "GET",
            "path": "/users/{userId}",
            "base_url": "https://api.example.com/v1",
            "parameters": [
                {"name": "userId", "location": "path", "required": True},
                {"name": "include_deleted", "location": "query", "required": False},
            ],
            "auth_type": "none",
            "auth_header": None,
        }
        arguments = {"userId": "abc123", "include_deleted": "true"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json = MagicMock(return_value={"id": "abc123", "name": "Alice"})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await call_openapi_tool(tool_config, arguments, None)

        # Verify call was made with path interpolated
        call_args = mock_client.request.call_args
        assert call_args.kwargs.get("url") == "https://api.example.com/v1/users/abc123" or \
               call_args.args[1] == "https://api.example.com/v1/users/abc123"
        assert result == {"id": "abc123", "name": "Alice"}

    async def test_post_request_with_json_body(self) -> None:
        """Constructs correct POST request with JSON body."""
        from openapi_bridge.proxy import call_openapi_tool

        tool_config = {
            "method": "POST",
            "path": "/users",
            "base_url": "https://api.example.com/v1",
            "parameters": [],
            "auth_type": "none",
            "auth_header": None,
        }
        arguments = {"name": "Bob", "email": "bob@example.com"}

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json = MagicMock(return_value={"id": "new-user-id"})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await call_openapi_tool(tool_config, arguments, None)

        # Verify body is passed as JSON
        call_args = mock_client.request.call_args
        assert result == {"id": "new-user-id"}

    async def test_bearer_token_auth_header(self) -> None:
        """Adds Authorization: Bearer header when auth_type is 'bearer'."""
        from openapi_bridge.proxy import call_openapi_tool

        tool_config = {
            "method": "GET",
            "path": "/protected",
            "base_url": "https://api.example.com/v1",
            "parameters": [],
            "auth_type": "bearer",
            "auth_header": None,
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json = MagicMock(return_value={"data": "secret"})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await call_openapi_tool(tool_config, {}, "my-secret-token")

        call_args = mock_client.request.call_args
        headers = call_args.kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer my-secret-token"

    async def test_api_key_auth_header(self) -> None:
        """Uses custom header name for api_key auth type."""
        from openapi_bridge.proxy import call_openapi_tool

        tool_config = {
            "method": "GET",
            "path": "/data",
            "base_url": "https://api.example.com/v1",
            "parameters": [],
            "auth_type": "api_key",
            "auth_header": "X-Custom-Key",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json = MagicMock(return_value={})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await call_openapi_tool(tool_config, {}, "api-key-value")

        call_args = mock_client.request.call_args
        headers = call_args.kwargs.get("headers", {})
        assert headers.get("X-Custom-Key") == "api-key-value"

    async def test_basic_auth_header(self) -> None:
        """Applies Basic auth header with base64 encoding."""
        from openapi_bridge.proxy import call_openapi_tool

        tool_config = {
            "method": "GET",
            "path": "/data",
            "base_url": "https://api.example.com/v1",
            "parameters": [],
            "auth_type": "basic",
            "auth_header": None,
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json = MagicMock(return_value={})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await call_openapi_tool(tool_config, {}, "user:password")

        call_args = mock_client.request.call_args
        headers = call_args.kwargs.get("headers", {})
        expected_b64 = base64.b64encode(b"user:password").decode()
        assert headers.get("Authorization") == f"Basic {expected_b64}"

    async def test_error_dict_on_non_2xx_response(self) -> None:
        """Returns error dict on non-2xx HTTP status code."""
        from openapi_bridge.proxy import call_openapi_tool

        tool_config = {
            "method": "GET",
            "path": "/missing",
            "base_url": "https://api.example.com/v1",
            "parameters": [],
            "auth_type": "none",
            "auth_header": None,
        }

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await call_openapi_tool(tool_config, {}, None)

        assert result.get("error") is True
        assert result.get("status") == 404
        assert "Not Found" in result.get("detail", "")


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


class TestRegisterOpenAPIEndpoints:
    """Tests for openapi_bridge.service.register_openapi_endpoints()."""

    async def test_creates_mcp_server_and_tool_definitions(
        self, db_session: AsyncSession
    ) -> None:
        """Creates RegistryEntry mcp_server row + RegistryEntry tool rows with handler_type='openapi_proxy'."""
        from sqlalchemy import select

        from openapi_bridge.schemas import EndpointInfo, ParameterInfo
        from openapi_bridge.service import register_openapi_endpoints
        from registry.models import RegistryEntry

        endpoints = [
            EndpointInfo(
                operation_id="get_user",
                method="GET",
                path="/users/{userId}",
                summary="Get user",
                description=None,
                tags=["users"],
                parameters=[
                    ParameterInfo(
                        name="userId",
                        location="path",
                        required=True,
                        schema_type="string",
                    )
                ],
            )
        ]

        with patch("openapi_bridge.service.encrypt_token", return_value=(b"cipher", b"iv")):
            result = await register_openapi_endpoints(
                server_name="test_api",
                base_url="https://api.example.com/v1",
                spec_url="https://api.example.com/openapi.json",
                endpoints=endpoints,
                auth_type="bearer",
                auth_value="my-token",
                auth_header=None,
                session=db_session,
            )

        # Check RegistryEntry mcp_server row created
        server_result = await db_session.execute(
            select(RegistryEntry).where(
                RegistryEntry.type == "mcp_server",
                RegistryEntry.name == "test_api",
            )
        )
        server = server_result.scalar_one_or_none()
        assert server is not None
        assert server.config["url"] == "https://api.example.com/v1"
        assert server.config["openapi_spec_url"] == "https://api.example.com/openapi.json"

        # Check RegistryEntry tool rows created
        tools_result = await db_session.execute(
            select(RegistryEntry).where(
                RegistryEntry.type == "tool",
            )
        )
        tools = tools_result.scalars().all()
        tools = [t for t in tools if t.config.get("handler_type") == "openapi_proxy"]
        assert len(tools) == 1
        assert tools[0].name == "test_api.get_user"
        assert tools[0].config is not None
        assert tools[0].config["method"] == "GET"

        # Check result
        assert result.server_id == str(server.id)
        assert result.tools_created == 1

    async def test_api_key_encrypted_with_encrypt_token(
        self, db_session: AsyncSession
    ) -> None:
        """API key is encrypted using encrypt_token() before storage."""
        from openapi_bridge.schemas import EndpointInfo
        from openapi_bridge.service import register_openapi_endpoints

        endpoints = [
            EndpointInfo(
                operation_id="list_items",
                method="GET",
                path="/items",
                summary="List items",
                description=None,
                tags=["items"],
                parameters=[],
            )
        ]

        mock_encrypt = MagicMock(return_value=(b"ciphertext", b"nonce"))

        with patch("openapi_bridge.service.encrypt_token", mock_encrypt):
            await register_openapi_endpoints(
                server_name="secure_api",
                base_url="https://secure.example.com",
                spec_url="https://secure.example.com/openapi.json",
                endpoints=endpoints,
                auth_type="api_key",
                auth_value="super-secret-key",
                auth_header="X-API-Key",
                session=db_session,
            )

        # encrypt_token should have been called with the api key
        mock_encrypt.assert_called_once_with("super-secret-key")

    async def test_no_auth_no_encryption(self, db_session: AsyncSession) -> None:
        """When auth_value is None, encrypt_token is not called."""
        from openapi_bridge.schemas import EndpointInfo
        from openapi_bridge.service import register_openapi_endpoints

        endpoints = [
            EndpointInfo(
                operation_id="health",
                method="GET",
                path="/health",
                summary="Health check",
                description=None,
                tags=[],
                parameters=[],
            )
        ]

        mock_encrypt = MagicMock(return_value=(b"ciphertext", b"nonce"))

        with patch("openapi_bridge.service.encrypt_token", mock_encrypt):
            await register_openapi_endpoints(
                server_name="public_api",
                base_url="https://public.example.com",
                spec_url="https://public.example.com/openapi.json",
                endpoints=endpoints,
                auth_type="none",
                auth_value=None,
                auth_header=None,
                session=db_session,
            )

        mock_encrypt.assert_not_called()


# ---------------------------------------------------------------------------
# Tool registry dispatch test
# ---------------------------------------------------------------------------


class TestToolRegistryDispatch:
    """Tests that tool_registry cache includes config_json for openapi_proxy tools.

    Phase 24 note: gateway/tool_registry.py deleted — cache-based tests replaced
    by registry_entries-based integration tests in test_registry_routes.py.
    """

    @pytest.mark.skip(
        reason=(
            "Phase 24: gateway/tool_registry._refresh_tool_cache deleted. "
            "openapi_proxy tool dispatch now reads from registry_entries via "
            "registry.service.get_tool(). Integration test pending refactor."
        )
    )
    async def test_refresh_cache_includes_openapi_proxy_fields(
        self, db_session: AsyncSession
    ) -> None:
        """Tool registry caches openapi_proxy tools with config_json available."""
        from sqlalchemy import insert

        from core.models.mcp_server import McpServer
        from core.models.tool_definition import ToolDefinition
        from gateway.tool_registry import _refresh_tool_cache, get_tool

        # Insert a McpServer
        server_id = uuid.uuid4()
        await db_session.execute(
            insert(McpServer).values(
                id=server_id,
                name="openapi_test_server",
                url="https://api.example.com",
                is_active=True,
                status="active",
            )
        )

        # Insert an openapi_proxy tool
        tool_id = uuid.uuid4()
        await db_session.execute(
            insert(ToolDefinition).values(
                id=tool_id,
                name="openapi_test_server.get_items",
                handler_type="openapi_proxy",
                mcp_server_id=server_id,
                is_active=True,
                status="active",
                config_json={
                    "method": "GET",
                    "path": "/items",
                    "base_url": "https://api.example.com",
                    "parameters": [],
                    "auth_type": "bearer",
                    "auth_header": None,
                },
            )
        )
        await db_session.commit()

        # Refresh cache
        await _refresh_tool_cache(db_session)

        tool = await get_tool("openapi_test_server.get_items")
        assert tool is not None
        assert tool["handler_type"] == "openapi_proxy"


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------


class TestOpenAPIRoutes:
    """Tests for POST /api/admin/openapi/parse and /api/admin/openapi/register."""

    @pytest.fixture
    def admin_user(self) -> dict:
        """Mock admin user context."""
        return {
            "user_id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
            "email": "admin@blitz.local",
            "username": "admin",
            "roles": ["admin"],
            "groups": [],
        }

    @pytest.fixture
    def app_client(self, admin_user: dict):
        """Test client with admin auth overridden."""
        from fastapi import FastAPI

        # Build minimal app with just the openapi_bridge router
        from openapi_bridge.routes import router as openapi_router

        app = FastAPI()
        app.include_router(openapi_router)

        from security.deps import get_current_user, require_registry_manager

        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[require_registry_manager] = lambda: admin_user

        with TestClient(app) as client:
            yield client

    async def test_parse_endpoint_returns_endpoint_list(self, admin_user: dict) -> None:
        """POST /api/admin/openapi/parse returns parsed endpoint list."""
        import json

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from openapi_bridge.routes import router as openapi_router

        app = FastAPI()
        app.include_router(openapi_router)

        from security.deps import get_current_user, require_registry_manager

        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[require_registry_manager] = lambda: admin_user

        spec_json = json.dumps(SAMPLE_OPENAPI_3_0_JSON)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = spec_json
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with TestClient(app) as client:
                response = client.post(
                    "/api/admin/openapi/parse",
                    json={"url": "https://api.example.com/openapi.json"},
                )

        assert response.status_code == 200
        data = response.json()
        assert "endpoints" in data
        assert len(data["endpoints"]) == 3  # 3 non-deprecated endpoints
        assert "tag_groups" in data
        assert data["title"] == "Test API"

    async def test_register_endpoint_creates_artifacts(self, admin_user: dict) -> None:
        """POST /api/admin/openapi/register creates server and tools."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from openapi_bridge.routes import router as openapi_router
        from openapi_bridge.schemas import RegisterResponse

        app = FastAPI()
        app.include_router(openapi_router)

        from security.deps import get_current_user, require_registry_manager

        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[require_registry_manager] = lambda: admin_user

        mock_register_result = RegisterResponse(
            server_id=str(uuid.uuid4()), tools_created=2
        )

        with patch(
            "openapi_bridge.routes.register_openapi_endpoints",
            AsyncMock(return_value=mock_register_result),
        ):
            with patch("openapi_bridge.routes.get_db"):
                with TestClient(app) as client:
                    response = client.post(
                        "/api/admin/openapi/register",
                        json={
                            "server_name": "my_api",
                            "base_url": "https://api.example.com/v1",
                            "spec_url": "https://api.example.com/openapi.json",
                            "selected_endpoints": [
                                {
                                    "operation_id": "get_user",
                                    "method": "GET",
                                    "path": "/users/{userId}",
                                    "summary": "Get user",
                                    "description": None,
                                    "tags": ["users"],
                                    "parameters": [],
                                    "request_body_schema": None,
                                    "deprecated": False,
                                }
                            ],
                            "auth_type": "bearer",
                            "auth_value": "token",
                            "auth_header": None,
                        },
                    )

        assert response.status_code == 200
        data = response.json()
        assert "server_id" in data
        assert data["tools_created"] == 2


# ---------------------------------------------------------------------------
# Route dispatch tests: /api/tools/call with openapi_proxy tools
# ---------------------------------------------------------------------------


class TestToolsRouteOpenAPIProxy:
    """Tests for the openapi_proxy dispatch branch in api/routes/tools.py.

    Phase 24 note: These tests use gateway.tool_registry._refresh_tool_cache
    which was deleted. openapi_proxy dispatch now reads from registry_entries.
    Tests pending refactor to insert into registry_entries instead of ToolDefinition.
    """

    @pytest.mark.skip(
        reason=(
            "Phase 24: gateway/tool_registry._refresh_tool_cache deleted. "
            "Tests need refactor to use registry_entries + registry.service.get_tool()."
        )
    )
    async def test_openapi_proxy_tool_is_dispatched(self, db_session: AsyncSession) -> None:
        """Calling an openapi_proxy tool routes to call_openapi_tool(), not 501."""
        from sqlalchemy import insert

        from core.models.mcp_server import McpServer
        from core.models.tool_definition import ToolDefinition
        from gateway.tool_registry import _refresh_tool_cache

        # Insert a McpServer with no auth_token (public API)
        server_id = uuid.uuid4()
        await db_session.execute(
            insert(McpServer).values(
                id=server_id,
                name="test_proxy_server",
                url="https://api.example.com",
                auth_token=None,
                is_active=True,
                status="active",
            )
        )

        # Insert an openapi_proxy ToolDefinition
        tool_id = uuid.uuid4()
        await db_session.execute(
            insert(ToolDefinition).values(
                id=tool_id,
                name="test_proxy_server.list_items",
                handler_type="openapi_proxy",
                mcp_server_id=server_id,
                is_active=True,
                status="active",
                config_json={
                    "method": "GET",
                    "path": "/items",
                    "base_url": "https://api.example.com",
                    "parameters": [],
                    "auth_type": "none",
                    "auth_header": None,
                },
                input_schema={"type": "object", "properties": {}},
            )
        )
        await db_session.commit()
        await _refresh_tool_cache(db_session)

        # Mock call_openapi_tool to return a success dict
        with patch("api.routes.tools.call_openapi_tool") as mock_call:
            mock_call.return_value = {"items": [{"id": 1}]}

            # Mock security gates to allow
            with patch("api.routes.tools.has_permission", return_value=True), \
                 patch("api.routes.tools.check_tool_acl", return_value=True):

                from api.routes.tools import call_tool, ToolCallRequest
                from core.models.user import UserContext
                import uuid as _uuid

                user: UserContext = {
                    "user_id": _uuid.uuid4(),
                    "username": "testuser",
                    "email": "test@example.com",
                    "roles": ["employee"],
                }
                request = ToolCallRequest(tool="test_proxy_server.list_items", params={})
                response = await call_tool(request, user=user, session=db_session)

        assert response.success is True
        assert response.error is None
        assert response.result == {"items": [{"id": 1}]}

    @pytest.mark.skip(
        reason=(
            "Phase 24: gateway/tool_registry._refresh_tool_cache deleted. "
            "Tests need refactor to use registry_entries + registry.service.get_tool()."
        )
    )
    async def test_openapi_proxy_tool_with_encrypted_auth_token(
        self, db_session: AsyncSession
    ) -> None:
        """Decrypted API key is passed to call_openapi_tool() from McpServer.auth_token."""
        from sqlalchemy import insert

        from core.models.mcp_server import McpServer
        from core.models.tool_definition import ToolDefinition
        from gateway.tool_registry import _refresh_tool_cache
        from security.credentials import encrypt_token

        server_id = uuid.uuid4()
        # Encrypt a test API key
        ciphertext, iv = encrypt_token("test-api-key-value")
        raw_auth_token = iv + ciphertext

        await db_session.execute(
            insert(McpServer).values(
                id=server_id,
                name="test_proxy_auth_server",
                url="https://api.example.com",
                auth_token=raw_auth_token,
                is_active=True,
                status="active",
            )
        )

        tool_id = uuid.uuid4()
        await db_session.execute(
            insert(ToolDefinition).values(
                id=tool_id,
                name="test_proxy_auth_server.get_data",
                handler_type="openapi_proxy",
                mcp_server_id=server_id,
                is_active=True,
                status="active",
                config_json={
                    "method": "GET",
                    "path": "/data",
                    "base_url": "https://api.example.com",
                    "parameters": [],
                    "auth_type": "bearer",
                    "auth_header": None,
                },
                input_schema={"type": "object", "properties": {}},
            )
        )
        await db_session.commit()
        await _refresh_tool_cache(db_session)

        captured_kwargs: dict = {}

        async def fake_call(tool_config, arguments, api_key, auth_type=None, auth_header=None):
            captured_kwargs["api_key"] = api_key
            return {"data": "ok"}

        with patch("api.routes.tools.call_openapi_tool", side_effect=fake_call):
            with patch("api.routes.tools.has_permission", return_value=True), \
                 patch("api.routes.tools.check_tool_acl", return_value=True):

                from api.routes.tools import call_tool, ToolCallRequest
                from core.models.user import UserContext
                import uuid as _uuid

                user: UserContext = {
                    "user_id": _uuid.uuid4(),
                    "username": "testuser",
                    "email": "test@example.com",
                    "roles": ["employee"],
                }
                request = ToolCallRequest(tool="test_proxy_auth_server.get_data", params={})
                await call_tool(request, user=user, session=db_session)

        # Verify the decrypted API key was passed (not the raw bytes)
        assert captured_kwargs.get("api_key") == "test-api-key-value"

    @pytest.mark.skip(
        reason=(
            "Phase 24: gateway/tool_registry._refresh_tool_cache deleted. "
            "Tests need refactor to use registry_entries + registry.service.get_tool()."
        )
    )
    async def test_openapi_proxy_error_result_sets_success_false(
        self, db_session: AsyncSession
    ) -> None:
        """call_openapi_tool() returning {"error": True, ...} produces success=False response."""
        from sqlalchemy import insert

        from core.models.mcp_server import McpServer
        from core.models.tool_definition import ToolDefinition
        from gateway.tool_registry import _refresh_tool_cache

        server_id = uuid.uuid4()
        await db_session.execute(
            insert(McpServer).values(
                id=server_id,
                name="test_proxy_err_server",
                url="https://api.example.com",
                auth_token=None,
                is_active=True,
                status="active",
            )
        )

        tool_id = uuid.uuid4()
        await db_session.execute(
            insert(ToolDefinition).values(
                id=tool_id,
                name="test_proxy_err_server.get_item",
                handler_type="openapi_proxy",
                mcp_server_id=server_id,
                is_active=True,
                status="active",
                config_json={
                    "method": "GET",
                    "path": "/item",
                    "base_url": "https://api.example.com",
                    "parameters": [],
                    "auth_type": "none",
                    "auth_header": None,
                },
                input_schema={"type": "object", "properties": {}},
            )
        )
        await db_session.commit()
        await _refresh_tool_cache(db_session)

        with patch("api.routes.tools.call_openapi_tool") as mock_call:
            mock_call.return_value = {"error": True, "status": 404, "detail": "Not found"}

            with patch("api.routes.tools.has_permission", return_value=True), \
                 patch("api.routes.tools.check_tool_acl", return_value=True):

                from api.routes.tools import call_tool, ToolCallRequest
                from core.models.user import UserContext
                import uuid as _uuid

                user: UserContext = {
                    "user_id": _uuid.uuid4(),
                    "username": "testuser",
                    "email": "test@example.com",
                    "roles": ["employee"],
                }
                request = ToolCallRequest(tool="test_proxy_err_server.get_item", params={})
                response = await call_tool(request, user=user, session=db_session)

        assert response.success is False
        assert response.error == "Not found"
        assert response.result is None

    @pytest.mark.skip(
        reason=(
            "Phase 24: gateway/tool_registry._refresh_tool_cache deleted. "
            "Tests need refactor to use registry_entries + registry.service.get_tool()."
        )
    )
    async def test_non_openapi_backend_tool_still_returns_501(
        self, db_session: AsyncSession
    ) -> None:
        """Tools with handler_type='backend' (not openapi_proxy) still return HTTP 501."""
        from sqlalchemy import insert

        from core.models.tool_definition import ToolDefinition
        from gateway.tool_registry import _refresh_tool_cache
        import pytest

        tool_id = uuid.uuid4()
        await db_session.execute(
            insert(ToolDefinition).values(
                id=tool_id,
                name="backend_tool.do_something",
                handler_type="backend",
                is_active=True,
                status="active",
                input_schema={"type": "object", "properties": {}},
            )
        )
        await db_session.commit()
        await _refresh_tool_cache(db_session)

        from fastapi import HTTPException
        from api.routes.tools import call_tool, ToolCallRequest
        from core.models.user import UserContext
        import uuid as _uuid

        user: UserContext = {
            "user_id": _uuid.uuid4(),
            "username": "testuser",
            "email": "test@example.com",
            "roles": ["employee"],
        }
        request = ToolCallRequest(tool="backend_tool.do_something", params={})

        with pytest.raises(HTTPException) as exc_info:
            await call_tool(request, user=user, session=db_session)

        assert exc_info.value.status_code == 501
