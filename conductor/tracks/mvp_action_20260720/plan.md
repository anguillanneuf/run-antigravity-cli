# Implementation Plan: Antigravity CLI GitHub Action (MVP)

## Phase 1: Project Scaffolding & Action Metadata [checkpoint: 0289bd8]
- [x] **Task: Scaffold Directory Structure & Setup Environment** (4729124)
  - [x] Create directories `src/` and `tests/`
  - [x] Create `requirements.txt` with base dependencies (`google-antigravity`, `requests`, `PyGithub`)
  - [x] Configure Python virtual environment files
- [x] **Task: Define Action Metadata (`action.yml`)** (8148795)
  - [x] Declare input parameters (`api-key`, `github-token`, `custom-prompt`, `fail-on-error`)
  - [x] Define composite steps (installing Python, installing packages, invoking entrypoint)
- [x] Task: Phase Verification & Checkpoint (Refer to workflow.md) (0289bd8)

## Phase 2: GitHub API Client & Event Parsing (TDD)
- [x] **Task: Write Tests for GitHub Event Parsing & API Client (Red Phase)** (2f591c3)
  - [x] Create `tests/test_github_client.py`
  - [x] Write unit tests for parsing `pull_request`, `push`, and `issue_comment` payloads
  - [x] Write unit tests for fetching PR patch/diff, parsing files, and mapping changed line ranges
  - [x] Write unit tests for posting inline comments using GitHub Review endpoints
  - [x] Verify that pytest runs and these new tests fail
- [x] **Task: Implement GitHub Event Parsing & API Client (Green Phase)** (c9b260a)
  - [x] Implement `src/github_client.py` to retrieve PR diff patches and map file line ranges
  - [x] Implement event-parsing logic to decode GITHUB_EVENT_PATH payload
  - [x] Implement REST API calls using `requests` to securely post review comments
  - [x] Run pytest to confirm all tests now pass
- [~] **Task: Phase Verification & Checkpoint (Refer to workflow.md)**

## Phase 3: Antigravity SDK Integration & Review Logic (TDD)
- [ ] Task: Write Tests for Antigravity Engine Integration (Red Phase)
  - [ ] Create `tests/test_review_engine.py`
  - [ ] Write unit tests for leasing/initializing an `Agent` using `LocalAgentConfig`
  - [ ] Write unit tests for parsing the agent's output and extracting specific review comments
  - [ ] Verify that pytest runs and these new tests fail
- [ ] Task: Implement Antigravity Review Engine (Green Phase)
  - [ ] Implement `src/review_engine.py` to interface with the `google-antigravity` SDK
  - [ ] Implement auto-generation of settings configuration (`~/.gemini/antigravity-cli/settings.json`) at runtime
  - [ ] Implement review logic to feed PR diff segments to the agent and collect reviews
  - [ ] Implement markdown validation (verifying suggestions use ` ```suggestion ` blocks)
  - [ ] Run pytest to confirm all tests now pass
- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)

## Phase 4: Main Entry Point & Orchestration Integration (TDD)
- [ ] Task: Write Integration and Local E2E Tests (Red Phase)
  - [ ] Add integration tests in `tests/test_entrypoint.py` to mock and link both modules
  - [ ] Verify end-to-end orchestration from event-trigger parsing to posting the comments
  - [ ] Verify tests fail as expected
- [ ] Task: Implement Main Orchestration Loop (Green Phase)
  - [ ] Complete `src/entrypoint.py` coordinating the Github Client and Review Engine
  - [ ] Add local simulation script `tests/simulate_run.py` to let developers test the full flow on mock local PRs
  - [ ] Ensure full test suite passes with >80% test coverage
- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)

## Phase 5: Live Verification & Self-Testing
- [ ] Task: Create Self-Testing GitHub Workflow & Documentation
  - [ ] Create `.github/workflows/test.yml` calling our local custom action
  - [ ] Write detailed `README.md` explaining setup, parameters, and enterprise Workload Identity configuration
- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)
