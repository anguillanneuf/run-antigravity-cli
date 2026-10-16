#!/usr/bin/env python3
"""Shift-Left Local Review CLI for running the Antigravity Review Engine locally before pushing."""

import argparse
import asyncio
import os
from pathlib import Path
import stat
import subprocess
import sys

# Ensure repository root is on sys.path
REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.context_resolver import (  # pylint: disable=wrong-import-position
    resolve_contexts_for_diff,
)
from src.github_client import (  # pylint: disable=wrong-import-position
    parse_diff_to_changed_lines,
)
from src.review_engine import (  # pylint: disable=wrong-import-position
    AntigravityReviewEngine,
)

ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_RED = "\033[31m"
ANSI_MAGENTA = "\033[35m"
ANSI_CYAN = "\033[36m"

SEVERITY_COLORS = {
    "CRITICAL": ANSI_MAGENTA + ANSI_BOLD,
    "HIGH": ANSI_RED + ANSI_BOLD,
    "MEDIUM": ANSI_YELLOW + ANSI_BOLD,
    "LOW": ANSI_CYAN,
}


def get_local_diff(
    staged=False,
    branch=None,
    working=False,
    file_path=None,
    cwd=None,
) -> str:
    """Retrieves a unified git diff for the requested local target.

    Args:
        staged: If True, inspect staged changes (`git diff --cached`).
        branch: Base branch name to compare against (`origin/<branch>...HEAD`).
        working: If True, inspect working tree changes against HEAD (`git diff HEAD`).
        file_path: Optional path to restrict the diff to a single file.
        cwd: Optional working directory to run git commands in.

    Returns:
        str: Raw unified diff string.
    """
    path_args = ["--", file_path] if file_path else []

    if branch:
        primary_cmd = [
            "git",
            "diff",
            f"origin/{branch}...HEAD",
            "--unified=3",
            *path_args,
        ]
        try:
            res = subprocess.run(
                primary_cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=cwd,
            )
            return res.stdout
        except subprocess.CalledProcessError:
            fallback_cmd = [
                "git",
                "diff",
                f"{branch}...HEAD",
                "--unified=3",
                *path_args,
            ]
            try:
                res = subprocess.run(
                    fallback_cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd=cwd,
                )
                return res.stdout
            except Exception:  # pylint: disable=broad-exception-caught
                return ""

    if staged:
        cmd = ["git", "diff", "--cached", "--unified=3", *path_args]
    elif working:
        cmd = ["git", "diff", "HEAD", "--unified=3", *path_args]
    else:
        # Default to staged if present, otherwise working tree HEAD
        cmd = ["git", "diff", "--cached", "--unified=3", *path_args]

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        return res.stdout
    except Exception:  # pylint: disable=broad-exception-caught
        return ""


def render_findings(findings, use_color=True) -> str:
    """Formats review findings for terminal display with optional ANSI color badges.

    Args:
        findings: List of review comment dicts.
        use_color: Whether to include ANSI color escape sequences.

    Returns:
        str: Formatted terminal output string.
    """
    if not findings:
        if use_color:
            return f"{ANSI_GREEN}{ANSI_BOLD}✅ No issues found! Local review passed.{ANSI_RESET}"
        return "✅ No issues found! Local review passed."

    lines = []
    header = f"🔍 Found {len(findings)} blocking review finding(s):"
    lines.append(f"{ANSI_BOLD}{header}{ANSI_RESET}" if use_color else header)
    lines.append("-" * 60)

    for idx, item in enumerate(findings, start=1):
        path = item.get("path", "unknown")
        line_num = item.get("line", 1)
        severity = str(item.get("severity", "HIGH")).upper()
        confidence = item.get("confidence", 4)
        category = str(item.get("category", "BUG")).upper()
        body = item.get("body", "").strip()

        badge = f"[{severity} | Confidence: {confidence}/5 | {category}]"
        location = f"{path}:{line_num}"

        if use_color:
            sev_color = SEVERITY_COLORS.get(severity, ANSI_RED)
            lines.append(
                f"{idx}. {sev_color}{badge}{ANSI_RESET} "
                f"{ANSI_CYAN}{ANSI_BOLD}{location}{ANSI_RESET}"
            )
        else:
            lines.append(f"{idx}. {badge} {location}")

        lines.append(f"   {body}")
        lines.append("-" * 60)

    return "\n".join(lines)


def install_pre_push_hook(repo_root=None) -> str:
    """Installs an executable Git pre-push hook that runs local_review.py.

    Args:
        repo_root: Path to repository root (defaults to REPO_ROOT).

    Returns:
        str: Path to the installed pre-push hook file.
    """
    root = Path(repo_root) if repo_root else Path(REPO_ROOT)
    hooks_dir = root / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "pre-push"

    hook_script = (
        "#!/usr/bin/env bash\n"
        "# Auto-generated by Antigravity Shift-Left Local Review CLI\n"
        "set -e\n"
        'REPO_ROOT="$(git rev-parse --show-toplevel)"\n'
        'PYTHON_BIN="python3"\n'
        'if [ -x "$REPO_ROOT/.venv/bin/python" ]; then\n'
        '    PYTHON_BIN="$REPO_ROOT/.venv/bin/python"\n'
        "fi\n"
        'echo "🤖 Running Antigravity local pre-push code review..."\n'
        '"$PYTHON_BIN" "$REPO_ROOT/scripts/local_review.py" --branch main\n'
    )

    hook_path.write_text(hook_script, encoding="utf-8")
    current_mode = os.stat(hook_path).st_mode
    os.chmod(
        hook_path,
        current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
    )
    return str(hook_path)


# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
async def run_local_review(
    staged=False,
    branch=None,
    working=False,
    file_path=None,
    min_severity="HIGH",
    min_confidence=4,
    enable_verifier=True,
    workspace_root=None,
    api_key=None,
    model=None,
    use_color=True,
) -> int:
    """Executes the local review workflow and prints formatted results.

    Returns:
        int: Exit code (0 if no blocking findings, 1 if findings exist).
    """
    root = workspace_root or REPO_ROOT
    diff_text = get_local_diff(
        staged=staged,
        branch=branch,
        working=working,
        file_path=file_path,
        cwd=root,
    )

    if not diff_text or not diff_text.strip():
        print("No local diff changes detected to review.")
        return 0

    changed_lines = parse_diff_to_changed_lines(diff_text)
    if not changed_lines:
        print("No added or modified lines found in diff.")
        return 0

    file_contexts = resolve_contexts_for_diff(
        diff_text=diff_text,
        changed_lines=changed_lines,
        base_dir=root,
    )

    effective_api_key = (
        api_key
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("INPUT_API_KEY")
        or os.environ.get("INPUT_API-KEY")
    )

    engine = AntigravityReviewEngine(
        api_key=effective_api_key,
        model=model,
        min_severity=min_severity,
        min_confidence=min_confidence,
        enable_verifier=enable_verifier,
    )

    findings = await engine.run_review(
        diff_text=diff_text,
        changed_lines=changed_lines,
        file_contexts=file_contexts,
        min_severity=min_severity,
        min_confidence=min_confidence,
        enable_verifier=enable_verifier,
    )

    report = render_findings(findings, use_color=use_color)
    print(report)

    return 1 if findings else 0


def parse_args(argv=None):
    """Parses command-line arguments for the local review CLI."""
    parser = argparse.ArgumentParser(
        description="Shift-Left Local Code Review CLI powered by Google Antigravity."
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Review staged changes (git diff --cached).",
    )
    parser.add_argument(
        "--branch",
        type=str,
        default=None,
        help="Review changes on current branch against <base> (e.g. main).",
    )
    parser.add_argument(
        "--working",
        action="store_true",
        help="Review unstaged working tree changes (git diff HEAD).",
    )
    parser.add_argument(
        "--file",
        dest="file_path",
        type=str,
        default=None,
        help="Restrict review to a specific modified file path.",
    )
    parser.add_argument(
        "--min-severity",
        type=str,
        default=os.environ.get("INPUT_MIN_SEVERITY", "HIGH"),
        choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        help="Minimum severity threshold (default: HIGH).",
    )
    parser.add_argument(
        "--min-confidence",
        type=int,
        default=int(os.environ.get("INPUT_MIN_CONFIDENCE", "4")),
        help="Minimum confidence threshold 1-5 (default: 4).",
    )
    parser.add_argument(
        "--disable-verifier",
        action="store_true",
        help="Disable Pass 2 Critic-Verifier scrutiny.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color codes in terminal output.",
    )
    parser.add_argument(
        "--install-hook",
        action="store_true",
        help="Install Git pre-push hook in .git/hooks/pre-push and exit.",
    )
    parser.add_argument(
        "--repo-root",
        type=str,
        default=None,
        help="Override repository root directory.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    """CLI entry point for scripts/local_review.py."""
    args = parse_args(argv)

    if args.install_hook:
        hook_path = install_pre_push_hook(repo_root=args.repo_root)
        print(f"✅ Installed Git pre-push hook at: {hook_path}")
        sys.exit(0)

    # Default to --staged if no target mode was explicitly specified
    staged = args.staged or (not args.branch and not args.working)

    exit_code = asyncio.run(
        run_local_review(
            staged=staged,
            branch=args.branch,
            working=args.working,
            file_path=args.file_path,
            min_severity=args.min_severity,
            min_confidence=args.min_confidence,
            enable_verifier=not args.disable_verifier,
            workspace_root=args.repo_root,
            use_color=not args.no_color,
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
