# Google Antigravity Code Review Action 🤖✨

An enterprise-grade, TDD-designed custom GitHub Action that leverages the **Google Antigravity SDK** and Gemini Models to perform high-quality, precise, and secure automated code reviews directly on your Pull Requests.

---

## 🌟 Key Features

* **AI-Powered Code Reviews**: Analyzes Pull Request diffs for security concerns, logic bugs, performance bottlenecks, and style inconsistencies.
* **Precise Inline Comments**: Automatically leaves feedback as inline review comments targeting the exact lines modified in the PR.
* **Seamless Local Simulation**: Includes a developer simulation script (`tests/simulate_run.py`) to run and dry-run reviews locally.
* **Interactive Trigger Command**: Supports triggering reviews on demand by leaving a `/review` comment on Pull Request issues.
* **Enterprise Security First**: Native support for **Google Cloud Workload Identity Federation (OIDC)**, eliminating the need to manage long-lived API keys or secrets.
* **Smart Config Merging**: Automatically and safely merges runtime credentials with custom user settings at `~/.gemini/antigravity-cli/settings.json` without destroying existing custom developer configurations.

---

## 📥 Action Inputs

| Input Parameter | Description | Required | Default |
| :--- | :--- | :--- | :--- |
| `github-token` | The GitHub Token used to fetch unified diffs and post review comments back to the PR. | **Yes** | `${{ github.token }}` |
| `api-key` | Google Cloud / Gemini API key. *(Optional if using Workload Identity Federation)*. | No | `""` |
| `workload-identity-provider` | Full GCP Workload Identity Provider resource name for keyless authentication. | No | `""` |
| `service-account` | GCP Service Account email to impersonate when using Workload Identity Federation. | No | `""` |
| `custom-prompt` | Additional developer guidelines or review prompts to direct the review agent. | No | `""` |
| `fail-on-error` | Whether to fail the workflow run if the orchestration engine throws an error. | No | `false` |
| `max-diff-lines` | Maximum modified lines allowed in a PR diff before skipping review to avoid resource exhaustion. | No | `'2000'` |
| `max-diff-files` | Maximum modified files allowed in a PR diff before skipping review to avoid resource exhaustion. | No | `'50'` |

---

## 🛡️ Resource Exhaustion & DDoS Protection

To protect public repositories from spam PRs, API quota depletion, and runner exhaustion:

1. **Author Association Gating**: Workflows automatically run AI reviews for trusted authors (`OWNER`, `MEMBER`, `COLLABORATOR`).
2. **`safe-to-test` Label for External Contributors**: For external fork PRs, reviews are held until a maintainer applies the `safe-to-test` label to the PR or issues a `/review` comment.
3. **Draft PR Skipping**: Draft pull requests are automatically skipped.
4. **Concurrency Controls**: Subsequent commits on the same PR immediately terminate outdated, in-flight review runs (`cancel-in-progress: true`).
5. **Diff & File Caps**: Use `max-diff-lines` (default 2000) and `max-diff-files` (default 50) to prevent gigantic generated PRs from draining LLM tokens.

---

## 🚀 Quick Start (API Key Authentication)

To get started quickly using a standard Gemini API key:

1. Generate an API Key from the Google AI Studio.
2. Store the API Key in your repository's secrets as `GEMINI_API_KEY`.
3. Create a workflow file in your repository at `.github/workflows/antigravity.yml`:

```yaml
name: 'Google Antigravity Code Review'

on:
  pull_request:
    types: [opened, synchronize, reopened]
  issue_comment:
    types: [created]

permissions:
  pull-requests: write # Required to post review comments

jobs:
  review:
    # Run only on pull request updates, or on comments containing '/review'
    if: |
      github.event_name == 'pull_request' ||
      (github.event_name == 'issue_comment' &&
       github.event.issue.pull_request &&
       contains(github.event.comment.body, '/review'))
    runs-on: ubuntu-latest
    steps:
      - name: Run Antigravity Review Agent
        uses: anguillanneuf/run-antigravity-cli@master
        with:
          api-key: ${{ secrets.GEMINI_API_KEY }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
          fail-on-error: true
```

---

## 🔗 Usage in External Repositories

Because this is a standard custom GitHub Action, any project on GitHub can reference and utilize this review agent directly without duplicating any of its code!

To run this code review agent on an external repository:

1. **Configure Repository Secrets**: Add `GEMINI_API_KEY` (or configure Google Cloud OIDC trust) in your external project's settings.
2. **Create Workflow File**: Create `.github/workflows/code-review.yml` in your external repository.
3. **Reference This Action**: Specify the repository path of this action (`uses: <owner>/<repo>@<ref>`) under the job step:

```yaml
      - name: Run Antigravity Review Agent
        uses: anguillanneuf/run-antigravity-cli@master
        with:
          api-key: ${{ secrets.GEMINI_API_KEY }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
          fail-on-error: true
          custom-prompt: |
            Please analyze the following pull request with extreme care. Focus on:
            1. Security vulnerabilities (OWASP Top 10, credential leaks, unsafe imports).
            2. Code quality, optimization, and potential bugs.
            3. ..
```

That's it! When a Pull Request is opened in the external repository, GitHub will automatically download this action, load its composite steps, install dependencies, and run the review under the external repository's context. An `actions/checkout` step is not needed because the review agent retrieves the PR diff directly via the GitHub REST API.

---

## 🔒 Secure Enterprise Setup (Workload Identity Federation)

For enterprise security compliance, we highly recommend using **Google Cloud Workload Identity Federation (OIDC)** instead of long-lived API keys. This enables passwordless authentication using GitHub's short-lived OIDC tokens.

### Step 1: Configure GCP Workload Identity Pool
1. Create a Workload Identity Pool and Provider in Google Cloud IAM:

```bash
GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)   
GOOGLE_CLOUD_PROJECT_NUMBER=$(gcloud projects describe $GOOGLE_CLOUD_PROJECT --format="value(projectNumber)")
REPO_OWNER="YOUR_GITHUB_ORG"
REPO_NAME="YOUR_REPO_NAME"

gcloud iam workload-identity-pools create "github-pool" \
  --project=$GOOGLE_CLOUD_PROJECT \
  --location="global" \
  --display-name="GitHub Pool"

gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project=$GOOGLE_CLOUD_PROJECT \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='$REPO_OWNER/$REPO_NAME'" \
  --issuer-uri="https://token.actions.githubusercontent.com"
```

2. Grant access to [Agent Platform](https://docs.cloud.google.com/iam/docs/roles-permissions/aiplatform#aiplatform.user) resources on the federated identity:
```bash
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --role="roles/aiplatform.user" \
  --member="principalSet://iam.googleapis.com/projects/$GOOGLE_CLOUD_PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/$REPO_OWNER/$REPO_NAME"
```

### Step 2: Configure your GitHub Actions Workflow
Ensure your workflow specifies `permissions: id-token: write` and configures the GCP auth step:

```yaml
name: 'Enterprise Antigravity Code Review'

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  pull-requests: write
  id-token: write # Required for requesting the JWT OIDC token

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - name: Authenticate to Google Cloud (OIDC)
        uses: google-github-actions/auth@v3
        with:
          project_id: ${{ vars.GCP_PROJECT_ID }} # Store your project ID in this Actions variable
          workload_identity_provider: ${{ vars.GCP_WORKLOAD_IDENTITY_PROVIDER }} # Store 'projects/YOUR_PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider' in this Action variable

      - name: Run Antigravity Review Agent
        uses: anguillanneuf/run-antigravity-cli@master
        with:
          gcp-project-id: ${{ vars.GCP_PROJECT_ID }}
          gcp-location: ${{ vars.GCP_LOCATION || 'global' }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
          model: ${{ vars.GEMINI_MODEL || 'gemini-3.8-flash' }}
          fail-on-error: true
          custom-prompt: |
            Please analyze the following pull request with extreme care. Focus on:
            1. Security vulnerabilities (OWASP Top 10, credential leaks, unsafe imports).
            2. Code quality, optimization, and potential bugs.
            3. ..
```

---

## 🛡️ CodeMender CLI Security Scan Workflow (`test-cm.yml`)

This repository also includes automated cybersecurity vulnerability scanning powered by the **Google CodeMender CLI (`cm`)** in `.github/workflows/test-cm.yml`.

### How It Works
1. **Keyless Authentication & ADC Generation**: Uses Google Cloud Workload Identity Federation (WIF) with `google-github-actions/auth@v3` (`create_credentials_file: true`, `export_environment_variables: true`) to generate Application Default Credentials (ADC) and export `GOOGLE_CLOUD_PROJECT` for CodeMender.
2. **Autonomous Tool Setup & Caching**: Downloads and caches the CodeMender Linux CLI binary directly from Google Artifact Registry.
3. **Headless CI Configuration**: Automatically generates non-interactive `~/.codemender/config.yaml` with safety confirmations bypassed and sandbox disabled for CI/container runners.
4. **Target File Resolution**: Dynamically calculates modified files from the Pull Request diff and resolves absolute paths for supported programming language extensions.
5. **Vulnerability Discovery**: Executes `cm find` on the changed files with absolute paths (or full workspace root).
6. **Actionable Reporting**: Publishes structured findings to `$GITHUB_STEP_SUMMARY` and posts/updates an interactive PR comment.

### 🛡️ Sandboxing & CI Runner Configuration
If you are running CodeMender inside an ephemeral Docker container or CI runner (which is already isolated), configure `project_paths: ["."]` and disable namespace sandboxing in `~/.codemender/config.yaml`:

```yaml
project_paths: ["."]
sandbox:
  enabled: false
```

Setting `project_paths: ["."]` declares the repository workspace as an allowed filesystem root, allowing CodeMender's agent to inspect parent directories, imported modules, and related project context during scans without triggering sandbox violation warnings. Always pass absolute paths (e.g. `cm find $(pwd)/src`) when invoking the CLI.

### GCP IAM Permissions & Repository Variables
Grant the Workload Identity Federation Service Account the following IAM role:
* **Vertex AI User**: `roles/aiplatform.user`

Configure the following GitHub repository variables in **Settings > Secrets and variables > Actions > Variables**:
* `GCP_PROJECT_ID`: Your Google Cloud Project ID.
* `GCP_WORKLOAD_IDENTITY_PROVIDER`: Full resource path of the Workload Identity Provider.
* `GCP_SERVICE_ACCOUNT_EMAIL`: Email of the impersonated Service Account.
* `GCP_LOCATION`: Google Cloud region for CodeMender / Vertex AI backend (e.g. `us-central1`).

### Manual Triggering (`workflow_dispatch`)
You can trigger a scan manually with custom inputs from GitHub Actions:
* `scan_mode`: `diff` (only modified files in PR/branch) or `full` (full workspace scan).
* `dry_run`: `true` (validates installation and auth without failing if GCP resources are initializing).
* `model`: CodeMender model tier (defaults to `gemini-3.5-flash`).


---

## 💻 Local Simulation and Testing

Developers can test and dry-run the entire review pipeline locally against any public or private pull request without committing to GitHub or triggering live builds.

### Requirements
Ensure you are in the python virtual environment with dependencies installed:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run Simulation
Provide the PR number, repository, and your active credentials:
```bash
python tests/simulate_run.py \
  --pr 42 \
  --repo "google/run-antigravity-cli" \
  --github-token "YOUR_GITHUB_PERSONAL_ACCESS_TOKEN" \
  --gemini-key "YOUR_GEMINI_API_KEY"
```

To see all available CLI simulation configurations:
```bash
python tests/simulate_run.py --help
```

---

## 🧪 Development and Verification

We follow a strict TDD methodology with high test coverage and strict lint rules:

```bash
# Run the complete test suite with coverage
pytest --cov=src --cov-report=term-missing

# Run code style formatter
black src/ tests/

# Run the strict code-quality linter
pylint src/
```

---

## 📄 License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
