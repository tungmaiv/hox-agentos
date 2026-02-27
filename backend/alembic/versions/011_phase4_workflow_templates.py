"""Phase 4 — Workflow template data migration

Inserts the two pre-built workflow templates (Morning Digest and Alert)
as is_template=true rows with owner_user_id=NULL.

owner_user_id=NULL is valid because the column was created nullable
in migration 010 — template rows have no owner user.

To apply this migration:
  just migrate
  (or from host: cd backend && .venv/bin/alembic upgrade head)
  (or via docker: docker exec -it blitz-postgres sh -c
    "cd /app && .venv/bin/alembic upgrade head")

Revision ID: 011
Revises: 010
Create Date: 2026-02-27
"""
import json
import pathlib

import sqlalchemy as sa
from alembic import op


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None

# Path to fixture files, resolved relative to this migration file:
# alembic/versions/ → alembic/ → backend/ → data/workflow_templates/
_FIXTURES_DIR = (
    pathlib.Path(__file__).parent.parent.parent / "data" / "workflow_templates"
)


_TEMPLATE_IDS: dict[str, str] = {
    "morning_digest.json": "00000000-0000-0000-0001-000000000001",
    "alert.json": "00000000-0000-0000-0001-000000000002",
}


def upgrade() -> None:
    bind = op.get_bind()
    for filename in ["morning_digest.json", "alert.json"]:
        fixture_path = _FIXTURES_DIR / filename
        data = json.loads(fixture_path.read_text())
        # Convert "morning_digest" → "Morning Digest"
        base_name = filename.replace(".json", "").replace("_", " ").title()
        bind.execute(
            sa.text(
                "INSERT INTO workflows "
                "(id, owner_user_id, name, description, definition_json, is_template, "
                " created_at, updated_at) "
                "VALUES (:id, NULL, :name, :description, CAST(:definition_json AS jsonb), true, "
                " now(), now()) "
                "ON CONFLICT DO NOTHING"
            ),
            {
                "id": _TEMPLATE_IDS[filename],
                "name": base_name,
                "description": f"Pre-built {base_name} template",
                "definition_json": json.dumps(data),
            },
        )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM workflows WHERE is_template = true")
    )
