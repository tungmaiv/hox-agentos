"""
Blitz AgentOS — FastAPI application factory.

Routes are registered here after the security layer (plans 01-02, 01-03)
provides JWT validation, RBAC, and Tool ACL.
"""
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from api.routes import (
    admin_agents,
    admin_credentials,
    admin_permissions,
    admin_skills,
    admin_tools,
    agents,
    conversations,
    credentials,
    health,
    memory_settings,
    mcp_servers,
    system_config,
    tools,
    user_instructions,
    user_preferences,
    user_skills,
    user_tools,
)
from api.routes.registry import router as registry_router
from api.routes.storage import router as storage_router
from api.routes.admin_keycloak import router as admin_keycloak_router
from api.routes.admin_skill_sharing import router as admin_skill_sharing_router
from api.routes.admin_local_users import router as admin_local_users_router
from api.routes.admin_llm import router as admin_llm_router
from api.routes.admin_memory import router as admin_memory_router
from api.routes.admin_system import router as admin_system_router
from api.routes.auth_local import router as auth_local_router
from api.routes.admin_notifications import router as admin_notifications_router
from api.routes.admin_sso_health import router as admin_sso_health_router
from api.routes.auth_config import router as auth_config_router
from api.routes.auth_local_password import router as auth_local_password_router
from api.routes.channels import router as channels_router
from api.routes.webhooks import router as webhooks_router
from api.routes.workflows import router as workflows_router
from core.config import settings
from core.db import RequestSessionMiddleware
from core.logging import configure_logging
from gateway import runtime
from openapi_bridge.routes import router as openapi_bridge_router
from skill_export.routes import router as skill_export_router
from skill_repos.routes import admin_router as skill_repos_admin_router
from skill_repos.routes import user_router as skill_repos_user_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.
    Runs startup logic before the first request, cleanup on shutdown.
    """
    # Unified registry is DB-backed (registry_entries table); no startup seeding needed.
    # Tool dispatch reads directly from registry_entries via UnifiedRegistryService.get_tool().

    # Remove any sandbox containers that survived a previous unclean shutdown.
    # Runs in a thread to avoid blocking the event loop (Docker SDK is synchronous).
    try:
        from sandbox.executor import SandboxExecutor

        await asyncio.to_thread(SandboxExecutor()._cleanup_leaked_containers)
    except Exception as exc:
        import structlog

        structlog.get_logger(__name__).warning(
            "sandbox_cleanup_startup_failed", error=str(exc)
        )

    # Validate embedding sidecar dimension at startup.
    # Non-fatal: backend still starts when sidecar isn't running (fallback to BGE_M3Provider).
    try:
        from memory.embeddings import SidecarEmbeddingProvider

        sidecar = SidecarEmbeddingProvider()
        await sidecar.validate_dimension()
    except Exception as exc:
        import structlog as _structlog

        _structlog.get_logger(__name__).warning(
            "embedding_sidecar_startup_check_failed", error=str(exc)
        )

    # Hypothesis 1 — pre-warm Keycloak config cache at startup.
    # Ensures get_keycloak_config() returns from cache (not DB) on first auth request.
    # Non-fatal: backend starts even when DB is temporarily unreachable.
    try:
        from security.keycloak_config import get_keycloak_config as _get_kc_config

        await _get_kc_config()
        import structlog as _structlog
        _structlog.get_logger(__name__).info("keycloak_config_prewarm_success")
    except Exception as exc:
        import structlog as _structlog
        _structlog.get_logger(__name__).warning(
            "keycloak_config_prewarm_failed", error=str(exc)
        )

    # Register SSO circuit breaker transition callback for admin notifications + Telegram alerts.
    try:
        from security.circuit_breaker import get_circuit_breaker
        from security.sso_notifications import on_sso_state_transition

        cb = get_circuit_breaker()
        cb.register_transition_callback(on_sso_state_transition)

        # Load thresholds from platform_config if available
        try:
            from core.db import async_session as _async_session
            from core.models.platform_config import PlatformConfig as _PC
            from sqlalchemy import select as _select

            async with _async_session() as _session:
                _result = await _session.execute(_select(_PC).where(_PC.id == 1))
                _row = _result.scalar_one_or_none()
                if _row:
                    cb.update_thresholds(
                        failure_threshold=_row.cb_failure_threshold,
                        recovery_timeout_seconds=float(_row.cb_recovery_timeout),
                        half_open_max_calls=_row.cb_half_open_max_calls,
                    )
        except Exception:
            pass  # Use defaults if DB not ready

        import structlog as _structlog
        _structlog.get_logger(__name__).info("sso_circuit_breaker_callback_registered")
    except Exception as exc:
        import structlog as _structlog
        _structlog.get_logger(__name__).warning(
            "sso_circuit_breaker_callback_registration_failed", error=str(exc)
        )

    # Hypothesis 5 — pre-warm JWKS cache at startup so the first auth request
    # does not pay the Keycloak round-trip latency.
    # Non-fatal: backend starts even when Keycloak is not yet ready.
    try:
        from security.keycloak_config import get_keycloak_config as _get_kc_for_jwks
        from security.jwt import _fetch_jwks_from_remote

        _kc = await _get_kc_for_jwks()
        if _kc is not None and _kc.enabled:
            import structlog as _structlog
            try:
                await _fetch_jwks_from_remote(_kc)
                _structlog.get_logger(__name__).info("jwks_prewarm=success")
            except Exception as exc:
                _structlog.get_logger(__name__).warning(
                    "jwks_prewarm=failed", error=str(exc)
                )
    except Exception as exc:
        import structlog as _structlog
        _structlog.get_logger(__name__).warning(
            "jwks_prewarm_setup_failed", error=str(exc)
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
    # Single DB session per HTTP request — must be added after CORSMiddleware so the
    # session is available when route handlers run (middleware executes in reverse order).
    app.add_middleware(RequestSessionMiddleware)

    # Expose GET /metrics — no auth, blitz-net internal only (no host port exposure).
    # prometheus.yml scrape target 'backend' hits this endpoint.
    Instrumentator().instrument(app).expose(app)

    # Health check — no auth, no /api prefix (reachable by load balancers)
    app.include_router(health.router)

    # Local auth — POST /api/auth/local/token (no auth required — it IS the auth)
    app.include_router(auth_local_router)

    # Local auth password change — POST /api/auth/local/change-password (JWT required)
    app.include_router(auth_local_password_router)

    # Auth config (public — no JWT, tells frontend auth mode)
    app.include_router(auth_config_router)

    # Admin CRUD for local users and groups — /api/admin/local/users + groups (registry:manage)
    app.include_router(admin_local_users_router)

    # Agent routes — all protected by 3-gate security chain
    app.include_router(agents.router, prefix="/api")

    # Credential vault routes — GET/DELETE only (Phase 2 stubs)
    app.include_router(credentials.router, prefix="/api")

    # Conversation list — GET /api/conversations/ (sidebar history)
    app.include_router(conversations.router, prefix="/api")

    # Custom instructions — GET/PUT /api/user/instructions/
    app.include_router(user_instructions.router, prefix="/api")

    # User LLM preferences — GET/PUT /api/users/me/preferences/
    app.include_router(user_preferences.router, prefix="/api")

    # Admin config — GET/PUT /api/admin/config (admin-only, Gate 2 RBAC)
    # Note: router already includes /api prefix in its definition
    app.include_router(system_config.router)

    # Admin agent CRUD — /api/admin/agents (registry:manage permission)
    # NOTE: kept for backward compat with existing admin UI; new code uses /api/registry/*
    app.include_router(admin_agents.router)

    # Admin tool CRUD — /api/admin/tools (registry:manage permission)
    app.include_router(admin_tools.router)

    # Admin MCP server CRUD — /api/admin/mcp-servers (tool:admin permission)
    # check-name MUST be registered before /{server_id} to avoid UUID routing collision
    app.include_router(mcp_servers.router)

    # Skill export — GET /api/admin/skills/{id}/export (registry:manage permission)
    # MUST be registered before admin_skills.router to prevent FastAPI routing collision:
    # the literal path segment "export" must take precedence over UUID /{skill_id}.
    app.include_router(skill_export_router)

    # Admin skill sharing — POST/DELETE/GET /api/admin/skills/{id}/share* (registry:manage)
    # MUST be registered before admin_skills.router: literal path segments "share" and
    # "shares" must take precedence over UUID /{skill_id} catch-all routes.
    app.include_router(admin_skill_sharing_router)

    # Admin skill CRUD — /api/admin/skills (registry:manage permission)
    app.include_router(admin_skills.router)

    # Admin permission management — /api/admin/permissions (registry:manage permission)
    app.include_router(admin_permissions.router)

    # Admin credential management — /api/admin/credentials (registry:manage permission)
    app.include_router(admin_credentials.router)

    # Admin LLM model config — GET/POST/DELETE /api/admin/llm/models (tool:admin permission)
    app.include_router(admin_llm_router)

    # Admin memory reindex — POST /api/admin/memory/reindex (tool:admin permission)
    app.include_router(admin_memory_router)

    # Admin system management — POST /api/admin/system/rescan-skills (tool:admin permission)
    app.include_router(admin_system_router)

    # Admin Keycloak identity config — GET/POST /api/admin/keycloak/* (tool:admin permission)
    # Internal provider config — GET /api/internal/keycloak/provider-config (X-Internal-Key)
    app.include_router(admin_keycloak_router)

    # Admin SSO health — GET /api/admin/sso/health, PUT /api/admin/sso/circuit-breaker/config
    app.include_router(admin_sso_health_router)

    # Admin notifications — GET/POST /api/admin/notifications/* (tool:admin permission)
    app.include_router(admin_notifications_router)

    # User skill listing and execution — GET /api/skills, POST /api/skills/{name}/run
    # Note: router already includes /api prefix in its definition
    app.include_router(user_skills.router)

    # User tool listing — GET /api/tools (concrete endpoint, not conditional)
    # Note: router already includes /api prefix in its definition
    app.include_router(user_tools.router)

    # Tool execution — POST /api/tools/call (all authenticated users; 3-gate security)
    # Note: router already includes /api prefix in its definition
    app.include_router(tools.router)

    # Memory settings — GET/DELETE /api/user/memory/facts, /api/user/memory/episodes
    # Chat preferences — GET/PUT /api/user/preferences
    # Note: router already includes /api prefix in its definition
    app.include_router(memory_settings.router)

    # CopilotKit AG-UI streaming endpoint — 3-gate security + LangGraph master agent
    app.include_router(runtime.router)

    # Workflow CRUD + triggers + SSE events — JWT protected
    # Note: router already includes /api prefix in its definition
    app.include_router(workflows_router)

    # Webhook trigger — public endpoint (no JWT), validates X-Webhook-Secret
    # Note: router already includes /api prefix in its definition
    app.include_router(webhooks_router)

    # Channel integration routes — incoming (no auth), pair/accounts (JWT)
    # Note: router already includes /api/channels prefix in its definition
    app.include_router(channels_router)

    # OpenAPI Bridge — admin wizard to connect REST APIs as tool definitions
    # Note: router already includes /api/admin/openapi prefix in its definition
    app.include_router(openapi_bridge_router)

    # Skill Repository management — admin CRUD + user browse/import
    # Admin: /api/admin/skill-repos (registry:manage)
    # User:  /api/skill-repos/browse, /api/skill-repos/import (chat)
    app.include_router(skill_repos_admin_router)
    app.include_router(skill_repos_user_router)

    # Unified registry CRUD — /api/registry/* (replaces old scattered admin routes)
    app.include_router(registry_router)

    # Storage service — /api/storage/* (file/folder/share management + memory indexing)
    # Note: router already includes /api/storage prefix in its definition
    app.include_router(storage_router)

    return app


app = create_app()
