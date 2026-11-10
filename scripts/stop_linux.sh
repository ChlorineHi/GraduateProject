#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
stop_pid() {
  local file="$1"
  if [[ -f "$file" ]]; then
    local pid
    pid="$(cat "$file")"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$file"
  fi
}
stop_pid logs/api.pid
stop_pid logs/web.pid
# Earlier sessions of this repo may have been started without a pid file.
if command -v fuser >/dev/null 2>&1; then
  fuser -k 8000/tcp >/dev/null 2>&1 || true
  fuser -k 5173/tcp >/dev/null 2>&1 || true
else
  pkill -f "uvicorn urbannoise.api:app --host 127.0.0.1 --port 8000" >/dev/null 2>&1 || true
  pkill -f "vite --host 127.0.0.1 --port 5173" >/dev/null 2>&1 || true
fi
echo "stop_linux.sh finished"
