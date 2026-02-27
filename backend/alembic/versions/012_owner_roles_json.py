"""Add owner_roles_json to workflow_runs and workflow_triggers.

Stores the owner's Keycloak roles at creation time so Celery workers
can build the correct UserContext instead of hardcoding ["employee"].

Revision ID: 012
Revises: 011
Create Date: 2026-02-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_runs",
        sa.Column(
            "owner_roles_json",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="[]",
        ),
    )
    op.add_column(
        "workflow_triggers",
        sa.Column(
            "owner_roles_json",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("workflow_triggers", "owner_roles_json")
    op.drop_column("workflow_runs", "owner_roles_json")
