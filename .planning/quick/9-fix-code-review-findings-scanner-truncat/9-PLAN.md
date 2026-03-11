---
phase: quick-9
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/skills/security_scanner.py
  - backend/agents/artifact_builder.py
  - frontend/src/components/admin/artifact-builder-client.tsx
autonomous: true
requirements: [QUICK-9]
must_haves:
  truths:
    - "LLM prompt reviewer receives up to 2000 chars of instruction_markdown (not 500)"
    - "fill_form tool return message counts instruction_markdown when it is filled"
    - "handleFork clears manualDraftRef so the forked draft is not overridden by stale manual edits"
  artifacts:
    - path: backend/skills/security_scanner.py
      provides: "Extended LLM review truncation limit"
      contains: "instruction[:2000]"
    - path: backend/agents/artifact_builder.py
      provides: "fill_form counts instruction_markdown"
      contains: "\"instruction_markdown\": instruction_markdown"
    - path: frontend/src/components/admin/artifact-builder-client.tsx
      provides: "handleFork clears manual draft lock"
      contains: "manualDraftRef.current = null"
  key_links:
    - from: backend/skills/security_scanner.py
      to: LLM prompt
      via: instruction[:2000] slice
      pattern: "instruction\\[:2000\\]"
---

<objective>
Apply three targeted code-review fixes: extend the LLM scanner's instruction preview window from 500 to 2000 chars, include instruction_markdown in the fill_form field count, and clear manualDraftRef on fork so the forked draft is not overridden by a stale manual JSON edit.

Purpose: Close security gap (truncated injection payloads bypass LLM reviewer), fix misleading fill_form return count, and fix fork UX bug where manual draft lock overrides the forked content.
Output: Three one-to-two-line edits across three files, committed atomically.
</objective>

<execution_context>
@/home/tungmv/.claude/get-shit-done/workflows/execute-plan.md
@/home/tungmv/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Apply all three targeted fixes</name>
  <files>
    backend/skills/security_scanner.py
    backend/agents/artifact_builder.py
    frontend/src/components/admin/artifact-builder-client.tsx
  </files>
  <action>
Make exactly these three edits — no surrounding code changes:

**Fix 1 — security_scanner.py line 257:**
Change:
```python
f"Instructions: {instruction[:500] if instruction else '(none)'}\n"
```
To:
```python
f"Instructions: {instruction[:2000] if instruction else '(none)'}\n"
```

**Fix 2 — artifact_builder.py lines 72-79:**
In the `filled` dict comprehension, add `"instruction_markdown": instruction_markdown,` as a new entry so the dict reads:
```python
filled = {
    k: v for k, v in {
        "name": name, "description": description, "artifact_type": artifact_type,
        "required_permissions": required_permissions, "model_alias": model_alias,
        "system_prompt": system_prompt, "handler_module": handler_module,
        "sandbox_required": sandbox_required, "entry_point": entry_point,
        "url": url, "version": version,
        "instruction_markdown": instruction_markdown,
    }.items() if v is not None
}
```

**Fix 3 — artifact-builder-client.tsx handleFork (around line 311):**
Before `setSimilarSkills(null);`, add:
```typescript
    // Release manual draft lock so the forked draft takes effect
    manualDraftRef.current = null;
```
The final lines of handleFork become:
```typescript
    // Release manual draft lock so the forked draft takes effect
    manualDraftRef.current = null;
    // Collapse the similar skills panel after forking
    setSimilarSkills(null);
  }, []);
```

Commit all three changes in one atomic commit:
`fix(quick-9): extend scanner truncation to 2000, fix fill_form count, clear manualDraftRef on fork`
  </action>
  <verify>
    <automated>
cd /home/tungmv/Projects/hox-agentos/backend && grep -n "instruction\[:2000\]" skills/security_scanner.py && grep -n '"instruction_markdown": instruction_markdown' agents/artifact_builder.py && grep -n "manualDraftRef.current = null" /home/tungmv/Projects/hox-agentos/frontend/src/components/admin/artifact-builder-client.tsx
    </automated>
  </verify>
  <done>
All three grep patterns match their target lines. No regressions in backend tests:
`cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q --tb=no -q 2>&1 | tail -3`
TypeScript check passes:
`cd /home/tungmv/Projects/hox-agentos/frontend && pnpm exec tsc --noEmit`
  </done>
</task>

</tasks>

<verification>
1. `grep "instruction\[:2000\]" backend/skills/security_scanner.py` — returns line 257
2. `grep '"instruction_markdown": instruction_markdown' backend/agents/artifact_builder.py` — returns line in filled dict
3. `grep "manualDraftRef.current = null" frontend/src/components/admin/artifact-builder-client.tsx` — returns line in handleFork
4. Backend pytest passes (no regression)
5. `pnpm exec tsc --noEmit` exits 0
</verification>

<success_criteria>
- instruction[:2000] present in security_scanner.py LLM prompt
- "instruction_markdown": instruction_markdown present in artifact_builder.py filled dict
- manualDraftRef.current = null present before setSimilarSkills(null) in handleFork
- All backend tests pass
- TypeScript check passes
</success_criteria>

<output>
After completion, create `.planning/quick/9-fix-code-review-findings-scanner-truncat/9-SUMMARY.md`
</output>
