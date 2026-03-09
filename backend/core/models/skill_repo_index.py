"""
SkillRepoIndex ORM model — index of skills synced from external repositories.

Each row represents a skill discovered in an external skill repository
(identified by repository_id). The embedding column holds the bge-m3 1024-dim
vector for the skill's description, enabling cosine-similarity nearest-neighbour
search for the "similar skills" feature in the artifact builder (SKBLD-04/05).

Query pattern:
    .order_by(SkillRepoIndex.embedding.cosine_distance(query_embedding))
    .limit(k)

HNSW index (m=16, ef_construction=64) created by migration 027 ensures
sub-linear search latency even as the index grows.

Migration: 027_skill_repo_index
"""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, JSON, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class SkillRepoIndex(Base):
    """Index entry for a skill from an external skill repository."""

    __tablename__ = "skill_repo_index"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # UUID of the SkillRepository row this skill was synced from (no FK — SQLite compat)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    skill_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON array of tag strings, e.g. ["email", "automation"]
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # bge-m3 1024-dim embedding of description (nullable until embedded)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
