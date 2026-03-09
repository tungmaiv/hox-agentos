"""
External skill repository management service.

Functions:
- fetch_index(url)                          — fetch and validate agentskills-index.json
- add_repo(url, session)                    — register a new repo (fetches index on add)
- remove_repo(repo_id, session)             — delete a repo (imported skills remain)
- sync_repo(repo_id, session)               — re-fetch index, update cached_index + skill_repo_index
- list_repos(session)                       — list all repos with skill_count
- browse_skills(query, session)             — aggregate + filter skills from all active repos
- search_similar(query_embedding, top_k,   — cosine search over skill_repo_index (SKBLD-04)
                 session)
- import_from_repo(repo_id, skill_name,     — import a skill via SkillImporter + SecurityScanner
                   user_id, session)
"""
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
import structlog
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.skill_definition import SkillDefinition
from core.models.skill_repo_index import SkillRepoIndex
from core.models.skill_repository import SkillRepository
from memory.embeddings import SidecarEmbeddingProvider
from skill_repos.schemas import (
    ImportResponse,
    IndexSchema,
    RepoInfo,
    SkillBrowseItem,
)
from skills.importer import SkillImporter
from skills.security_scanner import SecurityScanner

logger = structlog.get_logger(__name__)


def _repo_to_info(repo: SkillRepository) -> RepoInfo:
    """Convert SkillRepository ORM instance to RepoInfo schema."""
    skill_count = 0
    if repo.cached_index and isinstance(repo.cached_index.get("skills"), list):
        skill_count = len(repo.cached_index["skills"])

    last_synced: str | None = None
    if repo.last_synced_at is not None:
        last_synced = repo.last_synced_at.isoformat()

    return RepoInfo(
        id=str(repo.id),
        name=repo.name,
        url=repo.url,
        description=repo.description,
        is_active=repo.is_active,
        last_synced_at=last_synced,
        skill_count=skill_count,
    )


async def fetch_index(url: str) -> dict[str, Any]:
    """Fetch and validate the agentskills-index.json from a remote repository.

    Args:
        url: Base URL of the repository (with or without trailing slash).

    Returns:
        Parsed and validated index dict.

    Raises:
        ValueError: When the index structure is invalid or missing required fields.
        httpx.HTTPError: When the HTTP request fails.
    """
    base = url.rstrip("/")
    index_url = f"{base}/agentskills-index.json"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(index_url)
        response.raise_for_status()

    raw = response.json()

    try:
        IndexSchema.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid agentskills-index.json: {exc}") from exc

    logger.info("repo_index_fetched", url=index_url, skill_count=len(raw.get("skills", [])))
    return raw


async def add_repo(url: str, session: AsyncSession) -> RepoInfo:
    """Register a new external skill repository.

    Fetches the index, validates it, checks name uniqueness,
    and creates a SkillRepository row.

    Args:
        url: Base URL of the repository.
        session: Async DB session.

    Returns:
        RepoInfo for the newly created repository.

    Raises:
        ValueError: When a repo with the same name already exists.
        httpx.HTTPError: When the index cannot be fetched.
    """
    index = await fetch_index(url)
    repo_meta: dict[str, Any] = index.get("repository", {})
    name: str = repo_meta.get("name", "")
    description: str | None = repo_meta.get("description") or None

    # Check name uniqueness
    existing = await session.execute(
        select(SkillRepository).where(SkillRepository.name == name)
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Repository with name '{name}' already exists")

    now = datetime.now(timezone.utc)
    repo = SkillRepository(
        name=name,
        url=url.rstrip("/"),
        description=description,
        cached_index=index,
        last_synced_at=now,
    )
    session.add(repo)
    await session.commit()
    await session.refresh(repo)

    logger.info("repo_added", name=name, url=url)
    return _repo_to_info(repo)


async def remove_repo(repo_id: UUID, session: AsyncSession) -> None:
    """Delete a registered skill repository.

    Imported skills in skill_definitions are NOT deleted — they remain in the
    system and can still be approved/rejected/run.

    Args:
        repo_id: UUID of the repository to delete.
        session: Async DB session.

    Raises:
        HTTPException(404): When the repo is not found.
    """
    result = await session.execute(
        select(SkillRepository).where(SkillRepository.id == repo_id)
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    await session.delete(repo)
    await session.commit()
    logger.info("repo_removed", repo_id=str(repo_id))


async def sync_repo(repo_id: UUID, session: AsyncSession) -> RepoInfo:
    """Re-fetch the index for a repository and update cached_index + last_synced_at.

    Also populates skill_repo_index table with embeddings for the "Find Similar"
    cosine search feature (SKBLD-04). Each skill entry gets an embedding computed
    from "name description" via SidecarEmbeddingProvider. If the sidecar is
    unavailable, the row is inserted with embedding=None (search gracefully skips it).

    Args:
        repo_id: UUID of the repository to sync.
        session: Async DB session.

    Returns:
        Updated RepoInfo.

    Raises:
        HTTPException(404): When the repo is not found.
    """
    result = await session.execute(
        select(SkillRepository).where(SkillRepository.id == repo_id)
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    index = await fetch_index(repo.url)
    repo.cached_index = index
    repo.last_synced_at = datetime.now(timezone.utc)

    # Populate skill_repo_index with embeddings ---------------------------------
    # Delete existing rows for this repository before re-inserting
    await session.execute(
        delete(SkillRepoIndex).where(SkillRepoIndex.repository_id == repo_id)
    )

    skills: list[dict[str, Any]] = index.get("skills", [])
    embedding_provider = SidecarEmbeddingProvider()
    indexed_count = 0

    for skill in skills:
        skill_name: str = skill.get("name", "")
        description: str | None = skill.get("description") or None
        meta: dict[str, Any] = skill.get("metadata") or {}
        source_url: str | None = meta.get("source_url") or skill.get("source_url") or None
        category: str | None = meta.get("category") or None
        tags: list | None = meta.get("tags") if isinstance(meta.get("tags"), list) else None

        # Compute embedding: embed "name description" text
        embedding: list[float] | None = None
        embed_text = f"{skill_name} {description or ''}".strip()
        try:
            vectors = await embedding_provider.embed([embed_text])
            embedding = vectors[0] if vectors else None
        except Exception as exc:
            logger.warning(
                "skill_repo_index_embed_failed",
                skill_name=skill_name,
                repo_id=str(repo_id),
                error=str(exc),
            )

        row = SkillRepoIndex(
            repository_id=repo_id,
            skill_name=skill_name,
            description=description,
            source_url=source_url,
            category=category,
            tags=tags,
            embedding=embedding,
            synced_at=datetime.now(timezone.utc),
        )
        session.add(row)
        indexed_count += 1

    await session.commit()
    await session.refresh(repo)

    logger.info(
        "repo_synced",
        repo_id=str(repo_id),
        skill_count=len(skills),
        indexed_count=indexed_count,
    )
    return _repo_to_info(repo)


async def list_repos(session: AsyncSession) -> list[RepoInfo]:
    """Return all registered repositories with skill counts.

    Args:
        session: Async DB session.

    Returns:
        List of RepoInfo, one per registered repository.
    """
    result = await session.execute(select(SkillRepository))
    repos = result.scalars().all()
    return [_repo_to_info(r) for r in repos]


async def browse_skills(
    query: str | None,
    session: AsyncSession,
    limit: int = 20,
    cursor: int = 0,
) -> list[SkillBrowseItem]:
    """Aggregate skills from all active repositories with optional search filter.

    Reads cached_index from each active SkillRepository. No remote requests.

    Args:
        query: Optional search string — case-insensitive substring match
               on skill name OR description.
        session: Async DB session.
        limit: Maximum number of items to return (default 20).
        cursor: Offset into the full result set for Load More pagination (default 0).

    Returns:
        List of SkillBrowseItem aggregated from all active repos, paginated.
    """
    result = await session.execute(
        select(SkillRepository).where(SkillRepository.is_active == True)  # noqa: E712
    )
    repos = result.scalars().all()

    items: list[SkillBrowseItem] = []
    for repo in repos:
        if not repo.cached_index:
            continue
        skills: list[dict[str, Any]] = repo.cached_index.get("skills", [])
        for skill in skills:
            name: str = skill.get("name", "")
            description: str | None = skill.get("description") or None

            if query:
                q = query.lower()
                name_match = q in name.lower()
                desc_match = q in (description or "").lower()
                if not name_match and not desc_match:
                    continue

            meta = skill.get("metadata") or {}
            items.append(
                SkillBrowseItem(
                    name=name,
                    description=description,
                    version=skill.get("version"),
                    repository_name=repo.name,
                    repository_id=str(repo.id),
                    metadata=meta or None,
                    category=meta.get("category"),
                    tags=meta.get("tags") if isinstance(meta.get("tags"), list) else None,
                    license=meta.get("license"),
                    author=meta.get("author"),
                    source_url=meta.get("source_url"),
                )
            )

    return items[cursor : cursor + limit]


async def search_similar(
    query_embedding: list[float],
    session: AsyncSession,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Search skill_repo_index for skills similar to the given embedding.

    Performs a cosine distance nearest-neighbour search over SkillRepoIndex rows
    that have a non-NULL embedding. Rows without embeddings are skipped (they were
    inserted with embedding=None because the sidecar was unavailable at sync time).

    The result includes repository_name by joining SkillRepository rows in a
    separate query (not a SQL join, to preserve async simplicity).

    Args:
        query_embedding: 1024-dim query vector to search against.
        session: Async DB session.
        top_k: Maximum number of results to return (default 5).

    Returns:
        List of dicts with keys: name, description, repository_name, source_url,
        category, tags. Ordered by cosine distance (most similar first).
        Empty list if no rows with embeddings exist.
    """
    # Cosine distance query — pgvector sorts ascending (closest = 0.0 first)
    stmt = (
        select(SkillRepoIndex)
        .where(SkillRepoIndex.embedding.is_not(None))
        .order_by(SkillRepoIndex.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        return []

    # Resolve repository names — fetch all referenced repos in one query
    repo_ids = list({row.repository_id for row in rows})
    repo_result = await session.execute(
        select(SkillRepository).where(SkillRepository.id.in_(repo_ids))
    )
    repo_map: dict[uuid.UUID, str] = {
        r.id: r.name for r in repo_result.scalars().all()
    }

    return [
        {
            "name": row.skill_name,
            "description": row.description,
            "repository_name": repo_map.get(row.repository_id, ""),
            "source_url": row.source_url,
            "category": row.category,
            "tags": row.tags,
        }
        for row in rows
    ]


async def import_from_repo(
    repo_id: UUID,
    skill_name: str,
    user_id: UUID,
    session: AsyncSession,
) -> ImportResponse:
    """Import a skill from a registered repository.

    Flow:
    1. Look up repo by id
    2. Find skill entry by name in cached_index
    3. Fetch SKILL.md via SkillImporter.import_from_url(skill_url)
    4. Run SecurityScanner.scan(skill_data, source_url=skill_url)
    5. Create SkillDefinition with status='pending_review' and security data

    Args:
        repo_id: UUID of the source repository.
        skill_name: Name of the skill to import (must exist in cached_index).
        user_id: UUID of the requesting user (stored as created_by).
        session: Async DB session.

    Returns:
        ImportResponse with skill_id, name, status, security_score, recommendation.

    Raises:
        HTTPException(404): When the repo is not found.
        HTTPException(404): When the skill_name is not found in the repo index.
    """
    # 1. Look up repo
    result = await session.execute(
        select(SkillRepository).where(SkillRepository.id == repo_id)
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    # 2. Find skill in cached_index
    skills: list[dict[str, Any]] = (repo.cached_index or {}).get("skills", [])
    skill_entry = next((s for s in skills if s.get("name") == skill_name), None)
    if skill_entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Skill '{skill_name}' not found in repository '{repo.name}'",
        )

    skill_url: str = skill_entry["skill_url"]

    # 3. Fetch SKILL.md via SkillImporter
    importer = SkillImporter()
    skill_data = await importer.import_from_url(skill_url)

    # 4. Security scan
    scanner = SecurityScanner()
    report = scanner.scan(skill_data, source_url=skill_url)

    # 5. Create SkillDefinition with pending_review quarantine
    skill = SkillDefinition(
        name=skill_data["name"],
        display_name=skill_data.get("display_name"),
        description=skill_data.get("description"),
        version=skill_data.get("version", "1.0.0"),
        skill_type=skill_data.get("skill_type", "instructional"),
        slash_command=skill_data.get("slash_command"),
        source_type="imported",
        instruction_markdown=skill_data.get("instruction_markdown"),
        procedure_json=skill_data.get("procedure_json"),
        input_schema=skill_data.get("input_schema"),
        output_schema=skill_data.get("output_schema"),
        status="pending_review",
        is_active=False,
        security_score=report.score,
        security_report={
            "score": report.score,
            "factors": report.factors,
            "recommendation": report.recommendation,
            "injection_matches": report.injection_matches,
        },
        created_by=user_id,
    )
    session.add(skill)
    await session.commit()
    await session.refresh(skill)

    logger.info(
        "skill_imported_from_repo",
        repo_id=str(repo_id),
        skill_name=skill_name,
        skill_id=str(skill.id),
        security_score=report.score,
        recommendation=report.recommendation,
        user_id=str(user_id),
    )

    return ImportResponse(
        skill_id=str(skill.id),
        name=skill.name,
        status="pending_review",
        security_score=report.score,
        security_recommendation=report.recommendation,
    )
