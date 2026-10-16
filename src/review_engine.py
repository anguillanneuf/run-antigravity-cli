"""Antigravity Review Engine integration for executing AI-driven code reviews."""

import os
import json
import re
from contextlib import asynccontextmanager
from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig

SEVERITY_LEVELS = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}

DEFAULT_SYSTEM_INSTRUCTIONS = (
    "You are an elite automated code review agent. "
    "Your objective is to perform high-quality, precise, and secure "
    "code reviews on Pull Request diffs.\n\n"
    "Instructions:\n"
    "1. You will be provided with the raw unified diff format of the code changes.\n"
    "2. For any genuine bug, security vulnerability, severe performance regression, "
    "or code defect, generate a specific code review comment.\n"
    "3. Output format MUST be a raw JSON array of objects with the following fields:\n"
    "   - 'path': (string) the file path relative to repository root.\n"
    "   - 'line': (integer) exact line number in target/new file where suggestion applies.\n"
    "   - 'severity': (string) one of 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'.\n"
    "   - 'confidence': (integer) confidence score 1 (speculative) to 5 (definite flaw).\n"
    "   - 'category': (string) one of 'SECURITY', 'BUG', 'PERFORMANCE', 'CODE_QUALITY'.\n"
    "   - 'body': (string) markdown suggestions explaining finding and proposing fixes.\n"
    "4. Do NOT output any conversational text. Return ONLY the raw JSON array.\n"
    "5. Do NOT suggest downgrading library or GitHub Action versions unless a verified "
    "critical bug exists in that specific version."
)

VERIFIER_SYSTEM_INSTRUCTIONS = (
    "You are an adversarial verification agent (the Critic-Verifier). "
    "Your objective is to ruthlessly eliminate false positives, speculative complaints, "
    "and pedantic nitpicks from candidate code review findings.\n\n"
    "Instructions:\n"
    "1. You will be provided with candidate findings generated from a pull request diff "
    "and surrounding source file contexts.\n"
    "2. For each candidate finding, apply devil's advocate scrutiny:\n"
    "   - Is this finding a true positive defect/vulnerability in practice, or an "
    "academic/theoretical complaint?\n"
    "   - In light of surrounding code context (guards, sanitizers, checks, type "
    "constraints, imports), is this issue genuinely reachable and exploitable?\n"
    "   - Is this an unexploitable shell expansion, safe string interpolation, or "
    "expected internal variable usage?\n"
    "   - Does this proposed comment offer real, actionable defect resolution, or is "
    "it pedantic noise?\n"
    "3. Output format MUST be a raw JSON array of objects with the following fields:\n"
    "   - 'path': (string) the file path.\n"
    "   - 'line': (integer) exact line number.\n"
    "   - 'severity': (string) one of 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'.\n"
    "   - 'confidence': (integer) confidence score 1 to 5.\n"
    "   - 'category': (string) one of 'SECURITY', 'BUG', 'PERFORMANCE', 'CODE_QUALITY'.\n"
    "   - 'body': (string) markdown description explaining the issue and concrete fix.\n"
    "   - 'verified': (boolean) true if confirmed genuine, false if discarded as a false alarm.\n"
    "   - 'rationale': (string) concise explanation for verification or rejection.\n"
    "4. Do NOT output any conversational text. Return ONLY the raw JSON array."
)


# pylint: disable=too-many-instance-attributes,too-many-arguments,too-many-positional-arguments,too-many-locals
class AntigravityReviewEngine:
    """Interfaces with the Google Antigravity SDK to execute automated code reviews."""

    def __init__(
        self,
        api_key=None,
        workload_identity_provider=None,
        service_account=None,
        gcp_project_id=None,
        gcp_location=None,
        custom_prompt=None,
        model=None,
        min_severity=None,
        min_confidence=None,
        enable_verifier=True,
    ):
        self.api_key = api_key
        self.workload_identity_provider = workload_identity_provider
        self.service_account = service_account
        self.gcp_project_id = gcp_project_id
        self.gcp_location = gcp_location
        self.custom_prompt = custom_prompt
        self.model = model
        self.min_severity = min_severity
        self.min_confidence = min_confidence
        self.enable_verifier = (
            enable_verifier
            if isinstance(enable_verifier, bool)
            else str(enable_verifier).lower() not in ("false", "0", "no")
        )
        self.last_file_contexts = None

    def ensure_settings_configured(self):
        """Generates or updates the local settings.json configuration file.

        The settings.json is updated non-destructively by merging new fields
        without erasing existing custom user configurations.
        """
        settings_dir = os.path.expanduser("~/.gemini/antigravity-cli")
        os.makedirs(settings_dir, exist_ok=True)
        settings_path = os.path.join(settings_dir, "settings.json")

        config_payload = {}
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    config_payload = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        if self.api_key:
            config_payload["gemini_api_key"] = self.api_key

        if (
            self.workload_identity_provider
            or self.service_account
            or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        ):
            config_payload["auth_mode"] = "workload_identity"
            if self.workload_identity_provider:
                config_payload["workload_identity_provider"] = (
                    self.workload_identity_provider
                )
            if self.service_account:
                config_payload["service_account"] = self.service_account
            if self.gcp_project_id:
                config_payload["gcp_project_id"] = self.gcp_project_id
            if self.gcp_location:
                config_payload["gcp_location"] = self.gcp_location

        if config_payload:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(config_payload, f, indent=2)

    @asynccontextmanager
    async def _lease_agent(self, instructions=None):
        """Leases an Antigravity Agent inside an async context manager."""
        effective_instructions = instructions or DEFAULT_SYSTEM_INSTRUCTIONS
        if self.custom_prompt and instructions is None:
            effective_instructions += f"\n\nCustom Guidelines:\n{self.custom_prompt}"

        config_kwargs = {
            "system_instructions": effective_instructions,
            "capabilities": CapabilitiesConfig(),
        }

        if self.model:
            config_kwargs["model"] = self.model
        elif os.environ.get("INPUT_MODEL") or os.environ.get("GEMINI_MODEL"):
            config_kwargs["model"] = os.environ.get("INPUT_MODEL") or os.environ.get(
                "GEMINI_MODEL"
            )

        if self.api_key:
            config_kwargs["api_key"] = self.api_key

        if (
            not self.api_key
            or self.workload_identity_provider
            or self.service_account
            or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        ):
            config_kwargs["vertex"] = True
            project = (
                self.gcp_project_id
                or os.environ.get("GCP_PROJECT_ID")
                or os.environ.get("GOOGLE_CLOUD_PROJECT")
                or os.environ.get("GCLOUD_PROJECT")
            )
            if project:
                config_kwargs["project"] = project
            location = (
                self.gcp_location
                or os.environ.get("GCP_LOCATION")
                or os.environ.get("GOOGLE_CLOUD_REGION")
                or "global"
            )
            if location:
                config_kwargs["location"] = location

            # For Vertex AI, ensure a standard GA model is set if not explicitly specified
            if "model" not in config_kwargs or not config_kwargs["model"]:
                config_kwargs["model"] = "gemini-2.5-flash"

        config = LocalAgentConfig(**config_kwargs)

        async with Agent(config) as agent:
            yield agent

    async def run_review(
        self,
        diff_text,
        changed_lines,
        file_contexts=None,
        min_severity=None,
        min_confidence=None,
        enable_verifier=None,
    ):
        """Executes a code review on the provided diff and filters comments to added/modified lines.

        Args:
            diff_text: Unified diff of changes.
            changed_lines: Mapping of file path to changed line numbers.
            file_contexts: Optional mapping of file path to surrounding file context.
            min_severity: Minimum severity threshold ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL').
            min_confidence: Minimum confidence score to retain (1-5).
            enable_verifier: Optional boolean toggle to enable/disable Pass 2 verifier.

        Returns:
            list[dict]: A list of verified inline review comments.
        """
        self.ensure_settings_configured()
        self.last_file_contexts = file_contexts

        verifier_active = (
            enable_verifier if enable_verifier is not None else self.enable_verifier
        )
        if isinstance(verifier_active, str):
            verifier_active = verifier_active.lower() not in ("false", "0", "no")

        # Pass 1: Candidate Generation
        prompt = (
            f"Please review the following pull request unified diff:\n\n"
            f"{diff_text}\n\n"
            f"Remember, return ONLY a valid JSON array of objects "
            f"with fields: 'path', 'line', 'severity', 'confidence', 'category', 'body'."
        )

        try:
            async with self._lease_agent() as agent:
                response = await agent.chat(prompt)

                # Gather all tokens asynchronously
                text_response = "".join([token async for token in response])

                raw_json = self._extract_json_from_response(text_response)
                if not raw_json:
                    return []

                comments = json.loads(raw_json)
                if not isinstance(comments, list):
                    return []

                valid_comments = self._filter_valid_comments(comments, changed_lines)

                target_min_sev = (
                    min_severity if min_severity is not None else self.min_severity
                )
                target_min_conf = (
                    min_confidence
                    if min_confidence is not None
                    else self.min_confidence
                )

                candidates = valid_comments
                if target_min_sev is not None or target_min_conf is not None:
                    candidates = self._filter_threshold_comments(
                        valid_comments,
                        min_severity=target_min_sev or "HIGH",
                        min_confidence=(
                            target_min_conf if target_min_conf is not None else 4
                        ),
                    )

                # Token optimization: if no candidates passed Pass 1, skip Pass 2 entirely
                if not candidates:
                    return []

                # If verifier is disabled, return candidates directly
                if not verifier_active:
                    return candidates

                # Pass 2: Critic-Verifier Pass
                return await self._run_verifier_pass(
                    candidates, file_contexts, changed_lines
                )
        except (json.JSONDecodeError, RuntimeError, ValueError):
            return []

    async def _run_verifier_pass(self, candidates, file_contexts, changed_lines):
        """Executes Pass 2 (Critic-Verifier) with devil's advocate scrutiny and file context.

        Args:
            candidates: List of candidate review comments from Pass 1.
            file_contexts: Optional mapping of file path to surrounding file context.
            changed_lines: Mapping of file path to changed line numbers.

        Returns:
            list[dict]: List of verified review comments.
        """
        if not candidates:
            return []

        if file_contexts:
            formatted_contexts = [
                f"--- File: {path} ---\n{ctx}" for path, ctx in file_contexts.items()
            ]
            contexts_str = "\n\n".join(formatted_contexts)
        else:
            contexts_str = "No surrounding file contexts available."

        candidates_json = json.dumps(candidates, indent=2)
        prompt = (
            "Please scrutinize and verify the following candidate code review findings "
            "against the provided surrounding source file contexts:\n\n"
            f"Candidate Findings:\n{candidates_json}\n\n"
            f"Surrounding File Contexts:\n{contexts_str}\n\n"
            "Remember to evaluate each candidate critically. Output ONLY the raw JSON array "
            "where each object includes 'path', 'line', 'severity', 'confidence', "
            "'category', 'body', 'verified' (true/false), and 'rationale'."
        )

        try:
            async with self._lease_agent(
                instructions=VERIFIER_SYSTEM_INSTRUCTIONS
            ) as agent:
                response = await agent.chat(prompt)
                text_response = "".join([token async for token in response])
                raw_json = self._extract_json_from_response(text_response)
                if not raw_json:
                    return candidates

                verified_items = json.loads(raw_json)
                if not isinstance(verified_items, list):
                    return candidates

                approved = [
                    item
                    for item in verified_items
                    if isinstance(item, dict) and item.get("verified", True) is True
                ]
                return self._filter_valid_comments(approved, changed_lines)
        except (json.JSONDecodeError, RuntimeError, ValueError):
            return candidates

    def _extract_json_from_response(self, text):
        """Locates and extracts raw JSON arrays from conversational or markdown-wrapped LLM text."""
        # Check if the output is wrapped inside a ```json ... ``` block
        match = re.search(
            r"```(?:json)?\s*(\[\s*\{.*\}\s*\])\s*```", text, re.DOTALL | re.IGNORECASE
        )
        if match:
            return match.group(1).strip()

        # Fallback to direct extraction of anything looking like a JSON array [ ... ]
        match = re.search(r"(\[\s*\{.*\}\s*\])", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Attempt to see if the whole text is a JSON array
        stripped = text.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            return stripped

        return ""

    def _validate_markdown_suggestions(self, body):
        """Ensures that code modifications use native suggestion blocks."""
        if not body:
            return body

        # Replace standard code blocks with ```suggestion if the body suggests a code change
        # and has a non-suggestion code block.
        lower_body = body.lower()
        if any(
            keyword in lower_body
            for keyword in [
                "suggest",
                "replace",
                "instead",
                "consider",
                "change",
                "try",
                "use",
            ]
        ):

            def replace_block(match):
                lang = match.group(1)
                content = match.group(2)
                if lang and lang.strip().lower() == "suggestion":
                    return match.group(0)
                # Convert to suggestion block
                return f"```suggestion\n{content.strip()}\n```"

            # Regex to match code blocks
            body = re.sub(
                r"```([a-zA-Z]*)\n(.*?)\n```", replace_block, body, flags=re.DOTALL
            )

        return body

    @staticmethod
    def _filter_threshold_comments(comments, min_severity="HIGH", min_confidence=4):
        """Filters review comments based on minimum severity and confidence thresholds."""
        min_sev_str = str(min_severity).upper().strip() if min_severity else "HIGH"
        min_sev_score = SEVERITY_LEVELS.get(min_sev_str, SEVERITY_LEVELS["HIGH"])

        try:
            min_conf_val = int(min_confidence) if min_confidence is not None else 4
        except (ValueError, TypeError):
            min_conf_val = 4

        filtered = []
        for c in comments:
            sev_str = str(c.get("severity", "LOW")).upper().strip()
            sev_score = SEVERITY_LEVELS.get(sev_str, SEVERITY_LEVELS["LOW"])

            try:
                conf_val = int(c.get("confidence", 1))
            except (ValueError, TypeError):
                conf_val = 1

            if sev_score >= min_sev_score and conf_val >= min_conf_val:
                filtered.append(c)

        return filtered

    def _filter_valid_comments(self, comments, changed_lines):
        """Filters out suggested comments that do not target added/modified lines or files."""
        filtered = []
        for comment in comments:
            path = comment.get("path")
            line = comment.get("line")
            body = comment.get("body")

            if not path or line is None or not body:
                continue

            # Check if this file was changed and if this line number was modified
            if path in changed_lines and int(line) in changed_lines[path]:
                validated_body = self._validate_markdown_suggestions(str(body))
                item = {
                    "path": path,
                    "line": int(line),
                    "body": validated_body,
                }
                if "severity" in comment:
                    item["severity"] = str(comment["severity"]).upper().strip()
                if "confidence" in comment:
                    try:
                        item["confidence"] = int(comment["confidence"])
                    except (ValueError, TypeError):
                        item["confidence"] = 1
                if "category" in comment:
                    item["category"] = str(comment["category"]).upper().strip()

                filtered.append(item)
        return filtered
