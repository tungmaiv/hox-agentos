# Phase 23: Skill Platform E — Enhanced Builder - Research

**Researched:** 2026-03-10
**Domain:** LangGraph agent extension, pgvector similarity search, Python code generation, security gate integration, React frontend builder extension
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Skill generation depth (SKBLD-01, 02, 03)**
- One-shot full scaffold: When admin describes a skill goal, the AI generates a complete `procedure_json` (steps, tool references, prompt templates) or `instruction_markdown` in a single response. No step-by-step interactive interrogation.
- Refinement: Chat-first by default (user says "add a step to filter by sender" → AI updates draft in place). A "Edit JSON" toggle in the preview panel lets technical admins drop to raw JSON editing on demand. Both modes coexist.
- Tool handler stub (SKBLD-03): For tool-type artifacts, AI generates a full Python stub: function signature, InputModel/OutputModel Pydantic classes, docstring with usage notes, and a `# TODO: implement` comment in the body.
- Stub delivery: Stub is auto-registered as a pending tool in the DB. A new `handler_code TEXT` column on `tool_definitions` stores the stub text. Tool status = `pending_stub`. Admin edits and registers via the existing tool management flow.

**Similar skills discovery & fork (SKBLD-04, 05)**
- Trigger: Dedicated "Find Similar" button in the right-side preview panel. Not proactive. Admin clicks when ready.
- Similarity strategy: pgvector cosine similarity on embedded name + description of the draft, searched against pre-embedded `skill_repo_index` entries. Reuses bge-m3 embedding pipeline. Returns top 3–5 results.
- Fork behavior: Forking an external skill replaces the current draft in the same builder session. The builder's existing `ArtifactBuilderState` is populated with the forked skill's full content (name, description, procedure_json/instruction_markdown, tags, category, allowed_tools).
- Fork attribution: `source_type='imported'`, plus a note in the draft (e.g., `forked_from: "skill-name@source-url"`). Carries through to the saved skill definition for security audit trail.

**Import sources & Claude Code skill import**
- Builder "Fork/Import" panel (new section in the right preview panel) has three import tabs:
  1. AgentSkills URL — existing URL import behavior
  2. Claude Code GitHub URL — fetches raw GitHub URL, applies format adapter (Claude Code YAML + markdown → agentskills.io fields)
  3. ZIP upload — triggers existing `POST /api/admin/skills/import/zip` endpoint (already implemented)
- Claude Code adapter maps: `name` → `name`, `description` → `description` + seed `instruction_markdown`, tool references → attempt to map to known tool names, category guessed from content (admin can override)
- Input sources for Claude Code: Both GitHub raw URL fetch AND paste raw YAML content (tab-switcher in import panel)

**Security gate (SKBLD-06, 07, 08)**
- Trigger: SecurityScanner runs on Save, before writing to DB. Applies to ALL saves — new builds, edits of existing active skills (re-scan on every edit), and forked skills.
- On-save flow:
  1. Admin clicks Save
  2. SecurityScanner runs synchronously on the draft content
  3. If recommendation = `approve` → skill saved as `active`
  4. If recommendation = `review` or `reject` → skill saved as `pending_review`; SecurityReportCard renders inline in the builder preview panel
- SecurityReportCard placement (SKBLD-07): After Save, the right-side preview panel switches to SecurityReportCard view: trust score (0–100), factor breakdown (progress bars per factor), tool permissions list, injection warning highlights, and recommendation badge.
- Admin approval (SKBLD-08): SecurityReportCard has an "Approve & Activate" button at the bottom for `review` or `reject` recommendations. Clicking shows a confirmation step. On confirm, skill transitions to `active`. Approval happens inline.
- Re-scan on edit: When admin edits an existing `active` skill and saves, scan re-runs. If re-scan returns `review` or `reject`, skill is moved back to `pending_review`.
- SecurityReportCard is a new A2UI component — displays in the builder preview panel, can also be reused in admin skill detail view.

### Claude's Discretion
- Exact pgvector index type for repo skill similarity (HNSW vs IVFFlat — HNSW preferred for small datasets)
- `handler_code` column name and exact status string for pending stubs (`pending_stub` or `draft`)
- SecurityReportCard visual design (factor bar colors, recommendation badge palette — follow existing badge patterns)
- Whether "Edit JSON" toggle shows a Monaco editor or a plain textarea
- Exact Claude Code field mapping for fields with no clean equivalent (e.g., `trigger`, `when_to_use`)
- Confirmation dialog copy for "Approve & Activate" override

### Deferred Ideas (OUT OF SCOPE)
- Batch re-scan of all existing skills (admin-triggered "Re-scan all" button in /admin/skills)
- Proactive similar skills (auto-surface as user types)
- Skill composition (one skill calling another)
- Auto-publish forked skills to agentskills.io
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SKBLD-01 | Builder generates complete `procedure_json` with steps, tool references, conditions, and prompt templates for procedural skills | LangGraph `generate_skill_content` node added to existing `artifact_builder.py`; LLM one-shot generation pattern documented |
| SKBLD-02 | Builder generates `instruction_markdown` for instructional skills with proper Agent Skills format | Same node handles both types via `artifact_type` branch; SKILL.md body format documented |
| SKBLD-03 | For tools: builder generates handler code scaffolding (Python function stub with Pydantic I/O models) | `handler_code TEXT` column + `pending_stub` status on `tool_definitions`; migration 026 |
| SKBLD-04 | Builder searches cached external repo indexes for similar skills and shows top 3–5 relevant examples | `SkillRepoService.search_similar()` using pgvector cosine on `skill_repo_index` table; bge-m3 sidecar for embedding |
| SKBLD-05 | "Fork" capability: user selects an existing external skill as starting point; builder pre-populates and adapts | Fork populates `ArtifactBuilderState` fields; `source_type='imported'` + `forked_from` attribution pattern |
| SKBLD-06 | Every artifact goes through SecurityScanner before activation — `security_review` node added to builder LangGraph | `SecurityScanner.scan()` already exists (Phase 21); called synchronously in save handler before DB write |
| SKBLD-07 | SecurityReportCard A2UI component shows trust score, factor breakdown, tool permissions, injection warnings, and recommendation | New React component reading `state.security_report`; badge follows existing `Badge` component pattern |
| SKBLD-08 | For `review` or `reject` recommendations, admin must explicitly approve before skill is activated | "Approve & Activate" button in SecurityReportCard calls `POST /api/admin/skills/{id}/review` with `decision=approve` |
</phase_requirements>

---

## Summary

Phase 23 extends an already-mature artifact builder LangGraph agent with three new capabilities: full skill content generation (procedure_json/instruction_markdown/tool stubs), similarity-based discovery from cached external repo indexes, and a mandatory security gate on every save. All three integrate with well-established project patterns and do not require new libraries.

The key insight is that the backend already has all the primitives needed: `SecurityScanner.scan()` (Phase 21), `SkillImporter.import_from_url()` + ZIP (Phase 22), the `skill_repo_index` table with cached external indexes, pgvector cosine distance (used in `memory/long_term.py`), and the `pending_review`/`active` skill lifecycle. This phase is primarily about wiring existing components into the builder agent and adding the security gate to the save path.

The largest new surface area is the frontend `artifact-builder-client.tsx` extension: the "Find Similar" button, the Fork/Import panel, the "Edit JSON" textarea toggle, and the `SecurityReportCard` component that renders after save. All of these sit in the existing right-side preview panel and read from `ArtifactBuilderState` fields that will be added as co-agent state.

**Primary recommendation:** Wire existing security/embedding/importer infrastructure into the builder agent through a new `security_review` save node and a `find_similar` tool call. Extend the frontend right panel with SecurityReportCard and a Find Similar results section. Add migration 026 for `handler_code` on `tool_definitions`.

---

## Standard Stack

### Core (all already in project — no new installations)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| LangGraph | 0.2+ (locked) | Builder agent graph nodes | Existing `artifact_builder.py` — add nodes without graph rewrite |
| SQLAlchemy async | current (locked) | pgvector cosine query | Pattern from `memory/long_term.py` — `embedding.cosine_distance()` |
| pgvector | 0.8+ (locked) | Similarity search on repo skills | `vector(1024)` column, cosine distance operator |
| bge-m3 sidecar | Phase 17 (locked) | Embed draft name+description for similarity | `SidecarEmbeddingProvider` already injectable |
| `SecurityScanner` | Phase 21 (locked) | Scan skill content before save | `scan(skill_data, source_url)` → `SecurityReport` |
| `SkillImporter` | Phase 22 (locked) | Claude Code YAML adapter | Add `import_from_claude_code_yaml()` method |
| `copilotkit_emit_state` | copilotkit 0.1.78 | Push `similar_skills`, `security_report` fields to frontend | Existing pattern in builder nodes |
| httpx | current (locked) | Fetch raw GitHub URLs for Claude Code import | Already used in `SkillImporter.import_from_url()` |

### Supporting (discretionary)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| HNSW index (pgvector) | 0.8+ | Accelerate cosine search on `skill_repo_index` | Use for similar skills search — faster than sequential scan at any dataset size, simple to create |
| `structlog` + `get_audit_logger()` | locked | Audit logging for security gate decisions | Required for every security gate approval/override per CLAUDE.md |
| Alembic | locked | Migration 026 — `handler_code TEXT` on `tool_definitions` | Next migration number: **026** (025 = `skill_is_promoted`) |

### No New Installations Required

All required libraries are already in `backend/pyproject.toml` and `frontend/package.json`. This phase adds no new Python or NPM dependencies.

---

## Architecture Patterns

### Current Builder Graph Topology

```
START → route_intent (conditional)
  |-> gather_type            (if artifact_type not set)
  |-> gather_details         (if type set but draft incomplete)
  |-> validate_and_present   (if draft ready)
  |-> fill_form_node         (after fill_form tool call)
Each node → END
```

### Extended Builder Graph Topology (Phase 23)

```
START → route_intent (conditional — extend existing)
  |-> gather_type            (unchanged)
  |-> gather_details         (unchanged — generates full content via prompt)
  |-> generate_skill_content (NEW — one-shot full procedure_json/instruction_markdown)
  |-> validate_and_present   (unchanged)
  |-> fill_form_node         (unchanged)
  |-> security_review_node   (NEW — called from save path, not router)
Each node → END
```

Note: `security_review_node` is invoked from the save handler, not via the LangGraph router. It runs synchronously within the same builder session message.

### Pattern 1: Extending ArtifactBuilderState

Add three new fields to `ArtifactBuilderState` in `backend/agents/state/artifact_builder_types.py`:

```python
# Source: existing artifact_builder_types.py pattern
class ArtifactBuilderState(TypedDict):
    # ... existing fields unchanged ...
    # Phase 23 additions:
    similar_skills: list[dict] | None          # top-k results from repo search
    security_report: dict | None               # SecurityReport serialized after save
    fork_source: str | None                    # "skill-name@source-url" attribution
    handler_code: str | None                   # Python stub for tool artifacts
```

These are emitted to frontend via `copilotkit_emit_state()` — same pattern as existing `artifact_draft`.

### Pattern 2: Security Gate in Save Handler

The security gate runs synchronously in the frontend save handler (NOT a new graph node). The frontend `handleSave()` currently calls `POST /api/admin/skills` directly. Phase 23 changes this to call a new `POST /api/admin/skills/builder-save` endpoint that:

1. Receives the full draft
2. Runs `SecurityScanner.scan(skill_data, source_url=None)` synchronously
3. If `approve`: saves as `status='active'`, returns `{status: 'active', security_report: {...}}`
4. If `review`/`reject`: saves as `status='pending_review'`, returns `{status: 'pending_review', security_report: {...}}`

The frontend then:
- Updates `builderState.security_report` from response
- Renders `SecurityReportCard` in the right panel
- Hides "Save to Registry" button, shows "Approve & Activate" button for non-approve

Alternatively (and more architecturally clean per CONTEXT.md), the security gate can be triggered as a LangGraph node called by the builder agent when it detects a save intent. The context document describes the gate in terms of the LangGraph builder agent (`security_review` node). Both approaches work — recommend the endpoint approach as it's simpler and doesn't require a new conversation turn.

**Decision needed by planner:** endpoint-based save vs. LangGraph node. CONTEXT.md says "SecurityScanner runs on Save" — endpoint approach is simplest.

### Pattern 3: pgvector Cosine Search for Similar Skills

The exact pattern from `memory/long_term.py` using `embedding.cosine_distance()`:

```python
# Source: backend/memory/long_term.py — cosine_distance pattern
# New method: SkillRepoService.search_similar()

from sqlalchemy import select
from core.models.skill_repo_index import SkillRepoIndex  # new ORM model or query cached_index

async def search_similar(
    self,
    query_embedding: list[float],
    top_k: int = 5,
    session: AsyncSession,
) -> list[dict]:
    """pgvector cosine search over pre-embedded skill_repo_index entries."""
    result = await session.execute(
        select(SkillRepoIndex)
        .where(SkillRepoIndex.embedding.is_not(None))
        .order_by(SkillRepoIndex.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    return [r.to_dict() for r in result.scalars().all()]
```

**Important:** The `skill_repo_index` embedding approach requires a decision on storage. Two options:
1. **JSONB in `skill_repositories.cached_index`** (current) — no embedding column, must do in-memory cosine. Acceptable for small datasets (<100 skills).
2. **Separate `skill_repo_index` table** with `embedding vector(1024)` column — proper pgvector search.

Option 2 is architecturally clean and matches `memory_facts` pattern. CONTEXT.md says "pgvector cosine similarity on embedded name + description of the draft, searched against pre-embedded `skill_repo_index` entries" — this confirms Option 2 with a new table.

### Pattern 4: Claude Code YAML Adapter

Add `import_from_claude_code_yaml()` to `SkillImporter`:

```python
# New method in backend/skills/importer.py
def import_from_claude_code_yaml(self, content: str) -> dict[str, Any]:
    """Parse Claude Code skill YAML (not SKILL.md format) and map to agentskills.io fields.

    Claude Code skill fields:
      name: str
      description: str (often a full paragraph)
      tools: list[str] (optional)
      trigger: str (optional — no clean equivalent)
      when_to_use: str (optional — merge into instruction_markdown)

    Mapping:
      name → name
      description → description + seed instruction_markdown
      tools → attempt to map to known tool names via allowed_tools
      trigger/when_to_use → prepend to instruction_markdown as context
    """
```

For tool reference mapping, use a simple lookup against known tool names from `gateway/tool_registry.py`.

### Pattern 5: Tool Handler Stub Generation

The LLM generates a Python stub for tool-type artifacts. The stub is stored in the new `handler_code TEXT` column on `tool_definitions` with `status='pending_stub'`. The existing `create_tool` endpoint at `POST /api/admin/tools` needs to accept the new fields. A separate `PATCH /api/admin/tools/{tool_id}/activate-stub` promotes it to `active`.

```python
# Example stub output from LLM (generated, not hand-rolled):
from pydantic import BaseModel

class EmailSummaryInput(BaseModel):
    user_id: str
    max_emails: int = 10

class EmailSummaryOutput(BaseModel):
    summaries: list[str]
    total_count: int

async def email_summary_handler(input: EmailSummaryInput) -> EmailSummaryOutput:
    """Summarize recent emails for a user.

    Usage: Called by the email agent to provide quick digest.
    Requires email:read ACL permission.
    """
    # TODO: implement
    raise NotImplementedError("Implement email_summary_handler")
```

### Recommended File Structure Changes

```
backend/
├── agents/
│   ├── artifact_builder.py          # EXTEND: add generate_skill_content, security_review_node
│   ├── artifact_builder_prompts.py  # EXTEND: add skill generation prompts
│   └── state/
│       └── artifact_builder_types.py # EXTEND: similar_skills, security_report, fork_source, handler_code
├── core/models/
│   ├── skill_repo_index.py          # NEW: ORM for skill_repo_index table (embedding column)
│   └── tool_definition.py          # EXTEND: add handler_code TEXT column
├── skills/
│   └── importer.py                 # EXTEND: add import_from_claude_code_yaml()
├── skill_repos/
│   └── service.py                  # EXTEND: add search_similar() method
├── api/routes/
│   ├── admin_skills.py             # EXTEND: add builder-save endpoint, inline approval endpoint
│   └── admin_tools.py              # EXTEND: add activate-stub endpoint
└── alembic/versions/
    └── 026_tool_handler_code.py    # NEW: handler_code + pending_stub status
    └── 027_skill_repo_index.py     # NEW: skill_repo_index table with vector(1024) embedding

frontend/src/components/admin/
├── artifact-builder-client.tsx     # EXTEND: Find Similar button, Fork/Import panel, Edit JSON toggle
├── artifact-preview.tsx            # EXTEND: add SecurityReportCard render slot
└── security-report-card.tsx        # NEW: A2UI component for trust score display
```

### Anti-Patterns to Avoid

- **Running SecurityScanner in a LangGraph node during conversation:** The scanner is deterministic and synchronous — call it in the save endpoint, not as an agent node. Nodes run on every user turn and should not run the scanner proactively.
- **Embedding draft content in the frontend `handleSave()` call:** The embedding for similarity search happens when the admin clicks "Find Similar" — not at save time. The save-time scan uses content analysis only (no embeddings).
- **Using `import_from_url()` for Claude Code GitHub URLs without raw URL conversion:** GitHub file URLs (github.com/user/repo/blob/main/skill.yaml) must be converted to raw.githubusercontent.com URLs before fetching.
- **In-memory cosine search over cached_index JSONB:** Do not iterate all skills in Python comparing cosine similarity. Use the pgvector `skill_repo_index` table with a proper vector column.
- **Storing handler_code as JSONB:** It is plain text — use `TEXT` column, no JSONB variant needed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Security content scanning | Custom pattern matching | `SecurityScanner.scan()` (Phase 21) | 6-factor weighted scoring, hard veto, prompt injection patterns, data flow analysis — all done |
| Skill parsing/import | Custom YAML parser | `SkillImporter.parse_skill_md()` | Handles frontmatter, body, all agentskills.io fields, ZIP — done |
| pgvector similarity search | In-memory cosine computation | `embedding.cosine_distance(vec)` SQLAlchemy | Exact pattern from `memory/long_term.py` — operator `<=>` via pgvector |
| Embedding text for search | Direct FlagEmbedding calls | `SidecarEmbeddingProvider` | Phase 17 sidecar with fallback — single call, no in-process model load |
| Security review approval flow | Custom approval workflow | `POST /api/admin/skills/{id}/review` with `decision=approve` | Existing endpoint from Phase 21 — same flow, just invoked from builder UI |

**Key insight:** Every backend primitive for this phase already exists. The implementation is about wiring existing components together, not building new infrastructure.

---

## Common Pitfalls

### Pitfall 1: `review_skill` endpoint requires `status='pending_review'`

**What goes wrong:** The existing `review_skill` endpoint (line 632 in admin_skills.py) raises HTTP 409 if the skill is not in `pending_review` status. Trying to approve an `active` skill (e.g., after re-scan on edit demoted it) will fail if the save path didn't properly set `status='pending_review'` first.

**Why it happens:** The review endpoint checks `skill.status != "pending_review"` and rejects non-pending skills.

**How to avoid:** The builder save path must set `status='pending_review'` and `is_active=False` atomically whenever the scan returns `review` or `reject`. Then the "Approve & Activate" button can call the existing review endpoint.

**Warning signs:** Frontend "Approve & Activate" returns 409 in testing.

### Pitfall 2: Re-scan on edit must handle existing active skills

**What goes wrong:** When admin edits an `active` skill and saves, the scan might return `review`. If the save path only handles `status='active'` → `status='pending_review'` transition, but the skill was already `active` (not `pending_review`), the save path needs to handle both directions.

**How to avoid:** The builder save endpoint must use `PUT /api/admin/skills/{id}` (update) for existing skills, not `POST`. After update, run scan and set status accordingly. The existing `update_skill` endpoint does NOT run a security scan — the builder-save endpoint must run it explicitly before calling the underlying update logic.

### Pitfall 3: GitHub URL → raw URL conversion for Claude Code import

**What goes wrong:** Fetching `github.com/user/repo/blob/main/skill.yaml` returns HTML, not YAML. `SkillImporter.import_from_url()` would parse HTML as YAML and fail with a parse error.

**Why it happens:** GitHub file view URLs serve HTML pages. Raw content requires `raw.githubusercontent.com/user/repo/main/skill.yaml`.

**How to avoid:** In `import_from_claude_code_yaml()` or the frontend, convert GitHub file URLs to raw URLs before fetching:
```python
# Pattern: replace "github.com/{user}/{repo}/blob/{ref}/" with
# "raw.githubusercontent.com/{user}/{repo}/{ref}/"
```

### Pitfall 4: `skill_repo_index` embedding requires Celery pre-computation

**What goes wrong:** The "Find Similar" feature requires skill_repo_index entries to have pre-computed embeddings. If the table is populated but embeddings are NULL, the cosine search returns empty results.

**Why it happens:** Embedding is async (Celery), not synchronous. When repos are synced, their index entries don't automatically get embeddings.

**How to avoid:** Add an embedding step to `SkillRepoService.sync_repo()` — after updating `cached_index`, queue a Celery task to embed all new skill entries in the `skill_repo_index` table. For MVP, synchronous embedding via sidecar during sync is acceptable (repo sync is admin-triggered, not on hot path).

### Pitfall 5: `ArtifactBuilderState` field expansion visible to copilotkit_emit_state

**What goes wrong:** Adding `similar_skills`, `security_report`, `handler_code` to `ArtifactBuilderState` TypedDict means they appear in every `copilotkit_emit_state()` call. If these fields are very large (e.g., `similar_skills` contains full skill content), it can bloat the SSE payload.

**How to avoid:** For `similar_skills`, emit only summary fields (name, description, repository_name, source_url) — not full `procedure_json` or `instruction_markdown`. The full content is fetched on fork.

### Pitfall 6: `source_type='imported'` vs `source_type='user_created'` for builder-built skills

**What goes wrong:** Skills built from scratch in the builder should use `source_type='user_created'`. Forked skills should use `source_type='imported'`. If the builder always sets `source_type='imported'`, the source reputation score in SecurityScanner will be 20 (unknown URL) instead of 40 (no URL / manual paste), affecting the security score.

**Why it happens:** `_score_source(None)` returns 40 for manual creation, `_score_source("unknown-url")` returns 20. Builder-generated skills have no source URL.

**How to avoid:** For builder-generated skills: pass `source_url=None` to `SecurityScanner.scan()`. For forked skills: pass the external skill's URL.

### Pitfall 7: Migration ordering — 026 must precede 027

**What goes wrong:** If `027_skill_repo_index.py` is created before `026_tool_handler_code.py`, Alembic will have a branching head or wrong sequence.

**How to avoid:** Create migrations in order: 026 first (handler_code on tool_definitions), 027 second (skill_repo_index table). Each must have `down_revision` pointing to the previous one.

---

## Code Examples

### Example 1: pgvector cosine search (from existing project pattern)

```python
# Source: backend/memory/long_term.py (verified in codebase)
# Pattern to replicate in SkillRepoService.search_similar()

result = await session.execute(
    select(SkillRepoIndex)
    .where(SkillRepoIndex.embedding.is_not(None))
    .order_by(SkillRepoIndex.embedding.cosine_distance(query_embedding))
    .limit(top_k)
)
```

### Example 2: SecurityScanner.scan() call pattern (from existing project)

```python
# Source: backend/api/routes/admin_skills.py line 274 (verified in codebase)
scanner = SecurityScanner()
report = scanner.scan(skill_data, source_url=body.source_url)
# report.score: int 0-100
# report.recommendation: "approve" | "review" | "reject"
# report.factors: dict[str, int] — per-factor breakdown
# report.injection_matches: list[str]

# Save with security data:
skill.security_score = report.score
skill.security_report = {
    "score": report.score,
    "factors": report.factors,
    "recommendation": report.recommendation,
    "injection_matches": report.injection_matches,
}
```

### Example 3: copilotkit_emit_state pattern (from existing builder)

```python
# Source: backend/agents/artifact_builder.py (verified in codebase)
# Pattern to replicate for similar_skills and security_report fields
await copilotkit_emit_state(config, {
    "artifact_type": artifact_type,
    "artifact_draft": artifact_draft,
    "validation_errors": validation_errors,
    "is_complete": is_complete,
    "similar_skills": similar_skills,      # Phase 23 addition
    "security_report": security_report,    # Phase 23 addition
})
```

### Example 4: Skill save flow with security gate (new pattern)

```python
# New endpoint: POST /api/admin/skills/builder-save
# Replaces the direct POST /api/admin/skills call from artifact-builder-client.tsx

async def builder_save_skill(
    body: BuilderSaveRequest,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> BuilderSaveResponse:
    """Save builder-created skill with mandatory security gate."""
    scanner = SecurityScanner()
    skill_data = body.skill_data
    report = scanner.scan(skill_data, source_url=skill_data.get("source_url"))

    if report.recommendation == "approve":
        status = "active"
        is_active = True
    else:
        status = "pending_review"
        is_active = False

    # Create or update skill
    skill = SkillDefinition(
        ...
        status=status,
        is_active=is_active,
        security_score=report.score,
        security_report={
            "score": report.score,
            "factors": report.factors,
            "recommendation": report.recommendation,
            "injection_matches": report.injection_matches,
        },
        source_type=skill_data.get("source_type", "user_created"),
        created_by=user["user_id"],
    )
    ...
    return BuilderSaveResponse(
        skill_id=str(skill.id),
        status=status,
        security_report=skill.security_report,
    )
```

### Example 5: ArtifactBuilderState extension

```python
# Source: backend/agents/state/artifact_builder_types.py (verified in codebase)
# Add to existing TypedDict:
class ArtifactBuilderState(TypedDict):
    # ... all existing fields unchanged ...
    # Phase 23 additions:
    similar_skills: list[dict] | None
    # Each entry: {name, description, repository_name, source_url, category, tags}
    security_report: dict | None
    # SecurityReport serialized: {score, factors, recommendation, injection_matches}
    fork_source: str | None
    # Attribution: "skill-name@https://source-url"
    handler_code: str | None
    # Python stub text for tool artifacts
```

### Example 6: `handler_code` migration (026)

```python
# backend/alembic/versions/026_tool_handler_code.py
# Add handler_code TEXT (nullable) + pending_stub status support to tool_definitions
def upgrade() -> None:
    op.add_column("tool_definitions", sa.Column("handler_code", sa.Text(), nullable=True))
    # Note: status column already accepts any string (String(20) without CHECK constraint)
    # No status enum migration needed — just start using "pending_stub" value
```

### Example 7: skill_repo_index table (027)

```python
# backend/alembic/versions/027_skill_repo_index.py
# New table: skill_repo_index with vector(1024) embedding
def upgrade() -> None:
    op.create_table(
        "skill_repo_index",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_skill_repo_index_embedding_hnsw",
        "skill_repo_index",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual skill creation via form | Conversational AI builder (LangGraph + CopilotKit) | Phase 12 | Exists, needs content generation upgrade |
| Import-only security gate | Gate on save (all paths) | Phase 23 | Builder-created skills now go through same gate as imports |
| No skill similarity | pgvector cosine on repo index | Phase 23 | Admin can discover related skills before building |
| Tool stubs: manual file editing | Auto-generated Pydantic stubs | Phase 23 | Reduces bootstrap time for new tool development |

---

## Open Questions

1. **`builder-save` as new endpoint vs. modifying existing `create_skill`**
   - What we know: `create_skill` currently does NOT run SecurityScanner (only import endpoints do)
   - What's unclear: Should the save endpoint be a new `POST /api/admin/skills/builder-save` route or should the existing `create_skill` be extended with an optional security gate flag?
   - Recommendation: New `builder-save` endpoint. Clean separation. Existing `create_skill` remains unchanged for programmatic use. Route ordering: `builder-save` must be declared before `/{skill_id}` (UUID catch-all) — same pattern as phase 22 sharing routes.

2. **`skill_repo_index` population strategy**
   - What we know: Embedding is async (sidecar). Repo sync is admin-triggered.
   - What's unclear: Should embedding happen synchronously at repo sync time (simple), or async via Celery (consistent with memory embedding pattern)?
   - Recommendation: Synchronous via sidecar at sync time. Repo sync is infrequent (manual), dataset is small (<200 skills per repo). Adding Celery task for this adds complexity with minimal benefit at 100-user scale.

3. **Edit JSON toggle: textarea vs Monaco editor**
   - What we know: CONTEXT.md explicitly says textarea is sufficient at this scale
   - What's unclear: Does a plain `<textarea>` need any JSON validation or pretty-printing?
   - Recommendation: Plain `<textarea>` with `JSON.stringify(draft, null, 2)` for formatting. Add a "Parse" button that attempts `JSON.parse()` and shows inline error if invalid. No Monaco needed.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8+ via `.venv/bin/pytest` |
| Config file | `backend/pyproject.toml` (pytest section) |
| Quick run command | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py tests/test_security_scanner.py tests/test_skill_importer.py -q` |
| Full suite command | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SKBLD-01 | Builder generates complete `procedure_json` for procedural skills | unit | `PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py::test_generate_procedural_skill_content -x` | ❌ Wave 0 |
| SKBLD-02 | Builder generates `instruction_markdown` for instructional skills | unit | `PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py::test_generate_instructional_skill_content -x` | ❌ Wave 0 |
| SKBLD-03 | Builder generates Python stub + registers as pending_stub tool | unit | `PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py::test_generate_tool_stub -x` | ❌ Wave 0 |
| SKBLD-04 | `SkillRepoService.search_similar()` returns top-k by cosine | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_skill_repos.py::test_search_similar_returns_top_k -x` | ❌ Wave 0 |
| SKBLD-05 | Fork populates ArtifactBuilderState from external skill | unit | `PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py::test_fork_external_skill -x` | ❌ Wave 0 |
| SKBLD-06 | Security gate runs on builder save — approve path | unit | `PYTHONPATH=. .venv/bin/pytest tests/api/test_admin_skills.py::test_builder_save_approve -x` | ❌ Wave 0 |
| SKBLD-06 | Security gate runs on builder save — review path | unit | `PYTHONPATH=. .venv/bin/pytest tests/api/test_admin_skills.py::test_builder_save_pending_review -x` | ❌ Wave 0 |
| SKBLD-07 | SecurityReportCard renders with correct data structure | manual | N/A — UI component visual test | N/A |
| SKBLD-08 | Inline approve transitions `pending_review` → `active` | unit | `PYTHONPATH=. .venv/bin/pytest tests/api/test_admin_skills.py::test_builder_inline_approve -x` | ❌ Wave 0 |

### Claude Code Import

| Feature | Test Type | Command |
|---------|-----------|---------|
| `import_from_claude_code_yaml()` parses name/description | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_skill_importer.py::test_import_claude_code_yaml -x` |
| GitHub URL → raw URL conversion | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_skill_importer.py::test_github_raw_url_conversion -x` |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=. .venv/bin/pytest tests/agents/test_artifact_builder.py tests/test_security_scanner.py tests/test_skill_repos.py -q`
- **Per wave merge:** `PYTHONPATH=. .venv/bin/pytest tests/ -q`
- **Phase gate:** Full suite green (currently 719 tests — must not drop) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/agents/test_artifact_builder.py` — add tests for SKBLD-01, 02, 03, 05 (file exists, new test functions needed)
- [ ] `tests/test_skill_repos.py` — add `test_search_similar_returns_top_k` for SKBLD-04 (file exists, new function)
- [ ] `tests/api/test_admin_skills.py` — add `test_builder_save_approve`, `test_builder_save_pending_review`, `test_builder_inline_approve` for SKBLD-06, 08 (file exists, new functions)
- [ ] `tests/test_skill_importer.py` — add `test_import_claude_code_yaml`, `test_github_raw_url_conversion` (file exists, new functions)
- [ ] All new test functions can mock LLM calls and SecurityScanner using existing `_patch_emit_state` and `patch()` patterns from `test_artifact_builder.py`

---

## Sources

### Primary (HIGH confidence)
- `backend/agents/artifact_builder.py` — full builder agent graph, node patterns, `fill_form` tool, `_extract_draft_from_response` pattern
- `backend/agents/state/artifact_builder_types.py` — TypedDict structure, existing fields
- `backend/skills/security_scanner.py` — `SecurityScanner.scan()` interface, `SecurityReport` dataclass, scoring factors
- `backend/skills/importer.py` — `SkillImporter` methods, Claude Code adapter insertion point
- `backend/skill_repos/service.py` — `SkillRepoService` structure, `cached_index` JSONB storage, `import_from_repo` security scan pattern
- `backend/memory/long_term.py` — pgvector cosine distance pattern (`embedding.cosine_distance()`)
- `backend/core/models/skill_definition.py` — `status`, `source_type`, `security_score`, `security_report` columns
- `backend/core/models/tool_definition.py` — existing columns, `status` as `String(20)` (no CHECK constraint = accepts `pending_stub`)
- `backend/api/routes/admin_skills.py` — `review_skill`, `create_skill`, import endpoints, `_require_registry_manager` gate
- `frontend/src/components/admin/artifact-builder-client.tsx` — `BuilderState` interface, `handleSave()`, right panel layout
- `.planning/phases/23-skill-platform-e-enhanced-builder/23-CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)
- `backend/alembic/versions/` directory listing — migration numbering (025 is last sequential, 83f730920f5a is hex-ID for platform_config; next sequential is 026)
- `backend/tests/agents/test_artifact_builder.py` — test patterns (autouse patch, mock config)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified in existing codebase files
- Architecture patterns: HIGH — all patterns derived from existing working code in the project
- Pitfalls: HIGH — derived from actual code inspection (status checks, URL handling, migration ordering)
- Validation architecture: HIGH — existing test files verified, new test function names are conventional

**Research date:** 2026-03-10
**Valid until:** 2026-04-10 (stable internal codebase — 30-day window appropriate)
