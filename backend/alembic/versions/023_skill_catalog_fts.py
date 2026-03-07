"""skill_catalog_fts

Revision ID: 023
Revises: 022
Create Date: 2026-03-07 00:00:00.000000

Phase 20-01: Add usage_count column and tsvector GIN index for FTS on skill_definitions.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add usage_count with default 0 — fire-and-forget increment on every skill invocation
    op.add_column(
        "skill_definitions",
        sa.Column(
            "usage_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # Create GIN index for tsvector FTS on name + description
    # Uses 'simple' language config (no stop-word stripping) — required for Vietnamese support
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_skill_definitions_fts
        ON skill_definitions
        USING GIN (
            to_tsvector('simple', coalesce(name, '') || ' ' || coalesce(description, ''))
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_skill_definitions_fts")
    op.drop_column("skill_definitions", "usage_count")
