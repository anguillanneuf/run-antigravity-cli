# Specification: Review Engine Precision & Shift-Left Tooling (`spec.md`)

## 1. Overview & Problem Statement
Currently, the Antigravity review action operates with **diff myopia** (seeing only isolated raw unified diffs) and in a **hyper-critical zero-shot auditor mode** without confidence scoring or severity thresholding. This leads to high false-positive rates, superficial/pedantic nitpicks on safe code constructs (e.g., shell expansions, internal variables), and an iterative "whack-a-mole" cycle where addressing one comment produces a new diff that triggers new false alarms.

This track introduces four complementary architectural enhancements:
1. **Severity & Confidence Thresholding:** Structured schema with configurable minimum severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) and confidence score (`1`–`5`), suppressing noise and nitpicks.
2. **Two-Pass Critic-Verifier Pipeline:** Pass 1 detects candidate findings; Pass 2 acts as a devil's advocate verifier with full context, discarding speculative or unexploitable findings.
3. **Context-Aware File Expansion:** Cures diff myopia by providing full file contents (for files < 1,000 lines) or 100-line windowed context, allowing the verifier to inspect surrounding guards and sanitizers.
4. **Shift-Left Local Review CLI:** A standalone developer CLI (`scripts/local_review.py`) that runs the same engine against local staged or branch diffs before pushing, complete with an optional pre-push git hook.

---

## 2. Functional Requirements

### FR-1: Structured Schema & Configurable Thresholding
- **FR-1.1:** Update LLM response schema from `path, line, body` to:
  - `path`: string
  - `line`: integer
  - `severity`: enum (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`)
  - `confidence`: integer (`1` to `5`)
  - `category`: enum (`SECURITY`, `BUG`, `PERFORMANCE`, `CODE_QUALITY`)
  - `body`: string (markdown description with actionable suggestions)
- **FR-1.2:** Add action inputs `min-severity` (default: `HIGH`) and `min-confidence` (default: `4`).
- **FR-1.3:** Filter candidate comments in `review_engine.py` against `min-severity` and `min-confidence`. Comments failing either threshold are dropped.

### FR-2: Two-Pass Critic-Verifier Pipeline
- **FR-2.1:** **Pass 1 (Candidate Detection):** Identifies potential vulnerabilities and bugs from the diff.
- **FR-2.2:** **Pass 2 (Verification / Devil's Advocate):** Receives the candidate findings alongside the surrounding file context. The verifier explicitly checks:
  1. Is this finding a true positive, or a false alarm/pedantic nitpick?
  2. Is this issue actually reachable/exploitable given surrounding code and guard clauses?
  3. Are there preconditions that make this issue impossible in this execution environment?
- **FR-2.3:** Discard any candidate finding that fails verification. Only verified findings are returned.
- **FR-2.4:** Support an action input `enable-verifier` (default: `true`) to allow toggling the verification pass.

### FR-3: Context-Aware File Expansion (Curing Diff Myopia)
- **FR-3.1:** Implement a context resolver in Python that maps changed lines in a diff to the underlying source files.
- **FR-3.2:** For files under 1,000 lines, provide the complete file content to the verifier pass.
- **FR-3.3:** For files with 1,000 lines or more, provide an expanded context window of up to 100 lines before and after each modified hunk.
- **FR-3.4:** For local execution, read files directly from the working tree. For CI execution, read files from the checked-out workspace or via the GitHub API if unavailable locally.

### FR-4: Shift-Left Local Review CLI (`scripts/local_review.py`)
- **FR-4.1:** Provide a standalone CLI executable in `scripts/local_review.py`.
- **FR-4.2:** Support review targets:
  - `--staged`: review `git diff --cached`
  - `--branch <base>`: review `git diff origin/<base>...HEAD`
  - `--working`: review unstaged working tree changes
  - `--file <path>`: review specific modified file
- **FR-4.3:** Format output cleanly in terminal with ANSI colors, severity badges, and file line pointers.
- **FR-4.4:** Provide an exit code: `0` if no blocking findings (above threshold), `1` if critical/high issues found.
- **FR-4.5:** Provide a `--install-hook` flag to install a Git `pre-push` hook that runs local review automatically.

### FR-5: Action & Workflow Metadata Integration
- **FR-5.1:** Update `action.yml` with new inputs: `min-severity`, `min-confidence`, `enable-verifier`.
- **FR-5.2:** Update `.github/workflows/test.yml` to utilize the new inputs.
- **FR-5.3:** Preserve 100% backward compatibility with existing workflows if new parameters are omitted.

---

## 3. Non-Functional Requirements
- **Token Efficiency:** When no candidates are found in Pass 1, Pass 2 is skipped entirely (zero extra LLM calls).
- **Resilience:** If the verifier pass encounters a timeout or formatting error, fail gracefully to the candidates that pass strict severity/confidence thresholding.
- **Code Coverage & Quality:** Adhere to project guidelines in `workflow.md`: write unit tests first (TDD), ensure >80% code coverage across `src/` and `scripts/`.

---

## 4. Acceptance Criteria
- [ ] Review engine suppresses subjective nitpicks and low-confidence warnings below threshold.
- [ ] The critic-verifier pass eliminates false positives on unexploitable shell expansion patterns.
- [ ] Context provider correctly supplies full or padded file context to the verifier without truncation errors.
- [ ] `python scripts/local_review.py --staged` runs against staged git diff and reports findings with exit codes.
- [ ] All unit tests pass with >80% coverage and no regression in existing tests.

---

## 5. Out of Scope
- Multi-repo dependency analysis or cross-repository call-graph scanning.
- Automated code modifications/auto-fixing directly in CI (suggestions remain text-only inline comments).
