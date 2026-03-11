---
created: 2026-03-02T03:46:09.011Z
title: Externalize all prompts from Python files into separate markdown files
area: general
files:
  - backend/agents/
  - backend/tools/
---

## Problem

LLM prompts (system prompts, instruction strings, few-shot examples) are currently inlined as Python string literals inside `.py` files. This makes prompt maintenance difficult:
- Hard to read/edit without Python context
- No syntax highlighting for markdown/JSON content
- Requires code changes and re-deploys to iterate on prompts
- Prompts mixed with business logic make code harder to review

## Solution

1. Create a `backend/prompts/` directory to store all prompt files
2. Use `.md` for system prompts and instruction text (human-readable, supports markdown formatting)
3. Use `.json` for structured prompts with few-shot examples or multi-part templates
4. Build a simple `PromptLoader` utility in `backend/core/prompts.py`:
   - `load_prompt(name: str) -> str` — reads from `backend/prompts/{name}.md`
   - Support variable substitution: `load_prompt("email_summary", user=..., date=...)`
   - Cache loaded files in memory to avoid repeated disk reads
5. Audit all `.py` files in `backend/agents/` and `backend/tools/` for inline prompt strings
6. Extract each prompt to its own file with a descriptive name (e.g., `master_agent_system.md`, `email_summarizer.md`)
7. Replace inline strings with `load_prompt("...")` calls
8. Document prompt file naming convention in `docs/dev-context.md`
