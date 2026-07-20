"""Unit tests for the Antigravity Review Engine integration."""

import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from src.review_engine import AntigravityReviewEngine


# Mock agent response as an async iterable
class MockAgentResponse:
    """Mock for the response returned by agent.chat() to simulate async iteration."""

    def __init__(self, tokens):
        self.tokens = tokens

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.tokens:
            raise StopAsyncIteration
        return self.tokens.pop(0)


@patch("os.makedirs")
@patch("builtins.open", new_callable=mock_open)
def test_settings_generation(mock_file, mock_makedirs):
    """Verify that settings.json is correctly generated when an API key is supplied."""
    engine = AntigravityReviewEngine(api_key="gemini-key-xyz")
    
    # Trigger setting configuration generation
    engine.ensure_settings_configured()
    
    mock_makedirs.assert_called_once()
    mock_file.assert_called_once()
    
    # Verify exact written content
    handle = mock_file()
    written_data = "".join(call.args[0] for call in handle.write.call_args_list)
    parsed_written = json.loads(written_data)
    assert parsed_written["gemini_api_key"] == "gemini-key-xyz"


@patch("src.review_engine.Agent")
@patch("src.review_engine.LocalAgentConfig")
@pytest.mark.asyncio
async def test_review_engine_initialization(mock_config_cls, mock_agent_cls):
    """Verify initialization and context leasing of the Google Antigravity Agent."""
    mock_agent_instance = MagicMock()
    mock_agent_instance.__aenter__.return_value = AsyncMock()
    mock_agent_cls.return_value = mock_agent_instance

    engine = AntigravityReviewEngine(api_key="gemini-key-xyz", custom_prompt="Review style guide.")
    
    async with engine._lease_agent() as agent: # pylint: disable=protected-access
        assert agent is not None

    mock_agent_cls.assert_called_once()
    mock_config_cls.assert_called_once()
    _, kwargs = mock_config_cls.call_args
    assert "Review style guide." in kwargs["system_instructions"]


@patch("src.review_engine.Agent")
@pytest.mark.asyncio
async def test_run_review_success(mock_agent_cls):
    """Verify successful review run, output parsing, and target line filtering."""
    # Set up mock agent and chat responses
    mock_agent = AsyncMock()
    mock_agent_cls.return_value.__aenter__.return_value = mock_agent

    mock_json_response = json.dumps([
        {"path": "src/main.py", "line": 5, "body": "Add a docstring to this function."},
        {"path": "src/main.py", "line": 10, "body": "Use constant instead of magic number."}
    ])
    mock_agent.chat.return_value = MockAgentResponse([mock_json_response])

    engine = AntigravityReviewEngine(api_key="gemini-key-xyz")
    
    changed_lines = {
        "src/main.py": [1, 2, 3, 5]  # Line 10 is NOT changed
    }
    
    comments = await engine.run_review(diff_text="mock-diff", changed_lines=changed_lines)
    
    assert len(comments) == 1
    assert comments[0]["path"] == "src/main.py"
    assert comments[0]["line"] == 5
    assert comments[0]["body"] == "Add a docstring to this function."


@patch("src.review_engine.Agent")
@pytest.mark.asyncio
async def test_run_review_markdown_json_wrapping(mock_agent_cls):
    """Verify that JSON wrapped in markdown code blocks is correctly extracted."""
    mock_agent = AsyncMock()
    mock_agent_cls.return_value.__aenter__.return_value = mock_agent

    wrapped_response = (
        "Here are my review suggestions:\n"
        "```json\n"
        '[\n'
        '  {"path": "src/main.py", "line": 3, "body": "Rename variable to avoid shadow shadow."}\n'
        ']\n'
        "```"
    )
    mock_agent.chat.return_value = MockAgentResponse([wrapped_response])

    engine = AntigravityReviewEngine(api_key="gemini-key-xyz")
    
    changed_lines = {"src/main.py": [3]}
    comments = await engine.run_review(diff_text="mock-diff", changed_lines=changed_lines)
    
    assert len(comments) == 1
    assert comments[0]["line"] == 3
    assert comments[0]["body"] == "Rename variable to avoid shadow shadow."


@patch("src.review_engine.Agent")
@pytest.mark.asyncio
async def test_run_review_malformed_json_fallback(mock_agent_cls):
    """Verify that the engine fails gracefully or returns empty list when response is malformed."""
    mock_agent = AsyncMock()
    mock_agent_cls.return_value.__aenter__.return_value = mock_agent
    mock_agent.chat.return_value = MockAgentResponse(["Not valid JSON or markdown."])

    engine = AntigravityReviewEngine(api_key="gemini-key-xyz")
    
    changed_lines = {"src/main.py": [3]}
    comments = await engine.run_review(diff_text="mock-diff", changed_lines=changed_lines)
    
    assert comments == []
