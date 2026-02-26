"""Add system_config and mcp_servers tables for Phase 3 Settings infrastructure

Revision ID: 007
Revises: 006
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # system_config: admin key/value store (key-addressable JSONB)
    op.create_table(
        "system_config",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # mcp_servers: MCP server registry (name, url, encrypted auth_token, is_active)
    op.create_table(
        "mcp_servers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "auth_token",
            sa.LargeBinary(),
            nullable=True,  # AES-256 encrypted
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Seed default agent feature flags and embedding model config
    op.execute("""
        INSERT INTO system_config (key, value) VALUES
            ('agent.email.enabled',              'true'::jsonb),
            ('agent.calendar.enabled',           'true'::jsonb),
            ('agent.project.enabled',            'true'::jsonb),
            ('embedding_model',                  '"bge-m3"'::jsonb),
            ('memory.episode_turn_threshold',    '10'::jsonb)
    """)


def downgrade() -> None:
    op.drop_table("mcp_servers")
    op.drop_table("system_config")
