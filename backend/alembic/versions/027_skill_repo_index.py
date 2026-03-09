"""create skill_repo_index table

Revision ID: 027
Revises: 026
Create Date: 2026-03-10

Phase 23-SKBLD-04/05: Similar skill search and fork from external repositories.
Creates skill_repo_index table with pgvector(1024) embedding column and HNSW
cosine index (m=16, ef_construction=64) for efficient nearest-neighbour skill
discovery across synced skill repositories.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgvector extension is active (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "skill_repo_index",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("repository_id", UUID(as_uuid=True), nullable=False),
        sa.Column("skill_name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("category", sa.Text, nullable=True),
        sa.Column("tags", sa.JSON, nullable=True),
        # Placeholder TEXT — converted to vector(1024) below
        sa.Column("embedding", sa.Text, nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Convert embedding placeholder to vector(1024)
    op.execute(
        "ALTER TABLE skill_repo_index ALTER COLUMN embedding TYPE vector(1024) USING NULL"
    )

    # HNSW cosine index with m=16, ef_construction=64
    op.execute("""
        CREATE INDEX ix_skill_repo_index_embedding_hnsw
        ON skill_repo_index USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        WHERE embedding IS NOT NULL
    """)

    # Repository lookup index
    op.create_index(
        "ix_skill_repo_index_repository_id",
        "skill_repo_index",
        ["repository_id"],
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS ix_skill_repo_index_embedding_hnsw"
    )
    op.drop_index("ix_skill_repo_index_repository_id", table_name="skill_repo_index")
    op.drop_table("skill_repo_index")
