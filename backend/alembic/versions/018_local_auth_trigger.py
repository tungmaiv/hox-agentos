"""Add updated_at trigger to local_users table.

Migration 017 created the local_users table with an updated_at column but
did not attach the set_updated_at() trigger (created in migration 006).
This migration adds the missing trigger so that updated_at is auto-maintained.

Revision ID: 018
Revises: 017
Create Date: 2026-03-04
"""
from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TRIGGER local_users_set_updated_at
        BEFORE UPDATE ON local_users
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS local_users_set_updated_at ON local_users;")
