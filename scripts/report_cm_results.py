#!/usr/bin/env python3
"""Format and publish CodeMender security scan reports to GitHub Step Summary and PR Comments."""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from typing import List, Optional

COMMENT_IDENTIFIER = "<!-- codemender-scan-report -->"


def format_step_summary(
    scan_output: str,
    exit_code: int,
    scanned_files: List[str],
    scan_mode: str = "diff",
    dry_run: bool = False,
) -> str:
    """Format CodeMender scan results as GitHub Flavored Markdown."""
    if dry_run:
        status_text = "⚠️ **Status:** Dry-Run / Pre-Flight Mode"
    elif exit_code == 0 and "vulnerability" not in scan_output.lower():
        status_text = "✅ **Status:** Passed (0 findings)"
    else:
        status_text = "⚠️ **Status:** Vulnerabilities / Issues Detected"

    file_list_md = "\n".join([f"- `{f}`" for f in scanned_files]) if scanned_files else "_No applicable code files scanned._"

    lines = [
        "### 🛡️ CodeMender Security Scan Report",
        "",
        status_text,
        "",
        f"- **Scan Mode:** `{scan_mode}`",
        f"- **Scanned Files Count:** {len(scanned_files)}",
        "",
        "<details>",
        "<summary><b>Target Files Scanned</b></summary>",
        "",
        file_list_md,
        "",
        "</details>",
        "",
        "#### CodeMender CLI Output",
        "```text",
        scan_output.strip() if scan_output else "(No output recorded)",
        "```",
        "",
    ]
    return "\n".join(lines)


def format_pr_comment(
    scan_output: str,
    exit_code: int,
    scanned_files: List[str],
    scan_mode: str = "diff",
    dry_run: bool = False,
) -> str:
    """Format PR comment body with an identifier for easy update."""
    summary_md = format_step_summary(
        scan_output=scan_output,
        exit_code=exit_code,
        scanned_files=scanned_files,
        scan_mode=scan_mode,
        dry_run=dry_run,
    )
    return f"{COMMENT_IDENTIFIER}\n\n{summary_md}"


def post_or_update_pr_comment(
    repo: str,
    pr_number: int,
    token: str,
    body: str,
) -> bool:
    """Post a new PR comment or update an existing one created by this workflow."""
    if not repo or not pr_number or not token:
        return False

    api_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "codemender-github-action",
    }

    try:
        # Check existing comments to update instead of spamming
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            comments = json.loads(resp.read().decode("utf-8"))

        existing_comment_id: Optional[int] = None
        for comment in comments:
            if COMMENT_IDENTIFIER in comment.get("body", ""):
                existing_comment_id = comment.get("id")
                break

        payload = json.dumps({"body": body}).encode("utf-8")

        if existing_comment_id:
            update_url = f"https://api.github.com/repos/{repo}/issues/comments/{existing_comment_id}"
            update_req = urllib.request.Request(
                update_url, data=payload, headers={**headers, "Content-Type": "application/json"}
            )
            update_req.get_method = lambda: "PATCH"  # type: ignore
            with urllib.request.urlopen(update_req) as resp:
                return resp.status in (200, 201)
        else:
            post_req = urllib.request.Request(
                api_url, data=payload, headers={**headers, "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(post_req) as resp:
                return resp.status in (200, 201)
    except Exception as e:
        print(f"Warning: Failed to post/update PR comment: {e}", file=sys.stderr)
        return False


def publish_scan_report(
    scan_output: str,
    exit_code: int,
    scanned_files: List[str],
    scan_mode: str = "diff",
    dry_run: bool = False,
    repo: Optional[str] = None,
    pr_number: Optional[int] = None,
    token: Optional[str] = None,
) -> None:
    """Publish report to $GITHUB_STEP_SUMMARY and optionally to PR comments."""
    summary_content = format_step_summary(
        scan_output=scan_output,
        exit_code=exit_code,
        scanned_files=scanned_files,
        scan_mode=scan_mode,
        dry_run=dry_run,
    )

    # 1. Append to GITHUB_STEP_SUMMARY
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(summary_content + "\n")

    # 2. Post PR Comment if PR context is available
    if repo and pr_number and token:
        comment_body = format_pr_comment(
            scan_output=scan_output,
            exit_code=exit_code,
            scanned_files=scanned_files,
            scan_mode=scan_mode,
            dry_run=dry_run,
        )
        post_or_update_pr_comment(
            repo=repo,
            pr_number=pr_number,
            token=token,
            body=comment_body,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish CodeMender scan report.")
    parser.add_argument("--output-file", default="", help="Path to raw scan output log file")
    parser.add_argument("--exit-code", type=int, default=0, help="Exit code from cm find")
    parser.add_argument("--files", nargs="*", default=[], help="Scanned files list")
    parser.add_argument("--scan-mode", default="diff", choices=["diff", "full"], help="Scan mode")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Dry run flag")
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY", ""), help="owner/repo")
    parser.add_argument("--pr-number", type=int, default=None, help="PR issue number")
    parser.add_argument("--token", default=os.getenv("GITHUB_TOKEN", ""), help="GitHub Token")

    args = parser.parse_args()

    raw_output = ""
    if args.output_file and os.path.exists(args.output_file):
        with open(args.output_file, "r", encoding="utf-8", errors="replace") as f:
            raw_output = f.read()

    publish_scan_report(
        scan_output=raw_output,
        exit_code=args.exit_code,
        scanned_files=args.files,
        scan_mode=args.scan_mode,
        dry_run=args.dry_run,
        repo=args.repo if args.repo else None,
        pr_number=args.pr_number,
        token=args.token if args.token else None,
    )


if __name__ == "__main__":
    main()
