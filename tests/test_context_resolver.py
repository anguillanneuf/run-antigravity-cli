"""Unit tests for the context-aware file expansion resolver."""

import os
from unittest.mock import MagicMock, patch
import pytest

from src.context_resolver import (
    ContextResolver,
    resolve_file_context,
    resolve_contexts_for_diff,
    extract_file_diffs,
)


def test_resolve_file_context_whole_file_under_threshold(tmp_path):
    """Files under 1,000 lines should have their full contents returned with line numbers."""
    test_file = tmp_path / "small_service.py"
    lines = [f"line_{i} = {i}\n" for i in range(1, 151)]
    test_file.write_text("".join(lines), encoding="utf-8")

    context = resolve_file_context(
        file_path="small_service.py",
        changed_lines=[50, 51],
        base_dir=str(tmp_path),
        max_whole_file_lines=1000,
    )

    assert context is not None
    # All lines from 1 to 150 should be present
    assert "1: line_1 = 1" in context
    assert "50: line_50 = 50" in context
    assert "150: line_150 = 150" in context
    # Should not have omission markers
    assert "omitted" not in context.lower()


def test_resolve_file_context_boundary_999_lines(tmp_path):
    """File with exactly 999 lines (< 1,000) should return the whole file."""
    test_file = tmp_path / "boundary.py"
    lines = [f"print({i})\n" for i in range(1, 1000)]
    test_file.write_text("".join(lines), encoding="utf-8")

    context = resolve_file_context(
        file_path="boundary.py",
        changed_lines=[500],
        base_dir=str(tmp_path),
        max_whole_file_lines=1000,
    )

    assert "1: print(1)" in context
    assert "999: print(999)" in context
    assert "omitted" not in context.lower()


def test_resolve_file_context_large_file_single_window(tmp_path):
    """File with >= 1,000 lines should slice a window of +/- 100 lines around changed lines."""
    test_file = tmp_path / "large_module.py"
    lines = [f"code_line_{i} = {i}\n" for i in range(1, 1501)]
    test_file.write_text("".join(lines), encoding="utf-8")

    # Changed at line 500. Padding = 100 lines -> window 400 to 600
    context = resolve_file_context(
        file_path="large_module.py",
        changed_lines=[500],
        base_dir=str(tmp_path),
        max_whole_file_lines=1000,
        hunk_padding=100,
    )

    assert context is not None
    # Boundary of window
    assert "400: code_line_400 = 400" in context
    assert "500: code_line_500 = 500" in context
    assert "600: code_line_600 = 600" in context

    # Outside the window should NOT be in context
    assert "100: code_line_100 = 100" not in context
    assert "800: code_line_800 = 800" not in context
    # Omission markers should be present
    assert "omitted" in context.lower()


def test_resolve_file_context_large_file_overlapping_windows(tmp_path):
    """Multiple changed lines whose padding windows overlap should be merged seamlessly."""
    test_file = tmp_path / "large_module.py"
    lines = [f"entry_{i} = {i}\n" for i in range(1, 1501)]
    test_file.write_text("".join(lines), encoding="utf-8")

    # Changed lines at 300 and 450.
    # Window 1: 200..400. Window 2: 350..550.
    # Merged window: 200..550
    context = resolve_file_context(
        file_path="large_module.py",
        changed_lines=[300, 450],
        base_dir=str(tmp_path),
        max_whole_file_lines=1000,
        hunk_padding=100,
    )

    assert "200: entry_200 = 200" in context
    assert "375: entry_375 = 375" in context  # Between the two changed lines
    assert "550: entry_550 = 550" in context

    # Ensure no omission marker between 200 and 550
    assert "entry_100 = 100" not in context
    assert "entry_700 = 700" not in context


def test_resolve_file_context_large_file_disjoint_windows(tmp_path):
    """Disjoint hunks in a large file should produce separate windows with an omission notice."""
    test_file = tmp_path / "large_service.py"
    lines = [f"data_{i} = {i}\n" for i in range(1, 2001)]
    test_file.write_text("".join(lines), encoding="utf-8")

    # Hunk 1 at 150 (window 50..250), Hunk 2 at 1500 (window 1400..1600)
    context = resolve_file_context(
        file_path="large_service.py",
        changed_lines=[150, 1500],
        base_dir=str(tmp_path),
        max_whole_file_lines=1000,
        hunk_padding=100,
    )

    assert "50: data_50 = 50" in context
    assert "250: data_250 = 250" in context
    assert "1400: data_1400 = 1400" in context
    assert "1600: data_1600 = 1600" in context

    # Line 800 should be omitted between the windows
    assert "data_800 = 800" not in context
    assert "omitted" in context.lower()


def test_resolve_file_context_clamped_at_file_boundaries(tmp_path):
    """Padding near the beginning or end of file should clamp to line 1 and max line without crash."""
    test_file = tmp_path / "boundary_module.py"
    lines = [f"line_{i} = {i}\n" for i in range(1, 1201)]
    test_file.write_text("".join(lines), encoding="utf-8")

    # Changed lines at line 5 (near start) and line 1195 (near end)
    context = resolve_file_context(
        file_path="boundary_module.py",
        changed_lines=[5, 1195],
        base_dir=str(tmp_path),
        max_whole_file_lines=1000,
        hunk_padding=100,
    )

    assert "1: line_1 = 1" in context
    assert "105: line_105 = 105" in context
    assert "1095: line_1095 = 1095" in context
    assert "1200: line_1200 = 1200" in context


def test_resolve_file_context_missing_file_falls_back_to_diff(tmp_path):
    """When a file does not exist locally, it should fall back to diff_content if provided."""
    diff_snippet = "@@ -1,5 +1,6 @@\n+import security_check\n def execute():\n     pass"

    context = resolve_file_context(
        file_path="deleted_or_remote_file.py",
        changed_lines=[2],
        base_dir=str(tmp_path),
        diff_content=diff_snippet,
    )

    assert context is not None
    assert "+import security_check" in context
    assert "diff" in context.lower() or "fallback" in context.lower()


def test_resolve_file_context_missing_file_without_diff_returns_fallback_notice(tmp_path):
    """When a file is completely missing and no diff is provided, returns informative fallback."""
    context = resolve_file_context(
        file_path="completely_missing.py",
        changed_lines=[10],
        base_dir=str(tmp_path),
    )

    assert context is not None
    assert "unavailable" in context.lower() or "not found" in context.lower()


def test_resolve_file_context_github_client_fallback(tmp_path):
    """When file is missing locally, attempts to fetch from GitHubClient if provided."""
    mock_client = MagicMock()
    remote_content = "\n".join([f"remote_line_{i}" for i in range(1, 51)])
    mock_client.fetch_file_content.return_value = remote_content

    context = resolve_file_context(
        file_path="remote_only.py",
        changed_lines=[10],
        base_dir=str(tmp_path),
        github_client=mock_client,
        ref="feature-branch",
    )

    mock_client.fetch_file_content.assert_called_once_with("remote_only.py", ref="feature-branch")
    assert "1: remote_line_1" in context
    assert "10: remote_line_10" in context


def test_extract_file_diffs():
    """extract_file_diffs correctly partitions unified diff by file path."""
    diff_text = (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1,3 +1,4 @@\n"
        "+# new comment\n"
        " def main():\n"
        "diff --git a/src/utils.py b/src/utils.py\n"
        "--- a/src/utils.py\n"
        "+++ b/src/utils.py\n"
        "@@ -10,3 +10,4 @@\n"
        "+# utils helper\n"
    )

    file_diffs = extract_file_diffs(diff_text)
    assert "src/app.py" in file_diffs
    assert "src/utils.py" in file_diffs
    assert "+# new comment" in file_diffs["src/app.py"]
    assert "+# utils helper" in file_diffs["src/utils.py"]


def test_resolve_contexts_for_diff(tmp_path):
    """resolve_contexts_for_diff processes all files in a unified diff and returns mapped contexts."""
    file_a = tmp_path / "app.py"
    file_a.write_text("def run():\n    return True\n", encoding="utf-8")

    diff_text = (
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1,2 +1,3 @@\n"
        " def run():\n"
        "+    # extra log\n"
        "     return True\n"
    )

    contexts = resolve_contexts_for_diff(
        diff_text=diff_text,
        changed_lines={"app.py": [2]},
        base_dir=str(tmp_path),
    )

    assert "app.py" in contexts
    assert "1: def run():" in contexts["app.py"]
    assert "2:     return True" in contexts["app.py"]
