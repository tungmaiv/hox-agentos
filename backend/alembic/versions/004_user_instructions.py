"""Add user_instructions table for per-user custom agent instructions

Revision ID: 004
Revises: 9754fd080ee2
Create Date: 2026-02-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "004"
down_revision = "9754fd080ee2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_instructions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # One row per user — upsert pattern
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, unique=True, index=True),
        # The custom instructions text (up to ~4000 chars)
        sa.Column("instructions", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("user_instructions")
