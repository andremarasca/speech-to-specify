"""Orchestrates all clause enforcement checks per §1 of Cláusulas Pétreas.

Runs each check in sequence. Stops on first failure unless --continue is set.
Also runs mypy and pytest if available.

Usage:
    python scripts/check_all.py [--continue] [--skip-tests] [--skip-mypy]

Exit codes:
    0 = all checks passed
    1 = one or more checks failed
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent


def _find_python() -> str:
    """Return the Python executable path."""
    return sys.executable


def _run_step(
    name: str,
    cmd: list[str],
    continue_on_fail: bool,
) -> bool:
    """Run a single step, printing status.

    Returns True if step passed, False if failed.
    """
    print(f"\n{'='*60}")
    print(f"  [{name}]")
    print(f"{'='*60}\n")

    start = time.monotonic()

    try:
        result = subprocess.run(
            cmd,
            capture_output=False,
            text=True,
        )
        elapsed = time.monotonic() - start
        passed = result.returncode == 0
    except FileNotFoundError:
        elapsed = time.monotonic() - start
        print(f"  Command not found: {cmd[0]}")
        passed = False

    status = "PASSED" if passed else "FAILED"
    print(f"\n  [{name}] {status} ({elapsed:.1f}s)")

    if not passed and not continue_on_fail:
        print(f"\n  Stopping at [{name}]. Use --continue to run all checks.")

    return passed


def main() -> int:
    python = _find_python()
    continue_on_fail = False
    skip_tests = False
    skip_mypy = False

    for arg in sys.argv[1:]:
        if arg == "--continue":
            continue_on_fail = True
        elif arg == "--skip-tests":
            skip_tests = True
        elif arg == "--skip-mypy":
            skip_mypy = True

    steps: list[tuple[str, list[str]]] = []

    # 1. Type checking (mypy)
    if not skip_mypy:
        steps.append(("mypy", [python, "-m", "mypy", "src/"]))

    # 2. Unit tests (pytest)
    if not skip_tests:
        steps.append(("pytest", [python, "-m", "pytest", "tests/", "-x", "-q"]))

    # 3. Import boundary check
    check_imports = SCRIPTS_DIR / "check_imports.py"
    if check_imports.is_file():
        steps.append(("check_imports", [python, str(check_imports)]))

    # 4. File size check
    check_sizes = SCRIPTS_DIR / "check_file_sizes.py"
    if check_sizes.is_file():
        steps.append(("check_file_sizes", [python, str(check_sizes)]))

    # 5. Module map generation
    generate_map = SCRIPTS_DIR / "generate_map.py"
    if generate_map.is_file():
        steps.append(("generate_map", [python, str(generate_map)]))

    # 6. Environment validation
    validate_env = SCRIPTS_DIR / "validate_env.py"
    if validate_env.is_file():
        steps.append(("validate_env", [python, str(validate_env)]))

    # 7. Exploration deadline check
    check_exp = SCRIPTS_DIR / "check_explorations.py"
    if check_exp.is_file():
        steps.append(("check_explorations", [python, str(check_exp)]))

    print("=" * 60)
    print("  check_all — Cláusulas Pétreas Enforcement Pipeline")
    print(f"  {len(steps)} step(s) to run")
    print("=" * 60)

    results: dict[str, bool] = {}
    failed = False

    for name, cmd in steps:
        passed = _run_step(name, cmd, continue_on_fail)
        results[name] = passed
        if not passed:
            failed = True
            if not continue_on_fail:
                break

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")

    for name, passed in results.items():
        icon = "✓" if passed else "✗"
        print(f"  {icon} {name}")

    not_run = [name for name, _ in steps if name not in results]
    for name in not_run:
        print(f"  - {name} (skipped)")

    passed_count = sum(1 for v in results.values() if v)
    failed_count = sum(1 for v in results.values() if not v)
    skipped_count = len(not_run)

    print(
        f"\n  {passed_count} passed, {failed_count} failed, " f"{skipped_count} skipped"
    )
    print(f"{'='*60}\n")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
