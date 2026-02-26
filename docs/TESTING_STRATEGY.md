# Testing Strategy (QA + Unit + Regression)

## Current issues found (important)
1. Test suite was out of sync with current API contracts.
   - Old tests expected `sources`; API now returns `citations`.
   - Service signatures changed (`project_id` required) but tests used old call patterns.
2. Test environment is not currently runnable here because `pytest` is not installed.
3. No regression gate yet for retrieval-quality changes (hybrid/rerank/query routing).
4. No automated release blocker based on eval thresholds yet.

## What was fixed now
- Updated integration tests to match current API schema and service signatures.
- Mocked expensive dependencies in endpoint tests (Ollama-heavy paths) to keep tests deterministic.

## Recommended test pyramid (lean and practical)

### 1) Unit tests (fast, every commit)
Scope:
- config parsing/validation
- filename sanitization
- eval profile save/load
- dataset save/load
- query router mode selection
- rerank scoring helpers

Target runtime: < 30s

### 2) Integration tests (on branch push)
Scope:
- `/api/projects` CRUD
- upload/query/eval flows
- dataset bootstrap + eval profile threshold checks
- audit/request-id behavior

Use mocks for LLM call where possible.

### 3) Regression tests (before merge to `OpenClawTesting` / main)
Scope:
- run eval on saved dataset(s) per chatbot profile
- compare against baseline pass_rate/avg_confidence
- fail pipeline if below thresholds

## Minimum CI gates to add
1. `python -m compileall app`
2. `python -m pytest -q`
3. `ruff check .`
4. Regression eval gate (profile-based)

## Suggested regression policy
Per chatbot profile:
- pass_rate must not drop by >5% from baseline
- avg_confidence must not drop by >0.05
- if `require_citations=true`, citation coverage should remain >=95%
- if `strict_abstain=true`, abstain violations should be zero

## Practical next steps (doable this week)
1. Install test deps:
   - `pip install -e ".[dev]"`
2. Add a `tests/regression/` folder with fixed datasets.
3. ✅ Added `scripts/run_regression.py` to run profile/dataset regression checks.
4. ✅ Added GitHub Action `.github/workflows/ci.yml` to run compile/lint/tests + regression gate on PR.

## Regression runner usage
- Free CI mode (default):
  - `python scripts/run_regression.py --mode mock`
- Live quality gate mode (local/staging with Ollama running):
  - `python scripts/run_regression.py --mode live`

## Definition of good QA for this project
- Feature changes always include test updates
- New chatbot profile gets its own dataset + threshold policy
- No merge without green unit/integration + stable regression metrics
