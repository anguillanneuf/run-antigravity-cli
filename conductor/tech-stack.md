# Technology Stack: Antigravity CLI GitHub Action

This document outlines the core technologies, runtimes, and dependencies selected for the development of the `run-antigravity-cli` GitHub Action.

## 1. Core Architecture & Runtime
- **GitHub Action Format**: **Composite Action** (`composite` runner)
  - *Rationale*: Allows cross-platform execution (Ubuntu, macOS, Windows runners), faster boot times than Docker-based actions, and clean step sharing.
- **Runtime Environment**: **Python 3.11+**
  - *Rationale*: The official Google Antigravity SDK is published as a Python library on PyPI, making Python the native choice for orchestrating the agent programmatically.
- **Package Manager**: **pip** (or `uv` for extremely fast, cached caching within the action runner)

## 2. Core Dependencies & Libraries
- **`google-antigravity`**: The official Python SDK for Google Antigravity. Provides programmatic agent leasing, policy management, and tool routing.
- **`requests` / `urllib3`**: For calling the GitHub REST API securely from our Python wrapper (fetching pull request diffs, getting file content, and posting inline review comments).
- **`PyGithub`** (Optional): A high-level Python library for the GitHub API, ensuring structured and type-safe interaction with PR objects.

## 3. Security & Authentication Stack
- **GitHub OIDC / Workload Identity Federation**: Recommended for secure, keyless access to Google Cloud/Vertex AI resources in enterprise environments (avoiding long-lived GCP service account keys).
- **GitHub Secrets (`GITHUB_TOKEN`)**: Automatically provided by the GitHub Action runner, used to authenticate API requests to read code and post comments back to the repository.
- **`settings.json` Config**: Dynamically generated at runtime under `~/.gemini/antigravity-cli/settings.json` to configure the Antigravity CLI settings securely during execution.
