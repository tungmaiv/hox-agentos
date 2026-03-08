---
phase: 21
slug: skill-platform-c-dependency-security-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/test_security_scanner.py tests/test_skills.py -q` |
| **Full suite command** | `cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 21-01-01 | 01 | 1 | SKSEC-04 | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_security_scanner.py -q` | ❌ W0 | ⬜ pending |
| 21-02-01 | 02 | 1 | SKSEC-01 | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_security_scanner.py -q` | ❌ W0 | ⬜ pending |
| 21-03-01 | 03 | 2 | SKSEC-02 | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_skill_executor.py -q` | ❌ W0 | ⬜ pending |
| 21-04-01 | 04 | 2 | SKSEC-03 | unit | `PYTHONPATH=. .venv/bin/pytest tests/test_skill_update_checker.py -q` | ❌ W0 | ⬜ pending |
| 21-04-02 | 04 | 2 | SKSEC-03 | migration | `PYTHONPATH=. .venv/bin/alembic check` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_security_scanner.py` — stubs for SKSEC-04 (weight rebalance) and SKSEC-01 (dependency scanning)
- [ ] `tests/test_skill_executor.py` — stubs for SKSEC-02 (allowed_tools enforcement)
- [ ] `tests/test_skill_update_checker.py` — stubs for SKSEC-03 (Celery update checker)
- [ ] Update existing `TestWeightedScoring.test_weights_sum_correctly` to reflect new 6-factor formula

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Admin sees orange `pending_review` badge after update checker triggers | SKSEC-03 | Requires running Celery task + UI inspection | Start stack, import a skill, manually trigger update checker task, verify admin catalog shows orange badge |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
