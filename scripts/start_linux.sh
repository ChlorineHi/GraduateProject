#!/usr/bin/env bash
# Start the API and the Vite dev server on the host. No containers.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
if [[ ! -x .venv/bin/python ]]; then
  echo "missing .venv; run scripts/setup_linux.sh first" >&2
  exit 1
fi
port_open() {
  timeout 0.3 bash -c "echo >/dev/tcp/127.0.0.1/$1" >/dev/null 2>&1
}
if port_open 8000; then
  echo "port 8000 is already in use. Run scripts/stop_linux.sh before starting again." >&2
  exit 1
fi
if port_open 5173; then
  echo "port 5173 is already in use. Run scripts/stop_linux.sh before starting again." >&2
  exit 1
fi
PYTHONPATH=src .venv/bin/python -m uvicorn urbannoise.api:app --host 127.0.0.1 --port 8000 > logs/api.log 2>&1 &
echo $! > logs/api.pid
npm run dev --prefix apps/web -- --host 127.0.0.1 --port 5173 --strictPort > logs/web.log 2>&1 &
echo $! > logs/web.pid
echo "api pid $(cat logs/api.pid) on http://127.0.0.1:8000"
echo "web pid $(cat logs/web.pid) on http://127.0.0.1:5173"
