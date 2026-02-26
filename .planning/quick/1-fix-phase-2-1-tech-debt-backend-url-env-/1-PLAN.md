---
phase: 02.1-tech-debt-cleanup
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/app/api/conversations/route.ts
  - frontend/src/app/api/conversations/[id]/route.ts
  - frontend/src/app/api/conversations/[id]/messages/route.ts
  - frontend/src/app/api/conversations/[id]/title/route.ts
  - frontend/src/app/api/copilotkit/route.ts
  - frontend/src/app/api/copilotkit/[...path]/route.ts
  - backend/core/models/user_instructions.py
  - backend/alembic/versions/005_fix_user_instructions_updated_at.py
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "All 6 affected frontend server routes use NEXT_PUBLIC_API_URL (not BACKEND_URL)"
    - "user_instructions.updated_at updates to current timestamp on every PUT"
    - "REQUIREMENTS.md shows [x] for all 12 completed requirements"
    - "ROADMAP.md shows [x] for 01-04-PLAN.md"
  artifacts:
    - path: "backend/alembic/versions/005_fix_user_instructions_updated_at.py"
      provides: "Migration adding DB-level trigger for updated_at auto-update"
      contains: "ALTER TABLE user_instructions ALTER COLUMN updated_at"
    - path: "backend/core/models/user_instructions.py"
      provides: "ORM model with onupdate=func.now() on updated_at column"
      contains: "onupdate=func.now()"
  key_links:
    - from: "frontend/.env.local"
      to: "frontend/src/app/api/*/route.ts"
      via: "process.env.NEXT_PUBLIC_API_URL"
      pattern: "NEXT_PUBLIC_API_URL"
---

<objective>
Close the fixable tech debt items from the v1.0 milestone audit: standardize the backend URL env var across all frontend server routes, fix the user_instructions.updated_at onupdate behavior, and correct stale documentation checkboxes in REQUIREMENTS.md and ROADMAP.md.

Purpose: Prevent deployment misconfiguration risk from the BACKEND_URL split, and ensure PUT /api/user/instructions/ returns accurate timestamps.
Output: 6 route files updated, 1 ORM model updated, 1 migration file added, 2 planning docs corrected.
</objective>

<execution_context>
@/home/tungmv/.claude/get-shit-done/workflows/execute-plan.md
@/home/tungmv/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/v1.0-MILESTONE-AUDIT.md
@frontend/.env.local
</context>

<tasks>

<task type="auto">
  <name>Task 1: Standardize backend URL env var across all frontend server routes</name>
  <files>
    frontend/src/app/api/conversations/route.ts
    frontend/src/app/api/conversations/[id]/route.ts
    frontend/src/app/api/conversations/[id]/messages/route.ts
    frontend/src/app/api/conversations/[id]/title/route.ts
    frontend/src/app/api/copilotkit/route.ts
    frontend/src/app/api/copilotkit/[...path]/route.ts
  </files>
  <action>
    The 5 routes currently use `process.env.BACKEND_URL` but `frontend/.env.local` only defines `NEXT_PUBLIC_API_URL=http://localhost:8000`. The `user/instructions/route.ts` already uses `NEXT_PUBLIC_API_URL` correctly. Standardize all 5 mismatched routes.

    For each of the 5 routes, change the backend URL declaration to use `NEXT_PUBLIC_API_URL`:

    1. `conversations/route.ts` line 20: change `process.env.BACKEND_URL ?? "http://localhost:8000"` to `process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"`
    2. `conversations/[id]/route.ts` line 9: same change (variable named `API_URL`)
    3. `conversations/[id]/messages/route.ts` line 22: same change (variable named `apiUrl`)
    4. `conversations/[id]/title/route.ts` line 9: same change (variable named `API_URL`)
    5. `copilotkit/route.ts` line 16: change `process.env.BACKEND_URL` to `process.env.NEXT_PUBLIC_API_URL` (variable named `BACKEND_URL` — rename to `API_URL` for clarity but keep fallback)
    6. `copilotkit/[...path]/route.ts` line 17: same change

    Note: `NEXT_PUBLIC_API_URL` is technically a public prefix but these are all server-side Next.js Route Handlers (never bundled to the browser), so using it here is safe and consistent with the existing pattern in `user/instructions/route.ts`. Do NOT introduce a new `BACKEND_URL` env var — that would require `.env.local` changes and perpetuate the split.

    No logic changes, only the env var name. The fallback `?? "http://localhost:8000"` stays in place.
  </action>
  <verify>
    <automated>grep -rn "process.env.BACKEND_URL" /home/tungmv/Projects/hox-agentos/frontend/src/app/api/ | wc -l</automated>
    <manual>Output must be 0 — no remaining BACKEND_URL references in frontend API routes</manual>
  </verify>
  <done>Zero occurrences of `process.env.BACKEND_URL` in `frontend/src/app/api/`; all 6 route files reference `process.env.NEXT_PUBLIC_API_URL`</done>
</task>

<task type="auto">
  <name>Task 2: Fix user_instructions.updated_at — add onupdate to ORM model and migration</name>
  <files>
    backend/core/models/user_instructions.py
    backend/alembic/versions/005_fix_user_instructions_updated_at.py
  </files>
  <action>
    Two changes required:

    **A. ORM model fix (`backend/core/models/user_instructions.py`):**

    The `updated_at` column currently has `server_default=func.now()` but no `onupdate`. Add `onupdate=func.now()` so SQLAlchemy triggers an UPDATE SET on every row update:

    ```python
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    ```

    **B. Alembic migration (`backend/alembic/versions/005_fix_user_instructions_updated_at.py`):**

    Create a new migration file with:
    - `revision = "005"`
    - `down_revision = "004"`
    - `branch_labels = None`
    - `depends_on = None`

    The upgrade() function must add a PostgreSQL trigger that fires BEFORE UPDATE to set `updated_at = now()`. This ensures the timestamp updates at the DB level regardless of ORM path:

    ```python
    def upgrade() -> None:
        # Create trigger function
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
        op.execute("DROP TRIGGER IF EXISTS user_instructions_set_updated_at ON user_instructions;")
        op.execute("DROP FUNCTION IF EXISTS set_updated_at();")
    ```

    Include all required imports: `from alembic import op`. No `sqlalchemy as sa` needed if not used.

    Do NOT run `alembic upgrade` — that requires Docker/DB access and must be done separately via `just migrate` or `docker exec psql`.
  </action>
  <verify>
    <automated>grep -n "onupdate" /home/tungmv/Projects/hox-agentos/backend/core/models/user_instructions.py && python3 -c "import ast; ast.parse(open('/home/tungmv/Projects/hox-agentos/backend/alembic/versions/005_fix_user_instructions_updated_at.py').read()); print('migration syntax OK')"</automated>
    <manual>Confirm: "onupdate" appears in user_instructions.py and migration file parses without syntax errors</manual>
  </verify>
  <done>`updated_at` column in `UserInstructions` model has `onupdate=func.now()`; migration 005 exists and is syntactically valid with upgrade()/downgrade() creating/dropping the trigger</done>
</task>

<task type="auto">
  <name>Task 3: Fix REQUIREMENTS.md and ROADMAP.md stale checkboxes</name>
  <files>
    .planning/REQUIREMENTS.md
    .planning/ROADMAP.md
  </files>
  <action>
    **A. REQUIREMENTS.md — update 12 completed requirement checkboxes:**

    Change `[ ]` to `[x]` for these requirements (they are complete per v1.0 audit):
    - AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06 (all Phase 1)
    - AGNT-01, AGNT-02, AGNT-07 (Phase 2)
    - MEMO-01, MEMO-05 (Phase 2)
    - INTG-04 (Phase 2)

    Also add `[x]` to `CHAN-01` (web chat is complete per UAT) — WAIT: the audit only lists 12 completed reqs, do not add CHAN-01 since the ROADMAP assigns it to Phase 5 which is not yet started. Only update the 12 confirmed by the audit.

    The traceability section at the bottom already shows "Completed (v1.0): 12" and "Last updated: 2026-02-26" — leave those lines intact.

    **B. ROADMAP.md — fix one stale plan checkbox:**

    On the line for `01-04-PLAN.md` (currently showing `- [ ] 01-04-PLAN.md`), change `[ ]` to `[x]`. All other Phase 1 plan lines (`01-01`, `01-02`, `01-03`) are already `[x]` — do not touch them.

    Verify no other plan lines are incorrectly unchecked: Phase 2 plans (02-01 through 02-05) should all be `[x]`. Phase 2.1 and Phase 3+ plans remain `[ ]`.
  </action>
  <verify>
    <automated>grep -c "\- \[x\] \*\*AUTH" /home/tungmv/Projects/hox-agentos/.planning/REQUIREMENTS.md && grep "\[x\].*01-04-PLAN" /home/tungmv/Projects/hox-agentos/.planning/ROADMAP.md</automated>
    <manual>REQUIREMENTS.md should show 6 AUTH requirements checked; ROADMAP.md 01-04-PLAN.md line should have [x]</manual>
  </verify>
  <done>REQUIREMENTS.md: all 12 completed requirements show `[x]`; ROADMAP.md: `01-04-PLAN.md` line shows `[x]`; no Phase 3+ items accidentally checked</done>
</task>

</tasks>

<verification>
After all tasks complete:

1. `grep -rn "process.env.BACKEND_URL" frontend/src/app/api/` → 0 matches
2. `grep -n "onupdate" backend/core/models/user_instructions.py` → shows onupdate=func.now()
3. `ls backend/alembic/versions/005_*.py` → file exists
4. `grep -c "\[x\]" .planning/REQUIREMENTS.md` → 12 checked items in requirements section (AUTH-01–06, AGNT-01, AGNT-02, AGNT-07, MEMO-01, MEMO-05, INTG-04)
5. `grep "\[x\].*01-04" .planning/ROADMAP.md` → [x] 01-04-PLAN.md line exists
</verification>

<success_criteria>
- Zero BACKEND_URL references in frontend/src/app/api/ — all 6 routes use NEXT_PUBLIC_API_URL
- user_instructions.updated_at has onupdate=func.now() in ORM model
- Migration 005 exists with PostgreSQL trigger for updated_at auto-update
- 12 requirements in REQUIREMENTS.md show [x] (matching v1.0 audit confirmed completions)
- ROADMAP.md 01-04-PLAN.md line shows [x]
</success_criteria>

<output>
After completion, create `.planning/phases/02.1-tech-debt-cleanup/02.1-01-SUMMARY.md` with:
- What was changed in each of the 3 tasks
- Note that migration 005 must be applied via `just migrate` or `docker exec psql` (cannot be applied from host without .env)
- Confirm: BACKEND_URL split closed, updated_at trigger in place, docs accurate
</output>
