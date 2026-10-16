"""Context-Aware File Expansion resolver.

Provides full or windowed file context to review engines.
"""

# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals

import os
import re
from typing import Any, Dict, List, Optional


def extract_file_diffs(diff_text: str) -> Dict[str, str]:
    """Partitions a unified diff into individual diff blocks mapped by target file path.

    Args:
        diff_text: The complete unified diff string.

    Returns:
        Dict[str, str]: Mapping of file path to the diff text for that file.
    """
    file_diffs: Dict[str, List[str]] = {}
    current_file: Optional[str] = None
    git_diff_pattern = re.compile(r"^diff --git a/.*? b/(.*)$")
    plus_pattern = re.compile(r"^\+\+\+ b/(.*)$")

    for line in diff_text.splitlines(keepends=True):
        git_match = git_diff_pattern.match(line)
        plus_match = plus_pattern.match(line)

        if git_match:
            current_file = git_match.group(1).strip()
            if current_file not in file_diffs:
                file_diffs[current_file] = []
        elif plus_match:
            current_file = plus_match.group(1).strip()
            if current_file not in file_diffs:
                file_diffs[current_file] = []

        if current_file:
            file_diffs[current_file].append(line)

    return {k: "".join(v) for k, v in file_diffs.items() if v}


class ContextResolver:
    """Resolves local or remote file context around changed lines to cure diff myopia."""

    def __init__(
        self,
        base_dir: Optional[str] = None,
        github_client: Any = None,
        ref: Optional[str] = None,
        max_whole_file_lines: int = 1000,
        hunk_padding: int = 100,
    ):
        self.base_dir = base_dir or os.getcwd()
        self.github_client = github_client
        self.ref = ref
        self.max_whole_file_lines = max_whole_file_lines
        self.hunk_padding = hunk_padding

    def resolve_context_for_file(
        self,
        file_path: str,
        changed_lines: Optional[List[int]] = None,
        diff_content: Optional[str] = None,
    ) -> str:
        """Resolves file context for a single file.

        Files with fewer than max_whole_file_lines lines are loaded in full with line numbers.
        Files with max_whole_file_lines or more lines are sliced into windows around changed lines.
        If the file cannot be found on disk, attempts remote retrieval via github_client,
        falling back to the diff content if available.
        """
        raw_lines = self._load_file_lines(file_path)

        if raw_lines is None:
            if diff_content:
                return (
                    f"// Context: File '{file_path}' unavailable on disk. "
                    f"Falling back to diff:\n{diff_content}"
                )
            return f"// Context: File '{file_path}' not found / unavailable."

        total_lines = len(raw_lines)
        if total_lines == 0:
            return f"// File '{file_path}' is empty (0 lines)."

        if total_lines < self.max_whole_file_lines:
            return self._format_numbered_lines(raw_lines, 1, total_lines)

        return self._slice_windowed_context(raw_lines, changed_lines)

    def _load_file_lines(self, file_path: str) -> Optional[List[str]]:
        """Attempts to load file lines from local workspace or remote GitHub client."""
        try:
            base_dir_resolved = os.path.realpath(self.base_dir)
            full_path = os.path.realpath(os.path.join(base_dir_resolved, file_path))
            if (
                os.path.commonpath([base_dir_resolved, full_path]) != base_dir_resolved
                or full_path == base_dir_resolved
            ):
                return None
        except (ValueError, TypeError):
            return None

        if os.path.isfile(full_path):
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    return f.readlines()
            except (IOError, OSError):
                pass

        if self.github_client and hasattr(self.github_client, "fetch_file_content"):
            try:
                content = self.github_client.fetch_file_content(file_path, ref=self.ref)
                return content.splitlines(keepends=True)
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        return None

    @staticmethod
    def _format_numbered_lines(lines: List[str], start_line: int, end_line: int) -> str:
        """Formats a subset of lines with line number prefixes (e.g. '1: def foo():')."""
        formatted = []
        for idx in range(start_line, end_line + 1):
            line_str = lines[idx - 1].rstrip("\r\n")
            formatted.append(f"{idx}: {line_str}")
        return "\n".join(formatted)

    def _slice_windowed_context(
        self, raw_lines: List[str], changed_lines: Optional[List[int]]
    ) -> str:
        """Slices context windows (+/- hunk_padding) around changed lines and merges overlaps."""
        total_lines = len(raw_lines)
        valid_changed = sorted(
            {
                line_no
                for line_no in (changed_lines or [])
                if 1 <= line_no <= total_lines
            }
        )

        if not valid_changed:
            end_line = min(total_lines, self.hunk_padding * 2)
            header = self._format_numbered_lines(raw_lines, 1, end_line)
            if end_line < total_lines:
                return f"{header}\n... [lines {end_line + 1}-{total_lines} omitted] ..."
            return header

        # Calculate padded intervals
        intervals: List[tuple[int, int]] = []
        for line_no in valid_changed:
            start = max(1, line_no - self.hunk_padding)
            end = min(total_lines, line_no + self.hunk_padding)
            intervals.append((start, end))

        # Merge overlapping or touching intervals
        merged: List[tuple[int, int]] = []
        for start, end in intervals:
            if not merged:
                merged.append((start, end))
            else:
                prev_start, prev_end = merged[-1]
                if start <= prev_end + 1:
                    merged[-1] = (prev_start, max(prev_end, end))
                else:
                    merged.append((start, end))

        # Build output with omission markers
        output_parts: List[str] = []
        last_end = 0

        for start, end in merged:
            if start > last_end + 1:
                omitted_start = last_end + 1
                omitted_end = start - 1
                output_parts.append(
                    f"... [lines {omitted_start}-{omitted_end} omitted] ..."
                )
            output_parts.append(self._format_numbered_lines(raw_lines, start, end))
            last_end = end

        if last_end < total_lines:
            output_parts.append(f"... [lines {last_end + 1}-{total_lines} omitted] ...")

        return "\n".join(output_parts)

    def resolve_contexts_for_diff(
        self, diff_text: str, changed_lines: Optional[Dict[str, List[int]]] = None
    ) -> Dict[str, str]:
        """Resolves file contexts for all files present in the diff or changed_lines mapping."""
        file_diffs = extract_file_diffs(diff_text)
        all_files = set(file_diffs.keys())
        if changed_lines:
            all_files.update(changed_lines.keys())

        contexts = {}
        for fpath in sorted(all_files):
            f_changed = changed_lines.get(fpath) if changed_lines else None
            f_diff = file_diffs.get(fpath)
            contexts[fpath] = self.resolve_context_for_file(
                file_path=fpath,
                changed_lines=f_changed,
                diff_content=f_diff,
            )
        return contexts


def resolve_file_context(
    file_path: str,
    changed_lines: Optional[List[int]] = None,
    base_dir: Optional[str] = None,
    max_whole_file_lines: int = 1000,
    hunk_padding: int = 100,
    diff_content: Optional[str] = None,
    github_client: Any = None,
    ref: Optional[str] = None,
) -> str:
    """Resolves surrounding file context for a single file path."""
    resolver = ContextResolver(
        base_dir=base_dir,
        github_client=github_client,
        ref=ref,
        max_whole_file_lines=max_whole_file_lines,
        hunk_padding=hunk_padding,
    )
    return resolver.resolve_context_for_file(
        file_path=file_path,
        changed_lines=changed_lines,
        diff_content=diff_content,
    )


def resolve_contexts_for_diff(
    diff_text: str,
    changed_lines: Optional[Dict[str, List[int]]] = None,
    base_dir: Optional[str] = None,
    max_whole_file_lines: int = 1000,
    hunk_padding: int = 100,
    github_client: Any = None,
    ref: Optional[str] = None,
) -> Dict[str, str]:
    """Resolves surrounding file contexts for all files referenced in a unified diff."""
    resolver = ContextResolver(
        base_dir=base_dir,
        github_client=github_client,
        ref=ref,
        max_whole_file_lines=max_whole_file_lines,
        hunk_padding=hunk_padding,
    )
    return resolver.resolve_contexts_for_diff(
        diff_text=diff_text,
        changed_lines=changed_lines,
    )
