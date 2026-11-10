#!/usr/bin/env bash
# Create a project-local virtualenv and install apps/web dependencies.
# Does not change machine-wide configuration (no system pip, no profile edits).
#   bash scripts/setup_linux.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required and was not found on PATH" >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "error: npm is required and was not found on PATH" >&2
  exit 1
fi
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "error: python3 >= 3.11 is required" >&2
  python3 --version >&2 || true
  exit 1
fi

if [[ ! -d "$ROOT/.venv" ]]; then
  python3 -m venv "$ROOT/.venv"
fi

"$ROOT/.venv/bin/python" -m pip install -e ".[dev]"
(cd "$ROOT/apps/web" && npm install)

mkdir -p "$ROOT/logs" "$ROOT/data"
if [[ ! -f "$ROOT/.env" && -f "$ROOT/.env.example" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "created .env from .env.example inside the repository"
fi

echo "setup complete"
echo "UNLAB_DATA_DIR is the local data directory (default ./data)."
echo "UNLAB_JWT_SECRET in .env.example is demo-only. Replace it before any non-demo use."
echo "Demo account passwords in README.md are demo-only."
