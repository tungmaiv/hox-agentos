---
status: complete
phase: 17-performance-embedding-sidecar
source: 17-01-SUMMARY.md, 17-02-SUMMARY.md, 17-03-SUMMARY.md, 17-04-SUMMARY.md, 17-05-SUMMARY.md, 17-06-SUMMARY.md, 17-07-SUMMARY.md
started: 2026-03-05T13:10:00Z
updated: 2026-03-05T13:10:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: —
name: (all tests complete)
expected: n/a
awaiting: n/a

## Tests

### 1. Embedding Sidecar in Docker Compose
expected: `embedding-sidecar` service present in docker-compose.yml using `michaelf34/infinity:latest` on port 7997 with `embedding_model_cache` named volume. Starting services brings it up.
result: pass

### 2. Backend starts with sidecar check (non-fatal)
expected: Run `just backend` (or check `just logs backend`). Backend starts successfully and logs either `embedding_sidecar_validated` (sidecar reachable) or `embedding_sidecar_startup_check_failed` (sidecar not yet warm). In either case, the backend starts and serves requests — it does NOT crash on startup if sidecar is unavailable.
result: pass

### 3. Admin dashboard — Memory tab visible
expected: Log in as an admin user and navigate to `/admin`. The admin dashboard navigation should show a "Memory" tab between "Config" and "Credentials". Clicking "Memory" navigates to `/admin/memory`.
result: pass

### 4. Admin Memory page — reindex confirmation dialog
expected: On the `/admin/memory` page, there is a "Memory Reindex" section with a danger-zone button. Clicking the button shows an inline confirmation dialog (not a modal popup). Confirming triggers the reindex; the page shows an in-progress state with a job_id. Errors (e.g., network failure) show an error banner.
result: pass

### 5. Admin Reindex API — 202 for admin, 403 for non-admin
expected: A POST to `/api/admin/memory/reindex` with `{"confirm": true}` returns 202 with a `job_id` when called with an admin JWT. With a non-admin JWT (e.g., employee role), it returns 403. Without `confirm: true`, it returns 422.
result: pass

### 6. duration_ms in backend logs
expected: Make a chat request or check existing backend logs. Log entries should include `duration_ms` fields for at least: memory search operations, LLM calls, tool executions. Each shows an integer value (e.g., `"duration_ms": 142`).
result: pass — memory_search:19ms, llm_call:2005ms, tool_call:4ms all present

### 7. Cache invalidation — user instructions PUT
expected: PUT `/api/user/instructions` with a new instruction value. The next agent turn should immediately use the updated instructions (not the cached old value). The cache TTL is 60s, so without invalidation there would be a delay — the PUT should cause immediate reflection.
result: pass — GET immediately after PUT returns new value; _instructions_cache.pop() called on every PUT (line 130)

### 8. useSkills() — no extra network requests on conversation switch
expected: Open the chat UI. Switch between two conversations. Check the browser network tab — there should NOT be a repeated `GET /api/skills` (or equivalent skills API call) on each conversation switch. Skills are fetched once and reused across conversation changes.
result: pass — network tab shows 2 skills requests on initial load (React StrictMode dev double-effect), zero additional requests on conversation switch

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
