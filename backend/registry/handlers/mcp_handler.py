"""
MCPHandler — type-specific handler for registry entries with type='mcp_server'.

validate_config: requires 'url' key for http_sse servers.

on_create: no-op for MVP (MCP discovery is triggered manually or at startup).
on_delete: evicts MCP client from the in-memory client cache.
"""
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from registry.handlers.base import RegistryHandler

logger = structlog.get_logger(__name__)


class MCPHandler(RegistryHandler):
    """Handler for MCP server registry entries."""

    async def on_create(self, entry: object, session: AsyncSession) -> None:
        """Log creation — MCP discovery happens at next startup or manual refresh."""
        logger.info(
            "registry_mcp_server_created",
            name=getattr(entry, "name", None),
        )

    async def on_delete(self, entry: object, session: AsyncSession) -> None:
        """
        Evict the MCP client from the in-memory cache.

        This ensures tool calls to this server fail fast rather than silently
        routing to a deleted server.
        """
        name = getattr(entry, "name", None)
        if name:
            try:
                # Import here to avoid circular imports at module load time
                from mcp.registry import MCPToolRegistry

                MCPToolRegistry.evict_client(name)
                logger.info("registry_mcp_client_evicted", name=name)
            except Exception as exc:
                # Non-fatal: log and continue. The client will eventually
                # time out or be evicted on next MCP refresh.
                logger.warning(
                    "registry_mcp_evict_failed",
                    name=name,
                    error=str(exc),
                )

    def validate_config(self, config: dict) -> None:
        """
        Validate MCP server config.

        HTTP SSE servers require a 'url' key.
        OpenAPI bridge servers require an 'openapi_spec_url' key.
        """
        server_type = config.get("server_type", "http_sse")

        if server_type == "http_sse":
            if not config.get("url"):
                raise ValueError(
                    "http_sse mcp_server config must include 'url'"
                )
        elif server_type == "openapi_bridge":
            if not config.get("openapi_spec_url") and not config.get("url"):
                raise ValueError(
                    "openapi_bridge mcp_server config must include 'openapi_spec_url' or 'url'"
                )
        else:
            # Unknown server type — require at minimum a url
            if not config.get("url"):
                raise ValueError(
                    f"mcp_server config with server_type='{server_type}' must include 'url'"
                )
