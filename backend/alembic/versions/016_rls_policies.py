"""Add PostgreSQL Row Level Security policies on all user-data tables.

Enables RLS as defense-in-depth: even if application-level user_id filtering
is bypassed, PostgreSQL enforces isolation at the DB level.

Tables receiving RLS:
  - memory_facts        (long-term memory facts)
  - memory_conversations (conversation turns / short-term memory)
  - user_credentials    (AES-256-GCM encrypted OAuth tokens)
  - workflow_runs       (workflow execution history)
  - memory_episodes     (summarized conversation episodes)
  - conversation_titles (conversation metadata per user)

Policy: USING (user_id = current_setting('app.user_id', true)::uuid)
  - The 'true' arg to current_setting means: return NULL if app.user_id not set
    (instead of raising an error). This makes the policy safe during migrations
    and maintenance operations where app.user_id is not set.
  - FORCE ROW LEVEL SECURITY applies RLS even to the table owner (blitz role).
  - BYPASSRLS is granted to blitz so that service code (Celery workers, FastAPI)
    can call SET LOCAL app.user_id = '...' before each user-scoped query.
    Without BYPASSRLS, FORCE RLS would block service queries that haven't set
    app.user_id (e.g., during startup or admin operations).

Service code MUST call set_rls_user_id(session, user_id) before every
user-scoped query so the app.user_id context variable is populated and
RLS policies evaluate correctly for normal request paths.

Revision ID: 016
Revises: 015
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None

# All user-scoped tables that require RLS isolation.
# These are the actual PostgreSQL table names (not conceptual names from CONTEXT.md).
_RLS_TABLES = [
    "memory_facts",
    "memory_conversations",
    "user_credentials",
    "workflow_runs",
    "memory_episodes",
    "conversation_titles",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # RLS is PostgreSQL-only — skip entirely for SQLite (used in unit tests)
        return

    for table in _RLS_TABLES:
        # Enable RLS on the table
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))  # nosec B608
        # FORCE ensures even the table owner (blitz role) is subject to RLS.
        # This is defense-in-depth: prevents accidental bypasses via psql connections.
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))  # nosec B608

        # SELECT, UPDATE, DELETE policy — checked against existing rows
        op.execute(
            sa.text(
                f"CREATE POLICY user_isolation ON {table} "  # nosec B608
                "USING (user_id = current_setting('app.user_id', true)::uuid)"
            )
        )

        # INSERT policy — WITH CHECK applies to new rows
        # Needed because USING does not apply to INSERT statements
        op.execute(
            sa.text(
                f"CREATE POLICY user_isolation_insert ON {table} "  # nosec B608
                "FOR INSERT WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)"
            )
        )

    # Grant BYPASSRLS to the blitz service role so that:
    # 1. Celery workers and backend API can access tables without RLS blocking them
    # 2. Service code can still call SET LOCAL app.user_id = '...' for user-scoped queries
    # This BYPASSRLS grant is complementary to (not a replacement for) SET LOCAL.
    op.execute(sa.text("GRANT BYPASSRLS TO blitz"))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table in _RLS_TABLES:
        op.execute(sa.text(f"DROP POLICY IF EXISTS user_isolation ON {table}"))  # nosec B608
        op.execute(sa.text(f"DROP POLICY IF EXISTS user_isolation_insert ON {table}"))  # nosec B608
        op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))  # nosec B608
        op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))  # nosec B608

    # Revoke BYPASSRLS (best-effort — ignore if not granted)
    op.execute(sa.text("REVOKE BYPASSRLS FROM blitz"))
