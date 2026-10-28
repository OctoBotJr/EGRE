#!/usr/bin/env bash
# The loop's gate. Nothing is committed unless this passes.
set -euo pipefail
cd "$(dirname "$0")/.."
FULL=0; [[ "${1:-}" == "--full" ]] && FULL=1
echo "[verify] ruff";   python -m ruff check src tests
echo "[verify] mypy";   python -m mypy src
echo "[verify] pytest"
if [[ $FULL -eq 1 ]]; then python -m pytest; else python -m pytest -m "not toolchain"; fi
echo "[verify] OK"
