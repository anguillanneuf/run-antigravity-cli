# Implementation Plan: Review Engine Precision & Shift-Left Tooling (`plan.md`)

## Phase 1: Severity & Confidence Thresholding (FR-1) [checkpoint: bccb0ef]
- [x] Task: Write failing unit tests for candidate schema parsing and threshold filtering (TDD Red) [afe4215]
  - [x] Write unit tests for schema parsing with `severity` and `confidence` fields
  - [x] Write unit tests for `min_severity` and `min_confidence` filtering logic in `AntigravityReviewEngine`
  - [x] Verify test suite fails as expected
- [x] Task: Implement schema update and threshold filtering in review engine (TDD Green) [bccb0ef]
  - [x] Update `DEFAULT_SYSTEM_INSTRUCTIONS` with explicit severity and confidence format
  - [x] Implement `_filter_threshold_comments()` in `src/review_engine.py`
  - [x] Update `src/entrypoint.py` to read `INPUT_MIN_SEVERITY` and `INPUT_MIN_CONFIDENCE`
  - [x] Verify all Phase 1 tests pass with >80% coverage
- [x] Task: Phase Verification & Checkpoint (Refer to workflow.md) [bccb0ef]

## Phase 2: Context-Aware File Expansion (FR-3)
- [x] Task: Write failing unit tests for file context resolution (TDD Red) [d86e8b9]
  - [x] Write unit tests for loading whole files (<1,000 lines) from repository/workspace
  - [x] Write unit tests for windowed context slicing (>=1,000 lines, 100-line padding around diff hunks)
  - [x] Write unit tests for missing file fallback to diff-only context
  - [x] Verify test suite fails as expected
- [x] Task: Implement Context Resolver module (TDD Green) [34da59e]
  - [x] Create `src/context_resolver.py` with `resolve_file_context()`
  - [x] Integrate context resolution into `src/entrypoint.py`
  - [x] Verify all Phase 2 tests pass with >80% coverage
- [~] Task: Phase Verification & Checkpoint (Refer to workflow.md)

## Phase 3: Two-Pass Critic-Verifier Pipeline (FR-2)
- [ ] Task: Write failing unit tests for Critic-Verifier workflow (TDD Red)
  - [ ] Write unit tests for Pass 1 (Candidate Generation) and Pass 2 (Verification Pass)
  - [ ] Write unit tests verifying that false alarms and unexploitable findings are pruned
  - [ ] Write unit tests verifying zero candidates skips Pass 2 (token optimization)
  - [ ] Write unit tests for verifier failure fallback to filtered candidate list
  - [ ] Verify test suite fails as expected
- [ ] Task: Implement Two-Pass Critic-Verifier in Review Engine (TDD Green)
  - [ ] Define `VERIFIER_SYSTEM_INSTRUCTIONS` prompt with devil's advocate scrutiny
  - [ ] Implement `_run_verifier_pass()` in `src/review_engine.py`
  - [ ] Wire two-pass execution into `run_review()` controlled by `enable_verifier`
  - [ ] Verify all Phase 3 tests pass with >80% coverage
- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)

## Phase 4: Shift-Left Local Review CLI & Git Hook (FR-4)
- [ ] Task: Write failing unit tests for Local Review CLI (TDD Red)
  - [ ] Write unit tests for git diff resolution (`--staged`, `--branch`, `--working`, `--file`)
  - [ ] Write unit tests for CLI output rendering, color-coding, and exit codes
  - [ ] Write unit tests for `--install-hook` writing executable `.git/hooks/pre-push`
  - [ ] Verify test suite fails as expected
- [ ] Task: Implement `scripts/local_review.py` CLI (TDD Green)
  - [ ] Create `scripts/local_review.py` with argparse interface
  - [ ] Integrate local Antigravity review engine leasing and local file context
  - [ ] Implement terminal renderer and pre-push hook installer
  - [ ] Verify all Phase 4 tests pass with >80% coverage
- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)

## Phase 5: Action Metadata, Workflows & End-to-End Validation (FR-5)
- [ ] Task: Update Action Manifest and Workflow Configurations
  - [ ] Update `action.yml` with `min-severity`, `min-confidence`, `enable-verifier`
  - [ ] Update `.github/workflows/test.yml` with new inputs
  - [ ] Update `README.md` with architectural details and local CLI instructions
- [ ] Task: Full Regression and Code Coverage Suite
  - [ ] Run full test suite: `pytest --cov=src --cov=scripts --cov-report=term-missing`
  - [ ] Confirm zero regressions and overall code coverage exceeds 80%
- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)
