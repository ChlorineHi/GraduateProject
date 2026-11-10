#!/usr/bin/env bash
# Run the project test suite with the virtualenv created by setup_linux.sh.
# Does not start or stop servers and does not change machine-wide configuration.
#   bash scripts/test_linux.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required and was not found on PATH" >&2
  exit 1
fi
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "error: .venv is missing. Run: bash scripts/setup_linux.sh" >&2
  exit 1
fi

export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$ROOT/.venv/bin/python" -m pytest -q --tb=line
