#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo "missing .venv; run scripts/setup_linux.sh first" >&2
  exit 1
fi
PYTHONPATH=src .venv/bin/python -m pytest -q --tb=line
npm run build --prefix apps/web
echo "test_linux.sh finished"
