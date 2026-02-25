"""
Blitz AgentOS — FastAPI application factory.

Routes are registered here after the security layer (plans 01-02, 01-03)
provides JWT validation, RBAC, and Tool ACL.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import agents, credentials, health
from core.config import settings
from core.logging import configure_logging
from gateway import runtime


def create_app() -> FastAPI:
    configure_logging(
        log_level=settings.log_level,
        audit_log_path=settings.audit_log_path,
    )

    app = FastAPI(
        title="Blitz AgentOS",
        version="1.0.0",
        description="Enterprise AI Assistant Platform",
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

    # CopilotKit AG-UI streaming endpoint — 3-gate security + LangGraph master agent
    app.include_router(runtime.router)

    return app


app = create_app()
