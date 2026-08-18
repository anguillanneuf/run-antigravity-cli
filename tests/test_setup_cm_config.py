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


def test_generate_cm_config_custom_overrides():
    config = generate_cm_config(
        model="gemini-3.1-pro",
        output_format="json",
        sandbox_enabled=True,
        sandbox_network_profile="permissive-open",
        extra_extensions=[".sh", ".yaml"],
        extra_exclude_dirs=["custom_build"],
    )
    assert config["model"] == "gemini-3.1-pro"
    assert config["output"]["format"] == "json"
    assert config["sandbox"]["enabled"] is True
    assert config["sandbox"]["network"]["profile"] == "permissive-open"
    assert ".sh" in config["scan"]["extensions"]["include"]
    assert ".yaml" in config["scan"]["extensions"]["include"]
    assert "custom_build" in config["scan"]["exclude_dirs"]


def test_render_cm_config_yaml():
    config = generate_cm_config()
    yaml_text = render_cm_config_yaml(config)
    assert "confirm_commands: false" in yaml_text
    assert "confirm_writes: false" in yaml_text
    assert "model: \"gemini-3.5-flash\"" in yaml_text
    assert "enabled: false" in yaml_text
    assert '".py"' in yaml_text
    assert '"node_modules"' in yaml_text


def test_write_cm_config(tmp_path):
    target_file = tmp_path / ".codemender" / "config.yaml"
    result_path = write_cm_config(output_path=str(target_file))
    
    assert os.path.exists(result_path)
    with open(result_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "confirm_commands: false" in content
    assert "confirm_writes: false" in content
    assert "enabled: false" in content
    assert "gemini-3.5-flash" in content


def test_main_cli(tmp_path, monkeypatch, capsys):
    from scripts.setup_cm_config import main
    target = tmp_path / "custom_config.yaml"
    monkeypatch.setattr("sys.argv", ["setup_cm_config.py", "--output", str(target), "--model", "gemini-3.1-pro", "--format", "json"])
    main()
    
    captured = capsys.readouterr()
    assert "successfully generated" in captured.out
    assert target.exists()

