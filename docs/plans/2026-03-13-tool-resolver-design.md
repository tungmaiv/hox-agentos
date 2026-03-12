# Tool Resolver Node — Design

**Date:** 2026-03-13
**Status:** Approved
**Scope:** Artifact Builder — procedural skill creation only

---

## Problem

The skill builder's procedural workflow has two weaknesses:

1. **Hardcoded tool list** in `artifact_builder_skill.md` — stale the moment a new tool is added
2. **LLM-guessed tool names** — the parent `generate_skill_content` node matches steps to tools by inference, producing hallucinated or incorrect tool names with no verification

Both cause skills to reference non-existent tools, which either silently fail at runtime or require manual correction after creation.

---

## Solution Overview

Insert a new `resolve_tools` LangGraph node into the artifact_builder graph, active **only for procedural skills**. This node:

- Queries the live tool registry (not a hardcoded list)
- Maps each described workflow step to a verified tool name + args hint + required permissions
- Flags unresolvable steps as `MISSING:intent-name`
- Stores results in graph state so `generate_skill_content` uses verified names instead of guessing

Skills with unresolved gaps are saved as `draft` and blocked from activation. When missing tools are later created, the system auto-detects resolution and moves the skill to `pending_activation` for admin review.

---

## Architecture

### Graph Topology Change

**Before (all skill types):**
```
gather_type → gather_details → generate_skill_content → validate_and_present
```

**After (procedural skill only):**
```
gather_type → gather_details → resolve_tools → generate_skill_content → validate_and_present
```

Instructional skills are unaffected — `resolve_tools` is skipped entirely.

### Routing Logic

In `_route_intent()`, after `artifact_type == "skill"` and `skill_type == "procedural"` is confirmed, check whether `resolved_tools` is populated in state. If not, route to `resolve_tools` before `generate_skill_content`.

---

## `resolve_tools` Node

### Model
`blitz/fast` — task is bounded matching, not reasoning. Keeps latency low.

### Input
- `_fetch_tool_reference_block()` output (already exists — reused as-is)
- User's skill description from `artifact_draft`

### Prompt Contract

```
You are a tool resolver. Map each workflow step to the best matching tool.

Available tools:
{tool_reference_block}

Skill description: {description}

For each step, output a JSON array only — no prose:
[
  {
    "intent": "fetch yesterday's tasks",
    "tool": "project.list_tasks",
    "args_hint": {"date": "yesterday"},
    "permissions": ["tool:project"]
  },
  {
    "intent": "send summary to Slack",
    "tool": "MISSING:send-slack-message",
    "args_hint": {"recipient": "team"},
    "permissions": []
  }
]

Rules:
- Use exact tool names from the available tools list only
- If no tool matches, prefix with "MISSING:" followed by kebab-case intent description
- Output valid JSON array only
```

### Output
Two new `ArtifactBuilderState` fields populated from parsed response:

```python
resolved_tools: list[dict]  # steps with matched tools → fed into generate_skill_content
tool_gaps: list[dict]       # steps with MISSING tools → fed into validate_and_present
```

### Fallback
If the node errors or returns unparseable JSON, fall through to `generate_skill_content` with empty `resolved_tools`. Existing LLM-based behavior is preserved — no regression.

---

## Permission Derivation

`required_permissions` is computed as the **union of permissions across all resolved tools**:

```python
required_permissions = list({
    perm
    for step in resolved_tools
    for perm in step.get("permissions", [])
})
```

This replaces the hardcoded permission list in `artifact_builder_skill.md`. The prompt section changes to:

```
required_permissions: DERIVED automatically from resolved tools — do not guess
```

For MISSING steps, permissions are unknown and marked as such in the gap record.

---

## Gap Handling

### What Gets Stored

When saving to the registry, `RegistryEntry.config` includes:

```json
{
  "skill_type": "procedural",
  "procedure_json": {"steps": [...]},
  "required_permissions": ["tool:project", "tool:calendar"],
  "tool_gaps": [
    {
      "intent": "send Slack message",
      "tool": "MISSING:send-slack-message",
      "args_hint": {"recipient": "team"},
      "required_permissions": "unknown"
    }
  ]
}
```

### Builder Chat Output (when gaps exist)

```
✅ Skill draft ready — 1 unresolved tool gap

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name: daily-standup
Type: procedural
Permissions: tool:project, tool:calendar (auto-derived)

Steps:
  ✅ Step 1 — fetch yesterday's tasks → project.list_tasks
  ✅ Step 2 — check calendar for conflicts → calendar.list_events
  ⚠️  Step 3 — send summary to Slack → MISSING: send-slack-message
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Skill saved as DRAFT. It cannot be activated until the gap is resolved.

Next: Build the missing tool in Tool Builder, then return here to activate.
```

### Activation Gate — Two Enforcement Points

**Point 1 — `skill_handler.on_create()`:**
- If `config.tool_gaps` is non-empty → force `status = "draft"` regardless of submitted status
- Log: `skill_saved_with_gaps, skill_id=..., gap_count=N`

**Point 2 — `PATCH /api/registry/{id}/status` (activate):**
- Before allowing `status → active`, check `config.tool_gaps`
- If non-empty → return `422`:
  ```json
  {
    "detail": "Skill has unresolved tool gaps. Create missing tools first.",
    "gaps": [...]
  }
  ```

---

## Auto-Resolution on Tool Creation

### Trigger
`tool_handler.on_create()` — runs after every new tool is saved to the registry.

### Logic

```python
async def on_create(self, entry: RegistryEntry, session: AsyncSession) -> None:
    # Find all draft skills with tool_gaps referencing this tool's intent
    draft_skills = await session.execute(
        select(RegistryEntry).where(
            RegistryEntry.type == "skill",
            RegistryEntry.status == "draft",
            RegistryEntry.deleted_at.is_(None),
        )
    )
    for skill in draft_skills.scalars():
        gaps = (skill.config or {}).get("tool_gaps", [])
        if not gaps:
            continue
        # Remove gaps whose MISSING name matches the new tool's name
        new_tool_slug = entry.name.replace(".", "-").replace("_", "-")
        remaining = [
            g for g in gaps
            if new_tool_slug not in g.get("tool", "")
        ]
        if len(remaining) < len(gaps):
            updated_config = {**skill.config, "tool_gaps": remaining}
            if not remaining:
                # All gaps resolved → move to pending_activation
                skill.status = "pending_activation"
                logger.info(
                    "skill_gaps_resolved",
                    skill_id=str(skill.id),
                    triggered_by_tool=entry.name,
                )
            skill.config = updated_config
            session.add(skill)
```

### Status Flow

```
draft (gaps present)
    ↓  tool created → tool_handler detects gap match
pending_activation (gaps cleared, admin notified via status badge)
    ↓  admin tests skill, clicks Activate
active
```

### Frontend Badge
`pending_activation` status renders as an amber badge in the skills list — visually distinct from `draft` (grey) and `active` (green). Admin sees it immediately without hunting.

---

## Changes Summary

| File | Change |
|------|--------|
| `backend/agents/artifact_builder.py` | Add `resolve_tools` node; update routing; add `resolved_tools`/`tool_gaps` to state; compute `required_permissions` from resolved tools |
| `backend/agents/state/artifact_builder_types.py` | Add `resolved_tools: list[dict]`, `tool_gaps: list[dict]` fields |
| `backend/registry/handlers/tool_handler.py` | Add auto-resolution logic in `on_create()` |
| `backend/registry/handlers/skill_handler.py` | Enforce `draft` status when `tool_gaps` non-empty in `on_create()` |
| `backend/api/routes/registry.py` | Add gap check to activate status transition |
| `backend/prompts/artifact_builder_skill.md` | Remove hardcoded permissions list; add gap summary output template; add `DERIVED` note for permissions |
| `frontend/src/app/(authenticated)/admin/skills/page.tsx` | Add `pending_activation` badge (amber) |

---

## Out of Scope

- Semantic/LLM-assisted gap matching in `tool_handler.on_create()` — slug-based matching is sufficient for MVP; can be upgraded later
- MCP tool resolution — MCP servers are a separate registry type; same pattern applies but deferred
- Instructional skill tool resolution — instructional skills reference tools loosely in markdown; no strict resolution needed

---

*Design approved: 2026-03-13*
