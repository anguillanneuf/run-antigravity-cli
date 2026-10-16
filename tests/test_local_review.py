"""Unit tests for the Shift-Left Local Review CLI (scripts/local_review.py)."""

import os
import stat
import subprocess
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from scripts.local_review import (
    get_local_diff,
    render_findings,
    install_pre_push_hook,
    run_local_review,
    main,
)


def test_get_local_diff_staged():
    """Verify --staged runs 'git diff --cached --unified=3'."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="diff --git a/a.py b/a.py\n+x = 1\n", stderr=""
        )
        diff = get_local_diff(staged=True)
        assert "+x = 1" in diff
        mock_run.assert_called_once()
        cmd = mock_run.call_args.args[0]
        assert "git" in cmd
        assert "diff" in cmd
        assert "--cached" in cmd


def test_get_local_diff_branch():
    """Verify --branch <base> runs 'git diff origin/<base>...HEAD' or falls back to '<base>...HEAD'."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="diff --git a/b.py b/b.py\n+y = 2\n", stderr=""
        )
        diff = get_local_diff(branch="main")
        assert "+y = 2" in diff
        cmd = mock_run.call_args.args[0]
        assert any("origin/main...HEAD" in part for part in cmd)


def test_get_local_diff_branch_fallback():
    """Verify --branch falls back to local branch ref when origin/<base> fails."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            subprocess.CalledProcessError(128, ["git", "diff"]),
            MagicMock(
                returncode=0, stdout="diff --git a/b.py b/b.py\n+y = 2\n", stderr=""
            ),
        ]
        diff = get_local_diff(branch="main")
        assert "+y = 2" in diff
        assert mock_run.call_count == 2


def test_get_local_diff_working():
    """Verify --working runs 'git diff HEAD' to inspect unstaged/working tree changes."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="diff --git a/c.py b/c.py\n+z = 3\n", stderr=""
        )
        diff = get_local_diff(working=True)
        assert "+z = 3" in diff
        cmd = mock_run.call_args.args[0]
        assert "HEAD" in cmd


def test_get_local_diff_specific_file():
    """Verify --file <path> restricts git diff to the target file path."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="diff --git a/src/app.py b/src/app.py\n+a = 4\n",
            stderr="",
        )
        diff = get_local_diff(staged=True, file_path="src/app.py")
        assert "+a = 4" in diff
        cmd = mock_run.call_args.args[0]
        assert "--" in cmd
        assert "src/app.py" in cmd


def test_render_findings_empty():
    """Verify terminal rendering when zero issues are found."""
    output = render_findings([])
    assert (
        "No issues found" in output
        or "0 findings" in output
        or "passed" in output.lower()
    )


def test_render_findings_with_ansi_and_badges():
    """Verify terminal rendering includes ANSI color codes, severity badges, and file:line pointers."""
    findings = [
        {
            "path": "src/auth.py",
            "line": 42,
            "severity": "CRITICAL",
            "confidence": 5,
            "category": "SECURITY",
            "body": "Hardcoded token detected.",
        },
        {
            "path": "src/db.py",
            "line": 18,
            "severity": "HIGH",
            "confidence": 4,
            "category": "BUG",
            "body": "Unclosed connection on exception.",
        },
    ]
    output = render_findings(findings, use_color=True)
    assert "src/auth.py:42" in output
    assert "CRITICAL" in output
    assert "SECURITY" in output
    assert "Hardcoded token detected." in output
    assert "src/db.py:18" in output
    assert "\033[" in output  # ANSI escape sequence


def test_install_pre_push_hook(tmp_path):
    """Verify --install-hook writes an executable .git/hooks/pre-push script."""
    git_dir = tmp_path / ".git" / "hooks"
    git_dir.mkdir(parents=True)

    hook_path = install_pre_push_hook(repo_root=str(tmp_path))
    assert os.path.exists(hook_path)
    content = open(hook_path, "r", encoding="utf-8").read()
    assert "#!/usr/bin/env bash" in content or "#!/bin/sh" in content
    assert "local_review.py" in content

    mode = os.stat(hook_path).st_mode
    assert bool(mode & stat.S_IXUSR)


@pytest.mark.asyncio
@patch("scripts.local_review.AntigravityReviewEngine")
@patch("scripts.local_review.get_local_diff")
async def test_run_local_review_returns_exit_code_1_on_blocking_findings(
    mock_get_diff, mock_engine_cls, tmp_path
):
    """Verify exit code 1 when blocking findings above threshold are returned."""
    sample_file = tmp_path / "src" / "app.py"
    sample_file.parent.mkdir(parents=True)
    sample_file.write_text("import os\nx = 'secret'\n", encoding="utf-8")

    mock_get_diff.return_value = (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1,1 +1,2 @@\n"
        " import os\n"
        "+x = 'secret'\n"
    )

    mock_engine = MagicMock()
    mock_engine.run_review = AsyncMock(
        return_value=[
            {
                "path": "src/app.py",
                "line": 2,
                "severity": "CRITICAL",
                "confidence": 5,
                "category": "SECURITY",
                "body": "Exposed secret.",
            }
        ]
    )
    mock_engine_cls.return_value = mock_engine

    exit_code = await run_local_review(
        staged=True,
        min_severity="HIGH",
        min_confidence=4,
        enable_verifier=True,
        workspace_root=str(tmp_path),
    )
    assert exit_code == 1
    mock_engine.run_review.assert_called_once()


@pytest.mark.asyncio
@patch("scripts.local_review.AntigravityReviewEngine")
@patch("scripts.local_review.get_local_diff")
async def test_run_local_review_returns_exit_code_0_when_clean(
    mock_get_diff, mock_engine_cls, tmp_path
):
    """Verify exit code 0 when no findings are returned."""
    mock_get_diff.return_value = (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1,1 +1,2 @@\n"
        " import os\n"
        "+x = 1\n"
    )

    mock_engine = MagicMock()
    mock_engine.run_review = AsyncMock(return_value=[])
    mock_engine_cls.return_value = mock_engine

    exit_code = await run_local_review(
        staged=True,
        workspace_root=str(tmp_path),
    )
    assert exit_code == 0


def test_main_cli_install_hook(tmp_path, monkeypatch):
    """Verify CLI --install-hook flag installs the hook and exits with 0."""
    git_hooks = tmp_path / ".git" / "hooks"
    git_hooks.mkdir(parents=True)
    monkeypatch.setattr(
        "sys.argv",
        ["local_review.py", "--install-hook", "--repo-root", str(tmp_path)],
    )
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    assert (git_hooks / "pre-push").exists()


@pytest.mark.asyncio
@patch("scripts.local_review.get_local_diff")
async def test_run_local_review_empty_diff(mock_get_diff):
    """Verify run_local_review exits with 0 immediately when diff is empty."""
    mock_get_diff.return_value = "   \n"
    exit_code = await run_local_review(staged=True)
    assert exit_code == 0


def test_render_findings_no_color():
    """Verify terminal rendering with use_color=False omits ANSI escape codes."""
    output_empty = render_findings([], use_color=False)
    assert "\033[" not in output_empty
    assert "No issues found" in output_empty

    findings = [
        {
            "path": "src/auth.py",
            "line": 10,
            "severity": "HIGH",
            "confidence": 4,
            "category": "BUG",
            "body": "Null dereference.",
        }
    ]
    output = render_findings(findings, use_color=False)
    assert "\033[" not in output
    assert "src/auth.py:10" in output


@patch("scripts.local_review.run_local_review", new_callable=AsyncMock)
def test_main_cli_runs_review(mock_run_review):
    """Verify main() parses flags and invokes run_local_review."""
    mock_run_review.return_value = 0
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--staged",
                "--min-severity",
                "CRITICAL",
                "--min-confidence",
                "5",
                "--disable-verifier",
                "--no-color",
            ]
        )
    assert exc_info.value.code == 0
    mock_run_review.assert_called_once()
    kwargs = mock_run_review.call_args.kwargs
    assert kwargs["staged"] is True
    assert kwargs["min_severity"] == "CRITICAL"
    assert kwargs["min_confidence"] == 5
    assert kwargs["enable_verifier"] is False
    assert kwargs["use_color"] is False
