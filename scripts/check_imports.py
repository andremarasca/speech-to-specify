"""Validates hexagonal architecture import rules.

Rules enforced (per §5 of Cláusulas Pétreas):
  - domain/  → imports nothing from ports/, adapters/, config/
  - ports/   → imports only from domain/
  - adapters/→ imports from ports/ and domain/ only
  - config/  → may import anything (composition root)
  - shared/  → imports nothing from domain/, ports/, adapters/, config/
  - No circular imports between layers.

Usage:
    python scripts/check_imports.py [--src-dir src]

Exit codes:
    0 = all imports valid
    1 = violations found
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

LAYER_ORDER = ["shared", "domain", "ports", "adapters", "config"]

ALLOWED_IMPORTS: dict[str, set[str]] = {
    "domain": set(),
    "ports": {"domain", "shared"},
    "adapters": {"ports", "domain", "shared"},
    "config": {"domain", "ports", "adapters", "shared"},
    "shared": set(),
}


def _get_layer(filepath: Path, src_dir: Path) -> str | None:
    """Determine which architectural layer a file belongs to."""
    try:
        rel = filepath.relative_to(src_dir)
    except ValueError:
        return None
    parts = rel.parts
    if not parts:
        return None
    top = parts[0]
    if top in ALLOWED_IMPORTS:
        return top
    return None


def _extract_imports(filepath: Path) -> list[str]:
    """Extract all import module names from a Python file."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return []

    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
    return modules


def _resolve_layer_from_import(module: str, src_package: str) -> str | None:
    """Given an import string, resolve which layer it targets."""
    parts = module.split(".")
    # Handle both 'src.domain.X' and 'domain.X' styles
    if parts[0] == src_package and len(parts) > 1:
        candidate = parts[1]
    elif parts[0] in ALLOWED_IMPORTS:
        candidate = parts[0]
    else:
        return None  # External package, not our concern

    return candidate if candidate in ALLOWED_IMPORTS else None


def check_imports(src_dir: Path) -> list[str]:
    """Check all .py files under src_dir for import violations.

    Returns list of violation description strings.
    """
    violations: list[str] = []
    src_package = src_dir.name  # e.g. "src"

    py_files = sorted(src_dir.rglob("*.py"))

    for filepath in py_files:
        source_layer = _get_layer(filepath, src_dir)
        if source_layer is None:
            continue

        allowed = ALLOWED_IMPORTS[source_layer]
        imports = _extract_imports(filepath)

        for module in imports:
            target_layer = _resolve_layer_from_import(module, src_package)
            if target_layer is None:
                continue  # External dependency
            if target_layer == source_layer:
                continue  # Same layer is fine
            if target_layer not in allowed:
                rel_path = filepath.relative_to(src_dir)
                violations.append(
                    f"  {rel_path} ({source_layer}/) "
                    f"imports from {target_layer}/ "
                    f"via '{module}' — FORBIDDEN"
                )

    return violations


def main() -> int:
    src_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("src")

    if not src_dir.is_dir():
        print(f"[check_imports] Directory not found: {src_dir}")
        print("[check_imports] Skipping — no hexagonal structure detected.")
        return 0

    # Check if hexagonal structure exists
    layers_present = [d for d in ALLOWED_IMPORTS if (src_dir / d).is_dir()]
    if not layers_present:
        print(
            "[check_imports] No hexagonal layers found (domain/, ports/, adapters/...)."
        )
        print("[check_imports] Skipping — structure not yet migrated.")
        return 0

    print(f"[check_imports] Scanning {src_dir}/ ...")
    print(f"[check_imports] Layers detected: {', '.join(layers_present)}")

    violations = check_imports(src_dir)

    if violations:
        print(f"\n[check_imports] FAILED — {len(violations)} import violation(s):\n")
        for v in violations:
            print(v)
        return 1

    print("[check_imports] PASSED — all imports respect hexagonal boundaries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
