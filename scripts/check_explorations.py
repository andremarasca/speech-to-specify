"""Checks exploration deadline governance per §14 of Cláusulas Pétreas.

Scans sandbox/ for files containing a @exploration-deadline marker comment.
Any exploration past its deadline triggers a FAIL, forcing a decision:
promote to src/, or delete.

Marker format (in any .py file):
    # @exploration-deadline 2025-03-15
    # @exploration-deadline 2025-03-15 reason: testing new parser approach

Usage:
    python scripts/check_explorations.py [--sandbox-dir sandbox]

Exit codes:
    0 = no expired explorations (or no sandbox)
    1 = expired explorations found
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

DEADLINE_PATTERN = re.compile(
    r"#\s*@exploration-deadline\s+(\d{4}-\d{2}-\d{2})" r"(?:\s+reason:\s*(.+))?",
    re.IGNORECASE,
)


def scan_explorations(
    sandbox_dir: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Scan sandbox for exploration deadlines.

    Returns (expired, active) lists of dicts with keys:
        file, deadline, reason, days_remaining (or days_overdue).
    """
    today = date.today()
    expired: list[dict[str, str]] = []
    active: list[dict[str, str]] = []

    for py_file in sorted(sandbox_dir.rglob("*.py")):
        try:
            content = py_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for match in DEADLINE_PATTERN.finditer(content):
            deadline_str = match.group(1)
            reason = match.group(2) or ""

            try:
                deadline = date.fromisoformat(deadline_str)
            except ValueError:
                continue

            rel_path = str(py_file.relative_to(sandbox_dir.parent))
            delta = (deadline - today).days

            entry = {
                "file": rel_path,
                "deadline": deadline_str,
                "reason": reason.strip(),
            }

            if delta < 0:
                entry["days_overdue"] = str(abs(delta))
                expired.append(entry)
            else:
                entry["days_remaining"] = str(delta)
                active.append(entry)

    return expired, active


def main() -> int:
    sandbox_dir = Path("sandbox")

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--sandbox-dir" and i + 1 < len(args):
            sandbox_dir = Path(args[i + 1])
            i += 2
        else:
            i += 1

    if not sandbox_dir.is_dir():
        print("[check_explorations] No sandbox/ directory found — SKIPPED.")
        return 0

    print(f"[check_explorations] Scanning {sandbox_dir}/ ...")

    expired, active = scan_explorations(sandbox_dir)

    if active:
        print(f"\n[check_explorations] {len(active)} active exploration(s):")
        for e in active:
            reason = f" — {e['reason']}" if e["reason"] else ""
            print(
                f"  ACTIVE  {e['file']}  (deadline: {e['deadline']}, "
                f"{e['days_remaining']}d remaining{reason})"
            )

    if expired:
        print(f"\n[check_explorations] {len(expired)} EXPIRED exploration(s):")
        for e in expired:
            reason = f" — {e['reason']}" if e["reason"] else ""
            print(
                f"  EXPIRED {e['file']}  (deadline: {e['deadline']}, "
                f"{e['days_overdue']}d overdue{reason})"
            )
        print(
            "\n[check_explorations] FAILED — promote to src/ or delete expired explorations."
        )
        return 1

    if not active:
        print("[check_explorations] No explorations with deadlines found.")

    print("[check_explorations] PASSED — no expired explorations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
