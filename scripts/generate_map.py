"""Generates a module map from src/ docstrings (§23 of Cláusulas Pétreas).

Reads every .py file under src/, extracts the module-level docstring,
and generates docs/map.md with a structured index.

Usage:
    python scripts/generate_map.py [--src-dir src] [--output docs/map.md]

Exit codes:
    0 = map generated successfully
    1 = src directory not found
"""

from __future__ import annotations

import ast
import sys
from datetime import datetime, timezone
from pathlib import Path


def extract_docstring(filepath: Path) -> str | None:
    """Extract the module-level docstring from a Python file."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return None

    return ast.get_docstring(tree)


def count_non_blank_lines(filepath: Path) -> int:
    try:
        content = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return 0
    return len([line for line in content.splitlines() if line.strip()])


def group_by_package(
    src_dir: Path,
) -> dict[str, list[tuple[Path, str | None, int]]]:
    """Group .py files by their top-level package within src/.

    Returns a dict: package_name -> [(filepath, docstring, line_count), ...]
    """
    packages: dict[str, list[tuple[Path, str | None, int]]] = {}

    for py_file in sorted(src_dir.rglob("*.py")):
        if py_file.name == "__init__.py":
            continue

        rel = py_file.relative_to(src_dir)
        parts = rel.parts
        package = parts[0] if len(parts) > 1 else "(root)"

        docstring = extract_docstring(py_file)
        line_count = count_non_blank_lines(py_file)

        packages.setdefault(package, []).append((py_file, docstring, line_count))

    return packages


def generate_map(src_dir: Path) -> str:
    """Generate the markdown content for the module map."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    packages = group_by_package(src_dir)

    lines = [
        "# Mapa de Módulos",
        "",
        f"> Gerado automaticamente em {now} por `scripts/generate_map.py`.",
        "> Não edite manualmente — será sobrescrito na próxima execução.",
        "",
    ]

    total_modules = 0
    undocumented = 0

    for package_name in sorted(packages):
        entries = packages[package_name]
        lines.append(f"## {package_name}/")
        lines.append("")
        lines.append("| Módulo | Linhas | Descrição |")
        lines.append("|--------|--------|-----------|")

        for filepath, docstring, line_count in entries:
            rel = filepath.relative_to(src_dir)
            module_name = str(rel).replace("\\", "/")
            first_line = ""
            if docstring:
                first_line = docstring.split("\n")[0].strip()
            else:
                first_line = "⚠️ _sem docstring_"
                undocumented += 1

            total_modules += 1
            lines.append(f"| `{module_name}` | {line_count} | {first_line} |")

        lines.append("")

    # Summary
    lines.append("---")
    lines.append("")
    lines.append(
        f"**Total:** {total_modules} módulos | " f"{undocumented} sem docstring"
    )
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    src_dir = Path("src")
    output = Path("docs/map.md")

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--src-dir" and i + 1 < len(args):
            src_dir = Path(args[i + 1])
            i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output = Path(args[i + 1])
            i += 2
        else:
            i += 1

    if not src_dir.is_dir():
        print(f"[generate_map] Directory not found: {src_dir}")
        return 1

    print(f"[generate_map] Scanning {src_dir}/ ...")

    content = generate_map(src_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")

    print(f"[generate_map] Map generated at {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
