---
phase: 23
slug: skill-platform-e-enhanced-builder
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/skills/ tests/api/test_admin_skills.py -q` |
| **Full suite command** | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~30 seconds (quick), ~60 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 23-01-01 | 01 | 1 | SKBLD-01 | unit | `PYTHONPATH=. .venv/bin/pytest tests/skills/test_builder_generate.py -q` | ❌ W0 | ⬜ pending |
| 23-01-02 | 01 | 1 | SKBLD-02 | unit | `PYTHONPATH=. .venv/bin/pytest tests/skills/test_builder_generate.py -q` | ❌ W0 | ⬜ pending |
| 23-01-03 | 01 | 1 | SKBLD-03 | unit | `PYTHONPATH=. .venv/bin/pytest tests/skills/test_builder_generate.py -q` | ❌ W0 | ⬜ pending |
| 23-02-01 | 02 | 1 | SKBLD-04 | unit | `PYTHONPATH=. .venv/bin/pytest tests/skills/test_similar_skills.py -q` | ❌ W0 | ⬜ pending |
| 23-02-02 | 02 | 1 | SKBLD-05 | unit | `PYTHONPATH=. .venv/bin/pytest tests/skills/test_similar_skills.py -q` | ❌ W0 | ⬜ pending |
| 23-03-01 | 03 | 2 | SKBLD-06 | unit | `PYTHONPATH=. .venv/bin/pytest tests/skills/test_security_gate.py -q` | ❌ W0 | ⬜ pending |
| 23-03-02 | 03 | 2 | SKBLD-07 | manual | N/A — frontend component | manual | ⬜ pending |
| 23-03-03 | 03 | 2 | SKBLD-08 | unit | `PYTHONPATH=. .venv/bin/pytest tests/skills/test_security_gate.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/skills/test_builder_generate.py` — stubs for SKBLD-01, SKBLD-02, SKBLD-03
- [ ] `tests/skills/test_similar_skills.py` — stubs for SKBLD-04, SKBLD-05
- [ ] `tests/skills/test_security_gate.py` — stubs for SKBLD-06, SKBLD-08

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SecurityReportCard renders inline in builder preview panel | SKBLD-07 | Frontend React component, no automated test | Open builder, create skill, save → verify SecurityReportCard appears in preview panel with score/factors/recommendation |
| "Edit JSON" toggle shows raw JSON editor | SKBLD-01/02 | Frontend UI interaction | Click "Edit JSON" toggle in builder → textarea with JSON content should appear |
| "Find Similar" button shows top 3–5 results | SKBLD-04 | Frontend UI interaction | Create draft with name+description → click "Find Similar" → verify results list appears |
| Fork replaces builder draft | SKBLD-05 | Frontend UI interaction | Click fork on a similar skill → verify builder form populates with forked skill content |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
