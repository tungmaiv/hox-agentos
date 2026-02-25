"""Add user_credentials table for AES-256 encrypted OAuth tokens

Revision ID: 003
Revises: 001
Create Date: 2026-02-25

Note: Migration 002 (memory_conversations) and 003 (user_credentials) both branch from 001.
When both are applied, Alembic will have two heads and REQUIRE a merge migration before
'alembic upgrade head' will succeed. The merge migration is created when both 002 and 003
co-exist (see Task 2 in 02-04 plan).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "003"
down_revision = "001"  # Branches from 001 in parallel with 002
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_credentials",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # user_id from JWT — never from request body
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        # Provider identifier: 'google', 'microsoft', etc.
        sa.Column("provider", sa.Text(), nullable=False),
        # AES-256-GCM encrypted token (ciphertext)
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        # AES-GCM initialization vector (random per encryption)
        sa.Column("iv", sa.LargeBinary(), nullable=False),
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
        # One credential per user per provider
        sa.UniqueConstraint("user_id", "provider", name="uq_user_credentials_user_provider"),
    )


def downgrade() -> None:
    op.drop_table("user_credentials")
