#!/usr/bin/env python3
"""Local simulation script for testing the Google Antigravity Code Review Action.

This script allows developers to run and test the complete orchestration flow locally
on real GitHub Pull Requests and with the Gemini API, without needing to run it as
a GitHub Action workflow.
"""

import argparse
import asyncio
import os
import sys

# Ensure project root is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.entrypoint import main_async


def parse_args():
    """Parses command line arguments for the simulation run."""
    parser = argparse.ArgumentParser(
        description="Simulate running the Google Antigravity review action locally."
    )
    parser.add_argument(
        "--pr",
        type=int,
        required=True,
        help="The GitHub Pull Request number to fetch and review.",
    )
    parser.add_argument(
        "--repo",
        type=str,
        required=True,
        help="The full GitHub repository name (e.g., 'google/run-antigravity-cli').",
    )
    parser.add_argument(
        "--github-token",
        type=str,
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub Personal Access Token (defaults to GITHUB_TOKEN env var).",
    )
    parser.add_argument(
        "--gemini-key",
        type=str,
        default=os.environ.get("GEMINI_API_KEY"),
        help="Gemini API Key (defaults to GEMINI_API_KEY env var).",
    )
    parser.add_argument(
        "--custom-prompt",
        type=str,
        default="Review the changes for security vulnerabilities, performance issues, and general code quality. Ensure correct suggestion blocks are used.",
        help="Custom review prompt for the Antigravity agent.",
    )
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="If set, exit with code 1 if the review orchestration fails.",
    )
    return parser.parse_args()


async def simulate_run_async():
    """Sets up the environment from command arguments and executes the Action loop."""
    args = parse_args()

    if not args.github_token:
        print(
            "❌ Error: GitHub Token is required. Provide --github-token or set GITHUB_TOKEN env var.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not args.gemini_key:
        print(
            "❌ Error: Gemini API Key is required. Provide --gemini-key or set GEMINI_API_KEY env var.",
            file=sys.stderr,
        )
        sys.exit(1)

    owner, repo_name = (
        args.repo.split("/", 1) if "/" in args.repo else ("mock-owner", args.repo)
    )

    # 1. Establish mock GitHub Action inputs & event payload environment
    os.environ["GITHUB_EVENT_NAME"] = "pull_request"
    os.environ["GITHUB_REPOSITORY"] = args.repo
    os.environ["INPUT_API-KEY"] = args.gemini_key
    os.environ["INPUT_GITHUB-TOKEN"] = args.github_token
    os.environ["INPUT_FAIL-ON-ERROR"] = "true" if args.fail_on_error else "false"
    os.environ["INPUT_CUSTOM-PROMPT"] = args.custom_prompt

    # Create a mock temporary event.json file
    import json
    import tempfile

    event_data = {
        "action": "opened",
        "number": args.pr,
        "pull_request": {
            "number": args.pr,
            "head": {"sha": "headsha123"},
            "base": {"sha": "basesha123"},
        },
        "repository": {
            "name": repo_name,
            "owner": {"login": owner},
        },
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as tmp_event_file:
        json.dump(event_data, tmp_event_file)
        os.environ["GITHUB_EVENT_PATH"] = tmp_event_file.name

    print("=" * 80)
    print(f"🚀 Starting Local Action Simulation")
    print(f"👉 Target Repo: {args.repo}")
    print(f"👉 Pull Request: #{args.pr}")
    print(f"👉 Mock Action Event file: {tmp_event_file.name}")
    print("=" * 80)

    try:
        exit_code = await main_async()
        print("=" * 80)
        print(f"🎉 Simulation completed with exit code: {exit_code}")
        print("=" * 80)
        sys.exit(exit_code)
    finally:
        # Clean up mock event file
        if os.path.exists(tmp_event_file.name):
            os.remove(tmp_event_file.name)


def main():
    """Main synchronous entry point."""
    asyncio.run(simulate_run_async())


if __name__ == "__main__":
    main()
