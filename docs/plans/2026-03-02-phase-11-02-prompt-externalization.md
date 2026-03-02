# Phase 11-02: Prompt Externalization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move all 7 inline LLM system prompts from Python files to `backend/prompts/*.md` files, backed by a `PromptLoader` utility with in-memory caching and `{variable}` substitution.

**Architecture:** A new `backend/core/prompts.py` module provides `load_prompt(name, **vars)` — reads `backend/prompts/{name}.md` on first call, caches in a module-level dict forever. Variable substitution uses `str.format_map()`. Three Python files are refactored to call `load_prompt()` instead of referencing inline string constants. `artifact_builder_prompts.py` keeps its existing public API (`get_gather_type_prompt`, `get_system_prompt`) — only the internals change.

**Tech Stack:** Python 3.12, `pathlib.Path`, no new dependencies

---

## Context — Files Being Changed

| File | Change |
|------|--------|
| `backend/core/prompts.py` | **Create** — `load_prompt()` + cache |
| `backend/prompts/` | **Create directory** + 7 `.md` files |
| `backend/agents/master_agent.py` | Remove `_DEFAULT_SYSTEM_PROMPT` constant, call `load_prompt("master-agent")` |
| `backend/agents/artifact_builder_prompts.py` | Remove 5 prompt constants + `_PROMPTS` dict, call `load_prompt()` per type |
| `backend/scheduler/tasks/embedding.py` | Replace inline prompt with `load_prompt("memory-summarizer", transcript=transcript)` |
| `backend/tests/test_prompts.py` | **Create** — unit tests for `load_prompt()` |

Current test count: **607 tests**. After this plan: **610 tests** (3 new, none deleted).

---

### Task 1: Write failing tests for PromptLoader

**Files:**
- Create: `backend/tests/test_prompts.py`

**Step 1: Create the test file**

```python
"""Tests for core.prompts.PromptLoader."""
import importlib
from pathlib import Path
from unittest.mock import patch

import pytest


def _reload_prompts() -> object:
    """Reload core.prompts to reset the module-level cache between tests."""
    import core.prompts as m
    importlib.reload(m)
    return m


def test_load_prompt_returns_file_content(tmp_path: Path) -> None:
    """load_prompt reads the .md file and returns its content."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "hello.md").write_text("Hello world", encoding="utf-8")

    m = _reload_prompts()
    with patch.object(m, "_PROMPTS_DIR", prompts_dir):
        result = m.load_prompt("hello")

    assert result == "Hello world"


def test_load_prompt_caches_on_second_call(tmp_path: Path) -> None:
    """Second call returns cached value without re-reading disk."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    prompt_file = prompts_dir / "cacheme.md"
    prompt_file.write_text("Original", encoding="utf-8")

    m = _reload_prompts()
    with patch.object(m, "_PROMPTS_DIR", prompts_dir):
        first = m.load_prompt("cacheme")
        # Overwrite file — second call must NOT reflect this change
        prompt_file.write_text("Modified", encoding="utf-8")
        second = m.load_prompt("cacheme")

    assert first == "Original"
    assert second == "Original"  # cached, not re-read


def test_load_prompt_variable_substitution(tmp_path: Path) -> None:
    """load_prompt applies {variable} substitution when vars are passed."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "greet.md").write_text("Hello {name}!", encoding="utf-8")

    m = _reload_prompts()
    with patch.object(m, "_PROMPTS_DIR", prompts_dir):
        result = m.load_prompt("greet", name="Blitz")

    assert result == "Hello Blitz!"


def test_load_prompt_missing_file_raises(tmp_path: Path) -> None:
    """load_prompt raises FileNotFoundError for unknown prompt names."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    m = _reload_prompts()
    with patch.object(m, "_PROMPTS_DIR", prompts_dir):
        with pytest.raises(FileNotFoundError):
            m.load_prompt("does-not-exist")
```

**Step 2: Run the tests to confirm they fail**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_prompts.py -v
```

Expected: **4 errors** — `ModuleNotFoundError: No module named 'core.prompts'` (the module doesn't exist yet).

---

### Task 2: Create PromptLoader in backend/core/prompts.py

**Files:**
- Create: `backend/core/prompts.py`

**Step 1: Create the file**

```python
"""
Prompt loader — reads LLM system prompts from backend/prompts/*.md files.

Prompts are cached in a module-level dict after the first read.
Variable substitution uses str.format_map() with {variable} syntax.

Usage:
    from core.prompts import load_prompt

    # No variables
    prompt = load_prompt("master-agent")

    # With variables
    prompt = load_prompt("memory-summarizer", transcript=transcript)
"""
from pathlib import Path

_PROMPTS_DIR: Path = Path(__file__).parent.parent / "prompts"
_cache: dict[str, str] = {}


def load_prompt(name: str, **vars: str) -> str:
    """
    Load a prompt from backend/prompts/{name}.md, with optional variable substitution.

    Args:
        name: Prompt file name without extension (e.g., "master-agent").
        **vars: Variables for {variable} substitution in the template.

    Returns:
        Rendered prompt string.

    Raises:
        FileNotFoundError: If backend/prompts/{name}.md does not exist.
    """
    if name not in _cache:
        path = _PROMPTS_DIR / f"{name}.md"
        _cache[name] = path.read_text(encoding="utf-8")
    template = _cache[name]
    return template.format_map(vars) if vars else template
```

**Step 2: Run tests to confirm they pass**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_prompts.py -v
```

Expected: **4 passed**.

**Step 3: Commit**

```bash
git add backend/core/prompts.py backend/tests/test_prompts.py
git commit -m "feat(11-02): add PromptLoader with file cache and variable substitution"
```

---

### Task 3: Create backend/prompts/ directory with 7 prompt files

**Files:**
- Create: `backend/prompts/master-agent.md`
- Create: `backend/prompts/artifact-gather-type.md`
- Create: `backend/prompts/artifact-agent.md`
- Create: `backend/prompts/artifact-tool.md`
- Create: `backend/prompts/artifact-skill.md`
- Create: `backend/prompts/artifact-mcp-server.md`
- Create: `backend/prompts/memory-summarizer.md`

**Step 1: Create `backend/prompts/master-agent.md`**

Exact content (copy verbatim from `master_agent.py:_DEFAULT_SYSTEM_PROMPT`):

```
You are Blitz, an intelligent AI assistant for Blitz employees. You are professional but warm — like a smart, helpful colleague. You are clear, direct, and occasionally light in tone.

When you don't know something: Say so directly. Don't make up information.

Format your responses with markdown when it improves clarity (headers, bold, code blocks). Keep responses focused and appropriately concise.

IMPORTANT — math formatting rules you must always follow:
- NEVER use LaTeX notation. No backslashes, no \frac, no \times, no \cdot.
- NEVER wrap math in ( ) or [ ] delimiters like ( x ) or [ x = 5 ].
- NEVER wrap math in backticks or code blocks.
- Write math as plain readable prose: '15 / 3 = 5', '1239 × 17 = 21063'.
- Use the Unicode × character for multiplication, ÷ for division.
```

**Step 2: Create `backend/prompts/artifact-gather-type.md`**

Read the exact content from `backend/agents/artifact_builder_prompts.py` lines 11–23 (`_GATHER_TYPE_PROMPT` triple-quoted string body) and write it to this file as plain text (no Python triple quotes, no variable wrapper — just the prompt text itself).

**Step 3: Create `backend/prompts/artifact-agent.md`**

Read exact content from `artifact_builder_prompts.py` lines 25–44 (`_AGENT_PROMPT` body) and write to this file.

**Step 4: Create `backend/prompts/artifact-tool.md`**

Read exact content from `artifact_builder_prompts.py` lines 46–73 (`_TOOL_PROMPT` body) and write to this file.

**Step 5: Create `backend/prompts/artifact-skill.md`**

Read exact content from `artifact_builder_prompts.py` lines 75–101 (`_SKILL_PROMPT` body) and write to this file.

**Step 6: Create `backend/prompts/artifact-mcp-server.md`**

Read exact content from `artifact_builder_prompts.py` lines 103–115 (`_MCP_SERVER_PROMPT` body) and write to this file.

**Step 7: Create `backend/prompts/memory-summarizer.md`**

```
Summarize this conversation in 2-3 sentences. Focus on key facts, decisions, and preferences expressed by the user.

{transcript}
```

Note: `{transcript}` is the variable substitution placeholder — it will be filled by `load_prompt("memory-summarizer", transcript=transcript)`.

**Step 8: Verify all 7 files exist**

```bash
ls backend/prompts/
```
Expected:
```
artifact-agent.md
artifact-gather-type.md
artifact-mcp-server.md
artifact-skill.md
artifact-tool.md
master-agent.md
memory-summarizer.md
```

**Step 9: Commit**

```bash
git add backend/prompts/
git commit -m "feat(11-02): add 7 prompt .md files to backend/prompts/"
```

---

### Task 4: Refactor master_agent.py

**Files:**
- Modify: `backend/agents/master_agent.py`

**Step 1: Add `load_prompt` import**

Find the imports section at the top of `master_agent.py`. Add after the existing local imports:

```python
from core.prompts import load_prompt
```

**Step 2: Remove `_DEFAULT_SYSTEM_PROMPT` constant (lines 188–201)**

Delete these lines entirely:
```python
_DEFAULT_SYSTEM_PROMPT = (
    "You are Blitz, an intelligent AI assistant for Blitz employees. "
    "You are professional but warm — like a smart, helpful colleague. "
    "You are clear, direct, and occasionally light in tone.\n\n"
    "When you don't know something: Say so directly. Don't make up information.\n\n"
    "Format your responses with markdown when it improves clarity (headers, bold, "
    "code blocks). Keep responses focused and appropriately concise.\n\n"
    "IMPORTANT — math formatting rules you must always follow:\n"
    "- NEVER use LaTeX notation. No backslashes, no \\frac, no \\times, no \\cdot.\n"
    "- NEVER wrap math in ( ) or [ ] delimiters like ( x ) or [ x = 5 ].\n"
    "- NEVER wrap math in backticks or code blocks.\n"
    "- Write math as plain readable prose: '15 / 3 = 5', '1239 × 17 = 21063'.\n"
    "- Use the Unicode × character for multiplication, ÷ for division."
)
```

**Step 3: Update the two usages of `_DEFAULT_SYSTEM_PROMPT`**

Usage 1 — in `_build_messages` function (around line 230):
```python
# Old:
system_content = _DEFAULT_SYSTEM_PROMPT
# New:
system_content = load_prompt("master-agent")
```

Usage 2 — in the workflow sub-agent invocation (around line 645):
```python
# Old:
messages = [SystemMessage(content=_DEFAULT_SYSTEM_PROMPT)] + messages
# New:
messages = [SystemMessage(content=load_prompt("master-agent"))] + messages
```

**Step 4: Run the full test suite**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: **607 passed** (same count — no tests deleted, no regressions from this change).

**Step 5: Commit**

```bash
git add backend/agents/master_agent.py
git commit -m "refactor(11-02): load master-agent system prompt from prompts/master-agent.md"
```

---

### Task 5: Refactor artifact_builder_prompts.py

**Files:**
- Modify: `backend/agents/artifact_builder_prompts.py`

**Step 1: Replace entire file content**

The new file keeps the same public API (`get_gather_type_prompt`, `get_system_prompt`) but removes all 5 prompt constants and the `_PROMPTS` dict. Replace the file with:

```python
"""
Artifact builder prompts — load from backend/prompts/artifact-*.md files.

Public API (unchanged):
    get_gather_type_prompt() -> str
    get_system_prompt(artifact_type: str) -> str
"""
from core.prompts import load_prompt

_PROMPT_NAMES: dict[str, str] = {
    "agent": "artifact-agent",
    "tool": "artifact-tool",
    "skill": "artifact-skill",
    "mcp_server": "artifact-mcp-server",
}


def get_gather_type_prompt() -> str:
    """Return the system prompt for the gather_type node."""
    return load_prompt("artifact-gather-type")


def get_system_prompt(artifact_type: str) -> str:
    """
    Return the system prompt for the given artifact type.

    Args:
        artifact_type: One of 'agent', 'tool', 'skill', 'mcp_server'.

    Raises:
        ValueError: If artifact_type is not recognized.
    """
    name = _PROMPT_NAMES.get(artifact_type)
    if name is None:
        raise ValueError(f"Unknown artifact type: {artifact_type!r}")
    return load_prompt(name)
```

**Step 2: Run the full test suite**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: **607 passed**.

**Step 3: Commit**

```bash
git add backend/agents/artifact_builder_prompts.py
git commit -m "refactor(11-02): load artifact builder prompts from prompts/artifact-*.md files"
```

---

### Task 6: Refactor scheduler/tasks/embedding.py

**Files:**
- Modify: `backend/scheduler/tasks/embedding.py`

**Step 1: Add `load_prompt` to the module-level imports**

Find the import block at the top of `embedding.py`. Add:

```python
from core.prompts import load_prompt
```

**Step 2: Replace the inline prompt (around lines 166–168)**

Old code:
```python
prompt = (
    "Summarize this conversation in 2-3 sentences. Focus on key facts, "
    "decisions, and preferences expressed by the user.\n\n" + transcript
)
```

New code:
```python
prompt = load_prompt("memory-summarizer", transcript=transcript)
```

**Step 3: Remove the lazy `HumanMessage` import (line 171) if it was the only lazy import**

Check if `from langchain_core.messages import HumanMessage` is already imported at the top of the file. If so, remove the inline import on line 171. If it's only imported lazily here, move it to the top-level imports block.

**Step 4: Run the full test suite**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: **607 passed**.

**Step 5: Verify no inline prompt strings remain in Python files**

```bash
grep -rn "_DEFAULT_SYSTEM_PROMPT\|_GATHER_TYPE_PROMPT\|_AGENT_PROMPT\|_TOOL_PROMPT\|_SKILL_PROMPT\|_MCP_SERVER_PROMPT" \
  backend/ --include="*.py" | grep -v ".venv" | grep -v __pycache__
```

Expected: zero results.

**Step 6: Commit**

```bash
git add backend/scheduler/tasks/embedding.py
git commit -m "refactor(11-02): load memory-summarizer prompt from prompts/memory-summarizer.md"
```

---

### Task 7: Final verification

**Step 1: Run full test suite one more time**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: **610 passed** (607 original + 4 new PromptLoader tests — wait, we added 4 test functions in Task 1. Actual count: 607 + 4 = 611. Confirm the exact number matches.)

> Note: If the count is off, run with `--collect-only` to compare: `PYTHONPATH=. .venv/bin/pytest tests/ --collect-only -q | tail -3`

**Step 2: Confirm prompts directory has exactly 7 files**

```bash
ls backend/prompts/ | wc -l
```
Expected: `7`

**Step 3: Confirm no inline prompts remain**

```bash
grep -rn "You are Blitz\|You are an AI assistant that helps administrators\|You are helping an administrator\|Summarize this conversation" \
  backend/ --include="*.py" | grep -v ".venv" | grep -v __pycache__ | grep -v alembic
```

Expected: zero results.
