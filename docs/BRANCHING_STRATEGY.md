# Lightweight Branching Strategy

## Goal
Move fast without breaking shared progress.

## Branches
- `main` -> stable production-ready milestones only
- `OpenClawTesting` -> integration/testing branch (active build stream)
- `feat/*` -> short-lived feature branches (1 feature = 1 branch)

## Naming
- `feat/<feature-name>` (e.g., `feat/eval-profiles`)
- `fix/<issue-name>`
- `chore/<topic>`
- `docs/<topic>`

## Workflow
1. Branch from `OpenClawTesting`
2. Implement one focused change
3. Run quick checks (compile/tests if available)
4. Commit with clear message
5. Push branch
6. Merge into `OpenClawTesting`
7. Delete feature branch after merge

## Merge cadence
- Merge small PRs frequently (daily if possible)
- Avoid long-running branches (>2-3 days)

## Release flow
- When a milestone is stable, merge `OpenClawTesting` -> `main`
- Tag release points (e.g., `v0.2.0`)

## Guardrails
- No direct commits to `main`
- Keep commits small and reversible
- Include docs updates when behavior changes
- Use feature flags/config toggles for risky changes when possible

## Current next branch
- `feat/eval-profiles` for flexible per-chatbot evaluation policies and dataset bootstrapping
