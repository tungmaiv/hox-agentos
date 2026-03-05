"""
Admin memory management routes.

POST /api/admin/memory/reindex — enqueue a full memory reindex job.

Security: requires tool:admin permission (Gate 2 RBAC).
The tool:admin permission is granted only to the it-admin role.
confirm=true in the request body is required to prevent accidental triggers.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.user import UserContext
from scheduler.tasks.embedding import reindex_memory_task
from security.deps import get_current_user
from security.rbac import has_permission

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/admin/memory", tags=["admin-memory"])


class ReindexRequest(BaseModel):
    confirm: bool

    @model_validator(mode="after")
    def must_confirm(self) -> "ReindexRequest":
        if not self.confirm:
            raise ValueError("confirm must be true to proceed with reindex")
        return self


class ReindexResponse(BaseModel):
    job_id: str
    message: str


async def _require_admin(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2 dependency: require tool:admin permission (it-admin role only)."""
    if not await has_permission(user, "tool:admin", session):
        raise HTTPException(status_code=403, detail="Admin permission required")
    return user


@router.post("/reindex", response_model=ReindexResponse, status_code=202)
async def trigger_reindex(
    body: ReindexRequest,
    user: UserContext = Depends(_require_admin),
) -> ReindexResponse:
    """
    Enqueue a full memory reindex job.

    Overwrites all embedding vectors and re-embeds from source text.
    Requires it-admin role and confirm=true in body.
    """
    task = reindex_memory_task.delay()
    logger.info(
        "memory_reindex_enqueued",
        job_id=task.id,
        user_id=str(user["user_id"]),
    )
    return ReindexResponse(
        job_id=task.id,
        message="Reindex job enqueued. All memory vectors will be re-embedded.",
    )
