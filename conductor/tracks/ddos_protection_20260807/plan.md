# Implementation Plan: DDoS Protection & Resource Exhaustion Guards

## Phase 1: Workflow Gating & Concurrency Controls (`test.yml`)
- [x] Task: Configure concurrency grouping and timeouts in workflow files
  - [x] Add `concurrency` group with `cancel-in-progress: true` to `.github/workflows/test.yml`
  - [x] Add explicit `timeout-minutes` to workflow jobs
- [x] Task: Add author association, draft PR, and label gating in `.github/workflows/test.yml`
  - [x] Add `if` condition to skip draft pull requests
  - [x] Add `if` condition checking `github.event.pull_request.author_association` (`OWNER`, `MEMBER`, `COLLABORATOR`) OR presence of `safe-to-test` label for external fork PRs
- [x] Task: Phase Verification & Checkpoint (Refer to workflow.md)

## Phase 2: Runtime Guards in Python Codebase & Action Interface
- [ ] Task: Write failing unit tests for diff size caps and guard parameters (Red Phase)
  - [ ] Create unit tests in `tests/` for diff line cap detection and skip handling
  - [ ] Run tests and verify they fail as expected
- [ ] Task: Implement diff size capping and runtime guards in Python wrapper (Green Phase)
  - [ ] Implement diff line counting and threshold checks in `src/`
  - [ ] Add structured logging when AGY execution is safely skipped
  - [ ] Run tests and verify they pass
- [ ] Task: Refactor and verify test coverage >80%
  - [ ] Refactor guard logic for maintainability
  - [ ] Run `pytest --cov=src --cov-report=term-missing` and confirm >80% coverage
- [ ] Task: Expose configurable inputs in `action.yml` and update documentation
  - [ ] Add `max_diff_lines` input parameter to `action.yml` with sensible default
  - [ ] Update `README.md` with security best practices and the `safe-to-test` label guide
- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)
