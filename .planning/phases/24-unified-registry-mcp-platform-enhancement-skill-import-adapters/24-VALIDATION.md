---
phase: 24
slug: unified-registry-mcp-platform-enhancement-skill-import-adapters
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-12
updated: 2026-03-12
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend), tsc --noEmit (frontend) |
| **Config file** | `backend/` — conftest.py at root, no pytest.ini |
| **Quick run command** | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q -x --ignore=tests/mcp -k "not slow"` |
| **Full suite command** | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q` |
| **Frontend check** | `cd /home/tungmv/Projects/hox-agentos/frontend && pnpm exec tsc --noEmit` |
| **Estimated runtime** | ~30-40 seconds |
| **Current baseline** | 879 tests collected |

---

## Sampling Rate

- **After every task commit:** Run quick command (ignores MCP tests, skips slow)
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite green + `tsc --noEmit` passes
- **Max feedback latency:** ~40 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 24-01-T1 | 01 | 1 | 24-01-DEBT | unit + build | `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_config.py -x -v && cd ../frontend && pnpm exec tsc --noEmit` | ✅ test_config.py exists | ⬜ pending |
| 24-01-T2 | 01 | 1 | 24-01-DEBT | unit | `cd backend && PYTHONPATH=. .venv/bin/pytest tests/ -q -x -k "not slow"` | ✅ existing suite | ⬜ pending |
| 24-02-T1 | 02 | 1 | 24-02-REG | unit | `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_registry_models.py -x -v` | ❌ Wave 0 task | ⬜ pending |
| 24-02-T2 | 02 | 1 | 24-02-REG | integration | `cd backend && PYTHONPATH=. .venv/bin/pytest tests/api/test_registry_routes.py tests/test_registry_models.py -x -v` | ❌ Wave 0 task | ⬜ pending |
| 24-03-T1 | 03 | 2 | 24-03-MCP | unit (mock) | `cd backend && PYTHONPATH=. .venv/bin/pytest tests/mcp/test_stdio_client.py tests/mcp/test_installer.py -x -v` | ❌ Wave 0 task | ⬜ pending |
| 24-03-T2 | 03 | 2 | 24-03-MCP | integration | `cd backend && PYTHONPATH=. .venv/bin/pytest tests/ -q -x -k "not slow"` | ✅ existing suite | ⬜ pending |
| 24-04-T1 | 04 | 2 | 24-04-SKL | unit (mock) | `cd backend && PYTHONPATH=. .venv/bin/pytest tests/skills/test_github_adapter.py tests/test_skill_importer.py -x -v` | ❌ Wave 0 task | ⬜ pending |
| 24-04-T2 | 04 | 2 | 24-04-SKL | unit | `cd backend && PYTHONPATH=. .venv/bin/pytest tests/skills/test_import_service.py -x -v` | ❌ Wave 0 task | ⬜ pending |
| 24-05-T1 | 05 | 2 | 24-05-SEC | unit (mock) | `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_security_scan_client.py -x -v` | ❌ Wave 0 task | ⬜ pending |
| 24-05-T2 | 05 | 2 | 24-05-SEC | smoke | `docker compose config --quiet 2>&1 \| grep -c security-scanner` | ❌ Wave 0 task | ⬜ pending |
| 24-06-T1 | 06 | 3 | 24-06-UI | unit (mock) | `cd backend && PYTHONPATH=. .venv/bin/pytest tests/api/test_admin_llm_config.py -x -v` | ❌ Wave 0 task | ⬜ pending |
| 24-06-T2 | 06 | 3 | 24-06-UI | build | `cd frontend && pnpm exec tsc --noEmit` | ✅ tsc check | ⬜ pending |
| 24-06-CP | 06 | 3 | 24-06-UI | visual | Human checkpoint | N/A (manual) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements (test stubs to create before or during implementation)

- [ ] `tests/test_registry_models.py` — RegistryEntry ORM model tests; covers 24-02-REG schema
- [ ] `tests/api/test_registry_routes.py` — CRUD endpoint tests for /api/registry/*; covers 24-02-REG
- [ ] `tests/mcp/test_stdio_client.py` — StdioMCPClient mock subprocess tests; covers 24-03-MCP
- [ ] `tests/mcp/test_installer.py` — MCPInstaller mock subprocess tests; covers 24-03-MCP
- [ ] `tests/skills/test_github_adapter.py` — GitHubAdapter mock httpx tests; covers 24-04-SKL
- [ ] `tests/skills/test_import_service.py` — UnifiedImportService pipeline tests; covers 24-04-SKL
- [ ] `tests/test_security_scan_client.py` — SecurityScanClient mock httpx + fallback tests; covers 24-05-SEC
- [ ] `tests/api/test_admin_llm_config.py` — Admin LLM config mock httpx tests; covers 24-06-UI
- [ ] Alembic merge: `cd backend && .venv/bin/alembic merge 027 83f730920f5a -m "028_merge_heads"` — required before registry migration (plan 02 wave 1)

Each PLAN.md includes the test creation as part of the task itself (TDD approach — tests written as first step before implementation code).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 4-tab admin layout renders correctly | 24-06-UI | Visual UI check | Open /admin, verify 4 tabs, click each, verify sub-nav |
| LLM config page adds model | 24-06-UI | External LiteLLM API dependency | Open /admin/system/llm, add test model, verify table updates |
| Docker security scanner health | 24-05-SEC | Docker service not in pytest | `just up security-scanner && curl http://localhost:8003/health` |
| Auth.ts retry on Keycloak down | 24-01-DEBT | Can't simulate Docker timing in unit test | Stop Keycloak, reload frontend, confirm no "Server error" crash |

---

## Execution Wave Summary

| Wave | Plans | Can Parallelize | Gate |
|------|-------|-----------------|------|
| 1 | 24-01, 24-02 | Yes (independent, no file overlap) | Full suite green |
| 2 | 24-03, 24-04, 24-05 | Yes (24-03 depends on 02, 24-04 depends on 02, 24-05 depends on 02 only) | Full suite green |
| 3 | 24-06 | No (depends on 02+03+04+05 complete) | Full suite + tsc + human checkpoint |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands
- [x] Sampling continuity: no consecutive tasks without automated verify
- [x] Wave 0 test stubs identified (created as TDD first-step within each task)
- [x] No watch-mode flags in any verify command
- [x] Feedback latency < 40s for quick run
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planned 2026-03-12
