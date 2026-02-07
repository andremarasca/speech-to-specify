"""Validates file size limits per §8 of Cláusulas Pétreas.

Rules:
  - WARNING at >200 lines (candidate for split)
  - ERROR at >300 lines (must be split)
  - Excludes __init__.py and migration files.

Usage:
    python scripts/check_file_sizes.py [--src-dir src] [--warn 200] [--error 300]

Exit codes:
    0 = all files within limits
    1 = files exceed error threshold
"""

from __future__ import annotations

import sys
from pathlib import Path

DEFAULT_WARN = 200
DEFAULT_ERROR = 300
EXCLUDED_FILENAMES = {"__init__.py", "conftest.py"}


def count_lines(filepath: Path) -> int:
    """Count non-blank lines in a Python file."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return 0
    return len([line for line in content.splitlines() if line.strip()])


def check_file_sizes(
    src_dir: Path,
    warn_threshold: int = DEFAULT_WARN,
    error_threshold: int = DEFAULT_ERROR,
) -> tuple[list[str], list[str]]:
    """Check all .py files for size violations.

    Returns (warnings, errors) as lists of formatted strings.
    """
    warnings: list[str] = []
    errors: list[str] = []

    py_files = sorted(src_dir.rglob("*.py"))

    for filepath in py_files:
        if filepath.name in EXCLUDED_FILENAMES:
            continue

        line_count = count_lines(filepath)

        if line_count > error_threshold:
            rel_path = filepath.relative_to(src_dir.parent)
            errors.append(
                f"  ERROR  {rel_path}: {line_count} lines "
                f"(limit: {error_threshold})"
            )
        elif line_count > warn_threshold:
            rel_path = filepath.relative_to(src_dir.parent)
            warnings.append(
                f"  WARN   {rel_path}: {line_count} lines "
                f"(soft limit: {warn_threshold})"
            )

    return warnings, errors


def main() -> int:
    src_dir = Path("src")
    warn_limit = DEFAULT_WARN
    error_limit = DEFAULT_ERROR

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--src-dir" and i + 1 < len(args):
            src_dir = Path(args[i + 1])
            i += 2
        elif args[i] == "--warn" and i + 1 < len(args):
            warn_limit = int(args[i + 1])
            i += 2
        elif args[i] == "--error" and i + 1 < len(args):
            error_limit = int(args[i + 1])
            i += 2
        else:
            i += 1

    if not src_dir.is_dir():
        print(f"[check_file_sizes] Directory not found: {src_dir}")
        return 1

    print(
        f"[check_file_sizes] Scanning {src_dir}/ (warn>{warn_limit}, error>{error_limit}) ..."
    )

    warnings, errors = check_file_sizes(src_dir, warn_limit, error_limit)

    if warnings:
        print(f"\n[check_file_sizes] {len(warnings)} file(s) above soft limit:")
        for w in warnings:
            print(w)

    if errors:
        print(f"\n[check_file_sizes] {len(errors)} file(s) above hard limit:")
        for e in errors:
            print(e)
        print(f"\n[check_file_sizes] FAILED — {len(errors)} file(s) must be split.")
        return 1

    if warnings:
        print(f"\n[check_file_sizes] PASSED with {len(warnings)} warning(s).")
    else:
        print("[check_file_sizes] PASSED — all files within limits.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
