"""Add created_at and updated_at to conversation_titles

Revision ID: 009
Revises: 008
Create Date: 2026-02-26
"""
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Migration 005 was later updated to include these columns at table creation.
    # Use ADD COLUMN IF NOT EXISTS so this migration is a no-op on fresh DBs.
    op.execute(sa.text(
        "ALTER TABLE conversation_titles "
        "ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
    ))
    op.execute(sa.text(
        "ALTER TABLE conversation_titles "
        "ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
    ))


def downgrade() -> None:
    op.execute("ALTER TABLE conversation_titles DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE conversation_titles DROP COLUMN IF EXISTS created_at")
