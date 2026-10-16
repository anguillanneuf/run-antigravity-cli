# Product Definition: Antigravity CLI GitHub Action

## Vision & Overview
The **Antigravity CLI GitHub Action** (`run-antigravity-cli`) is a custom GitHub Action designed to integrate the Google Antigravity CLI (`agy`) directly into GitHub CI/CD workflows. It acts as a powerful, next-generation code review companion that accelerates peer review by providing instant, AI-driven, inline feedback directly on changed lines of code in pull requests (PRs). Additionally, it functions as an automated security and vulnerability pre-screening guardrail—finding exposed secrets or severe security flaws before human review begins.

## Core Features
1. **Context-Aware Diff PR Reviews**: Extracts changed files and line ranges from Pull Request diffs while expanding surrounding file context (full file under 1,000 lines or 100-line padded windows) to cure diff myopia while commenting strictly on altered lines.
2. **Security & Vulnerability Pre-screening**: Automatically screens incoming pull request diffs for exposed credentials (API keys, secrets) or high-severity security anti-patterns, notifying developers immediately.
3. **Two-Pass Critic-Verifier Pipeline & Thresholding**: Eliminates false positives and pedantic nitpicks using configurable severity (`min-severity`) and confidence (`min-confidence`) thresholds paired with a Pass 2 devil's advocate Critic-Verifier agent (`enable-verifier`).
4. **Shift-Left Local Review CLI**: Provides `scripts/local_review.py` and an optional Git `pre-push` hook (`--install-hook`) so developers can run the exact same review engine locally on staged, branch, or working-tree changes before pushing.
5. **Flexible Authentication Options**: Supports standard GitHub secrets/API key integrations as well as Google Cloud Workload Identity Federation (OIDC) / Application Default Credentials (ADC) for enterprise-grade authentication.
6. **Customizable Review Prompts**: Allows repository maintainers to pass custom instructions or system prompts to guide the AI, enabling tailored review behaviors based on project-specific rules.
7. **DDoS & Resource Exhaustion Guardrails**: Built-in workflow gating (author association checks, `safe-to-test` label requirement for external PRs, draft skipping), concurrency controls, and diff line/file size caps to protect maintainers against spam PRs and API quota depletion.

## Target Scenarios
- **PR Gating and Acceleration**: Providing immediate feedback to contributors upon opening a Pull Request, allowing them to fix obvious issues before a human reviewer looks at the code.
- **Vulnerability Guardrails**: Blocking commits or highlighting PRs that accidentally introduce credentials or obvious vulnerabilities.

## Success Criteria (MVP)
- A complete, publishable GitHub Action structure with full documentation (`README.md`, `action.yml`).
- A fully functional test workflow demonstrating successful local or remote execution of the action.
