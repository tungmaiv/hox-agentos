# Phase 4 — Plan 04-05: Pre-Built Templates

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Seed two pre-built workflow templates (Morning Digest and Alert) as JSON fixtures, load them via an Alembic data migration, and wire the template gallery's "Use template" button so it calls the copy API and redirects the user to the new canvas editor.

**Architecture:** Two JSON fixtures live in `backend/data/workflow_templates/` and are inserted by Alembic migration `011_phase4_workflow_templates.py` as `is_template=true` rows with `owner_user_id=NULL`. The `GET /api/workflows/templates` and `POST /api/workflows/templates/{id}/copy` routes already exist from 04-01 — this plan only seeds the data and replaces the non-functional form button in `workflows/page.tsx` with a `TemplateCard` client component that calls the copy API and navigates to the new workflow via `useRouter`.

**Tech Stack:** Alembic `op.get_bind()` + SQLAlchemy `text()`, Python `json`, Next.js 15 App Router, `useRouter` from `next/navigation`.

---

## Task 1: Template JSON Fixtures + Validation Tests

**Files:**
- Create: `backend/data/workflow_templates/morning_digest.json`
- Create: `backend/data/workflow_templates/alert.json`
- Create: `backend/data/__init__.py` (empty, makes directory a package)
- Create: `backend/tests/test_workflow_fixtures.py`

**Step 1: Create data directory and fixtures**

```bash
mkdir -p backend/data/workflow_templates
touch backend/data/__init__.py
```

**Step 2: Write failing tests**

```python
# backend/tests/test_workflow_fixtures.py
import json
import pathlib

FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "data" / "workflow_templates"


def _load(filename: str) -> dict:
    with open(FIXTURES_DIR / filename) as f:
        return json.load(f)


def test_morning_digest_schema_version():
    data = _load("morning_digest.json")
    assert data["schema_version"] == "1.0"


def test_morning_digest_has_required_node_types():
    data = _load("morning_digest.json")
    node_types = {n["type"] for n in data["nodes"]}
    assert "trigger_node" in node_types
    assert "tool_node" in node_types
    assert "condition_node" in node_types
    assert "agent_node" in node_types
    assert "channel_output_node" in node_types


def test_morning_digest_edges_connect_to_existing_nodes():
    data = _load("morning_digest.json")
    node_ids = {n["id"] for n in data["nodes"]}
    for edge in data["edges"]:
        assert edge["source"] in node_ids, f"Edge source {edge['source']} not in nodes"
        assert edge["target"] in node_ids, f"Edge target {edge['target']} not in nodes"


def test_morning_digest_condition_has_true_edge():
    data = _load("morning_digest.json")
    condition_id = next(n["id"] for n in data["nodes"] if n["type"] == "condition_node")
    true_edges = [e for e in data["edges"] if e["source"] == condition_id and e.get("sourceHandle") == "true"]
    assert len(true_edges) == 1


def test_alert_schema_version():
    data = _load("alert.json")
    assert data["schema_version"] == "1.0"


def test_alert_has_required_node_types():
    data = _load("alert.json")
    node_types = {n["type"] for n in data["nodes"]}
    assert "trigger_node" in node_types
    assert "tool_node" in node_types
    assert "condition_node" in node_types
    assert "channel_output_node" in node_types


def test_alert_trigger_is_webhook():
    data = _load("alert.json")
    trigger = next(n for n in data["nodes"] if n["type"] == "trigger_node")
    assert trigger["data"]["trigger_type"] == "webhook"


def test_alert_condition_has_true_edge():
    data = _load("alert.json")
    condition_id = next(n["id"] for n in data["nodes"] if n["type"] == "condition_node")
    true_edges = [e for e in data["edges"] if e["source"] == condition_id and e.get("sourceHandle") == "true"]
    assert len(true_edges) == 1


def test_alert_keyword_match_params():
    data = _load("alert.json")
    tool_nodes = [n for n in data["nodes"] if n["type"] == "tool_node"]
    keyword_nodes = [n for n in tool_nodes if n["data"]["tool_name"] == "keyword_match"]
    assert len(keyword_nodes) == 1
    assert "URGENT" in keyword_nodes[0]["data"]["params"]["keywords"]
    assert "BLOCKER" in keyword_nodes[0]["data"]["params"]["keywords"]
```

**Step 3: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_workflow_fixtures.py -v
```
Expected: `FileNotFoundError: [Errno 2] No such file or directory: '.../morning_digest.json'`

**Step 4: Create `backend/data/workflow_templates/morning_digest.json`**

```json
{
  "schema_version": "1.0",
  "nodes": [
    {
      "id": "trigger-1",
      "type": "trigger_node",
      "position": { "x": 250, "y": 50 },
      "data": {
        "label": "Weekday Morning",
        "trigger_type": "cron",
        "cron_expression": "0 8 * * 1-5"
      }
    },
    {
      "id": "tool-1",
      "type": "tool_node",
      "position": { "x": 250, "y": 180 },
      "data": {
        "label": "Fetch Email",
        "tool_name": "fetch_email",
        "params": { "period": "last_24h" }
      }
    },
    {
      "id": "condition-1",
      "type": "condition_node",
      "position": { "x": 250, "y": 310 },
      "data": {
        "label": "Has emails?",
        "expression": "output.count > 0"
      }
    },
    {
      "id": "agent-1",
      "type": "agent_node",
      "position": { "x": 100, "y": 440 },
      "data": {
        "label": "Summarize Emails",
        "agent": "email",
        "instruction": "Summarize the emails into a concise daily digest, highlighting the most important messages and action items."
      }
    },
    {
      "id": "channel-1",
      "type": "channel_output_node",
      "position": { "x": 100, "y": 570 },
      "data": {
        "label": "Send to Telegram",
        "channel": "telegram",
        "template": "{{current_output}}"
      }
    }
  ],
  "edges": [
    { "id": "e1", "source": "trigger-1", "target": "tool-1" },
    { "id": "e2", "source": "tool-1", "target": "condition-1" },
    {
      "id": "e3",
      "source": "condition-1",
      "target": "agent-1",
      "sourceHandle": "true"
    },
    { "id": "e4", "source": "agent-1", "target": "channel-1" }
  ]
}
```

**Step 5: Create `backend/data/workflow_templates/alert.json`**

```json
{
  "schema_version": "1.0",
  "nodes": [
    {
      "id": "trigger-1",
      "type": "trigger_node",
      "position": { "x": 250, "y": 50 },
      "data": {
        "label": "Webhook Trigger",
        "trigger_type": "webhook"
      }
    },
    {
      "id": "tool-1",
      "type": "tool_node",
      "position": { "x": 250, "y": 180 },
      "data": {
        "label": "Keyword Match",
        "tool_name": "keyword_match",
        "params": { "keywords": ["URGENT", "BLOCKER"] }
      }
    },
    {
      "id": "condition-1",
      "type": "condition_node",
      "position": { "x": 250, "y": 310 },
      "data": {
        "label": "Keyword matched?",
        "expression": "output.matched == true"
      }
    },
    {
      "id": "tool-2",
      "type": "tool_node",
      "position": { "x": 100, "y": 440 },
      "data": {
        "label": "Create Task",
        "tool_name": "create_task",
        "params": {}
      }
    },
    {
      "id": "channel-1",
      "type": "channel_output_node",
      "position": { "x": 100, "y": 570 },
      "data": {
        "label": "Alert via Telegram",
        "channel": "telegram",
        "template": "{{current_output}}"
      }
    }
  ],
  "edges": [
    { "id": "e1", "source": "trigger-1", "target": "tool-1" },
    { "id": "e2", "source": "tool-1", "target": "condition-1" },
    {
      "id": "e3",
      "source": "condition-1",
      "target": "tool-2",
      "sourceHandle": "true"
    },
    { "id": "e4", "source": "tool-2", "target": "channel-1" }
  ]
}
```

**Step 6: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_workflow_fixtures.py -v
```
Expected: `8 passed`

**Step 7: Commit**

```bash
cd backend && git add data/ tests/test_workflow_fixtures.py
git commit -m "feat(04-05): add Morning Digest and Alert workflow template fixtures"
```

---

## Task 2: Alembic Data Migration 011

**Files:**
- Create: `backend/alembic/versions/011_phase4_workflow_templates.py`

**Step 1: Generate migration stub**

```bash
cd backend && .venv/bin/alembic revision -m "phase4_workflow_templates"
```

This creates a file like `backend/alembic/versions/<hash>_phase4_workflow_templates.py`. Rename it:

```bash
mv backend/alembic/versions/*phase4_workflow_templates.py \
   backend/alembic/versions/011_phase4_workflow_templates.py
```

**Step 2: Write the migration**

Replace the generated file content with:

```python
"""Phase 4: seed pre-built workflow templates

Revision ID: 011
Revises: 010
Create Date: 2026-02-27
"""
from __future__ import annotations

import json

from alembic import op
from sqlalchemy import text

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None

# Stable UUIDs so downgrade can delete them precisely
MORNING_DIGEST_ID = "a0000000-0000-0000-0000-000000000001"
ALERT_ID = "a0000000-0000-0000-0000-000000000002"

MORNING_DIGEST = {
    "schema_version": "1.0",
    "nodes": [
        {
            "id": "trigger-1",
            "type": "trigger_node",
            "position": {"x": 250, "y": 50},
            "data": {
                "label": "Weekday Morning",
                "trigger_type": "cron",
                "cron_expression": "0 8 * * 1-5",
            },
        },
        {
            "id": "tool-1",
            "type": "tool_node",
            "position": {"x": 250, "y": 180},
            "data": {
                "label": "Fetch Email",
                "tool_name": "fetch_email",
                "params": {"period": "last_24h"},
            },
        },
        {
            "id": "condition-1",
            "type": "condition_node",
            "position": {"x": 250, "y": 310},
            "data": {"label": "Has emails?", "expression": "output.count > 0"},
        },
        {
            "id": "agent-1",
            "type": "agent_node",
            "position": {"x": 100, "y": 440},
            "data": {
                "label": "Summarize Emails",
                "agent": "email",
                "instruction": "Summarize the emails into a concise daily digest, highlighting the most important messages and action items.",
            },
        },
        {
            "id": "channel-1",
            "type": "channel_output_node",
            "position": {"x": 100, "y": 570},
            "data": {
                "label": "Send to Telegram",
                "channel": "telegram",
                "template": "{{current_output}}",
            },
        },
    ],
    "edges": [
        {"id": "e1", "source": "trigger-1", "target": "tool-1"},
        {"id": "e2", "source": "tool-1", "target": "condition-1"},
        {
            "id": "e3",
            "source": "condition-1",
            "target": "agent-1",
            "sourceHandle": "true",
        },
        {"id": "e4", "source": "agent-1", "target": "channel-1"},
    ],
}

ALERT = {
    "schema_version": "1.0",
    "nodes": [
        {
            "id": "trigger-1",
            "type": "trigger_node",
            "position": {"x": 250, "y": 50},
            "data": {"label": "Webhook Trigger", "trigger_type": "webhook"},
        },
        {
            "id": "tool-1",
            "type": "tool_node",
            "position": {"x": 250, "y": 180},
            "data": {
                "label": "Keyword Match",
                "tool_name": "keyword_match",
                "params": {"keywords": ["URGENT", "BLOCKER"]},
            },
        },
        {
            "id": "condition-1",
            "type": "condition_node",
            "position": {"x": 250, "y": 310},
            "data": {
                "label": "Keyword matched?",
                "expression": "output.matched == true",
            },
        },
        {
            "id": "tool-2",
            "type": "tool_node",
            "position": {"x": 100, "y": 440},
            "data": {
                "label": "Create Task",
                "tool_name": "create_task",
                "params": {},
            },
        },
        {
            "id": "channel-1",
            "type": "channel_output_node",
            "position": {"x": 100, "y": 570},
            "data": {
                "label": "Alert via Telegram",
                "channel": "telegram",
                "template": "{{current_output}}",
            },
        },
    ],
    "edges": [
        {"id": "e1", "source": "trigger-1", "target": "tool-1"},
        {"id": "e2", "source": "tool-1", "target": "condition-1"},
        {
            "id": "e3",
            "source": "condition-1",
            "target": "tool-2",
            "sourceHandle": "true",
        },
        {"id": "e4", "source": "tool-2", "target": "channel-1"},
    ],
}

TEMPLATES = [
    (
        MORNING_DIGEST_ID,
        "Morning Digest",
        "Fetch your emails each weekday morning, check if any arrived, "
        "summarize them, and send the digest to Telegram.",
        MORNING_DIGEST,
    ),
    (
        ALERT_ID,
        "Alert on Urgent Keyword",
        "Watch incoming webhooks for URGENT or BLOCKER keywords, create a "
        "task when matched, and send an alert to Telegram.",
        ALERT,
    ),
]


def upgrade() -> None:
    conn = op.get_bind()
    for template_id, name, description, definition in TEMPLATES:
        conn.execute(
            text(
                """
                INSERT INTO workflows
                    (id, owner_user_id, name, description, definition_json, is_template, created_at, updated_at)
                VALUES
                    (:id, NULL, :name, :description, :definition::jsonb, true, now(), now())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": template_id,
                "name": name,
                "description": description,
                "definition": json.dumps(definition),
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "DELETE FROM workflows WHERE id = ANY(:ids) AND is_template = true"
        ),
        {"ids": [MORNING_DIGEST_ID, ALERT_ID]},
    )
```

**Step 3: Run the migration**

```bash
just migrate
```

Expected output ends with: `Running upgrade 010 -> 011, phase4_workflow_templates`

If `just migrate` is unavailable (backend not running), run directly:

```bash
cd backend && .venv/bin/alembic upgrade head
```

**Step 4: Verify templates exist in DB**

```bash
just db
```

Then in psql:

```sql
SELECT id, name, is_template FROM workflows WHERE is_template = true;
```

Expected: two rows — Morning Digest and Alert on Urgent Keyword.

Type `\q` to exit psql.

**Step 5: Commit**

```bash
git add backend/alembic/versions/011_phase4_workflow_templates.py
git commit -m "feat(04-05): Alembic migration 011 — seed Morning Digest and Alert templates"
```

---

## Task 3: TemplateCard Client Component

The `workflows/page.tsx` created in 04-01 renders a `<form>` button for template copy. A native form POST to a JSON API route would display raw JSON in the browser rather than redirecting. This task replaces it with a `TemplateCard` client component that calls the copy API and navigates to the new workflow.

**Files:**
- Create: `frontend/src/components/canvas/template-card.tsx`
- Modify: `frontend/src/app/workflows/page.tsx`

**Step 1: Create `frontend/src/components/canvas/template-card.tsx`**

```typescript
"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

interface TemplateCardProps {
  id: string;
  name: string;
  description: string | null;
}

export function TemplateCard({ id, name, description }: TemplateCardProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUseTemplate() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/workflows/templates/${id}/copy`, {
        method: "POST",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError((body as { detail?: string }).detail ?? "Failed to copy template");
        return;
      }
      const workflow = (await res.json()) as { id: string };
      router.push(`/workflows/${workflow.id}`);
    } catch {
      setError("Network error — please try again");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="border rounded-lg p-4 bg-gray-50">
      <h3 className="font-medium">{name}</h3>
      {description && (
        <p className="text-sm text-gray-500 mt-1">{description}</p>
      )}
      {error && (
        <p className="text-xs text-red-500 mt-2">{error}</p>
      )}
      <button
        type="button"
        onClick={handleUseTemplate}
        disabled={loading}
        className="mt-3 text-sm px-3 py-1 bg-white border rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? "Copying…" : "Use template →"}
      </button>
    </div>
  );
}
```

**Step 2: Update `frontend/src/app/workflows/page.tsx`**

Replace the template section (the `{templates.map(…)}` block) to use `TemplateCard`:

Old code (lines inside the templates section):
```typescript
            {templates.map((t) => (
              <div key={t.id} className="border rounded-lg p-4 bg-gray-50">
                <h3 className="font-medium">{t.name}</h3>
                {t.description && (
                  <p className="text-sm text-gray-500 mt-1">{t.description}</p>
                )}
                <form action={`/api/workflows/templates/${t.id}/copy`} method="POST" className="mt-3">
                  <button
                    type="submit"
                    className="text-sm px-3 py-1 bg-white border rounded hover:bg-gray-100"
                  >
                    Use template →
                  </button>
                </form>
              </div>
            ))}
```

New code:
```typescript
            {templates.map((t) => (
              <TemplateCard
                key={t.id}
                id={t.id}
                name={t.name}
                description={t.description}
              />
            ))}
```

Also add the import at the top of `workflows/page.tsx` (after other imports):
```typescript
import { TemplateCard } from "@/components/canvas/template-card";
```

**Step 3: TypeScript build check**

```bash
cd frontend && pnpm build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully` (or the workflow pages compile without TypeScript errors; build may fail on other unrelated missing pages — that is acceptable as long as no errors reference `template-card.tsx` or `workflows/page.tsx`).

If you see errors on `workflows/page.tsx`, check:
- The import path `@/components/canvas/template-card` is correct
- `TemplateCard` props match the `WorkflowTemplate` interface fields

**Step 4: Commit**

```bash
cd frontend && git add src/components/canvas/template-card.tsx src/app/workflows/page.tsx
git commit -m "feat(04-05): TemplateCard client component — copy template + redirect to canvas"
```

---

## Task 4: Smoke Test + Final Commit

**Goal:** Verify end-to-end: templates appear in the API response, copying one creates a real workflow row.

**Step 1: Start services**

```bash
just up
just backend
```

Wait for `Application startup complete.`

**Step 2: Get an access token**

```bash
TOKEN=$(curl -s -X POST \
  'https://keycloak.blitz.local:7443/realms/blitz-internal/protocol/openid-connect/token' \
  --insecure \
  -d 'client_id=blitz-portal&grant_type=password&username=admin&password=<PASSWORD_FROM_DEV_SECRETS>' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

Replace `<PASSWORD_FROM_DEV_SECRETS>` with the value from `.dev-secrets`.

**Step 3: List templates**

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/workflows/templates | python3 -m json.tool
```

Expected: JSON array with two objects — Morning Digest and Alert on Urgent Keyword — both with `"is_template": true`.

**Step 4: Copy the Morning Digest template**

```bash
TEMPLATE_ID=$(curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/workflows/templates \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/workflows/templates/${TEMPLATE_ID}/copy \
  | python3 -m json.tool
```

Expected: JSON object with:
- `"is_template": false`
- `"template_source_id"` matching `$TEMPLATE_ID`
- `"definition_json"` containing `"schema_version": "1.0"` and all 5 nodes

**Step 5: Verify the copy exists in user's workflow list**

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/workflows | python3 -m json.tool
```

Expected: array containing the copied workflow with `"name": "Morning Digest"`.

**Step 6: Run full backend test suite**

```bash
cd backend && .venv/bin/pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all tests pass (no failures in `test_workflow_fixtures.py`).

**Step 7: Final commit tagging Phase 4 complete**

```bash
git add -A
git status   # review what's staged — should be only plan file if code committed in previous tasks
git commit -m "docs(04-05): add plan for pre-built templates (Phase 4 complete)"
```

---

## Phase 4 Summary

All five plans shipped:

| Plan | Scope | Key Artifacts |
|---|---|---|
| 04-01 | Workflow CRUD + DB + Canvas shell | `workflow.py` models, `workflows.py` routes, Alembic 010, canvas shell |
| 04-02 | Compiler + node handlers | `graphs.py`, `node_handlers.py`, `condition_evaluator.py`, `workflow_state.py` |
| 04-03 | Execution engine + triggers | `workflow_events.py`, `workflow_execution.py`, SSE + cron + webhook routes |
| 04-04 | HITL + canvas UI | `AsyncPostgresSaver`, 6 node renderers, hooks, `WorkflowCanvas`, `RunControls` |
| 04-05 | Templates | `morning_digest.json`, `alert.json`, Alembic 011, `TemplateCard` |

**Gate criteria verified when:**
1. User can drag nodes, connect edges, and save a workflow with `schema_version: "1.0"` ✓ (04-01)
2. Workflow compiles to a `StateGraph` and executes end-to-end ✓ (04-02, 04-03)
3. Morning Digest template runs: fetch email → condition → summarize → send to Telegram ✓ (04-05)
4. Alert template runs: webhook → keyword match → condition → create task → notify ✓ (04-05)
5. HITL approval node pauses execution and shows Approve/Reject in the canvas ✓ (04-04)
6. Cron-triggered workflow runs as job owner with full 3-gate ACL ✓ (04-03)
