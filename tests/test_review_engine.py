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


@patch("os.path.exists")
@patch("os.makedirs")
@patch("builtins.open", new_callable=mock_open)
def test_settings_generation(mock_file, mock_makedirs, mock_exists):
    """Verify that settings.json is correctly generated when an API key is supplied."""
    mock_exists.return_value = False
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


@patch("os.path.exists")
@patch("os.makedirs")
def test_settings_generation_preserves_existing(mock_makedirs, mock_exists):
    """Verify that settings.json is updated by preserving existing settings when an API key is supplied."""
    mock_exists.return_value = True
    engine = AntigravityReviewEngine(api_key="gemini-key-xyz")

    existing_data = '{"other_setting": "value-123"}'

    # We mock open specifically so we can handle different behavior for 'r' and 'w'
    m = mock_open(read_data=existing_data)
    with patch("builtins.open", m):
        engine.ensure_settings_configured()

    mock_makedirs.assert_called_once()

    # Verify read was called with 'r'
    m.assert_any_call(
        os.path.expanduser("~/.gemini/antigravity-cli/settings.json"),
        "r",
        encoding="utf-8",
    )
    # Verify write was called with 'w'
    m.assert_any_call(
        os.path.expanduser("~/.gemini/antigravity-cli/settings.json"),
        "w",
        encoding="utf-8",
    )

    # Gather written content
    handle = m()
    written_data = "".join(call.args[0] for call in handle.write.call_args_list)
    parsed_written = json.loads(written_data)
    assert parsed_written["gemini_api_key"] == "gemini-key-xyz"
    assert parsed_written["other_setting"] == "value-123"


@patch("src.review_engine.Agent")
@patch("src.review_engine.LocalAgentConfig")
@pytest.mark.asyncio
async def test_review_engine_initialization(mock_config_cls, mock_agent_cls):
    """Verify initialization and context leasing of the Google Antigravity Agent."""
    mock_agent_instance = MagicMock()
    mock_agent_instance.__aenter__.return_value = AsyncMock()
    mock_agent_cls.return_value = mock_agent_instance

    engine = AntigravityReviewEngine(
        api_key="gemini-key-xyz", custom_prompt="Review style guide."
    )

    async with engine._lease_agent() as agent:  # pylint: disable=protected-access
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

    mock_json_response = json.dumps(
        [
            {
                "path": "src/main.py",
                "line": 5,
                "body": "Add a docstring to this function.",
            },
            {
                "path": "src/main.py",
                "line": 10,
                "body": "Use constant instead of magic number.",
            },
        ]
    )
    mock_agent.chat.return_value = MockAgentResponse([mock_json_response])

    engine = AntigravityReviewEngine(api_key="gemini-key-xyz")

    changed_lines = {"src/main.py": [1, 2, 3, 5]}  # Line 10 is NOT changed

    comments = await engine.run_review(
        diff_text="mock-diff", changed_lines=changed_lines
    )

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
        "[\n"
        '  {"path": "src/main.py", "line": 3, "body": "Rename variable to avoid shadow shadow."}\n'
        "]\n"
        "```"
    )
    mock_agent.chat.return_value = MockAgentResponse([wrapped_response])

    engine = AntigravityReviewEngine(api_key="gemini-key-xyz")

    changed_lines = {"src/main.py": [3]}
    comments = await engine.run_review(
        diff_text="mock-diff", changed_lines=changed_lines
    )

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
    comments = await engine.run_review(
        diff_text="mock-diff", changed_lines=changed_lines
    )

    assert comments == []


def test_validate_markdown_suggestions():
    """Verify that _validate_markdown_suggestions correctly identifies and converts standard code blocks to suggestion blocks when appropriate."""
    engine = AntigravityReviewEngine()

    # 1. Body containing a "suggest" keyword and a standard python code block should be converted
    body = "Consider using this helper function instead:\n```python\nreturn get_user_data()\n```"
    validated = engine._validate_markdown_suggestions(body)
    assert "```suggestion" in validated
    assert "```python" not in validated
    assert "return get_user_data()" in validated

    # 2. Body containing an already formatted ```suggestion block should be preserved
    body_already = "Try this:\n```suggestion\nreturn get_user_data()\n```"
    validated_already = engine._validate_markdown_suggestions(body_already)
    assert "```suggestion" in validated_already
    assert validated_already == body_already

    # 3. Body with no triggers should not be touched
    body_no_trigger = (
        "Check this general documentation block:\n```python\nprint('hello')\n```"
    )
    validated_no_trigger = engine._validate_markdown_suggestions(body_no_trigger)
    assert "```python" in validated_no_trigger
    assert "```suggestion" not in validated_no_trigger


@patch("os.path.exists")
@patch("os.makedirs")
@patch("builtins.open", new_callable=mock_open)
def test_wif_settings_generation(mock_file, mock_makedirs, mock_exists):
    """Verify that settings.json correctly configures Workload Identity Federation when WIF parameters are supplied."""
    mock_exists.return_value = False
    engine = AntigravityReviewEngine(
        workload_identity_provider="projects/123/locations/global/workloadIdentityPools/pool/providers/provider",
        service_account="sa@project.iam.gserviceaccount.com",
        gcp_project_id="my-gcp-project",
        gcp_location="us-central1",
    )

    engine.ensure_settings_configured()

    mock_makedirs.assert_called_once()
    mock_file.assert_called_once()

    handle = mock_file()
    written_data = "".join(call.args[0] for call in handle.write.call_args_list)
    parsed_written = json.loads(written_data)

    assert parsed_written["auth_mode"] == "workload_identity"
    assert (
        parsed_written["workload_identity_provider"]
        == "projects/123/locations/global/workloadIdentityPools/pool/providers/provider"
    )
    assert parsed_written["service_account"] == "sa@project.iam.gserviceaccount.com"
    assert parsed_written["gcp_project_id"] == "my-gcp-project"
    assert parsed_written["gcp_location"] == "us-central1"


@patch("os.path.exists")
@patch("os.makedirs")
@patch("builtins.open", new_callable=mock_open)
def test_wif_settings_generation_with_api_key_fallback(
    mock_file, mock_makedirs, mock_exists
):
    """Verify settings.json includes both WIF settings and gemini_api_key for fallback support."""
    mock_exists.return_value = False
    engine = AntigravityReviewEngine(
        api_key="fallback-gemini-key",
        workload_identity_provider="projects/123/locations/global/workloadIdentityPools/pool/providers/provider",
        service_account="sa@project.iam.gserviceaccount.com",
    )

    engine.ensure_settings_configured()

    handle = mock_file()
    written_data = "".join(call.args[0] for call in handle.write.call_args_list)
    parsed_written = json.loads(written_data)

    assert parsed_written["auth_mode"] == "workload_identity"
    assert parsed_written["gemini_api_key"] == "fallback-gemini-key"
    assert (
        parsed_written["workload_identity_provider"]
        == "projects/123/locations/global/workloadIdentityPools/pool/providers/provider"
    )


@patch("src.review_engine.LocalAgentConfig")
@patch("src.review_engine.Agent")
@pytest.mark.asyncio
async def test_lease_agent_config_auth_modes(
    mock_agent_cls, mock_local_config_cls, monkeypatch
):
    """Verify that _lease_agent passes api_key or vertex/project/location parameters to LocalAgentConfig based on auth mode."""
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("GCLOUD_PROJECT", raising=False)
    monkeypatch.delenv("INPUT_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    # 1. API Key mode
    engine_key = AntigravityReviewEngine(api_key="my-api-key")
    async with engine_key._lease_agent():
        pass

    mock_local_config_cls.assert_called_with(
        system_instructions=(
            pytest.any_int
            if False
            else mock_local_config_cls.call_args.kwargs["system_instructions"]
        ),
        capabilities=mock_local_config_cls.call_args.kwargs["capabilities"],
        api_key="my-api-key",
    )

    # 2. WIF / Vertex AI mode (no API key)
    engine_wif = AntigravityReviewEngine(
        workload_identity_provider="projects/123/locations/global/workloadIdentityPools/pool/providers/provider",
        service_account="sa@project.iam.gserviceaccount.com",
        gcp_project_id="my-gcp-project",
        gcp_location="us-central1",
    )
    async with engine_wif._lease_agent():
        pass

    mock_local_config_cls.assert_called_with(
        system_instructions=mock_local_config_cls.call_args.kwargs[
            "system_instructions"
        ],
        capabilities=mock_local_config_cls.call_args.kwargs["capabilities"],
        vertex=True,
        project="my-gcp-project",
        location="us-central1",
        model="gemini-2.5-flash",
    )

    # 3. Explicit Model mode
    engine_custom_model = AntigravityReviewEngine(
        api_key="my-api-key",
        model="gemini-2.5-pro",
    )
    async with engine_custom_model._lease_agent():
        pass

    mock_local_config_cls.assert_called_with(
        system_instructions=mock_local_config_cls.call_args.kwargs[
            "system_instructions"
        ],
        capabilities=mock_local_config_cls.call_args.kwargs["capabilities"],
        model="gemini-2.5-pro",
        api_key="my-api-key",
    )


def test_filter_threshold_comments():
    """Verify that _filter_threshold_comments correctly drops findings below severity or confidence threshold."""
    engine = AntigravityReviewEngine()

    candidates = [
        {
            "path": "a.py",
            "line": 1,
            "severity": "CRITICAL",
            "confidence": 5,
            "category": "SECURITY",
            "body": "Critical issue",
        },
        {
            "path": "b.py",
            "line": 2,
            "severity": "HIGH",
            "confidence": 4,
            "category": "BUG",
            "body": "High issue",
        },
        {
            "path": "c.py",
            "line": 3,
            "severity": "HIGH",
            "confidence": 3,
            "category": "BUG",
            "body": "High but low confidence",
        },
        {
            "path": "d.py",
            "line": 4,
            "severity": "MEDIUM",
            "confidence": 5,
            "category": "CODE_QUALITY",
            "body": "Medium issue",
        },
        {
            "path": "e.py",
            "line": 5,
            "severity": "LOW",
            "confidence": 5,
            "category": "CODE_QUALITY",
            "body": "Low issue",
        },
    ]

    # Filter with min_severity=HIGH, min_confidence=4
    filtered = engine._filter_threshold_comments(
        candidates, min_severity="HIGH", min_confidence=4
    )
    assert len(filtered) == 2
    assert [c["path"] for c in filtered] == ["a.py", "b.py"]

    # Filter with min_severity=MEDIUM, min_confidence=4
    filtered_med = engine._filter_threshold_comments(
        candidates, min_severity="MEDIUM", min_confidence=4
    )
    assert len(filtered_med) == 3
    assert [c["path"] for c in filtered_med] == ["a.py", "b.py", "d.py"]

    # Case-insensitive severity check
    filtered_case = engine._filter_threshold_comments(
        candidates, min_severity="high", min_confidence=4
    )
    assert len(filtered_case) == 2


@patch("src.review_engine.Agent")
@pytest.mark.asyncio
async def test_run_review_with_severity_and_confidence(mock_agent_cls):
    """Verify run_review filters comments using min_severity and min_confidence and preserves metadata fields."""
    mock_agent = AsyncMock()
    mock_agent_cls.return_value.__aenter__.return_value = mock_agent

    mock_json_response = json.dumps(
        [
            {
                "path": "src/main.py",
                "line": 5,
                "severity": "CRITICAL",
                "confidence": 5,
                "category": "SECURITY",
                "body": "SQL injection vulnerability detected.",
            },
            {
                "path": "src/main.py",
                "line": 6,
                "severity": "MEDIUM",
                "confidence": 5,
                "category": "CODE_QUALITY",
                "body": "Variable name could be more descriptive.",
            },
            {
                "path": "src/main.py",
                "line": 7,
                "severity": "HIGH",
                "confidence": 2,
                "category": "BUG",
                "body": "Speculative race condition.",
            },
        ]
    )
    mock_agent.chat.return_value = MockAgentResponse([mock_json_response])

    engine = AntigravityReviewEngine(api_key="gemini-key-xyz")
    changed_lines = {"src/main.py": [5, 6, 7]}

    comments = await engine.run_review(
        diff_text="mock-diff",
        changed_lines=changed_lines,
        min_severity="HIGH",
        min_confidence=4,
    )

    assert len(comments) == 1
    assert comments[0]["path"] == "src/main.py"
    assert comments[0]["line"] == 5
    assert comments[0]["severity"] == "CRITICAL"
    assert comments[0]["confidence"] == 5
    assert comments[0]["category"] == "SECURITY"
    assert "SQL injection" in comments[0]["body"]


@patch("src.review_engine.Agent")
@pytest.mark.asyncio
async def test_two_pass_critic_verifier_workflow(mock_agent_cls):
    """Verify that Pass 1 generates candidates and Pass 2 filters unverified candidates."""
    mock_agent = AsyncMock()
    mock_agent_cls.return_value.__aenter__.return_value = mock_agent

    pass1_response = json.dumps(
        [
            {
                "path": "src/auth.py",
                "line": 15,
                "severity": "CRITICAL",
                "confidence": 5,
                "category": "SECURITY",
                "body": "Hardcoded secret key in session config.",
            },
            {
                "path": "src/auth.py",
                "line": 20,
                "severity": "HIGH",
                "confidence": 4,
                "category": "SECURITY",
                "body": "Unsanitized parameter passed to internal logger.",
            },
        ]
    )
    pass2_response = json.dumps(
        [
            {
                "path": "src/auth.py",
                "line": 15,
                "severity": "CRITICAL",
                "confidence": 5,
                "category": "SECURITY",
                "body": "Hardcoded secret key in session config.",
                "verified": True,
                "rationale": "Genuinely exposed API secret.",
            },
            {
                "path": "src/auth.py",
                "line": 20,
                "severity": "HIGH",
                "confidence": 4,
                "category": "SECURITY",
                "body": "Unsanitized parameter passed to internal logger.",
                "verified": False,
                "rationale": "False positive: internal logger already masks PII.",
            },
        ]
    )

    mock_agent.chat.side_effect = [
        MockAgentResponse([pass1_response]),
        MockAgentResponse([pass2_response]),
    ]

    engine = AntigravityReviewEngine(api_key="gemini-key-xyz")
    changed_lines = {"src/auth.py": [15, 20]}
    file_contexts = {
        "src/auth.py": "1: import os\n...\n15: SECRET = '123'\n...\n20: logger.info(p)\n"
    }

    comments = await engine.run_review(
        diff_text="mock diff",
        changed_lines=changed_lines,
        file_contexts=file_contexts,
        enable_verifier=True,
    )

    assert mock_agent.chat.call_count == 2
    assert len(comments) == 1
    assert comments[0]["line"] == 15
    assert comments[0]["severity"] == "CRITICAL"
    assert "Hardcoded secret key" in comments[0]["body"]


@patch("src.review_engine.Agent")
@pytest.mark.asyncio
async def test_verifier_skips_when_zero_candidates(mock_agent_cls):
    """Verify that Pass 2 is completely skipped when Pass 1 produces no candidates (token optimization)."""
    mock_agent = AsyncMock()
    mock_agent_cls.return_value.__aenter__.return_value = mock_agent

    mock_agent.chat.side_effect = [
        MockAgentResponse(["[]"]),
    ]

    engine = AntigravityReviewEngine(api_key="gemini-key-xyz")
    changed_lines = {"src/auth.py": [15]}

    comments = await engine.run_review(
        diff_text="mock diff",
        changed_lines=changed_lines,
        enable_verifier=True,
    )

    assert mock_agent.chat.call_count == 1
    assert comments == []


@patch("src.review_engine.Agent")
@pytest.mark.asyncio
async def test_verifier_skips_when_candidates_below_threshold(mock_agent_cls):
    """Verify that Pass 2 is skipped when all Pass 1 candidates fall below severity/confidence thresholds."""
    mock_agent = AsyncMock()
    mock_agent_cls.return_value.__aenter__.return_value = mock_agent

    pass1_response = json.dumps(
        [
            {
                "path": "src/utils.py",
                "line": 10,
                "severity": "LOW",
                "confidence": 2,
                "category": "CODE_QUALITY",
                "body": "Variable naming nitpick.",
            }
        ]
    )
    mock_agent.chat.side_effect = [
        MockAgentResponse([pass1_response]),
    ]

    engine = AntigravityReviewEngine(api_key="gemini-key-xyz")
    changed_lines = {"src/utils.py": [10]}

    comments = await engine.run_review(
        diff_text="mock diff",
        changed_lines=changed_lines,
        min_severity="HIGH",
        min_confidence=4,
        enable_verifier=True,
    )

    assert mock_agent.chat.call_count == 1
    assert comments == []


@patch("src.review_engine.Agent")
@pytest.mark.asyncio
async def test_verifier_disabled_returns_pass1_candidates(mock_agent_cls):
    """Verify that when enable_verifier=False, Pass 2 is not called and Pass 1 candidates are returned."""
    mock_agent = AsyncMock()
    mock_agent_cls.return_value.__aenter__.return_value = mock_agent

    pass1_response = json.dumps(
        [
            {
                "path": "src/utils.py",
                "line": 10,
                "severity": "HIGH",
                "confidence": 5,
                "category": "BUG",
                "body": "Potential off-by-one error.",
            }
        ]
    )
    mock_agent.chat.side_effect = [
        MockAgentResponse([pass1_response]),
    ]

    engine = AntigravityReviewEngine(api_key="gemini-key-xyz")
    changed_lines = {"src/utils.py": [10]}

    comments = await engine.run_review(
        diff_text="mock diff",
        changed_lines=changed_lines,
        enable_verifier=False,
    )

    assert mock_agent.chat.call_count == 1
    assert len(comments) == 1
    assert comments[0]["line"] == 10


@patch("src.review_engine.Agent")
@pytest.mark.asyncio
async def test_verifier_resilience_fallback_on_error(mock_agent_cls):
    """Verify that if Pass 2 verifier encounters an error or malformed JSON, it falls back to Pass 1 candidates."""
    mock_agent = AsyncMock()
    mock_agent_cls.return_value.__aenter__.return_value = mock_agent

    pass1_response = json.dumps(
        [
            {
                "path": "src/server.py",
                "line": 50,
                "severity": "CRITICAL",
                "confidence": 5,
                "category": "SECURITY",
                "body": "Command injection vulnerability.",
            }
        ]
    )

    mock_agent.chat.side_effect = [
        MockAgentResponse([pass1_response]),
        MockAgentResponse(["Internal verifier error: non-json payload"]),
    ]

    engine = AntigravityReviewEngine(api_key="gemini-key-xyz")
    changed_lines = {"src/server.py": [50]}

    comments = await engine.run_review(
        diff_text="mock diff",
        changed_lines=changed_lines,
        enable_verifier=True,
    )

    assert mock_agent.chat.call_count == 2
    assert len(comments) == 1
    assert comments[0]["line"] == 50
    assert "Command injection" in comments[0]["body"]

