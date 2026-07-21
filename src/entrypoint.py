"""Main orchestrator and entry point for the Antigravity CLI GitHub Action."""

import asyncio
import os
import sys
from src.github_client import (
    GitHubEventContext,
    GitHubClient,
    parse_diff_to_changed_lines,
)
from src.review_engine import AntigravityReviewEngine


async def main_async() -> int:  # pylint: disable=too-many-locals,too-many-return-statements
    """Performs the async core execution of the review action.

    Returns:
        int: The process exit code (0 for success/soft-pass, 1 for critical failure).
    """
    # 1. Retrieve action inputs
    api_key = os.environ.get("INPUT_API-KEY")
    github_token = os.environ.get("INPUT_GITHUB-TOKEN")
    fail_on_error_str = os.environ.get("INPUT_FAIL-ON-ERROR", "true").strip().lower()
    fail_on_error = fail_on_error_str in ["true", "1", "yes"]
    custom_prompt = os.environ.get("INPUT_CUSTOM-PROMPT")

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

        print(
            f"Found modifications in {len(changed_lines)} files. Running review engine..."
        )

        # 5. Execute Antigravity Review Engine
        engine = AntigravityReviewEngine(api_key=api_key, custom_prompt=custom_prompt)
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
