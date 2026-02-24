"""Initial schema: tool_acl table

Creates the tool_acl table for Gate 3 (per-user Tool ACL),
enables the pgvector extension for future memory vector search,
and enables uuid-ossp for UUID generation.

Revision ID: 001
Revises:
Create Date: 2026-02-24
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension (required for vector(1024) columns in memory_facts)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Enable uuid-ossp for UUID generation in PostgreSQL
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table(
        "tool_acl",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("granted_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "tool_name", name="uq_tool_acl_user_tool"),
    )

    # Index for fast ACL lookup by user_id
    op.create_index(
        "ix_tool_acl_user_id",
        "tool_acl",
        ["user_id"],
    )

    # Seed: deny email.fetch for dev test user
    # UUID matches the fixed test user in Keycloak blitz-internal realm.
    # Replace with actual test user UUID from .dev-secrets after Keycloak
    # client is registered (see docs/dev-context.md).
    op.execute("""
        INSERT INTO tool_acl (user_id, tool_name, allowed)
        VALUES ('00000000-0000-0000-0000-000000000001', 'email.fetch', false)
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("ix_tool_acl_user_id", table_name="tool_acl")
    op.drop_table("tool_acl")
