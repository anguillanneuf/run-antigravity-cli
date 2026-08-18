"""Unit tests for CodeMender scan reporting helper."""

import os
from unittest.mock import patch, MagicMock
import pytest

from scripts.report_cm_results import (
    format_step_summary,
    format_pr_comment,
    post_or_update_pr_comment,
    publish_scan_report,
    main,
)


def test_format_step_summary_success_no_findings():
    summary = format_step_summary(
        scan_output="No security vulnerabilities found.",
        exit_code=0,
        scanned_files=["src/entrypoint.py", "src/review_engine.py"],
        scan_mode="diff",
        dry_run=False,
    )
    assert "### 🛡️ CodeMender Security Scan Report" in summary
    assert "✅ **Status:** Passed (0 findings)" in summary
    assert "`src/entrypoint.py`" in summary
    assert "No security vulnerabilities found." in summary


def test_format_step_summary_dry_run():
    summary = format_step_summary(
        scan_output="Resource setup has just started. Please try again shortly.",
        exit_code=0,
        scanned_files=[],
        scan_mode="diff",
        dry_run=True,
    )
    assert "⚠️ **Status:** Dry-Run / Pre-Flight Mode" in summary
    assert "Resource setup has just started" in summary


def test_format_step_summary_findings_detected():
    findings_output = "Found 1 high severity vulnerability: SQL Injection in handler.py:45"
    summary = format_step_summary(
        scan_output=findings_output,
        exit_code=1,
        scanned_files=["handler.py"],
        scan_mode="diff",
        dry_run=False,
    )
    assert "⚠️ **Status:** Vulnerabilities / Issues Detected" in summary
    assert "SQL Injection" in summary


def test_format_pr_comment():
    comment = format_pr_comment(
        scan_output="Clean scan",
        exit_code=0,
        scanned_files=["src/main.py"],
        scan_mode="diff",
        dry_run=False,
    )
    assert "<!-- codemender-scan-report -->" in comment
    assert "### 🛡️ CodeMender Security Scan Report" in comment


def test_post_or_update_pr_comment():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b'[{"id": 12345, "body": "<!-- codemender-scan-report --> Old report"}]'
        mock_response.status = 200
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        success = post_or_update_pr_comment(
            repo="owner/repo",
            pr_number=42,
            token="dummy_token",
            body="<!-- codemender-scan-report --> New report",
        )
        assert success is True


def test_post_new_pr_comment():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b'[{"id": 99999, "body": "Unrelated comment"}]'
        mock_response.status = 201
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        success = post_or_update_pr_comment(
            repo="owner/repo",
            pr_number=42,
            token="dummy_token",
            body="<!-- codemender-scan-report --> New report",
        )
        assert success is True


def test_publish_scan_report(tmp_path, monkeypatch):
    step_summary_file = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(step_summary_file))
    
    with patch("scripts.report_cm_results.post_or_update_pr_comment") as mock_post:
        mock_post.return_value = True
        publish_scan_report(
            scan_output="Scan completed cleanly.",
            exit_code=0,
            scanned_files=["src/app.py"],
            scan_mode="diff",
            dry_run=False,
            repo="owner/repo",
            pr_number=10,
            token="test_token",
        )
    
    assert step_summary_file.exists()
    content = step_summary_file.read_text(encoding="utf-8")
    assert "CodeMender Security Scan Report" in content


def test_main_cli(tmp_path, monkeypatch):
    log_file = tmp_path / "scan.log"
    log_file.write_text("Scan finished 0 issues found")
    summary_file = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))
    monkeypatch.setattr("sys.argv", [
        "report_cm_results.py",
        "--output-file", str(log_file),
        "--exit-code", "0",
        "--files", "src/main.py",
        "--scan-mode", "diff",
    ])
    
    main()
    assert summary_file.exists()
    assert "Scan finished 0 issues found" in summary_file.read_text()
