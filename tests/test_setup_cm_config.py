"""Unit tests for CodeMender CI configuration generation helper."""

import os
import pytest
from scripts.setup_cm_config import (
    generate_cm_config,
    render_cm_config_yaml,
    write_cm_config,
    DEFAULT_SCAN_EXTENSIONS,
    DEFAULT_EXCLUDE_DIRS,
)


def test_generate_cm_config_defaults():
    config = generate_cm_config()
    assert config["tools"]["confirm_commands"] is False
    assert config["tools"]["confirm_writes"] is False
    assert config["tools"]["cleanup_candidate_branches"] is True
    assert config["sandbox"]["enabled"] is False
    assert config["model"] == "gemini-3.5-flash"
    assert config["output"]["format"] == "table"
    assert config["scan"]["extensions"]["include"] == DEFAULT_SCAN_EXTENSIONS
    assert "node_modules" in config["scan"]["exclude_dirs"]
    assert "vendor" in config["scan"]["exclude_dirs"]
    assert config["vcs"]["type"] == "git"
    assert config["server"] == {}


def test_generate_cm_config_with_server_project_and_location():
    config = generate_cm_config(
        project_id="my-gcp-project",
        location="us-central1",
    )
    assert config["server"]["project"] == "my-gcp-project"
    assert config["server"]["location"] == "us-central1"


def test_generate_cm_config_custom_overrides():
    config = generate_cm_config(
        model="gemini-3.1-pro",
        output_format="json",
        sandbox_enabled=True,
        sandbox_network_profile="permissive-open",
        extra_extensions=[".sh", ".yaml"],
        extra_exclude_dirs=["custom_build"],
        project_id="test-proj-123",
        location="us-east1",
    )
    assert config["model"] == "gemini-3.1-pro"
    assert config["output"]["format"] == "json"
    assert config["sandbox"]["enabled"] is True
    assert config["sandbox"]["network"]["profile"] == "permissive-open"
    assert ".sh" in config["scan"]["extensions"]["include"]
    assert ".yaml" in config["scan"]["extensions"]["include"]
    assert "custom_build" in config["scan"]["exclude_dirs"]
    assert config["server"]["project"] == "test-proj-123"
    assert config["server"]["location"] == "us-east1"


def test_render_cm_config_yaml_with_server():
    config = generate_cm_config(project_id="my-sample-project", location="us-central1")
    yaml_text = render_cm_config_yaml(config)
    assert 'project: "my-sample-project"' in yaml_text
    assert 'location: "us-central1"' in yaml_text
    assert "confirm_commands: false" in yaml_text
    assert "confirm_writes: false" in yaml_text
    assert 'model: "gemini-3.5-flash"' in yaml_text
    assert "enabled: false" in yaml_text
    assert '".py"' in yaml_text
    assert '"node_modules"' in yaml_text


def test_write_cm_config(tmp_path):
    target_file = tmp_path / ".codemender" / "config.yaml"
    result_path = write_cm_config(
        output_path=str(target_file),
        project_id="my-project-id",
        location="europe-west1",
    )
    
    assert os.path.exists(result_path)
    with open(result_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    assert 'project: "my-project-id"' in content
    assert 'location: "europe-west1"' in content
    assert "confirm_commands: false" in content
    assert "confirm_writes: false" in content
    assert "enabled: false" in content
    assert "gemini-3.5-flash" in content


def test_main_cli(tmp_path, monkeypatch, capsys):
    from scripts.setup_cm_config import main
    target = tmp_path / "custom_config.yaml"
    monkeypatch.setattr("sys.argv", [
        "setup_cm_config.py",
        "--output", str(target),
        "--model", "gemini-3.1-pro",
        "--format", "json",
        "--project-id", "cli-proj",
        "--location", "us-central1",
    ])
    main()
    
    captured = capsys.readouterr()
    assert "successfully generated" in captured.out
    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert 'project: "cli-proj"' in content
    assert 'location: "us-central1"' in content


def test_main_cli_with_google_cloud_project_env(tmp_path, monkeypatch, capsys):
    from scripts.setup_cm_config import main
    target = tmp_path / "env_config.yaml"
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-gcp-project")
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.setattr("sys.argv", [
        "setup_cm_config.py",
        "--output", str(target),
    ])
    main()

    captured = capsys.readouterr()
    assert "successfully generated" in captured.out
    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert 'project: "env-gcp-project"' in content


def test_write_cm_config_tilde_expansion(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    result_path = write_cm_config(
        output_path="~/.codemender/config.yaml",
        project_id="tilde-proj",
    )
    assert os.path.exists(result_path)
    assert str(tmp_path) in result_path
    with open(result_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "sandbox:" in content
    assert "enabled: false" in content
    assert 'project: "tilde-proj"' in content


def test_generate_cm_config_with_project_paths():
    config = generate_cm_config(
        project_paths=["/home/runner/work/my-repo", "/tmp/scan"],
    )
    assert config["project_paths"] == ["/home/runner/work/my-repo", "/tmp/scan"]
    assert config["sandbox"]["enabled"] is False

    yaml_text = render_cm_config_yaml(config)
    assert 'project_paths: ["/home/runner/work/my-repo", "/tmp/scan"]' in yaml_text
    assert "sandbox:\n  enabled: false" in yaml_text
