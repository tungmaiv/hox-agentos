---
phase: quick-5
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/skill_repos/service.py
  - backend/skill_repos/schemas.py
  - frontend/src/components/admin/skill-store-repositories.tsx
autonomous: true
requirements: [QUICK-5]

must_haves:
  truths:
    - "Adding a GitHub repo URL (e.g. https://github.com/HKUDS/CLI-Anything) succeeds even when no agentskills-index.json exists — repo is registered with empty skills list using GitHub API name+description"
    - "Entering owner/repo shorthand (e.g. HKUDS/CLI-Anything) in Add Repository dialog is normalized to https://github.com/owner/repo before submit"
    - "When agentskills-index.json returns non-404 HTTP error, the original error is still surfaced (not silenced)"
    - "Repos added via GitHub fallback show correct name and description from GitHub API"
  artifacts:
    - path: "backend/skill_repos/service.py"
      provides: "fetch_index with GitHub fallback + normalize_repo_url helper"
      exports: [fetch_index, normalize_repo_url, add_repo]
    - path: "frontend/src/components/admin/skill-store-repositories.tsx"
      provides: "owner/repo shorthand normalization before POST"
  key_links:
    - from: "skill-store-repositories.tsx handleAdd()"
      to: "backend POST /api/admin/skill-repos"
      via: "normalize_github_shorthand() transforms addUrl before fetch body"
    - from: "service.py fetch_index()"
      to: "api.github.com/repos/{owner}/{repo}"
      via: "GitHub fallback on 404 from agentskills-index.json"
---

<objective>
Make Skill Repository registration resilient to GitHub repos that lack agentskills-index.json, and friendlier with owner/repo shorthand input.

Purpose: GitHub repositories (e.g. HKUDS/CLI-Anything) don't serve agentskills-index.json. Without fallback, every attempt to add them fails with an opaque HTTP 404. Users should be able to add any GitHub repo as a source — it gets registered with name+description from GitHub API and an empty skills list. Skill browsing gracefully returns 0 results for empty repos.

Output:
- `service.py`: `fetch_index` falls back to GitHub API on 404 for github.com URLs; new `normalize_repo_url()` exported for reuse
- `schemas.py`: no structural change required (IndexSchema allows empty skills list already)
- `skill-store-repositories.tsx`: `handleAdd` normalizes owner/repo shorthand before submit; dialog placeholder/hint updated
</objective>

<execution_context>
@/home/tungmv/.claude/get-shit-done/workflows/execute-plan.md
@/home/tungmv/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@backend/skill_repos/service.py
@backend/skill_repos/schemas.py
@frontend/src/components/admin/skill-store-repositories.tsx

<interfaces>
<!-- Key contracts the executor needs. No codebase exploration needed. -->

From backend/skill_repos/service.py (current fetch_index):
```python
async def fetch_index(url: str) -> dict[str, Any]:
    base = url.rstrip("/")
    index_url = f"{base}/agentskills-index.json"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(index_url)
        response.raise_for_status()   # <-- raises on 404, currently crashes add_repo
    raw = response.json()
    try:
        IndexSchema.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid agentskills-index.json: {exc}") from exc
    return raw
```

From backend/skill_repos/schemas.py (IndexSchema):
```python
class IndexSchema(BaseModel):
    repository: dict[str, Any]  # must contain: name, description, url, version
    skills: list[dict[str, Any]]
```
Note: `skills` has no `min_length` constraint — an empty list `[]` is valid.

From backend/skill_repos/service.py (add_repo):
```python
async def add_repo(url: str, session: AsyncSession) -> RepoInfo:
    index = await fetch_index(url)
    repo_meta: dict[str, Any] = index.get("repository", {})
    name: str = repo_meta.get("name", "")
    description: str | None = repo_meta.get("description") or None
    ...
```

GitHub REST API (no auth needed for public repos):
- GET https://api.github.com/repos/{owner}/{repo}
- Returns: { "name": str, "description": str|null, "html_url": str, ... }
- Rate limit: 60 requests/hour unauthenticated (acceptable for admin-only use)

Frontend Add Repository dialog (current handleAdd):
```tsx
const handleAdd = async () => {
    if (!addUrl.trim()) return;
    ...
    body: JSON.stringify({ url: addUrl.trim() }),
    ...
};
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Backend — GitHub fallback in fetch_index + normalize_repo_url</name>
  <files>backend/skill_repos/service.py, backend/tests/test_skill_repo_service.py</files>
  <behavior>
    - normalize_repo_url("HKUDS/CLI-Anything") -> "https://github.com/HKUDS/CLI-Anything"
    - normalize_repo_url("owner/repo") -> "https://github.com/owner/repo"
    - normalize_repo_url("https://github.com/owner/repo") -> "https://github.com/owner/repo" (passthrough)
    - normalize_repo_url("https://skills.example.com") -> "https://skills.example.com" (non-GitHub passthrough)
    - fetch_index on github.com URL that returns 404 for agentskills-index.json: calls GitHub API, returns synthetic index {"repository": {"name": repo_name, "description": desc, "url": url, "version": "0.0.0"}, "skills": []}
    - fetch_index on non-github.com URL that returns 404: raises httpx.HTTPStatusError (no change from current behavior)
    - fetch_index on github.com URL with valid agentskills-index.json: returns the real index (no fallback needed)
    - fetch_index on non-404 HTTP error (e.g. 500) for github.com URL: raises httpx.HTTPStatusError (not silenced)
  </behavior>
  <action>
    Add `normalize_repo_url(url: str) -> str` function above `fetch_index`. Logic: if input matches `^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$` (no scheme, no dot-slash, just owner/repo), prepend "https://github.com/". Otherwise return as-is.

    Modify `fetch_index` to catch `httpx.HTTPStatusError` with `status_code == 404` ONLY when `base` matches `https://github.com/{owner}/{repo}` (i.e., URL path has exactly 2 non-empty segments). In that case:
    1. Extract owner/repo from the URL path.
    2. Call `GET https://api.github.com/repos/{owner}/{repo}` with the same `httpx.AsyncClient` (timeout=10.0, headers={"Accept": "application/vnd.github+json", "User-Agent": "blitz-agentos"}).
    3. If GitHub API returns 200: build and return synthetic index dict: `{"repository": {"name": data["name"], "description": data.get("description") or "", "url": base, "version": "0.0.0"}, "skills": []}` — skip IndexSchema validation (it's internally constructed, always valid).
    4. If GitHub API returns non-200: raise `ValueError(f"GitHub repo not found or inaccessible: {owner}/{repo}")`.
    5. For 404 on non-GitHub URLs: re-raise the original `httpx.HTTPStatusError`.

    Also call `normalize_repo_url` at the top of `add_repo` before passing url to `fetch_index`:
    ```python
    url = normalize_repo_url(url)
    ```

    Write tests in `backend/tests/test_skill_repo_service.py` using `unittest.mock.patch` to mock `httpx.AsyncClient.get`. Test all 8 behavior cases above.
  </action>
  <verify>
    <automated>cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/test_skill_repo_service.py -v -x 2>&1 | tail -30</automated>
  </verify>
  <done>All 8 behavior cases pass. fetch_index handles GitHub 404 gracefully. normalize_repo_url exported from service.py.</done>
</task>

<task type="auto">
  <name>Task 2: Frontend — owner/repo shorthand normalization in Add Repository dialog</name>
  <files>frontend/src/components/admin/skill-store-repositories.tsx</files>
  <action>
    Add a pure function `normalizeRepoUrl(raw: string): string` inside the component file (above the component). Logic mirrors the backend:
    - If input matches `/^[A-Za-z0-9_.\-]+\/[A-Za-z0-9_.\-]+$/` (exactly owner/repo, no scheme), return `"https://github.com/" + raw`.
    - Otherwise return `raw` unchanged.

    In `handleAdd`, apply normalization before posting:
    ```tsx
    const normalized = normalizeRepoUrl(addUrl.trim());
    // then use `normalized` instead of `addUrl.trim()` in JSON.stringify body
    ```

    Also update the dialog hint text and placeholder for clarity:
    - Placeholder: `"https://skills.example.com or owner/repo"`
    - Hint paragraph: replace current text with:
      "Enter a full URL (must serve `agentskills-index.json`) or a GitHub shorthand like `owner/repo` (e.g. `HKUDS/CLI-Anything`)."

    Do NOT change input `type` — keep it as `type="url"` would reject non-URL input; change to `type="text"` to allow owner/repo shorthand. Change `type="text"`.

    No TypeScript `any` usage. Function must be typed `(raw: string): string`.
  </action>
  <verify>
    <automated>cd /home/tungmv/Projects/hox-agentos/frontend && pnpm exec tsc --noEmit 2>&1 | tail -20</automated>
  </verify>
  <done>TypeScript passes. Dialog accepts owner/repo shorthand. Placeholder and hint updated. normalizeRepoUrl tested mentally: "HKUDS/CLI-Anything" -> "https://github.com/HKUDS/CLI-Anything", "https://..." -> passthrough.</done>
</task>

</tasks>

<verification>
End-to-end smoke check (manual, after both tasks):
1. Open Admin > Skill Store > Repositories
2. Click "Add Repository", type `HKUDS/CLI-Anything` (shorthand) — should register successfully with GitHub name+description and 0 skills
3. Click "Add Repository", type `https://github.com/HKUDS/CLI-Anything` (full URL) — same result
4. Click "Add Repository", type a non-existent GitHub repo — should show clear error (not 404 crash)
5. Existing agentskills-index.json URLs must still work unchanged

Backend tests: `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/test_skill_repo_service.py -v`
Frontend types: `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm exec tsc --noEmit`
</verification>

<success_criteria>
- normalize_repo_url("HKUDS/CLI-Anything") returns "https://github.com/HKUDS/CLI-Anything"
- fetch_index on a GitHub URL with no agentskills-index.json returns synthetic index (name+description from GitHub API, empty skills list) instead of raising
- fetch_index on non-GitHub 404 still raises (backward compatible)
- Frontend Add Repository dialog accepts owner/repo shorthand and posts normalized URL
- All existing backend tests still pass (no regressions)
- TypeScript compiles with no errors
</success_criteria>

<output>
After completion, create `.planning/quick/5-skill-repo-graceful-github-fallback-owne/5-SUMMARY.md` with:
- What was built
- Files modified
- Key decisions (e.g. GitHub API URL parsing approach, shorthand regex)
- Commit hash
</output>
