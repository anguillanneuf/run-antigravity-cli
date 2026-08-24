#!/usr/bin/env python3
"""Resolve and filter changed PR files for CodeMender security scan."""

import argparse
import os
import subprocess
from typing import List, Optional

DEFAULT_SUPPORTED_EXTENSIONS: List[str] = [
    ".py", ".java", ".go", ".js", ".ts", ".c", ".cc", ".cpp", ".h", ".rb", ".php"
]

DEFAULT_EXCLUDE_DIRS: List[str] = [
    "node_modules", "vendor", "dist", "bin", ".git", ".venv", "__pycache__", ".github"
]

DEFAULT_EXCLUDE_FILES: List[str] = [
    ".min.js", ".generated.go", ".pb.go"
]


def filter_scan_files(
    files: List[str],
    extensions: Optional[List[str]] = None,
    exclude_dirs: Optional[List[str]] = None,
    exclude_files: Optional[List[str]] = None,
) -> List[str]:
    """Filter a list of file paths by allowed extensions and excluded directories/files."""
    allowed_exts = extensions if extensions is not None else DEFAULT_SUPPORTED_EXTENSIONS
    excluded_dirs = exclude_dirs if exclude_dirs is not None else DEFAULT_EXCLUDE_DIRS
    excluded_files = exclude_files if exclude_files is not None else DEFAULT_EXCLUDE_FILES

    filtered: List[str] = []
    for file_path in files:
        # Normalize path separators
        norm_path = os.path.normpath(file_path)
        parts = norm_path.split(os.sep)

        # Check if in excluded directory
        if any(part in excluded_dirs for part in parts):
            continue

        filename = os.path.basename(norm_path)
        # Check excluded filename suffixes
        if any(filename.endswith(suffix) for suffix in excluded_files):
            continue

        # Check file extension
        _, ext = os.path.splitext(filename)
        if ext in allowed_exts:
            filtered.append(norm_path)

    return filtered


def get_changed_files_from_git(base_ref: str = "origin/main", head_ref: str = "HEAD") -> List[str]:
    """Run git diff against base ref to retrieve changed files."""
    try:
        cmd = ["git", "diff", "--name-only", f"{base_ref}...{head_ref}"]
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        files = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
        return files
    except Exception:
        # Fallback to two-dot diff or empty list if git diff fails
        try:
            cmd = ["git", "diff", "--name-only", base_ref, head_ref]
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
        except Exception:
            return []


def resolve_target_scan_files(
    base_ref: str = "origin/main",
    head_ref: str = "HEAD",
    root_dir: str = ".",
    extensions: Optional[List[str]] = None,
    full_scan: bool = False,
    absolute: bool = False,
) -> List[str]:
    """Resolve target files to be scanned based on diff or full scan mode."""
    if full_scan:
        all_files: List[str] = []
        for root, dirs, filenames in os.walk(root_dir):
            # Prune excluded dirs in-place
            dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDE_DIRS]
            for fn in filenames:
                rel_path = os.path.relpath(os.path.join(root, fn), root_dir)
                all_files.append(rel_path)
        files = filter_scan_files(all_files, extensions=extensions)
    else:
        changed = get_changed_files_from_git(base_ref=base_ref, head_ref=head_ref)
        files = filter_scan_files(changed, extensions=extensions)

    if absolute:
        abs_root = os.path.abspath(root_dir)
        return [os.path.abspath(os.path.join(abs_root, f)) for f in files]
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve target files for CodeMender scan.")
    parser.add_argument("--base-ref", default=os.getenv("GITHUB_BASE_REF", "origin/main"), help="Git base ref")
    parser.add_argument("--head-ref", default=os.getenv("GITHUB_SHA", "HEAD"), help="Git head ref")
    parser.add_argument("--root-dir", default=".", help="Root directory for file resolution")
    parser.add_argument("--full", action="store_true", default=False, help="Perform full repo scan")
    parser.add_argument("--absolute", action="store_true", default=False, help="Output absolute file paths for CLI invocation")
    parser.add_argument("--output-github-env", action="store_true", default=False, help="Write output to GITHUB_OUTPUT")

    args = parser.parse_args()
    target_files = resolve_target_scan_files(
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        root_dir=args.root_dir,
        full_scan=args.full,
        absolute=args.absolute,
    )

    file_list_str = " ".join(target_files)
    count = len(target_files)

    print(f"Resolved {count} files for CodeMender scan:")
    for f in target_files:
        print(f"  - {f}")

    if args.output_github_env and "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as gh_out:
            gh_out.write(f"file_count={count}\n")
            gh_out.write(f"files={file_list_str}\n")


if __name__ == "__main__":
    main()
