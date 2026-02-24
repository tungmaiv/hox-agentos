"""
Blitz AgentOS — FastAPI application factory.

Routes are registered in subsequent plans (02-04) after security is implemented.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.logging import configure_logging
from core.schemas.common import HealthResponse


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

    @app.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        return HealthResponse(status="ok")

    # Routes registered after security is implemented in plans 02-04

    return app


app = create_app()
