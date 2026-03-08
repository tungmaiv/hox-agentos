"""
check_skill_updates -- daily Celery task to detect upstream skill changes.

Fetches source_url for each active imported skill, computes SHA-256 hash,
and creates a pending_review version row when content has changed.

Null-baseline handling: If source_hash is None (first run after migration),
stores the current hash WITHOUT creating a pending_review row. This avoids
spurious "Update available" indicators for all imported skills on first run.

Pattern: asyncio.run() wrapping async def -- same as embedding.py.
SKSEC-03: Monitors imported skills for upstream changes.
"""
import asyncio
import hashlib
from typing import Any

import httpx
import structlog

from core.db import async_session
from scheduler.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    queue="default",
    name="scheduler.tasks.check_skill_updates.check_skill_updates_task",
)
def check_skill_updates_task() -> None:
    """Daily check for upstream changes to imported skill source URLs."""
    asyncio.run(_check_all_skill_updates())


async def _check_all_skill_updates() -> None:
    from sqlalchemy import select

    from core.models.skill_definition import SkillDefinition

    async with async_session() as session:
        result = await session.execute(
            select(SkillDefinition).where(
                SkillDefinition.source_type == "imported",
                SkillDefinition.source_url.isnot(None),
                SkillDefinition.status == "active",
            )
        )
        skills = result.scalars().all()

    logger.info("skill_update_check_started", skill_count=len(skills))

    for skill in skills:
        try:
            await _check_single_skill(skill)
        except Exception as exc:
            logger.error(
                "skill_update_check_error",
                skill_name=getattr(skill, "name", "unknown"),
                error=str(exc),
            )


async def _check_single_skill(skill: Any) -> None:
    from sqlalchemy import update

    from core.models.skill_definition import SkillDefinition

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(skill.source_url)
            resp.raise_for_status()
    except Exception as exc:
        logger.warning(
            "skill_update_check_fetch_failed",
            skill_name=skill.name,
            error=str(exc),
        )
        return

    new_hash = hashlib.sha256(resp.content).hexdigest()

    if skill.source_hash is None:
        # No baseline -- store hash without creating pending_review
        async with async_session() as session:
            await session.execute(
                update(SkillDefinition)
                .where(SkillDefinition.id == skill.id)
                .values(source_hash=new_hash)
            )
            await session.commit()
        logger.info(
            "skill_update_baseline_stored",
            skill_name=skill.name,
            skill_id=str(skill.id),
        )
        return

    if new_hash == skill.source_hash:
        return  # No change

    # Change detected -- create pending_review version row
    new_version = _bump_version(skill.version)
    async with async_session() as session:
        new_row = SkillDefinition(
            name=skill.name,
            display_name=skill.display_name,
            description=skill.description,
            version=new_version,
            status="pending_review",
            skill_type=skill.skill_type,
            source_type=skill.source_type,
            source_url=skill.source_url,
            source_hash=new_hash,
            instruction_markdown=skill.instruction_markdown,
            procedure_json=skill.procedure_json,
            input_schema=skill.input_schema,
            output_schema=skill.output_schema,
            license=skill.license,
            compatibility=skill.compatibility,
            metadata_json=skill.metadata_json,
            allowed_tools=skill.allowed_tools,
            tags=skill.tags,
            category=skill.category,
            created_by=skill.created_by,
        )
        session.add(new_row)
        await session.commit()

    logger.info(
        "skill_update_detected",
        skill_name=skill.name,
        old_version=skill.version,
        new_version=new_version,
    )


def _bump_version(version: str) -> str:
    """Bump patch segment: '1.0.0' -> '1.0.1'. Handles non-semver gracefully."""
    parts = version.split(".")
    if len(parts) >= 3:
        try:
            parts[2] = str(int(parts[2]) + 1)
            return ".".join(parts)
        except ValueError:
            pass
    return f"{version}.1"
