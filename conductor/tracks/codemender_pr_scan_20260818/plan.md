# Implementation Plan: CodeMender CLI PR Scan Workflow Integration (`test-cm.yml`)

This plan guides the creation of the `.github/workflows/test-cm.yml` workflow and supporting configuration helpers to run `cm find` on PR changes with Workload Identity Federation authentication.

## Phase 1: CI Environment Scaffolding & Configuration Templates

- [x] Task: Create CodeMender CI configuration template and generator helper [2786df1]
    - [x] Define headless configuration template (`.codemender/config.yaml`) with `tools.confirm_commands: false`, `tools.confirm_writes: false`, `sandbox.enabled: false`, supported scan extensions, and `model: "gemini-3.5-flash"`.
    - [x] Create Python helper or script (`scripts/setup_cm_config.py` or inline action step) to initialize `.codemender/config.yaml` safely.
    - [x] Write unit tests to verify config generation and validity.
- [x] Task: Create PR diff file extraction and extension filtering logic [91ef6dd]
    - [x] Write script/helper (`scripts/resolve_pr_files.py`) to parse PR diff / git diff against base ref and filter supported extensions.
    - [x] Write unit tests for diff resolution, extension filtering, and fallback when no matching files are changed.
- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)

## Phase 2: Workflow Definition (`.github/workflows/test-cm.yml`) & Reporting Integration

- [ ] Task: Build complete GitHub Action workflow `.github/workflows/test-cm.yml`
    - [ ] Configure triggers (`pull_request`, `pull_request_target`, `workflow_dispatch` with `scan_mode` and `dry_run` inputs) and author/label gating.
    - [ ] Add Workload Identity Federation (WIF) authentication step using `google-github-actions/auth@v3`.
    - [ ] Add CodeMender CLI download, caching via `actions/cache`, and binary setup at `/usr/local/bin/cm`.
    - [ ] Add workspace initialization (`cm init`) and `cm find` execution step with diff/full mode switching and dry-run handling.
    - [ ] Add step to format findings into `$GITHUB_STEP_SUMMARY` and post a GitHub PR comment on pull request events.
- [ ] Task: Workflow syntax validation and simulation tests
    - [ ] Write validation test to check YAML syntax and action structure against GitHub Actions schema.
    - [ ] Execute automated tests and ensure zero errors.
- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)

## Phase 3: Documentation & Verification Guide

- [ ] Task: Document CodeMender workflow setup and WIF configuration
    - [ ] Update `README.md` with instructions on required GCP IAM roles (`roles/aiplatform.user`), GitHub repository variables (`GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT_EMAIL`), and manual verification steps.
- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)
