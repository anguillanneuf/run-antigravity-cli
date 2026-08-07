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
  contents: read
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
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Run Antigravity Review Agent
        uses: google/run-antigravity-cli@v1 # Replace with your repo name / tag
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
        uses: google/run-antigravity-cli@v1 # Point to this repo name and tag/branch
        with:
          api-key: ${{ secrets.GEMINI_API_KEY }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
          fail-on-error: true
```

That's it! When a Pull Request is opened in the external repository, GitHub will automatically check out this action, load its composite steps, install dependencies, and run the review under the external repository's context.

---

## 🔒 Secure Enterprise Setup (Workload Identity Federation)

For enterprise security compliance, we highly recommend using **Google Cloud Workload Identity Federation (OIDC)** instead of long-lived API keys. This enables passwordless authentication using GitHub's short-lived OIDC tokens.

### Step 1: Configure GCP Workload Identity Pool
1. Create a Workload Identity Pool and Provider in Google Cloud IAM:
   ```bash
   gcloud iam workload-identity-pools create "github-pool" \
     --project="YOUR_PROJECT_ID" \
     --location="global" \
     --display-name="GitHub Pool"

   gcloud iam workload-identity-pools providers create-oidc "github-provider" \
     --project="YOUR_PROJECT_ID" \
     --location="global" \
     --workload-identity-pool="github-pool" \
     --display-name="GitHub Provider" \
     --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
     --issuer-uri="https://token.actions.githubusercontent.com"
   ```

2. Create a Google Cloud Service Account for Antigravity:
   ```bash
   gcloud iam service-accounts create "antigravity-reviewer" \
     --project="YOUR_PROJECT_ID" \
     --display-name="Antigravity Reviewer Service Account"
   ```

3. Allow GitHub repositories to assume the Service Account:
   ```bash
   gcloud iam service-accounts add-iam-policy-binding "antigravity-reviewer@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --project="YOUR_PROJECT_ID" \
     --role="roles/iam.workloadIdentityUser" \
     --member="principalSet://iam.googleapis.com/projects/YOUR_PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/YOUR_ORGANIZATION/YOUR_REPO"
   ```

4. Grant necessary IAM roles to the Service Account.
   - Agent Platform User
   - Workload Identity User
   - Service Account Token Creator
   - Gemini for Google Cloud User
   - Cloud Trace Agent
   - Logs Writer
   - Monitoring Viewer

### Step 2: Configure your GitHub Actions Workflow
Ensure your workflow specifies `permissions: id-token: write` and configures the GCP auth step:

```yaml
name: 'Enterprise Antigravity Code Review'

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write
  id-token: write # Required for requesting the JWT OIDC token

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Authenticate to Google Cloud (OIDC)
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: 'projects/YOUR_PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider'
          service_account: 'antigravity-reviewer@YOUR_PROJECT_ID.iam.gserviceaccount.com'

      - name: Run Antigravity Review Agent
        uses: ./
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          fail-on-error: true
```

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
This project is licensed under the Apache License 2.0. See the LICENSE file for details.
