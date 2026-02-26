"""Add DB-level trigger to auto-update user_instructions.updated_at on row update

Revision ID: 006
Revises: 005
Create Date: 2026-02-26
"""
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create trigger function (idempotent via CREATE OR REPLACE)
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    # Attach trigger to user_instructions table
    op.execute("""
        CREATE TRIGGER user_instructions_set_updated_at
        BEFORE UPDATE ON user_instructions
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS user_instructions_set_updated_at ON user_instructions;"
    )
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")
