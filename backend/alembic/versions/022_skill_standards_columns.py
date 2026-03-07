"""skill_standards_columns

Revision ID: 022
Revises: 83f730920f5a
Create Date: 2026-03-07 00:00:00.000000

Phase 19-01: Add 7 agentskills.io standard columns to skill_definitions.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "022"
down_revision: Union[str, None] = "83f730920f5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "skill_definitions",
        sa.Column("license", sa.Text(), nullable=True),
    )
    op.add_column(
        "skill_definitions",
        sa.Column("compatibility", sa.Text(), nullable=True),
    )
    op.add_column(
        "skill_definitions",
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "skill_definitions",
        sa.Column(
            "allowed_tools",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "skill_definitions",
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "skill_definitions",
        sa.Column("category", sa.Text(), nullable=True),
    )
    op.add_column(
        "skill_definitions",
        sa.Column("source_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("skill_definitions", "source_url")
    op.drop_column("skill_definitions", "category")
    op.drop_column("skill_definitions", "tags")
    op.drop_column("skill_definitions", "allowed_tools")
    op.drop_column("skill_definitions", "metadata_json")
    op.drop_column("skill_definitions", "compatibility")
    op.drop_column("skill_definitions", "license")
