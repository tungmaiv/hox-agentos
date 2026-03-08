"""add is_promoted column to skill_definitions

Revision ID: 025
Revises: 024
Create Date: 2026-03-08

Phase 22-SKMKT-01: Admin can promote skills to the marketplace catalog.
Adds a boolean is_promoted column (NOT NULL, default false) to skill_definitions.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "skill_definitions",
        sa.Column(
            "is_promoted",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("skill_definitions", "is_promoted")
