"""Integration and orchestration tests for the main custom action entrypoint."""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.github_client import GitHubEventContext, GitHubClient
from src.review_engine import AntigravityReviewEngine


@pytest.fixture
def mock_env():
    """Provides a base mock environment for GitHub Actions execution."""
    with patch.dict(
        os.environ,
        {
            "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_EVENT_PATH": "/tmp/event.json",
            "GITHUB_REPOSITORY": "google/run-antigravity-cli",
            "INPUT_API-KEY": "mock-api-key-123",
            "INPUT_GITHUB-TOKEN": "mock-github-token-456",
            "INPUT_FAIL-ON-ERROR": "true",
            "INPUT_CUSTOM-PROMPT": "Review carefully.",
        },
        clear=True,
    ):
        yield


@pytest.mark.asyncio
@patch("src.entrypoint.GitHubEventContext.from_env")
@patch("src.entrypoint.GitHubClient")
@patch("src.entrypoint.AntigravityReviewEngine")
async def test_entrypoint_pull_request_success(
    mock_engine_cls, mock_client_cls, mock_context_from_env, mock_env
):
    """Verify standard end-to-end orchestration for a successful pull_request review event."""
    from src.entrypoint import main_async

    # 1. Set up mock GHEventContext
    mock_context = MagicMock(spec=GitHubEventContext)
    mock_context.event_name = "pull_request"
    mock_context.repo_owner = "google"
    mock_context.repo_name = "run-antigravity-cli"
    mock_context.token = "mock-github-token-456"
    mock_context.pr_number = 42
    mock_context.head_sha = "headsha123"
    mock_context.base_sha = "basesha123"
    mock_context.is_review_requested = False
    mock_context_from_env.return_value = mock_context

    # 2. Set up mock GitHubClient
    mock_client = MagicMock(spec=GitHubClient)
    mock_client.fetch_pr_diff.return_value = "mock-diff-patch"
    mock_client.post_review_comments.return_value = True
    mock_client_cls.return_value = mock_client

    # 3. Set up mock AntigravityReviewEngine
    mock_engine = MagicMock(spec=AntigravityReviewEngine)
    mock_reviews = [
        {"path": "src/main.py", "line": 5, "body": "```suggestion\nprint('hello')\n```"}
    ]
    mock_engine.run_review = AsyncMock(return_value=mock_reviews)
    mock_engine_cls.return_value = mock_engine

    # Patch parse_diff_to_changed_lines to return mock line mapping
    with patch("src.entrypoint.parse_diff_to_changed_lines") as mock_parse_diff:
        mock_parse_diff.return_value = {"src/main.py": [5]}

        # Execute entrypoint orchestration
        exit_code = await main_async()

        # Verify exit code is 0 (success)
        assert exit_code == 0

        # Verify client and engine interactions
        mock_context_from_env.assert_called_once()
        mock_client_cls.assert_called_once_with(
            token="mock-github-token-456", repo="google/run-antigravity-cli"
        )
        mock_client.fetch_pr_diff.assert_called_once_with(42)
        mock_parse_diff.assert_called_once_with("mock-diff-patch")

        mock_engine_cls.assert_called_once_with(
            api_key="mock-api-key-123", custom_prompt="Review carefully."
        )
        mock_engine.run_review.assert_called_once_with(
            "mock-diff-patch", {"src/main.py": [5]}
        )
        mock_client.post_review_comments.assert_called_once_with(
            pr_number=42,
            comments=mock_reviews,
            body="🤖 **Google Antigravity Code Review**\n\nI have reviewed the changes in this Pull Request and left inline feedback.",
        )


@pytest.mark.asyncio
@patch("src.entrypoint.GitHubEventContext.from_env")
@patch("src.entrypoint.GitHubClient")
@patch("src.entrypoint.AntigravityReviewEngine")
async def test_entrypoint_review_failure_fails_build_when_fail_on_error_true(
    mock_engine_cls, mock_client_cls, mock_context_from_env, mock_env
):
    """Verify that execution failures exit with code 1 if fail-on-error input is set to true."""
    from src.entrypoint import main_async

    # 1. Set up mock context
    mock_context = MagicMock(spec=GitHubEventContext)
    mock_context.event_name = "pull_request"
    mock_context.repo_owner = "google"
    mock_context.repo_name = "run-antigravity-cli"
    mock_context.token = "mock-github-token-456"
    mock_context.pr_number = 42
    mock_context_from_env.return_value = mock_context

    # 2. Set up mock GitHubClient to fail
    mock_client = MagicMock(spec=GitHubClient)
    mock_client.fetch_pr_diff.side_effect = RuntimeError("API rate limit exceeded")
    mock_client_cls.return_value = mock_client

    # Execute and verify exit code is 1 (failure)
    exit_code = await main_async()
    assert exit_code == 1


@pytest.mark.asyncio
@patch("src.entrypoint.GitHubEventContext.from_env")
@patch("src.entrypoint.GitHubClient")
@patch("src.entrypoint.AntigravityReviewEngine")
@patch.dict(os.environ, {"INPUT_FAIL-ON-ERROR": "false"})
async def test_entrypoint_review_failure_ignores_error_when_fail_on_error_false(
    mock_engine_cls, mock_client_cls, mock_context_from_env, mock_env
):
    """Verify that execution failures exit with code 0 (soft-pass) if fail-on-error input is false."""
    from src.entrypoint import main_async

    # 1. Set up mock context
    mock_context = MagicMock(spec=GitHubEventContext)
    mock_context.event_name = "pull_request"
    mock_context.repo_owner = "google"
    mock_context.repo_name = "run-antigravity-cli"
    mock_context.token = "mock-github-token-456"
    mock_context.pr_number = 42
    mock_context_from_env.return_value = mock_context

    # 2. Set up mock GitHubClient to fail
    mock_client = MagicMock(spec=GitHubClient)
    mock_client.fetch_pr_diff.side_effect = RuntimeError("API rate limit exceeded")
    mock_client_cls.return_value = mock_client

    # Execute and verify exit code is 0 despite the error
    exit_code = await main_async()
    assert exit_code == 0


@pytest.mark.asyncio
@patch("src.entrypoint.GitHubEventContext.from_env")
async def test_entrypoint_no_pr_number(mock_context_from_env, mock_env):
    """Verify skipping review when the event has no PR number."""
    from src.entrypoint import main_async

    mock_context = MagicMock(spec=GitHubEventContext)
    mock_context.event_name = "push"
    mock_context.pr_number = None
    mock_context.repo_owner = "google"
    mock_context.repo_name = "run-antigravity-cli"
    mock_context.token = "mock-github-token-456"
    mock_context_from_env.return_value = mock_context

    exit_code = await main_async()
    assert exit_code == 0


@pytest.mark.asyncio
@patch("src.entrypoint.GitHubEventContext.from_env")
async def test_entrypoint_issue_comment_not_requested(mock_context_from_env, mock_env):
    """Verify skipping review when an issue comment event is detected without the /review command."""
    from src.entrypoint import main_async

    mock_context = MagicMock(spec=GitHubEventContext)
    mock_context.event_name = "issue_comment"
    mock_context.pr_number = 42
    mock_context.is_review_requested = False
    mock_context.repo_owner = "google"
    mock_context.repo_name = "run-antigravity-cli"
    mock_context.token = "mock-github-token-456"
    mock_context_from_env.return_value = mock_context

    exit_code = await main_async()
    assert exit_code == 0


@pytest.mark.asyncio
@patch("src.entrypoint.GitHubEventContext.from_env")
@patch("src.entrypoint.GitHubClient")
async def test_entrypoint_empty_diff(mock_client_cls, mock_context_from_env, mock_env):
    """Verify skipping review when the pull request diff is empty."""
    from src.entrypoint import main_async

    mock_context = MagicMock(spec=GitHubEventContext)
    mock_context.event_name = "pull_request"
    mock_context.pr_number = 42
    mock_context.repo_owner = "google"
    mock_context.repo_name = "run-antigravity-cli"
    mock_context.token = "mock-github-token-456"
    mock_context_from_env.return_value = mock_context

    mock_client = MagicMock(spec=GitHubClient)
    mock_client.fetch_pr_diff.return_value = ""
    mock_client_cls.return_value = mock_client

    exit_code = await main_async()
    assert exit_code == 0


@pytest.mark.asyncio
@patch("src.entrypoint.GitHubEventContext.from_env")
@patch("src.entrypoint.GitHubClient")
@patch("src.entrypoint.AntigravityReviewEngine")
async def test_entrypoint_no_comments(
    mock_engine_cls, mock_client_cls, mock_context_from_env, mock_env
):
    """Verify exiting successfully when no comments are generated by the review engine."""
    from src.entrypoint import main_async

    mock_context = MagicMock(spec=GitHubEventContext)
    mock_context.event_name = "pull_request"
    mock_context.pr_number = 42
    mock_context.repo_owner = "google"
    mock_context.repo_name = "run-antigravity-cli"
    mock_context.token = "mock-github-token-456"
    mock_context_from_env.return_value = mock_context

    mock_client = MagicMock(spec=GitHubClient)
    mock_client.fetch_pr_diff.return_value = "mock-diff"
    mock_client_cls.return_value = mock_client

    mock_engine = MagicMock(spec=AntigravityReviewEngine)
    mock_engine.run_review = AsyncMock(return_value=[])
    mock_engine_cls.return_value = mock_engine

    with patch("src.entrypoint.parse_diff_to_changed_lines") as mock_parse_diff:
        mock_parse_diff.return_value = {"main.py": [1]}
        exit_code = await main_async()
        assert exit_code == 0


@patch("src.entrypoint.main_async", new_callable=AsyncMock)
@patch("sys.exit")
def test_entrypoint_main_sync(mock_exit, mock_main_async):
    """Verify the synchronous main entrypoint function runs and calls sys.exit."""
    from src.entrypoint import main

    mock_main_async.return_value = 42
    main()
    mock_main_async.assert_called_once()
    mock_exit.assert_called_once_with(42)
