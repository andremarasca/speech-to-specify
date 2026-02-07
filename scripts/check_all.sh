#!/usr/bin/env bash
# Cláusulas Pétreas — full enforcement pipeline (Unix/macOS)
# Usage: scripts/check_all.sh [--continue] [--skip-tests] [--skip-mypy]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

"$PYTHON" "$SCRIPT_DIR/check_all.py" "$@"
