# Specification: CodeMender CLI PR Scan Workflow Integration (`test-cm.yml`)

## 1. Overview & Context
This track introduces a GitHub Actions CI workflow (`.github/workflows/test-cm.yml`) and supporting tooling to explore, test, and integrate the Google CodeMender CLI (`cm`) into the repository. The workflow authenticates to Google Cloud keylessly using Workload Identity Federation (WIF), installs the CodeMender CLI from Google Artifact Registry with caching, configures headless CI settings (`.codemender/config.yaml`), extracts changed files from Pull Requests (or scans full repository on-demand via `workflow_dispatch`), runs `cm find` to autonomously detect cybersecurity vulnerabilities, and publishes actionable results to both `$GITHUB_STEP_SUMMARY` and as a GitHub PR comment. It also provides pre-flight dry-run handling for gracefully validating installation and authentication in environments where GCP backend resources are still provisioning.

## 2. Functional Requirements
- **FR-1: Workflow Triggering & Security Gating**
  - Trigger on `pull_request` (internal) and `pull_request_target` (forks) for events: `[opened, synchronize, reopened, labeled]`.
  - Enforce DDoS and spam protection gating:
    - Author association check (`OWNER`, `MEMBER`, `COLLABORATOR`) or require `safe-to-test` label for fork/external PRs.
    - Skip draft PRs (`github.event.pull_request.draft == false`).
  - Support manual on-demand triggering via `workflow_dispatch` with inputs:
    - `scan_mode`: `diff` (default, only changed files) or `full` (full workspace scan).
    - `dry_run`: `false` (default) or `true` (validate CLI install & auth only, skip scan failure if GCP provisioning is in progress).
  - Use concurrency controls (`concurrency.group` and `cancel-in-progress: true`) to avoid redundant runs.

- **FR-2: Cloud Authentication via Workload Identity Federation (WIF)**
  - Use `google-github-actions/auth@v3` to authenticate keylessly via OIDC using repository variables/secrets:
    - `GCP_PROJECT_ID`
    - `GCP_WORKLOAD_IDENTITY_PROVIDER`
    - `GCP_SERVICE_ACCOUNT_EMAIL`
  - Ensure runner `permissions` include:
    - `contents: read` (for code checkout)
    - `pull-requests: write` (for posting scan summary comments)
    - `id-token: write` (for requesting OIDC tokens)

- **FR-3: CodeMender CLI Installation & Workspace Initialization**
  - Download Linux x86_64 binary (`cm-linux-amd64.zip`) from Google Artifact Registry production endpoint (`cmoc-prod / codemender-cli-production`).
  - Cache binary across workflow runs via `actions/cache` using version/endpoint hash.
  - Install binary to `/usr/local/bin/cm` and ensure executable permissions.
  - Run `cm init --verify` to establish workspace state and check backend connectivity.
  - Include graceful handling during dry-run / provisioning states (e.g. `Resource setup has just started`).

- **FR-4: Headless CI Configuration (`.codemender/config.yaml`)**
  - Configure CodeMender parameters specifically for automated non-interactive CI:
    - `tools.confirm_commands: false` (disables interactive terminal prompts)
    - `tools.confirm_writes: false` (disables interactive confirmation)
    - `output.format: table` (with capability for json parsing)
    - `sandbox.enabled: false` (or `sandbox.network.profile: permissive-open` since GitHub runner is already an isolated VM)
    - `scan.extensions.include`: `[".py", ".java", ".go", ".js", ".ts", ".c", ".cc", ".cpp", ".h", ".rb", ".php"]`
    - `scan.exclude_dirs`: `["node_modules", "vendor", "dist", "bin"]`
    - `model: "gemini-3.5-flash"`

- **FR-5: Diff Resolution & `cm find` Execution**
  - In `diff` mode: calculate modified files using `git diff` against base branch, filter by supported extensions, and pass paths to `cm find`.
  - In `full` mode: execute `cm find` on the workspace root.
  - Capture stdout/stderr and exit codes.

- **FR-6: Findings Reporting (Step Summary & PR Comment)**
  - Format scan output into GitHub Flavored Markdown and append to `$GITHUB_STEP_SUMMARY`.
  - On PR events, post or update a dedicated PR comment containing the CodeMender scan report with collapsible details when findings are detected.

## 3. Non-Functional Requirements
- **Security**: Keyless OIDC auth; untrusted fork protection via label gating.
- **Performance**: CLI caching to ensure fast bootstrap (< 5s on cache hit).
- **Resilience**: Clear error reporting and dry-run tolerance when GCP backend resources are initializing.

## 4. Acceptance Criteria
- [ ] `.github/workflows/test-cm.yml` exists, is valid YAML, and passes GitHub Action syntax checks.
- [ ] Workflow checks out repository, authenticates via WIF, installs and caches `cm`, and sets up `.codemender/config.yaml`.
- [ ] `diff` mode accurately identifies changed files and executes `cm find` on them; `full` mode scans the workspace.
- [ ] Scan output is formatted and appended to GitHub Step Summary.
- [ ] Pull request comments are created/updated with scan findings for PR events.
- [ ] `workflow_dispatch` supports manual triggering with `scan_mode` and `dry_run` inputs.

## 5. Out of Scope
- Automated code auto-fixing (`cm fix` / auto-committing patches) directly in CI without human review.
- Non-Linux OS runners (workflow is optimized for `ubuntu-latest`).
