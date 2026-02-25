---
phase: 02-agent-core-and-conversational-chat
plan: "01"
subsystem: infra
tags: [litellm, langchain, chatOpenAI, llm-routing, tdd, model-aliases]

# Dependency graph
requires:
  - phase: 01-identity-and-infrastructure-skeleton
    provides: core/config.py with get_llm() implementation and Settings with litellm_url/litellm_master_key
provides:
  - LiteLLM config with general_settings.master_key enforcement (os.environ/LITELLM_MASTER_KEY)
  - 3 TDD tests proving get_llm() contract for all 4 blitz/* aliases and unknown alias passthrough
affects:
  - 02-02 (master agent uses get_llm — confirmed routing contract)
  - 02-03 (tool tests may import get_llm for mock setup)
  - all subsequent agent plans that instantiate LLM clients

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "get_llm(alias) is the single entry point for all LLM clients — never import anthropic/openai directly"
    - "LiteLLM env var interpolation uses os.environ/VAR_NAME syntax (not ${VAR} shell syntax)"
    - "ChatOpenAI stores base_url as openai_api_base and model as model_name (langchain-openai attr names)"

key-files:
  created: []
  modified:
    - infra/litellm/config.yaml
    - backend/tests/test_config.py

key-decisions:
  - "ChatOpenAI attribute for base_url is openai_api_base (not base_url) in langchain-openai; model is model_name"
  - "Tests for get_llm() do not need settings override — module-level settings already have litellm_url from .env or conftest"
  - "LiteLLM general_settings.master_key uses os.environ/LITELLM_MASTER_KEY interpolation syntax per LiteLLM docs"
  - "Unknown aliases pass through unchanged (blitz/master -> blitz-master, custom/my-model -> custom/my-model)"

patterns-established:
  - "Test get_llm() by calling it directly and asserting on llm.openai_api_base and llm.model_name"
  - "3 new get_llm tests are additive — never replace or modify existing test_config.py tests"

requirements-completed:
  - AGNT-07

# Metrics
duration: 5min
completed: 2026-02-25
---

# Phase 2 Plan 01: LiteLLM Config and get_llm() TDD Summary

**LiteLLM proxy authentication enforced via general_settings.master_key and ChatOpenAI routing verified — 3 new TDD tests confirm all 4 blitz/* aliases map correctly through port 4000**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-02-24T19:58:42Z
- **Completed:** 2026-02-25T03:31:36Z
- **Tasks:** 1 (TDD task — RED+GREEN+verify)
- **Files modified:** 2

## Accomplishments
- Added `general_settings.master_key: os.environ/LITELLM_MASTER_KEY` to `infra/litellm/config.yaml` — LiteLLM proxy now enforces authentication on all API calls
- Added `test_get_llm_returns_chatopenai_pointing_at_litellm` — verifies `openai_api_base` contains `4000` or `litellm`
- Added `test_get_llm_uses_correct_model_alias` — verifies all 4 aliases map correctly (`blitz/master` -> `blitz-master`, etc.)
- Added `test_get_llm_unknown_alias_passes_through` — verifies unknown aliases pass through unchanged; LiteLLM handles the error
- Full test suite: 61 tests pass, 0 failures (58 existing + 3 new)

## Task Commits

Each task was committed atomically:

1. **Task 1: TDD — verify get_llm() contract and complete LiteLLM config** - `3fb749d` (test)

**Plan metadata:** (docs commit follows)

_Note: TDD tasks may have multiple commits (test -> feat -> refactor). This task went GREEN immediately because Phase 1 already implemented get_llm() correctly — tests confirmed rather than drove implementation._

## Files Created/Modified
- `infra/litellm/config.yaml` - Added `general_settings.master_key: os.environ/LITELLM_MASTER_KEY` to enforce proxy authentication
- `backend/tests/test_config.py` - Appended 3 new TDD tests verifying get_llm() contract for all 4 aliases and unknown passthrough

## Actual Attribute Names on ChatOpenAI Instance

Discovered via `dir(llm)` introspection with test env vars set:

| Purpose | Attribute Name | Example Value |
|---------|---------------|---------------|
| Base URL | `openai_api_base` | `'http://litellm:4000/v1'` |
| Model name | `model_name` | `'blitz-master'` |
| API key | `openai_api_key` | `SecretStr('**********')` |
| Streaming | `streaming` | `True` |

The `base_url` constructor argument maps to `openai_api_base` as the stored attribute. The `model` constructor argument maps to `model_name`. Both existing Phase 1 tests already used these correct names.

## Decisions Made

- **ChatOpenAI attribute names:** `openai_api_base` (not `base_url`) and `model_name` (not `model`) are the stored attribute names in langchain-openai. The constructor uses aliases `base_url`/`model` that map to these internal names.
- **LiteLLM env var syntax:** `os.environ/LITELLM_MASTER_KEY` is the correct LiteLLM interpolation syntax. Shell-style `${LITELLM_MASTER_KEY}` is NOT supported in LiteLLM config.
- **TDD note:** Tests went GREEN immediately (no implementation change needed) because Phase 1 built `get_llm()` completely. This is expected — the TDD here verifies the contract, not drives new implementation.
- **No settings override needed in new tests:** Unlike the existing Phase 1 tests that use `patch.dict` for safety, the 3 new tests call `get_llm()` directly. The module-level `settings` object already has `litellm_url = http://litellm:4000` from the conftest or environment, so assertions work without overrides.

## Deviations from Plan

None - plan executed exactly as written.

The plan anticipated tests might fail in RED phase due to attribute name mismatches. Instead, the 3 tests passed immediately because:
1. Phase 1 implemented `get_llm()` completely with correct `openai_api_base` attribute
2. The `getattr(llm, "openai_api_base", None) or getattr(llm, "base_url", None)` chain in the plan's test template would have worked correctly either way

The final test code uses `llm.openai_api_base` directly (matching existing tests in the file) since the attribute name was confirmed via introspection before writing.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. The `general_settings.master_key` reads from `LITELLM_MASTER_KEY` environment variable which is already in the `.env` template.

## Next Phase Readiness

- **LiteLLM contract proven:** Every call to `get_llm()` returns `ChatOpenAI(openai_api_base='http://litellm:4000/v1', model_name='<alias>')`. The 02-02 master agent can rely on this.
- **All 4 aliases verified:** `blitz/master`, `blitz/fast`, `blitz/coder`, `blitz/summarizer` all route correctly.
- **Unknown alias behavior confirmed:** Pass-through; LiteLLM returns a 404/error, not backend code. Agent error handling in 02-02 can assume `get_llm()` itself never throws for unknown aliases.
- **No blockers** for 02-02 (LangGraph master agent scaffolding).

---
*Phase: 02-agent-core-and-conversational-chat*
*Completed: 2026-02-25*
