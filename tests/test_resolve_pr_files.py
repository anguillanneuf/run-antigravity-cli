"""Unit tests for resolving changed PR files for CodeMender scan."""

import json
import os
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from scripts.resolve_pr_files import (
    filter_scan_files,
    get_changed_files_from_git,
    resolve_target_scan_files,
    main,
    DEFAULT_SUPPORTED_EXTENSIONS,
)


def test_filter_scan_files():
    raw_files = [
        "src/entrypoint.py",
        "README.md",
        "tests/test_app.py",
        "node_modules/pkg/index.js",
        ".venv/lib/python.py",
        "src/app.min.js",
        "service/handler.go",
        "vendor/go.mod",
        "src/component.ts",
    ]

    filtered = filter_scan_files(raw_files)
    assert "src/entrypoint.py" in filtered
    assert "tests/test_app.py" in filtered
    assert "service/handler.go" in filtered
    assert "src/component.ts" in filtered
    
    # Excluded files/dirs
    assert "README.md" not in filtered
    assert "node_modules/pkg/index.js" not in filtered
    assert ".venv/lib/python.py" not in filtered
    assert "src/app.min.js" not in filtered
    assert "vendor/go.mod" not in filtered


def test_filter_scan_files_custom_extensions():
    raw_files = ["script.sh", "deploy.yaml", "main.py"]
    filtered = filter_scan_files(raw_files, extensions=[".sh", ".yaml"])
    assert "script.sh" in filtered
    assert "deploy.yaml" in filtered
    assert "main.py" not in filtered


def test_get_changed_files_from_git():
    mock_diff = "src/main.py\nsrc/utils.py\nREADME.md\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_diff, stderr="")
        files = get_changed_files_from_git(base_ref="origin/main", head_ref="HEAD")
        assert files == ["src/main.py", "src/utils.py", "README.md"]


def test_get_changed_files_from_git_error_fallback():
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, ["git", "diff"]),
            MagicMock(returncode=0, stdout="fallback.py\n", stderr=""),
        ]
        files = get_changed_files_from_git(base_ref="main", head_ref="HEAD")
        assert files == ["fallback.py"]


def test_get_changed_files_from_git_total_error():
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("git failed")
        files = get_changed_files_from_git(base_ref="main", head_ref="HEAD")
        assert files == []


def test_resolve_target_scan_files_diff_mode():
    with patch("scripts.resolve_pr_files.get_changed_files_from_git") as mock_git:
        mock_git.return_value = ["src/review.py", "docs/index.md", "tests/test_review.py"]
        targets = resolve_target_scan_files(base_ref="origin/main", head_ref="HEAD", full_scan=False)
        assert targets == ["src/review.py", "tests/test_review.py"]


def test_resolve_target_scan_files_full_scan(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')")
    (tmp_path / "test.txt").write_text("text file")
    
    targets = resolve_target_scan_files(root_dir=str(tmp_path), full_scan=True)
    assert len(targets) == 1
    assert targets[0].endswith("app.py")


def test_main_cli(tmp_path, monkeypatch, capsys):
    output_file = tmp_path / "github_output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    monkeypatch.setattr("sys.argv", ["resolve_pr_files.py", "--full", "--output-github-env"])
    
    with patch("scripts.resolve_pr_files.resolve_target_scan_files") as mock_resolve:
        mock_resolve.return_value = ["src/entrypoint.py", "src/github_client.py"]
        main()
    
    captured = capsys.readouterr()
    assert "Resolved 2 files for CodeMender scan" in captured.out
    
    content = output_file.read_text()
    assert "file_count=2" in content
    assert "files=src/entrypoint.py src/github_client.py" in content
