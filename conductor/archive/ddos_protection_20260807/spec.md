# Specification: DDoS Protection & Resource Exhaustion Guards

## Overview
This track introduces security controls and resource guards to protect the `run-antigravity-cli` GitHub Action and its test workflows (`.github/workflows/test.yml`) against resource exhaustion, API quota depletion, and spam PRs originating from public forks or malicious actors.

## Functional Requirements

### 1. Workflow Gating & Author Checks (`test.yml`)
- **Author Association Check**: Automatically run the AGY review action on PRs from trusted actors (`OWNER`, `MEMBER`, `COLLABORATOR`).
- **External Fork Protection**: For external PRs (`FIRST_TIME_CONTRIBUTOR`, `FIRST_TIMER`, `NONE`, `CONTRIBUTOR`), require maintainer approval via a specific PR label (e.g. `safe-to-test`) or explicit workflow condition before triggering resource-intensive AI reviews.
- **Draft PR Exclusion**: Skip AGY AI reviews automatically for draft PRs to avoid wasting tokens on work-in-progress code.

### 2. Concurrency & Rate Control (`test.yml`)
- **Concurrency Grouping**: Implement GitHub Actions `concurrency` configuration (`group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}`, `cancel-in-progress: true`) so subsequent commits on the same PR immediately terminate outdated, in-flight review runs.
- **Run Timeout Limits**: Enforce strict job `timeout-minutes` on review steps to prevent hung processes from consuming runner minutes.

### 3. Runtime Safeguards (`action.yml` & Python codebase)
- **Diff Size Caps**: Configure maximum line/file diff thresholds in the Python action wrapper to prevent gigantic or generated PRs from consuming excessive LLM token budget.
- **Informative Status Outputs**: Log clear, helpful warning messages when a review is skipped due to trust policies, draft status, or size limits.

## Non-Functional Requirements
- **Maintainer Experience**: Zero friction for repository maintainers and trusted team members.
- **Test Coverage**: Maintain >80% unit test coverage for all new Python security and guard modules.
- **Backward Compatibility**: Existing action inputs and outputs must remain fully compatible.

## Acceptance Criteria
- [ ] PRs from external contributors do NOT invoke LLM API calls unless labeled `safe-to-test` or authorized.
- [ ] Pushing new commits to an open PR automatically cancels prior active workflow runs for that PR.
- [ ] Draft PRs are cleanly skipped with an explicit log output.
- [ ] Diffs exceeding the configured max-lines threshold fail-safe (log warning and skip or cap review).
- [ ] Unit tests cover author association gating, draft checking, and diff threshold logic.

## Out of Scope
- Implementing paid GitHub billing alerts or third-party webhooks.
- Modifying Google Cloud backend quota limits directly.
