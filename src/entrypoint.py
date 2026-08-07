"""Main orchestrator and entry point for the Antigravity CLI GitHub Action."""

import asyncio
import os
from pathlib import Path
import sys

# Add the repository root to sys.path so 'from src....' imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.github_client import (  # pylint: disable=wrong-import-position
    GitHubEventContext,
    GitHubClient,
    parse_diff_to_changed_lines,
)
from src.review_engine import (  # pylint: disable=wrong-import-position
    AntigravityReviewEngine,
)


async def main_async() -> (
    int
):  # pylint: disable=too-many-locals,too-many-return-statements,too-many-statements
    """Performs the async core execution of the review action.

    Returns:
        int: The process exit code (0 for success/soft-pass, 1 for critical failure).
    """
    # 1. Retrieve action inputs (supporting both hyphens and underscores)
    api_key = os.environ.get("INPUT_API-KEY") or os.environ.get("INPUT_API_KEY")
    workload_identity_provider = os.environ.get(
        "INPUT_WORKLOAD-IDENTITY-PROVIDER"
    ) or os.environ.get("INPUT_WORKLOAD_IDENTITY_PROVIDER")
    service_account = os.environ.get("INPUT_SERVICE-ACCOUNT") or os.environ.get(
        "INPUT_SERVICE_ACCOUNT"
    )
    gcp_project_id = os.environ.get("INPUT_GCP-PROJECT-ID") or os.environ.get(
        "INPUT_GCP_PROJECT_ID"
    )
    gcp_location = os.environ.get("INPUT_GCP-LOCATION") or os.environ.get(
        "INPUT_GCP_LOCATION"
    )
    github_token = os.environ.get("INPUT_GITHUB-TOKEN") or os.environ.get(
        "INPUT_GITHUB_TOKEN"
    )
    fail_on_error_str = (
        os.environ.get("INPUT_FAIL-ON-ERROR")
        or os.environ.get("INPUT_FAIL_ON_ERROR")
        or "true"
    ).strip().lower()
    fail_on_error = fail_on_error_str in ["true", "1", "yes"]
    custom_prompt = os.environ.get("INPUT_CUSTOM-PROMPT") or os.environ.get(
        "INPUT_CUSTOM_PROMPT"
    )

    max_diff_lines_raw = os.environ.get("INPUT_MAX-DIFF-LINES") or os.environ.get(
        "INPUT_MAX_DIFF_LINES"
    ) or "2000"
    try:
        max_diff_lines = int(max_diff_lines_raw.strip())
    except ValueError:
        max_diff_lines = 2000

    max_diff_files_raw = os.environ.get("INPUT_MAX-DIFF-FILES") or os.environ.get(
        "INPUT_MAX_DIFF_FILES"
    ) or "50"
    try:
        max_diff_files = int(max_diff_files_raw.strip())
    except ValueError:
        max_diff_files = 50

    print("🤖 Google Antigravity Code Review Action starting...")

    try:
        # 2. Parse event context from environment
        print("Parsing GitHub Action event context...")
        context = GitHubEventContext.from_env()
        print(
            f"Triggered by event: '{context.event_name}' on repository: "
            f"'{context.repo_owner}/{context.repo_name}'"
        )

        if not context.pr_number:
            print(
                f"Event '{context.event_name}' does not have an associated Pull Request. "
                "Skipping review."
            )
            return 0

        # Check for review request triggers in issue comments
        if context.event_name == "issue_comment" and not context.is_review_requested:
            print(
                "Issue comment event detected, but no '/review' command was found. Skipping review."
            )
            return 0

        # 3. Fetch PR Diff using GitHub Client
        token = github_token or context.token
        repo_fullname = f"{context.repo_owner}/{context.repo_name}"

        print(f"Initializing GitHub Client for '{repo_fullname}'...")
        client = GitHubClient(token=token, repo=repo_fullname)

        print(f"Fetching diff/patch for Pull Request #{context.pr_number}...")
        diff_text = client.fetch_pr_diff(context.pr_number)

        if not diff_text or not diff_text.strip():
            print("The pull request diff is empty. Skipping review.")
            return 0

        # 4. Map changed lines
        changed_lines = parse_diff_to_changed_lines(diff_text)
        if not changed_lines:
            print("No added or modified lines found in this diff. Skipping review.")
            return 0

        changed_files_count = len(changed_lines)
        total_changed_lines = sum(len(lines) for lines in changed_lines.values())

        if 0 < max_diff_files < changed_files_count:
            print(
                f"⚠️ Diff modifies {changed_files_count} files, exceeding max limit "
                f"({max_diff_files} files). Skipping AI review to prevent resource exhaustion."
            )
            return 0

        if 0 < max_diff_lines < total_changed_lines:
            print(
                f"⚠️ Diff contains {total_changed_lines} modified lines, exceeding max limit "
                f"({max_diff_lines} lines). Skipping AI review to prevent resource exhaustion."
            )
            return 0

        print(
            f"Found modifications in {changed_files_count} files ({total_changed_lines} lines). "
            "Running review engine..."
        )

        # 5. Execute Antigravity Review Engine
        engine = AntigravityReviewEngine(
            api_key=api_key,
            workload_identity_provider=workload_identity_provider,
            service_account=service_account,
            gcp_project_id=gcp_project_id,
            gcp_location=gcp_location,
            custom_prompt=custom_prompt,
        )
        comments = await engine.run_review(diff_text, changed_lines)

        if not comments:
            print(
                "No suggestions or security concerns identified by the AI review engine. Great job!"
            )
            return 0

        print(
            "AI Review completed. Posting "
            f"{len(comments)} inline comment(s) to Pull Request #{context.pr_number}..."
        )

        # 6. Post comments back to GitHub PR
        body_summary = (
            "🤖 **Google Antigravity Code Review**\n\n"
            "I have reviewed the changes in this Pull Request and left inline feedback."
        )
        success = client.post_review_comments(
            pr_number=context.pr_number, comments=comments, body=body_summary
        )

        if success:
            print("Successfully posted all inline comments to the Pull Request!")
            return 0
        raise RuntimeError(
            "GitHub API returned error code when posting review comments"
        )

    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"❌ Error during action execution: {e}", file=sys.stderr)
        if fail_on_error:
            print(
                "Action configured to fail on error ('fail-on-error' is set to true). "
                "Failing build.",
                file=sys.stderr,
            )
            return 1
        print(
            "Action configured to soft-pass on error ('fail-on-error' is set to false). "
            "Exiting successfully.",
            file=sys.stderr,
        )
        return 0


def main():
    """Synchronous entry point wrapping the async execution loop."""
    exit_code = asyncio.run(main_async())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
