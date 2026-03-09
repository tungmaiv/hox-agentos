"""
External skill repository routes.

Admin routes (registry:manage permission):
  GET    /api/admin/skill-repos           — list all repos
  POST   /api/admin/skill-repos           — add a repo by URL
  DELETE /api/admin/skill-repos/{id}      — remove a repo
  POST   /api/admin/skill-repos/{id}/sync — re-sync a repo index

User routes (chat permission):
  GET  /api/skill-repos/browse            — browse/search skills across all repos
  POST /api/skill-repos/import            — import a skill from a repo
"""
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.user import UserContext
from security.deps import get_current_user, require_registry_manager
from security.rbac import has_permission
from skill_repos.schemas import (
    ImportRequest,
    ImportResponse,
    RepoCreate,
    RepoInfo,
    SearchSimilarRequest,
    SearchSimilarResponse,
    SkillBrowseItem,
)
from skill_repos.service import (
    add_repo,
    browse_skills,
    import_from_repo,
    list_repos,
    remove_repo,
    search_similar,
    sync_repo,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Admin router
# ---------------------------------------------------------------------------

admin_router = APIRouter(prefix="/api/admin/skill-repos", tags=["admin-skill-repos"])


@admin_router.post("/search-similar", response_model=SearchSimilarResponse)
async def search_similar_route(
    body: SearchSimilarRequest,
    user: UserContext = Depends(require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> SearchSimilarResponse:
    """Find skills similar to the given name and description using pgvector cosine search.

    Embeds the provided name+description via the embedding sidecar, then queries
    skill_repo_index for the top-k nearest neighbours by cosine distance.

    Route declared BEFORE /{repo_id} catch-alls to avoid path conflicts.
    """
    from memory.embeddings import SidecarEmbeddingProvider

    embed_text = f"{body.name} {body.description}".strip()
    provider = SidecarEmbeddingProvider()

    try:
        vectors = await provider.embed([embed_text])
        query_embedding = vectors[0]
    except Exception as exc:
        logger.warning(
            "search_similar_embed_failed",
            user_id=str(user["user_id"]),
            error=str(exc),
        )
        return SearchSimilarResponse(results=[])

    results = await search_similar(
        query_embedding=query_embedding,
        top_k=body.top_k,
        session=session,
    )

    logger.info(
        "admin_skill_repos_search_similar",
        user_id=str(user["user_id"]),
        name=body.name,
        result_count=len(results),
    )
    return SearchSimilarResponse(results=results)


@admin_router.get("", response_model=list[RepoInfo])
async def list_repos_route(
    user: UserContext = Depends(require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> list[RepoInfo]:
    """List all registered external skill repositories."""
    repos = await list_repos(session)
    logger.info("admin_skill_repos_listed", user_id=str(user["user_id"]), count=len(repos))
    return repos


@admin_router.post("", response_model=RepoInfo, status_code=201)
async def add_repo_route(
    body: RepoCreate,
    user: UserContext = Depends(require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> RepoInfo:
    """Register a new external skill repository by URL.

    Fetches agentskills-index.json from the URL to validate the repo.
    """
    try:
        repo_info = await add_repo(body.url, session)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    logger.info(
        "admin_skill_repo_added",
        repo_name=repo_info.name,
        url=body.url,
        user_id=str(user["user_id"]),
    )
    return repo_info


@admin_router.delete("/{repo_id}", status_code=204)
async def remove_repo_route(
    repo_id: UUID,
    user: UserContext = Depends(require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Remove a registered repository.

    Imported skills that came from this repository are NOT deleted — they remain
    in the system at their current status and can still be used.
    """
    await remove_repo(repo_id, session)
    logger.info(
        "admin_skill_repo_removed",
        repo_id=str(repo_id),
        user_id=str(user["user_id"]),
    )


@admin_router.post("/{repo_id}/sync", response_model=RepoInfo)
async def sync_repo_route(
    repo_id: UUID,
    user: UserContext = Depends(require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> RepoInfo:
    """Re-sync a repository by re-fetching its agentskills-index.json."""
    repo_info = await sync_repo(repo_id, session)
    logger.info(
        "admin_skill_repo_synced",
        repo_id=str(repo_id),
        user_id=str(user["user_id"]),
    )
    return repo_info


# ---------------------------------------------------------------------------
# User router
# ---------------------------------------------------------------------------

user_router = APIRouter(prefix="/api/skill-repos", tags=["skill-repos"])


async def _require_chat(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2 dependency: require chat permission."""
    if not await has_permission(user, "chat", session):
        raise HTTPException(status_code=403, detail="Chat permission required")
    return user


@user_router.get("/browse", response_model=list[SkillBrowseItem])
async def browse_skills_route(
    q: str | None = Query(None, description="Search query — filters by name and description"),
    limit: int = Query(20, ge=1, le=100, description="Page size (default 20)"),
    cursor: int = Query(0, ge=0, description="Offset cursor for Load More pagination"),
    user: UserContext = Depends(_require_chat),
    session: AsyncSession = Depends(get_db),
) -> list[SkillBrowseItem]:
    """Browse skills from all active registered repositories with optional search."""
    items = await browse_skills(q, session, limit=limit, cursor=cursor)
    logger.info(
        "skill_repos_browse",
        user_id=str(user["user_id"]),
        query=q,
        limit=limit,
        cursor=cursor,
        result_count=len(items),
    )
    return items


@user_router.post("/import", response_model=ImportResponse, status_code=201)
async def import_skill_route(
    body: ImportRequest,
    user: UserContext = Depends(_require_chat),
    session: AsyncSession = Depends(get_db),
) -> ImportResponse:
    """Import a skill from a registered repository.

    The skill enters pending_review status and must be approved by an admin
    before it becomes active. A security scan runs automatically on import.
    """
    try:
        repo_uuid = UUID(body.repository_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="Invalid repository_id — must be a UUID"
        ) from exc

    result = await import_from_repo(
        repo_id=repo_uuid,
        skill_name=body.skill_name,
        user_id=user["user_id"],
        session=session,
    )
    logger.info(
        "skill_repo_import",
        repo_id=body.repository_id,
        skill_name=body.skill_name,
        skill_id=result.skill_id,
        user_id=str(user["user_id"]),
    )
    return result
