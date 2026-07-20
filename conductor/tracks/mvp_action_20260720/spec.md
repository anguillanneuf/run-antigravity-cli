# Specification: Antigravity CLI GitHub Action (MVP)

## 1. Overview
This specification defines the Minimum Viable Product (MVP) for `run-antigravity-cli`, a custom Composite GitHub Action that integrates the Google Antigravity CLI and Python SDK into GitHub CI/CD workflows. The action will automate inline code reviews, security scans, and pull request gating.

---

## 2. Architecture & Directory Layout
We will use a standard structured repository layout:
```
run-antigravity-cli/
├── action.yml               # GitHub Action metadata & composite step definitions
├── requirements.txt         # Package dependencies (google-antigravity, requests, etc.)
├── src/
│   ├── __init__.py
│   ├── entrypoint.py        # Environment & event-parsing entry point
│   ├── review_engine.py     # Antigravity SDK integration & agent leasing
│   └── github_client.py     # GitHub REST API interface (fetching diffs, posting reviews)
├── tests/
│   ├── __init__.py
│   ├── test_entrypoint.py
│   ├── test_review_engine.py
│   └── test_github_client.py
└── .github/
    └── workflows/
        └── test.yml         # Self-testing/verification workflow
```

---

## 3. Functional Requirements

### 3.1 GitHub Event Support
The action must parse and support three trigger contexts:
1. **`pull_request` (opened, synchronize)**:
   - Extract the PR number and target commit SHAs.
   - Retrieve the pull request patch/diff.
   - Focus reviews only on the changed lines of code (Diff-only PR review).
2. **`push` (commit)**:
   - Extract the pushed commits.
   - Review changes on the pushed commits.
3. **`issue_comment` (created)**:
   - Detect if the comment contains `/review`.
   - Trigger a PR re-review and post comments.

### 3.2 Antigravity Agent Orchestration
- Use the official Python SDK (`google-antigravity`) to programmatically lease and initialize the review agent.
- Dynamically generate a `~/.gemini/antigravity-cli/settings.json` config at runtime using the provided API key or service credentials.
- Set custom system instructions (custom review prompt) passed via action inputs.
- Stream the agent's response to handle inline code reviews.

### 3.3 GitHub Posting & Formatting
- **Inline PR Commenting**: Post comments directly on the exact file, line number, and diff side of the changes.
- **GitHub Suggestions**: AI-proposed code modifications must be formatted in a ` ```suggestion ` block.
- **Security Scans**: Highlight potential exposed secrets/credentials or severe anti-patterns with a security icon (🔒).

---

## 4. Non-Functional Requirements
- **Cross-Platform Compatibility**: Must run natively on `ubuntu-latest`, `macos-latest`, and `windows-latest` runners.
- **Secure Credentials Handling**: Support API key injection as well as GCP Service Account credentials (Application Default Credentials).
- **Graceful Error Handling**: If the Antigravity SDK fails, the action should log the error clearly and decide whether to fail or pass based on action inputs (e.g., `fail-on-error`).

---

## 5. Acceptance Criteria
1. **Unit & Mock Tests**: Passes all tests with simulated mock payloads, achieving >80% coverage.
2. **End-to-End Local Test**: A local script successfully parses a mock PR event JSON and generates simulated review outputs.
3. **Live Workflow Run**: A test workflow executes on GitHub and posts at least one inline comment to a test pull request.

---

## 6. Out of Scope (For Future Tracks)
- Caching of agent sessions across separate action runs.
- Adding custom terminal tools for the agent inside the action (keeping the agent read-only for security).
