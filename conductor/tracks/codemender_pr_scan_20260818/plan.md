# Implementation Plan: CodeMender CLI PR Scan Workflow Integration (`test-cm.yml`)

This plan guides the creation of the `.github/workflows/test-cm.yml` workflow and supporting configuration helpers to run `cm find` on PR changes with Workload Identity Federation authentication.

## Phase 1: CI Environment Scaffolding & Configuration Templates [checkpoint: 91ef6dd]

- [x] Task: Create CodeMender CI configuration template and generator helper [2786df1]
    - [x] Define headless configuration template (`.codemender/config.yaml`) with `tools.confirm_commands: false`, `tools.confirm_writes: false`, `sandbox.enabled: false`, supported scan extensions, and `model: "gemini-3.5-flash"`.
    - [x] Create Python helper or script (`scripts/setup_cm_config.py` or inline action step) to initialize `.codemender/config.yaml` safely.
    - [x] Write unit tests to verify config generation and validity.
- [x] Task: Create PR diff file extraction and extension filtering logic [91ef6dd]
    - [x] Write script/helper (`scripts/resolve_pr_files.py`) to parse PR diff / git diff against base ref and filter supported extensions.
    - [x] Write unit tests for diff resolution, extension filtering, and fallback when no matching files are changed.
- [x] Task: Phase Verification & Checkpoint (Refer to workflow.md) [91ef6dd]

## Phase 2: Workflow Definition (`.github/workflows/test-cm.yml`) & Reporting Integration [checkpoint: c715bd7]

- [x] Task: Build complete GitHub Action workflow `.github/workflows/test-cm.yml` [ecebb20]
    - [x] Configure triggers (`pull_request`, `pull_request_target`, `workflow_dispatch` with `scan_mode` and `dry_run` inputs) and author/label gating.
    - [x] Add Workload Identity Federation (WIF) authentication step using `google-github-actions/auth@v3`.
    - [x] Add CodeMender CLI download, caching via `actions/cache`, and binary setup at `/usr/local/bin/cm`.
    - [x] Add workspace initialization (`cm init`) and `cm find` execution step with diff/full mode switching and dry-run handling.
    - [x] Add step to format findings into `$GITHUB_STEP_SUMMARY` and post a GitHub PR comment on pull request events.
- [x] Task: Workflow syntax validation and simulation tests [3b79ac1]
    - [x] Write validation test to check YAML syntax and action structure against GitHub Actions schema.
    - [x] Execute automated tests and ensure zero errors.
- [x] Task: Phase Verification & Checkpoint (Refer to workflow.md) [c715bd7]

## Phase 3: Documentation & Verification Guide

- [ ] Task: Document CodeMender workflow setup and WIF configuration
    - [ ] Update `README.md` with instructions on required GCP IAM roles (`roles/aiplatform.user`), GitHub repository variables (`GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT_EMAIL`), and manual verification steps.
- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)
