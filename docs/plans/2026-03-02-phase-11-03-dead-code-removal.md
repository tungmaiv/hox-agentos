# Phase 11-03: Dead Code Removal Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Delete `classify_intent()` and its test file — both are dead code never called from production.

**Architecture:** `backend/agents/subagents/router.py` contains only `classify_intent()` and its prompt constant. It is never imported by any production file. `backend/tests/agents/test_router.py` tests only `classify_intent()`. Both files are deleted in full. Nothing else changes.

**Tech Stack:** Python, pytest, git

---

## Context

Current test count: **607 tests**

`router.py` contains:
- `_CLASSIFICATION_PROMPT` constant (inline prompt string)
- `classify_intent(message: str) -> str` async function

Neither is imported anywhere in production code. The only references are in `test_router.py`.

After deletion: **601 tests** (607 − 6 deleted test functions).

---

### Task 1: Confirm router.py has no production callers

**Step 1: Grep for any production imports**

```bash
grep -rn "classify_intent\|from agents.subagents.router\|import router" \
  backend/ --include="*.py" \
  | grep -v ".venv" | grep -v __pycache__ | grep -v "tests/"
```

Expected: **zero results** — no production code imports `classify_intent` or `router`.

**Step 2: Grep including tests to see the full picture**

```bash
grep -rn "classify_intent\|from agents.subagents.router" \
  backend/ --include="*.py" \
  | grep -v ".venv" | grep -v __pycache__
```

Expected: results only in `tests/agents/test_router.py` (6 lines).

---

### Task 2: Delete both files

**Files:**
- Delete: `backend/agents/subagents/router.py`
- Delete: `backend/tests/agents/test_router.py`

**Step 1: Delete the files**

```bash
rm backend/agents/subagents/router.py
rm backend/tests/agents/test_router.py
```

**Step 2: Verify they are gone**

```bash
ls backend/agents/subagents/
ls backend/tests/agents/
```

`router.py` and `test_router.py` must not appear in either listing.

---

### Task 3: Verify zero references remain

**Step 1: Confirm no remaining classify_intent references**

```bash
grep -rn "classify_intent\|from agents.subagents.router" \
  backend/ --include="*.py" \
  | grep -v ".venv" | grep -v __pycache__
```

Expected: **zero results**.

---

### Task 4: Run the full test suite

**Step 1: Run tests**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: **601 passed, 0 failed** (607 − 6 deleted tests).

If any test fails, it means something unexpectedly imported `router.py`. Investigate before proceeding.

---

### Task 5: Commit

```bash
git add -u backend/agents/subagents/router.py backend/tests/agents/test_router.py
git commit -m "refactor(11-03): delete classify_intent dead code and its tests"
```

> Note: `git add -u` stages deleted files. Confirm with `git status` that both deletions are staged.
