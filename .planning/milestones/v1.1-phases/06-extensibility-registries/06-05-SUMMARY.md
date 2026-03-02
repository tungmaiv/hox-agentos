---
phase: 06-extensibility-registries
plan: 05
subsystem: skills
tags: [ast, safe-eval, security-scanner, skill-importer, procedural-skills, ag-ui]

# Dependency graph
requires:
  - phase: 06-extensibility-registries
    provides: "SkillDefinition ORM model, admin CRUD routes, Pydantic schemas"
provides:
  - "SkillValidator for procedure_json validation"
  - "AST-based safe expression evaluator (no eval/exec)"
  - "SkillExecutor with 3-gate security and AG-UI step_progress streaming"
  - "SecurityScanner with weighted 0-100 trust scoring"
  - "SkillImporter for AgentSkills SKILL.md format parsing"
  - "Admin import/review/security-report endpoints"
affects: [06-06-PLAN]

# Tech tracking
tech-stack:
  added: [pyyaml]
  patterns:
    - "AST-walk safety validation: parse expression AST, check node types against safe whitelist, reject unsafe constructs"
    - "Weighted multi-factor scoring: source reputation (30%), tool scope (25%), prompt safety (25%), complexity (10%), author verification (10%)"
    - "Import quarantine pipeline: parse -> validate -> scan -> pending_review status"

key-files:
  created:
    - backend/skills/__init__.py
    - backend/skills/safe_eval.py
    - backend/skills/validator.py
    - backend/skills/executor.py
    - backend/skills/security_scanner.py
    - backend/skills/importer.py
    - backend/tests/test_safe_eval.py
    - backend/tests/test_skill_validator.py
    - backend/tests/test_skill_executor.py
    - backend/tests/test_security_scanner.py
    - backend/tests/test_skill_importer.py
  modified:
    - backend/api/routes/admin_skills.py
    - backend/tests/api/test_admin_skills.py

key-decisions:
  - "AST-walk for validation safety check (not _SafeEvaluator subclass) -- avoids evaluation with None variables at validate-time"
  - "Validator dry-run checks AST node types only (not values) -- unknown variables are fine at validation, resolved at runtime"
  - "httpx imported at module top level in importer.py -- lazy imports not patchable in tests (same gotcha as project_agent.py)"
  - "/import route declared before /{skill_id} routes -- prevents FastAPI UUID matching collision on POST path"

patterns-established:
  - "Safe expression evaluator pattern: AST parse + NodeVisitor whitelist, reject all non-whitelisted node types"
  - "Import quarantine pattern: parse -> validate -> security scan -> pending_review -> admin approve/reject"
  - "Weighted security scoring: factor_score * weight summed across all factors"

requirements-completed: [EXTD-06]

# Metrics
duration: 10min
completed: 2026-02-28
---

# Phase 6 Plan 05: Skill System Core Summary

**AST-based safe expression evaluator (no eval/exec), SkillValidator/Executor with 3-gate security and AG-UI streaming, SecurityScanner with weighted trust scoring, and SkillImporter with quarantine pipeline**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-28T11:57:24Z
- **Completed:** 2026-02-28T12:08:18Z
- **Tasks:** 2
- **Files modified:** 13

## Accomplishments
- AST-based safe expression evaluator supporting comparisons, len(), and/or/not operators -- no eval(), no exec()
- SkillValidator validates procedure_json with 12 rule categories: schema version, step types, variable references, cycle detection, prompt size, expression safety
- SkillExecutor runs tool/llm/condition step pipelines with tool registry lookup, ACL gate, LLM invocation, and AG-UI step_progress event streaming
- SecurityScanner computes 0-100 weighted trust scores across 5 factors with prompt injection pattern detection
- SkillImporter parses AgentSkills SKILL.md format (YAML frontmatter + markdown body)
- Import pipeline: parse -> validate -> security scan -> quarantine (pending_review)
- Admin review endpoints: approve/reject quarantined skills, security report retrieval
- 91 new skill-system tests, full suite 513 passed with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: SkillValidator + Safe Expression Evaluator + SkillExecutor** - `8820480` (feat)
2. **Task 2: Security Scanner + Skill Importer + Admin Endpoints** - `a580d9b` (feat)

## Files Created/Modified
- `backend/skills/__init__.py` - Skills package init
- `backend/skills/safe_eval.py` - AST-based safe expression evaluator with UnsafeExpressionError
- `backend/skills/validator.py` - SkillValidator with 12 validation rule categories and AST safety checking
- `backend/skills/executor.py` - SkillExecutor with tool/llm/condition step handlers, AG-UI events, audit logging
- `backend/skills/security_scanner.py` - SecurityScanner with weighted scoring, INJECTION_PATTERNS list
- `backend/skills/importer.py` - SkillImporter with parse_skill_md() and import_from_url()
- `backend/api/routes/admin_skills.py` - Added /import, /{id}/review, /{id}/security-report; replaced validate stub
- `backend/tests/test_safe_eval.py` - 30 tests for safe eval (comparisons, functions, boolops, unsafe rejection)
- `backend/tests/test_skill_validator.py` - 22 tests for validator (schema, steps, refs, conditions, routing)
- `backend/tests/test_skill_executor.py` - 10 tests for executor (tool, llm, chained, condition, events, failures)
- `backend/tests/test_security_scanner.py` - 19 tests for scanner (scoring, injection, scope, weights)
- `backend/tests/test_skill_importer.py` - 10 tests for importer (parsing, errors, URL fetch)
- `backend/tests/api/test_admin_skills.py` - Updated validate test from stub to real validator

## Decisions Made
- AST-walk validation checks node types only (not values) -- dry-run at validation time cannot have real variable values; runtime evaluator handles actual evaluation
- httpx imported at module top level in importer.py -- lazy imports not patchable in tests (consistent with existing project pattern)
- /import route declared before /{skill_id} routes to prevent FastAPI UUID matching collision
- Validator condition safety check uses ast.walk + whitelist set instead of subclassing _SafeEvaluator -- avoids TypeError from None variable comparisons

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed condition expression validation in SkillValidator**
- **Found during:** Task 1 (SkillValidator tests)
- **Issue:** Initial approach used safe_eval_condition() with dummy variables for validation dry-run. This caused "Unknown variable: x" errors for valid expressions since actual step outputs aren't available at validation time.
- **Fix:** Replaced evaluator-based validation with AST node type whitelist walk -- checks structural safety (no imports, no attribute access, only len() calls) without evaluating values
- **Files modified:** backend/skills/validator.py
- **Verification:** All 22 validator tests pass, including condition expressions with forward references
- **Committed in:** 8820480 (Task 1 commit)

**2. [Rule 1 - Bug] Updated 06-03 validate stub test to match real validator behavior**
- **Found during:** Task 2 (full suite regression check)
- **Issue:** test_validate_skill_stub expected the old stub (always returns valid). With real SkillValidator, the invalid procedure_json (missing schema_version, step id) correctly fails.
- **Fix:** Renamed to test_validate_skill_valid with proper procedure_json, added test_validate_skill_invalid for error case
- **Files modified:** backend/tests/api/test_admin_skills.py
- **Verification:** Full suite 513 passed
- **Committed in:** a580d9b (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required. PyYAML already available in backend venv.

## Next Phase Readiness
- All 5 skill modules in backend/skills/ ready for wiring into master agent graph in 06-06
- SkillExecutor event_emitter callback pattern ready for AG-UI EventEncoder integration
- Admin import/review pipeline fully functional for skill provisioning workflow
- Full test suite green (513 tests) -- safe foundation for 06-06 (skill invocation wiring)

## Self-Check: PASSED

- All 13 files verified present on disk
- Both task commits (8820480, a580d9b) verified in git log
- 513 tests passing, 0 failures

---
*Phase: 06-extensibility-registries*
*Completed: 2026-02-28*
