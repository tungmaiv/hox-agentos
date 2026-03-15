---
phase: 28
slug: storage-service
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 28 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) + vitest / pnpm run build (frontend) |
| **Config file** | `backend/pyproject.toml` (pytest config) |
| **Quick run command** | `cd backend && PYTHONPATH=. .venv/bin/pytest tests/storage/ -q` |
| **Full suite command** | `cd backend && PYTHONPATH=. .venv/bin/pytest tests/ -q && cd ../frontend && pnpm run build` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && PYTHONPATH=. .venv/bin/pytest tests/storage/ -q`
- **After every plan wave:** Run full suite (backend + frontend build)
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 28-01-01 | 01 | 0 | STOR-01 | unit | `PYTHONPATH=. .venv/bin/pytest tests/storage/test_minio_client.py -q` | ❌ W0 | ⬜ pending |
| 28-01-02 | 01 | 1 | STOR-01 | unit | `PYTHONPATH=. .venv/bin/pytest tests/storage/test_minio_client.py -q` | ❌ W0 | ⬜ pending |
| 28-01-03 | 01 | 1 | STOR-02 | unit | `PYTHONPATH=. .venv/bin/pytest tests/storage/test_file_service.py -q` | ❌ W0 | ⬜ pending |
| 28-02-01 | 02 | 1 | STOR-02 | integration | `PYTHONPATH=. .venv/bin/pytest tests/api/test_file_routes.py -q` | ❌ W0 | ⬜ pending |
| 28-02-02 | 02 | 1 | STOR-03 | integration | `PYTHONPATH=. .venv/bin/pytest tests/api/test_file_routes.py -q` | ❌ W0 | ⬜ pending |
| 28-02-03 | 02 | 2 | STOR-04 | integration | `PYTHONPATH=. .venv/bin/pytest tests/api/test_file_shares.py -q` | ❌ W0 | ⬜ pending |
| 28-03-01 | 03 | 2 | STOR-05 | unit | `PYTHONPATH=. .venv/bin/pytest tests/storage/test_embed_file.py -q` | ❌ W0 | ⬜ pending |
| 28-03-02 | 03 | 2 | STOR-05 | unit | `PYTHONPATH=. .venv/bin/pytest tests/storage/test_embed_file.py -q` | ❌ W0 | ⬜ pending |
| 28-03-03 | 03 | 3 | STOR-06 | manual | `cd frontend && pnpm run build` | ✅ | ⬜ pending |
| 28-03-04 | 03 | 3 | STOR-06 | manual | `cd frontend && pnpm run build` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/storage/__init__.py` — test package init
- [ ] `tests/storage/test_minio_client.py` — stubs for STOR-01 (MinIO connectivity, presigned URLs)
- [ ] `tests/storage/test_file_service.py` — stubs for STOR-02 (upload, folder ops, SHA-256 dedup)
- [ ] `tests/api/test_file_routes.py` — stubs for STOR-02, STOR-03 (upload route, download, list)
- [ ] `tests/api/test_file_shares.py` — stubs for STOR-04 (share create, permission check, revoke)
- [ ] `tests/storage/test_embed_file.py` — stubs for STOR-05 (text extraction, Celery embed task)
- [ ] `tests/conftest.py` update — add `minio_mock` fixture (moto or aioboto3 mock)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| File Manager UI: grid/list toggle, folder tree, breadcrumb nav | STOR-06 | Frontend interaction requires browser | Navigate to `/files`, toggle views, create folder, verify breadcrumb updates |
| Drag-and-drop upload with progress tray | STOR-02 | Drag events cannot be reliably automated in headless | Drop files onto main area, verify tray appears with per-file progress |
| Share dialog typeahead search | STOR-04 | Requires live user DB + browser interaction | Open share dialog, type partial username, verify suggestions appear |
| Memory badge (🧠) on indexed files | STOR-05 | Visual indicator requires rendering check | Add file to memory, verify brain badge appears on file icon in grid and list view |
| Re-embedding toast on file update | STOR-05 | Celery async + toast notification | Update a memory-indexed file, wait for Celery task, verify toast appears |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
