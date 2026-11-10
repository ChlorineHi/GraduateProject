#!/usr/bin/env bash
# UrbanNoiseLab native Linux setup. Docker is not used.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -e ".[dev]"
if [[ -f apps/web/package-lock.json ]]; then
  npm ci --prefix apps/web
else
  npm install --prefix apps/web
fi
echo "setup_linux.sh finished"
