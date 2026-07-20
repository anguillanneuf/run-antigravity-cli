import os
import json
import pytest
from unittest.mock import patch, mock_open, MagicMock
from src.github_client import (
    GitHubClient,
    GitHubEventContext,
    parse_diff_to_changed_lines
)

# Test event payload templates
MOCK_PR_PAYLOAD = {
    "pull_request": {
        "number": 42,
        "head": {"sha": "headsha1234567890"},
        "base": {"sha": "basesha1234567890"}
    }
}

MOCK_PUSH_PAYLOAD = {
    "before": "beforesha1234567890",
    "after": "aftersha1234567890",
    "commits": [{"id": "aftersha1234567890", "message": "feat: test commit"}]
}

MOCK_COMMENT_PAYLOAD = {
    "issue": {
        "number": 42,
        "pull_request": {"html_url": "https://api.github.com/repos/owner/repo/pulls/42"}
    },
    "comment": {
        "body": "/review please look at this"
    }
}

MOCK_DIFF = """diff --git a/src/entrypoint.py b/src/entrypoint.py
index e69de29..83f124c 100644
--- a/src/entrypoint.py
+++ b/src/entrypoint.py
@@ -1,3 +1,6 @@
 import os
+import sys
+
+def main():
+    print("Hello")
-    pass
"""


@patch.dict(os.environ, {
    "GITHUB_EVENT_NAME": "pull_request",
    "GITHUB_REPOSITORY": "google/run-antigravity-cli",
    "GITHUB_TOKEN": "gh-token-123",
})
@patch("builtins.open", new_callable=mock_open, read_data=json.dumps(MOCK_PR_PAYLOAD))
def test_parse_pull_request_event(mock_file):
    """Verify parsing of pull_request event context."""
    os.environ["GITHUB_EVENT_PATH"] = "/tmp/event.json"
    
    context = GitHubEventContext.from_env()
    assert context.event_name == "pull_request"
    assert context.repo_owner == "google"
    assert context.repo_name == "run-antigravity-cli"
    assert context.token == "gh-token-123"
    assert context.pr_number == 42
    assert context.head_sha == "headsha1234567890"
    assert context.base_sha == "basesha1234567890"


@patch.dict(os.environ, {
    "GITHUB_EVENT_NAME": "push",
    "GITHUB_REPOSITORY": "google/run-antigravity-cli",
    "GITHUB_TOKEN": "gh-token-123",
})
@patch("builtins.open", new_callable=mock_open, read_data=json.dumps(MOCK_PUSH_PAYLOAD))
def test_parse_push_event(mock_file):
    """Verify parsing of push event context."""
    os.environ["GITHUB_EVENT_PATH"] = "/tmp/event.json"
    
    context = GitHubEventContext.from_env()
    assert context.event_name == "push"
    assert context.pr_number is None
    assert context.head_sha == "aftersha1234567890"
    assert context.base_sha == "beforesha1234567890"


@patch.dict(os.environ, {
    "GITHUB_EVENT_NAME": "issue_comment",
    "GITHUB_REPOSITORY": "google/run-antigravity-cli",
    "GITHUB_TOKEN": "gh-token-123",
})
@patch("builtins.open", new_callable=mock_open, read_data=json.dumps(MOCK_COMMENT_PAYLOAD))
def test_parse_issue_comment_event(mock_file):
    """Verify parsing of issue_comment trigger payload."""
    os.environ["GITHUB_EVENT_PATH"] = "/tmp/event.json"
    
    context = GitHubEventContext.from_env()
    assert context.event_name == "issue_comment"
    assert context.pr_number == 42
    assert context.is_review_requested is True


def test_parse_diff_to_changed_lines():
    """Verify parsing unified diff patch and mapping added/modified lines."""
    changed_lines = parse_diff_to_changed_lines(MOCK_DIFF)
    
    # Assert src/entrypoint.py was changed
    assert "src/entrypoint.py" in changed_lines
    # Lines 2, 3, 4, 5 were added/modified in the new file
    assert changed_lines["src/entrypoint.py"] == [2, 3, 4, 5]


@patch("requests.get")
def test_fetch_pr_diff(mock_get):
    """Verify fetching pull request diff from GitHub API."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = MOCK_DIFF
    mock_get.return_callable = mock_response
    mock_get.return_value = mock_response

    client = GitHubClient(token="gh-token-123", repo="google/run-antigravity-cli")
    diff_text = client.fetch_pr_diff(pr_number=42)
    
    assert diff_text == MOCK_DIFF
    mock_get.assert_called_once_with(
        "https://api.github.com/repos/google/run-antigravity-cli/pulls/42",
        headers={
            "Authorization": "Bearer gh-token-123",
            "Accept": "application/vnd.github.v3.diff"
        }
    )


@patch("requests.post")
def test_post_review_comments(mock_post):
    """Verify posting draft/review comments via GitHub Review API."""
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_post.return_value = mock_response

    client = GitHubClient(token="gh-token-123", repo="google/run-antigravity-cli")
    comments = [
        {"path": "src/entrypoint.py", "line": 4, "body": "Great function, but needs a docstring!"}
    ]
    
    success = client.post_review_comments(pr_number=42, comments=comments, body="Antigravity Code Review Results")
    
    assert success is True
    mock_post.assert_called_once()
    
    # Verify mock post arguments
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.github.com/repos/google/run-antigravity-cli/pulls/42/reviews"
    assert kwargs["headers"]["Authorization"] == "Bearer gh-token-123"
    assert kwargs["headers"]["Accept"] == "application/vnd.github.v3+json"
    
    payload = kwargs["json"]
    assert payload["event"] == "COMMENT"
    assert payload["body"] == "Antigravity Code Review Results"
    assert payload["comments"][0]["path"] == "src/entrypoint.py"
    assert payload["comments"][0]["line"] == 4
    assert payload["comments"][0]["side"] == "RIGHT"
