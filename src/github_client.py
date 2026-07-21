"""GitHub REST API client and action event parsing utilities."""

import os
import json
import re
import requests


# pylint: disable=too-many-instance-attributes,too-many-arguments,too-many-positional-arguments,too-many-locals,too-few-public-methods
class GitHubEventContext:
    """Parses and exposes GitHub event metadata from actions runner environment."""

    def __init__(
        self,
        event_name,
        repo_owner,
        repo_name,
        token,
        pr_number=None,
        head_sha=None,
        base_sha=None,
        is_review_requested=False,
    ):
        self.event_name = event_name
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.token = token
        self.pr_number = pr_number
        self.head_sha = head_sha
        self.base_sha = base_sha
        self.is_review_requested = is_review_requested

    @classmethod
    def from_env(cls):
        """Loads and decodes event metadata from environment variables."""
        event_name = os.getenv("GITHUB_EVENT_NAME", "")
        repository = os.getenv("GITHUB_REPOSITORY", "")
        token = os.getenv("GITHUB_TOKEN", "")

        repo_owner, repo_name = "", ""
        if "/" in repository:
            repo_owner, repo_name = repository.split("/", 1)

        event_path = os.getenv("GITHUB_EVENT_PATH", "")

        pr_number = None
        head_sha = None
        base_sha = None
        is_review_requested = False

        if event_path:
            try:
                with open(event_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                payload = {}

            if event_name == "pull_request":
                pr_payload = payload.get("pull_request", {})
                pr_number = pr_payload.get("number")
                head_sha = pr_payload.get("head", {}).get("sha")
                base_sha = pr_payload.get("base", {}).get("sha")

            elif event_name == "push":
                head_sha = payload.get("after")
                base_sha = payload.get("before")

            elif event_name == "issue_comment":
                comment_payload = payload.get("comment", {})
                comment_body = comment_payload.get("body", "")
                if "/review" in comment_body:
                    is_review_requested = True

                issue_payload = payload.get("issue", {})
                pr_number = issue_payload.get("number")

        return cls(
            event_name=event_name,
            repo_owner=repo_owner,
            repo_name=repo_name,
            token=token,
            pr_number=pr_number,
            head_sha=head_sha,
            base_sha=base_sha,
            is_review_requested=is_review_requested,
        )


def parse_diff_to_changed_lines(diff_text):
    """Parses a unified diff and returns a dict mapping file paths

    to a list of modified/added line numbers.
    """
    changed_lines = {}
    current_file = None
    current_line = 0

    # Match chunk headers like @@ -1,3 +1,6 @@
    chunk_header_pattern = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            changed_lines[current_file] = []
        elif line.startswith("--- a/"):
            continue
        elif current_file:
            match = chunk_header_pattern.match(line)
            if match:
                current_line = int(match.group(1))
            elif line.startswith("+"):
                # Avoid matching "+++ " header line
                if not line.startswith("+++"):
                    changed_lines[current_file].append(current_line)
                    current_line += 1
            elif line.startswith("-"):
                # Line was deleted, does not exist in target file
                continue
            else:
                # Unchanged context line
                current_line += 1

    # Filter out empty files
    return {k: v for k, v in changed_lines.items() if v}


class GitHubClient:
    """Interacts with GitHub REST API endpoints."""

    def __init__(self, token, repo):
        self.token = token
        self.repo = repo
        self.base_url = f"https://api.github.com/repos/{repo}"

    def fetch_pr_diff(self, pr_number):
        """Fetches the raw diff of a pull request."""
        url = f"{self.base_url}/pulls/{pr_number}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3.diff",
        }
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response.text

    def post_review_comments(self, pr_number, comments, body):
        """Submits a pull request review with inline comments."""
        url = f"{self.base_url}/pulls/{pr_number}/reviews"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }

        api_comments = []
        for c in comments:
            api_comments.append(
                {
                    "path": c["path"],
                    "line": c["line"],
                    "side": "RIGHT",
                    "body": c["body"],
                }
            )

        payload = {"event": "COMMENT", "body": body, "comments": api_comments}

        response = requests.post(url, headers=headers, json=payload, timeout=20)
        return response.status_code in (200, 201)
