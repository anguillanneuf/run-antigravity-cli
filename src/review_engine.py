"""Antigravity Review Engine integration for executing AI-driven code reviews."""

import os
import json
import re
from contextlib import asynccontextmanager
from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig

DEFAULT_SYSTEM_INSTRUCTIONS = (
    "You are an elite automated code review agent. "
    "Your objective is to perform high-quality, precise, and secure "
    "code reviews on Pull Request diffs.\n\n"
    "Instructions:\n"
    "1. You will be provided with the raw unified diff format of the code changes.\n"
    "2. For any bug, security issue, styling inconsistency, or performance concern, "
    "you should generate a specific code review comment.\n"
    "3. Output format MUST be a raw JSON array of objects with exactly three fields:\n"
    "   - 'path': (string) the file path relative to repository root.\n"
    "   - 'line': (integer) the exact line number in the target/new file "
    "where the suggestion is.\n"
    "   - 'body': (string) the markdown suggestions. Include suggestion blocks if useful.\n"
    "4. Do NOT output any conversational text. Return ONLY the raw JSON array.\n"
    "5. Do NOT suggest downgrading library or GitHub Action versions unless a verified critical bug exists in that specific version."
)


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
    ):
        self.api_key = api_key
        self.workload_identity_provider = workload_identity_provider
        self.service_account = service_account
        self.gcp_project_id = gcp_project_id
        self.gcp_location = gcp_location
        self.custom_prompt = custom_prompt
        self.model = model

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
    async def _lease_agent(self):
        """Leases an Antigravity Agent inside an async context manager."""
        instructions = DEFAULT_SYSTEM_INSTRUCTIONS
        if self.custom_prompt:
            instructions += f"\n\nCustom Guidelines:\n{self.custom_prompt}"

        config_kwargs = {
            "system_instructions": instructions,
            "capabilities": CapabilitiesConfig(),
        }

        if self.model:
            config_kwargs["model"] = self.model
        elif os.environ.get("INPUT_MODEL") or os.environ.get("GEMINI_MODEL"):
            config_kwargs["model"] = (
                os.environ.get("INPUT_MODEL") or os.environ.get("GEMINI_MODEL")
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

    async def run_review(self, diff_text, changed_lines):
        """Executes a code review on the provided diff and filters comments to added/modified lines.

        Returns:
            list[dict]: A list of verified inline review comments.
        """
        self.ensure_settings_configured()

        # Prompt instruction
        prompt = (
            f"Please review the following pull request unified diff:\n\n"
            f"{diff_text}\n\n"
            f"Remember, return ONLY a valid JSON array of objects "
            f"with fields: 'path', 'line', 'body'."
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

                return self._filter_valid_comments(comments, changed_lines)
        except (json.JSONDecodeError, RuntimeError, ValueError):
            return []

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
                filtered.append(
                    {"path": path, "line": int(line), "body": validated_body}
                )
        return filtered
