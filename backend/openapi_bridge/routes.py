"""
Admin routes for the OpenAPI Bridge.

POST /api/admin/openapi/parse    — parse a spec URL, return endpoint list
POST /api/admin/openapi/register — register selected endpoints as tools

Security: both endpoints require JWT + registry:manage permission (Gate 2 RBAC).
The standard admin pattern is used: _require_registry_manager dependency.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.user import UserContext
from openapi_bridge.parser import fetch_and_parse_openapi
from openapi_bridge.schemas import (
    ParseRequest,
    ParseResponse,
    RegisterRequest,
    RegisterResponse,
)
from openapi_bridge.service import register_openapi_endpoints
from security.deps import get_current_user
from security.rbac import has_permission

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin/openapi", tags=["admin-openapi"])


async def _require_registry_manager(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2 dependency: require registry:manage permission."""
    if not await has_permission(user, "registry:manage", session):
        raise HTTPException(
            status_code=403, detail="Registry manage permission required"
        )
    return user


@router.post("/parse")
async def parse_openapi_spec(
    body: ParseRequest,
    user: UserContext = Depends(_require_registry_manager),
) -> ParseResponse:
    """
    Fetch and parse an OpenAPI spec from a URL.

    Returns a structured list of endpoints with parameter info, grouped by tags.
    Deprecated operations are excluded.

    Gate 1: JWT validated by get_current_user.
    Gate 2: registry:manage permission required.
    """
    logger.info(
        "openapi_parse_requested",
        url=body.url,
        user_id=str(user["user_id"]),
    )

    try:
        result = await fetch_and_parse_openapi(body.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning(
            "openapi_parse_failed",
            url=body.url,
            error=str(exc),
            user_id=str(user["user_id"]),
        )
        raise HTTPException(
            status_code=422,
            detail=f"Failed to fetch or parse spec: {str(exc)[:200]}",
        ) from exc

    return result


@router.post("/register")
async def register_openapi_server(
    body: RegisterRequest,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """
    Register selected OpenAPI endpoints as callable tool definitions.

    Creates an McpServer row + ToolDefinition rows with handler_type='openapi_proxy'.
    Invalidates the tool cache so new tools are immediately callable.

    Gate 1: JWT validated by get_current_user.
    Gate 2: registry:manage permission required.
    """
    logger.info(
        "openapi_register_requested",
        server_name=body.server_name,
        endpoint_count=len(body.selected_endpoints),
        user_id=str(user["user_id"]),
    )

    try:
        result = await register_openapi_endpoints(
            server_name=body.server_name,
            base_url=body.base_url,
            spec_url=body.spec_url,
            endpoints=body.selected_endpoints,
            auth_type=body.auth_type,
            auth_value=body.auth_value,
            auth_header=body.auth_header,
            session=session,
        )
    except Exception as exc:
        logger.warning(
            "openapi_register_failed",
            server_name=body.server_name,
            error=str(exc),
            user_id=str(user["user_id"]),
        )
        raise HTTPException(
            status_code=422,
            detail=f"Failed to register OpenAPI endpoints: {str(exc)[:200]}",
        ) from exc

    return result
