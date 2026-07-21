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
    "4. Do NOT output any conversational text. Return ONLY the raw JSON array."
)


class AntigravityReviewEngine:
    """Interfaces with the Google Antigravity SDK to execute automated code reviews."""

    def __init__(self, api_key=None, custom_prompt=None):
        self.api_key = api_key
        self.custom_prompt = custom_prompt

    def ensure_settings_configured(self):
        """Generates or updates the local settings.json configuration file.

        The settings.json is updated non-destructively by merging new fields
        without erasing existing custom user configurations.
        """
        settings_dir = os.path.expanduser("~/.gemini/antigravity-cli")
        os.makedirs(settings_dir, exist_ok=True)
        settings_path = os.path.join(settings_dir, "settings.json")

        if self.api_key:
            config_payload = {}
            if os.path.exists(settings_path):
                try:
                    with open(settings_path, "r", encoding="utf-8") as f:
                        config_payload = json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass
            config_payload["gemini_api_key"] = self.api_key
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(config_payload, f, indent=2)

    @asynccontextmanager
    async def _lease_agent(self):
        """Leases an Antigravity Agent inside an async context manager."""
        instructions = DEFAULT_SYSTEM_INSTRUCTIONS
        if self.custom_prompt:
            instructions += f"\n\nCustom Guidelines:\n{self.custom_prompt}"

        config = LocalAgentConfig(
            system_instructions=instructions, capabilities=CapabilitiesConfig()
        )

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
