---
phase: 23-skill-platform-e-enhanced-builder
plan: 02
subsystem: skill-builder
tags: [skill-platform, builder, content-generation, claude-code-import, tool-stub]
dependency_graph:
  requires: [23-01]
  provides: [generate_skill_content_node, import_from_claude_code_yaml, activate-stub-endpoint]
  affects: [artifact_builder, skill_importer, admin_tools_api]
tech_stack:
  added: []
  patterns:
    - "LangGraph node: _generate_skill_content_node with conditional routing"
    - "SkillImporter.import_from_claude_code_yaml() maps Claude Code YAML to agentskills shape"
    - "GitHub blob URL → raw.githubusercontent.com conversion in import_from_url()"
    - "PATCH /activate-stub endpoint with pending_stub → active promotion + 409 guard"
key_files:
  created: []
  modified:
    - backend/agents/artifact_builder.py
    - backend/agents/artifact_builder_prompts.py
    - backend/skills/importer.py
    - backend/api/routes/admin_tools.py
    - backend/core/schemas/registry.py
    - backend/tests/skills/test_builder_generate.py
    - backend/tests/test_skill_importer.py
    - backend/tests/api/test_admin_tools.py
decisions:
  - "[23-02]: _route_intent checks for skill content absence before routing to generate_skill_content — avoids re-generating content on subsequent messages"
  - "[23-02]: instruction_markdown detection: if LLM wraps markdown in code block, strip it — handles model variance"
  - "[23-02]: ToolDefinitionUpdate now includes status + handler_code fields — required for stub workflow"
  - "[23-02]: activate-stub endpoint placed before check-name GET route — literal path segment avoids UUID catch-all conflict"
  - "[23-02]: Claude Code YAML category guessed from description keywords when not explicit — email→communication, calendar→productivity, claude→ai, default→general"
metrics:
  duration: "6 minutes"
  completed: "2026-03-09"
  tasks: 2
  files: 8
---

# Phase 23 Plan 02: Skill Builder Content Generation + Claude Code Import Summary

**One-liner:** Full skill content generation (procedure_json / instruction_markdown / handler_code Python stub) via a single LLM shot in the artifact builder, plus Claude Code YAML import adapter with GitHub URL conversion.

## What Was Built

### Task 1: generate_skill_content_node + prompts (SKBLD-01, 02, 03)

Added `get_skill_generation_prompt()` to `artifact_builder_prompts.py`:
- Procedural skill: instructs LLM to output JSON with `procedure_json.steps` array
- Instructional skill: instructs LLM to output markdown starting with `# `
- Tool artifact: instructs LLM to output Python stub with `InputModel`/`OutputModel` Pydantic classes and `async handler()` function

Added `_generate_skill_content_node()` to `artifact_builder.py`:
- Builds prompt via `get_skill_generation_prompt()`
- Calls `get_llm("blitz/master")` with system prompt
- Parses response: procedural → extracts JSON `procedure_json`; instructional → sets `instruction_markdown`; tool → extracts Python code block as `handler_code`
- Calls `_emit_builder_state()` with updated draft
- Returns updated state dict

Updated `_route_intent()` to route to `"generate_skill_content"` when:
- `artifact_type` in (`"skill"`, `"tool"`) AND draft has `name` + `description`
- AND content is still missing (no `procedure_json`, `instruction_markdown`, or `handler_code`)

Registered `generate_skill_content` node and `END` edge in `create_artifact_builder_graph()`.

Replaced 3 xfail stubs in `tests/skills/test_builder_generate.py` with real passing tests (TDD: RED then GREEN).

### Task 2: Claude Code import adapter + activate-stub endpoint (SKBLD-03)

Added `SkillImporter._github_to_raw_url(url)` static method:
- Converts `github.com/{user}/{repo}/blob/{branch}/{path}` to `raw.githubusercontent.com/{user}/{repo}/{branch}/{path}`
- Called in `import_from_url()` when hostname is `github.com`

Added `SkillImporter.import_from_claude_code_yaml(content)` method:
- Parses YAML via `yaml.safe_load()`
- Maps: `name` → `name`, `description` → `description` + seeded `instruction_markdown`
- `when_to_use` + `trigger` prepended to instruction_markdown as `## When to Use` / `## Trigger` sections
- `tools` list → `allowed_tools`
- `category` explicit or guessed from description keywords
- Returns agentskills.io shape dict

Added `PATCH /api/admin/tools/{tool_id}/activate-stub` endpoint:
- Auth: `_require_registry_manager` dependency
- 404 if tool not found; 409 if status != `pending_stub`
- Sets `status = "active"` and `is_active = True`
- Commits and returns `ToolDefinitionResponse`
- Audit log: `action="tool_stub_activated"`, `tool_id`, `user_id`
- Route placed before `/{tool_id}` catch-all

Added `status` and `handler_code` fields to `ToolDefinitionUpdate` and `ToolDefinitionResponse` schemas.

## Decisions Made

- `_route_intent` checks content absence before routing to `generate_skill_content` — once `procedure_json`/`instruction_markdown`/`handler_code` is set, subsequent messages go to `gather_details` instead of re-generating content
- Python code block extraction uses `_extract_python_code_block()` with regex; falls back to full content if no code fence found
- `ToolDefinitionUpdate` extended with `status` and `handler_code` (Rule 2 auto-fix — required for stub workflow test to set pending_stub state via PUT)
- Claude Code YAML `skill_type` defaults to `"instructional"` — Claude Code skills have no execution engine, they are instructions for the AI

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added status + handler_code to ToolDefinitionUpdate schema**
- **Found during:** Task 2 implementation
- **Issue:** `ToolDefinitionUpdate` schema lacked `status` and `handler_code` fields, preventing the test from setting `pending_stub` status via the PUT endpoint (needed for activate-stub flow)
- **Fix:** Added `status: str | None = None` and `handler_code: str | None = None` to `ToolDefinitionUpdate`; added `handler_code: str | None` to `ToolDefinitionResponse`
- **Files modified:** `backend/core/schemas/registry.py`
- **Commit:** 7f40085

## Test Results

- `tests/skills/test_builder_generate.py`: 3/3 pass (replaced xfail stubs)
- `tests/test_skill_importer.py`: 37/37 pass (2 new tests added)
- `tests/api/test_admin_tools.py`: all pass (2 new tests added)
- Full suite: 849 passed, 1 skipped (was 719 at v1.2 — growth from multiple phases)

## Self-Check: PASSED

Files exist:
- backend/agents/artifact_builder.py — FOUND
- backend/agents/artifact_builder_prompts.py — FOUND
- backend/skills/importer.py — FOUND
- backend/api/routes/admin_tools.py — FOUND

Commits exist:
- 754ca8e — FOUND (Task 1: generate_skill_content_node)
- 7f40085 — FOUND (Task 2: Claude Code import + activate-stub)
