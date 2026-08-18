#!/usr/bin/env python3
"""Validation tests for .github/workflows/test-cm.yml workflow file."""

import os
import re
import sys
import pytest

WORKFLOW_PATH = os.path.join(os.path.dirname(__file__), "..", ".github", "workflows", "test-cm.yml")


def test_workflow_file_exists():
    assert os.path.exists(WORKFLOW_PATH)


def test_workflow_content_and_structure():
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify triggers
    assert "name: 'CodeMender Security Scan Workflow'" in content
    assert "pull_request:" in content
    assert "pull_request_target:" in content
    assert "workflow_dispatch:" in content

    # Verify inputs
    assert "scan_mode:" in content
    assert "dry_run:" in content

    # Verify OIDC and write permissions
    assert "contents: read" in content
    assert "pull-requests: write" in content
    assert "id-token: write" in content

    # Verify Workload Identity Federation configuration
    assert "google-github-actions/auth@v3" in content
    assert "vars.GCP_PROJECT_ID" in content
    assert "vars.GCP_WORKLOAD_IDENTITY_PROVIDER" in content
    assert "vars.GCP_SERVICE_ACCOUNT_EMAIL" in content

    # Verify Artifact Registry CLI download URL
    assert "artifactregistry.googleapis.com" in content
    assert "cmoc-prod" in content
    assert "codemender-cli-production" in content

    # Verify referenced scripts
    assert "scripts/setup_cm_config.py" in content
    assert "scripts/resolve_pr_files.py" in content
    assert "scripts/report_cm_results.py" in content


def test_referenced_scripts_exist_and_executable():
    base_dir = os.path.join(os.path.dirname(__file__), "..")
    scripts = [
        "scripts/setup_cm_config.py",
        "scripts/resolve_pr_files.py",
        "scripts/report_cm_results.py",
    ]
    for script_rel in scripts:
        script_full = os.path.join(base_dir, script_rel)
        assert os.path.exists(script_full), f"Missing script: {script_rel}"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__]))

