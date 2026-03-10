---
phase: quick-5
plan: 01
subsystem: skill-repos
tags: [github-fallback, skill-store, url-normalization, resilience]
dependency_graph:
  requires: []
  provides: [normalize_repo_url, fetch_index_github_fallback]
  affects: [skill_repos/service.py, skill-store-repositories.tsx]
tech_stack:
  added: []
  patterns: [github-rest-api-fallback, owner-repo-shorthand-normalization]
key_files:
  created:
    - backend/tests/test_skill_repo_service.py
  modified:
    - backend/skill_repos/service.py
    - frontend/src/components/admin/skill-store-repositories.tsx
decisions:
  - "GitHub fallback triggered only on 404 + github.com URL with exactly two path segments — avoids false fallback on sub-paths"
  - "Non-404 errors (500, etc.) propagate unchanged — original error surfaced, not silenced"
  - "GitHub API timeout uses 30.0s (same client context) — no extra timeout config needed"
  - "Synthetic index version is 0.0.0 — signals it was auto-generated, not from a real agentskills-index.json"
  - "Frontend input type changed from url to text — browser url validation rejects owner/repo shorthand"
  - "normalizeRepoUrl regex ^[A-Za-z0-9_.\\-]+\\/[A-Za-z0-9_.\\-]+$ — allows dots/dashes in org names (my.org)"
metrics:
  duration: "~3 minutes (169 seconds)"
  completed_date: "2026-03-10"
  tasks_completed: 2
  files_modified: 3
---

# Quick Task 5: Skill Repo Graceful GitHub Fallback + Owner/Repo Shorthand — Summary

**One-liner:** GitHub 404 fallback in fetch_index() using GitHub REST API + owner/repo shorthand normalization in both backend and frontend.

## What Was Built

### Task 1 — Backend: GitHub fallback in `fetch_index` + `normalize_repo_url`

**`normalize_repo_url(url: str) -> str`** — new exported function in `skill_repos/service.py`:
- Detects `owner/repo` shorthand (regex: `^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+$`)
- Expands to `https://github.com/owner/repo`
- Full URLs and non-matching inputs pass through unchanged

**`fetch_index(url)` — GitHub 404 fallback:**
- On `httpx.HTTPStatusError` with `status_code == 404`:
  - If URL matches `https://github.com/{owner}/{repo}` (exactly two path segments), calls `GET https://api.github.com/repos/{owner}/{repo}`
  - GitHub API 200: returns synthetic index `{"repository": {"name": ..., "description": ..., "url": ..., "version": "0.0.0"}, "skills": []}`
  - GitHub API non-200: raises `ValueError("GitHub repo not found or inaccessible: owner/repo")`
  - Non-GitHub URL with 404: re-raises original `httpx.HTTPStatusError` (backward compatible)
- Non-404 errors (500, etc.) for any URL: re-raise immediately without fallback

**`add_repo(url)` update:** calls `normalize_repo_url(url)` at top before passing to `fetch_index`.

**Tests:** 11 tests in `backend/tests/test_skill_repo_service.py` covering all 8 behavior cases. TDD: RED (all 8 failed) → GREEN (all 11 pass). Existing 26 tests in `test_skill_repos.py` still pass.

### Task 2 — Frontend: owner/repo shorthand normalization

**`normalizeRepoUrl(raw: string): string`** — pure function added above component:
- Same logic as backend: matches `/^[A-Za-z0-9_.\-]+\/[A-Za-z0-9_.\-]+$/`, prepends `https://github.com/`
- Typed `(raw: string): string` — no `any`

**`handleAdd()` update:** applies `normalizeRepoUrl(addUrl.trim())` before posting URL to backend.

**Dialog UI updates:**
- Input `type` changed from `"url"` to `"text"` — browser URL validation rejected `owner/repo` shorthand
- Placeholder: `"https://skills.example.com or owner/repo"`
- Hint: explains both full URL and GitHub shorthand with `HKUDS/CLI-Anything` example

## Commits

| Task | Commit | Files |
|------|--------|-------|
| 1 — Backend fallback + normalize | `2bec8e8` | `backend/skill_repos/service.py`, `backend/tests/test_skill_repo_service.py` |
| 2 — Frontend shorthand normalization | `606367a` | `frontend/src/components/admin/skill-store-repositories.tsx` |

## Key Decisions

1. **GitHub URL detection regex** `^https://github\.com/([^/]+)/([^/]+)$` — exactly two path segments. URLs like `https://github.com/owner/repo/tree/main` are not matched, preventing false fallback on sub-paths.

2. **Same `httpx.AsyncClient` context for GitHub API call** — avoids opening a second client, uses the same 30.0s timeout for the fallback call.

3. **Synthetic index version `"0.0.0"`** — signals the index was auto-generated from GitHub metadata, not from a real `agentskills-index.json`. Skill count will show 0 until user syncs or repo adds an index file.

4. **Non-404 errors not silenced** — only `status_code == 404` triggers fallback. A 500 from either the index fetch or the GitHub API propagates as-is, surfacing the true error.

5. **Frontend `type="text"` instead of `type="url"`** — browser's built-in URL validation (which rejects `owner/repo` format) would block shorthand input before JavaScript runs.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- FOUND: `backend/tests/test_skill_repo_service.py`
- FOUND: `backend/skill_repos/service.py`
- FOUND: `frontend/src/components/admin/skill-store-repositories.tsx`
- FOUND commit: `2bec8e8` (feat: backend fallback + normalize)
- FOUND commit: `606367a` (feat: frontend shorthand normalization)
