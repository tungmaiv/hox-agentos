"""
Blitz AgentOS — FastAPI application factory.

Routes are registered here after the security layer (plans 01-02, 01-03)
provides JWT validation, RBAC, and Tool ACL.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import (
    agents,
    conversations,
    credentials,
    health,
    mcp_servers,
    system_config,
    user_instructions,
)
from core.config import settings
from core.logging import configure_logging
from gateway import runtime


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.
    Runs startup logic before the first request, cleanup on shutdown.
    """
    # Discover and register MCP tools from active mcp_servers DB rows.
    # Servers unreachable at startup are skipped with a warning log — they
    # can be retried later without a restart.
    try:
        from mcp.registry import MCPToolRegistry

        await MCPToolRegistry.refresh()
    except Exception as exc:
        # Never block startup on MCP discovery failure (DB may be empty)
        import structlog

        structlog.get_logger(__name__).warning(
            "mcp_refresh_failed", error=str(exc)
        )

    yield
    # Shutdown cleanup (nothing needed for MVP)


def create_app() -> FastAPI:
    configure_logging(
        log_level=settings.log_level,
        audit_log_path=settings.audit_log_path,
    )

    app = FastAPI(
        title="Blitz AgentOS",
        version="1.0.0",
        description="Enterprise AI Assistant Platform",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check — no auth, no /api prefix (reachable by load balancers)
    app.include_router(health.router)

    # Agent routes — all protected by 3-gate security chain
    app.include_router(agents.router, prefix="/api")

    # Credential vault routes — GET/DELETE only (Phase 2 stubs)
    app.include_router(credentials.router, prefix="/api")

    # Conversation list — GET /api/conversations/ (sidebar history)
    app.include_router(conversations.router, prefix="/api")

    # Custom instructions — GET/PUT /api/user/instructions/
    app.include_router(user_instructions.router, prefix="/api")

    # Admin config — GET/PUT /api/admin/config (admin-only, Gate 2 RBAC)
    # Note: router already includes /api prefix in its definition
    app.include_router(system_config.router)

    # MCP server CRUD — GET/POST/DELETE /api/admin/mcp-servers (admin-only)
    # Note: router already includes /api prefix in its definition
    app.include_router(mcp_servers.router)

    # CopilotKit AG-UI streaming endpoint — 3-gate security + LangGraph master agent
    app.include_router(runtime.router)

    return app


app = create_app()
