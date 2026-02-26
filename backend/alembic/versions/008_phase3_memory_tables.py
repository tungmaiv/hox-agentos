"""Add memory_episodes and memory_facts tables for Phase 3 long-term memory

Revision ID: 008
Revises: 007
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure pgvector extension is active
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "memory_episodes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
        # No FK to users table — Keycloak manages user identity.
        # user_id values are validated at the application layer via JWT (Gate 1).
    )
    # Convert embedding column to vector(1024) after creation
    op.execute(
        "ALTER TABLE memory_episodes ALTER COLUMN embedding TYPE vector(1024) USING NULL"
    )

    op.create_table(
        "memory_facts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("superseded_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # No FK to users table — Keycloak manages user identity.
        # user_id values are validated at the application layer via JWT (Gate 1).
    )
    op.execute(
        "ALTER TABLE memory_facts ALTER COLUMN embedding TYPE vector(1024) USING NULL"
    )

    # User isolation indexes (support parameterized WHERE user_id = $1 queries)
    op.create_index("ix_memory_episodes_user_id", "memory_episodes", ["user_id"])
    op.create_index(
        "ix_memory_episodes_user_conversation",
        "memory_episodes",
        ["user_id", "conversation_id"],
    )
    op.create_index("ix_memory_facts_user_id", "memory_facts", ["user_id"])

    # HNSW indexes for cosine similarity search (partial — only on non-null embeddings)
    op.execute("""
        CREATE INDEX ix_memory_facts_embedding_hnsw
        ON memory_facts USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX ix_memory_episodes_embedding_hnsw
        ON memory_episodes USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL
    """)

    # updated_at trigger for memory_facts (soft-delete: superseded_at tracks conflicts)
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN NEW.updated_at = now(); RETURN NEW; END;
        $$ language 'plpgsql'
    """)
    op.execute("""
        CREATE TRIGGER memory_facts_updated_at
        BEFORE UPDATE ON memory_facts
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS memory_facts_updated_at ON memory_facts")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    op.drop_index("ix_memory_episodes_embedding_hnsw", table_name="memory_episodes")
    op.drop_index("ix_memory_facts_embedding_hnsw", table_name="memory_facts")
    op.drop_index("ix_memory_episodes_user_conversation", table_name="memory_episodes")
    op.drop_index("ix_memory_episodes_user_id", table_name="memory_episodes")
    op.drop_index("ix_memory_facts_user_id", table_name="memory_facts")
    op.drop_table("memory_facts")
    op.drop_table("memory_episodes")
