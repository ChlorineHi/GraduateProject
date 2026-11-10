#!/usr/bin/env bash
# Start uvicorn and Vite on 127.0.0.1. Logs and pid files go under logs/.
# Does not change machine-wide configuration. If a port is taken, exit without
# killing the process that owns it.
#   bash scripts/start_linux.sh
#   UNLAB_API_PORT=8010 UNLAB_WEB_PORT=5174 bash scripts/start_linux.sh
set -euo pipefail
set -m

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

load_dotenv() {
  local file="$1" line key value
  [[ -f "$file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
    [[ "$line" =~ ^(UNLAB_[A-Za-z0-9_]+)=(.*)$ ]] || continue
    key="${BASH_REMATCH[1]}"
    value="${BASH_REMATCH[2]}"
    if [[ "$value" =~ ^\".*\"$ || "$value" =~ ^\'.*\'$ ]]; then
      value="${value:1:${#value}-2}"
    fi
    if [[ -z "${!key+x}" ]]; then
      export "$key=$value"
    fi
  done <"$file"
}

port_busy() {
  local port="$1"
  "$ROOT/.venv/bin/python" -c 'import socket, sys
sock = socket.socket()
sock.settimeout(0.4)
try:
    sock.connect(("127.0.0.1", int(sys.argv[1])))
except OSError:
    raise SystemExit(1)
finally:
    sock.close()
' "$port"
}

pid_alive() {
  local pidfile="$1" pid
  [[ -f "$pidfile" ]] || return 1
  pid="$(tr -cd '0-9' <"$pidfile" || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

wait_http() {
  local url="$1" tries="$2" i
  for i in $(seq 1 "$tries"); do
    if "$ROOT/.venv/bin/python" -c 'import sys, urllib.request
url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=2) as response:
        raise SystemExit(0 if 200 <= response.status < 400 else 1)
except Exception:
    raise SystemExit(1)
' "$url"; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

load_dotenv "$ROOT/.env"

if [[ -z "${UNLAB_API_PORT:-}" ]]; then
  UNLAB_API_PORT=8000
fi
if [[ -z "${UNLAB_WEB_PORT:-}" ]]; then
  UNLAB_WEB_PORT=5173
fi
if [[ -z "${UNLAB_DATA_DIR:-}" ]]; then
  UNLAB_DATA_DIR="./data"
fi
export UNLAB_API_PORT UNLAB_WEB_PORT UNLAB_DATA_DIR

if [[ ! "$UNLAB_API_PORT" =~ ^[0-9]+$ || "$UNLAB_API_PORT" -lt 1 || "$UNLAB_API_PORT" -gt 65535 ]]; then
  echo "error: UNLAB_API_PORT must be a TCP port" >&2
  exit 1
fi
if [[ ! "$UNLAB_WEB_PORT" =~ ^[0-9]+$ || "$UNLAB_WEB_PORT" -lt 1 || "$UNLAB_WEB_PORT" -gt 65535 ]]; then
  echo "error: UNLAB_WEB_PORT must be a TCP port" >&2
  exit 1
fi
if [[ "$UNLAB_API_PORT" == "$UNLAB_WEB_PORT" ]]; then
  echo "error: UNLAB_API_PORT and UNLAB_WEB_PORT must differ" >&2
  exit 1
fi

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "error: .venv is missing. Run: bash scripts/setup_linux.sh" >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "error: npm is required and was not found on PATH" >&2
  exit 1
fi
if [[ ! -d "$ROOT/apps/web/node_modules" ]]; then
  echo "error: apps/web/node_modules is missing. Run: bash scripts/setup_linux.sh" >&2
  exit 1
fi

mkdir -p "$ROOT/logs" "$UNLAB_DATA_DIR"

if pid_alive "$ROOT/logs/api.pid" || pid_alive "$ROOT/logs/web.pid"; then
  echo "error: pid files in logs/ are still running. Run: bash scripts/stop_linux.sh" >&2
  exit 1
fi
rm -f "$ROOT/logs/api.pid" "$ROOT/logs/web.pid"

if port_busy "$UNLAB_API_PORT"; then
  echo "error: 127.0.0.1:${UNLAB_API_PORT} is already in use. Not killing it." >&2
  echo "       Set UNLAB_API_PORT to a free port and start again." >&2
  exit 1
fi
if port_busy "$UNLAB_WEB_PORT"; then
  echo "error: 127.0.0.1:${UNLAB_WEB_PORT} is already in use. Not killing it." >&2
  echo "       Set UNLAB_WEB_PORT to a free port and start again." >&2
  exit 1
fi

export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

echo "----- $(date -Is) api 127.0.0.1:${UNLAB_API_PORT} UNLAB_DATA_DIR=${UNLAB_DATA_DIR} -----" >>"$ROOT/logs/api.log"
if [[ -n "${UNLAB_JWT_SECRET+x}" ]]; then
  echo "UNLAB_JWT_SECRET is set for this process. The value is not written to the log. Demo passwords stay demo-only."
else
  echo "UNLAB_JWT_SECRET is unset. The application demo default will be used. Demo only."
fi
echo "----- $(date -Is) web 127.0.0.1:${UNLAB_WEB_PORT} proxy UNLAB_API_PORT=${UNLAB_API_PORT} -----" >>"$ROOT/logs/web.log"

nohup "$ROOT/.venv/bin/python" -m uvicorn urbannoise.api:app --host 127.0.0.1 --port "$UNLAB_API_PORT" >>"$ROOT/logs/api.log" 2>&1 </dev/null &
echo $! >"$ROOT/logs/api.pid"
disown "$!" 2>/dev/null || true

nohup bash -c 'cd "$1" && exec npm run dev -- --host 127.0.0.1 --port "$2" --strictPort' _ "$ROOT/apps/web" "$UNLAB_WEB_PORT" >>"$ROOT/logs/web.log" 2>&1 </dev/null &
echo $! >"$ROOT/logs/web.pid"
disown "$!" 2>/dev/null || true

if ! wait_http "http://127.0.0.1:${UNLAB_API_PORT}/api/health" 180; then
  echo "error: API did not become healthy. Last lines of logs/api.log:" >&2
  tail -n 40 "$ROOT/logs/api.log" >&2 || true
  bash "$ROOT/scripts/stop_linux.sh" || true
  exit 1
fi
if ! wait_http "http://127.0.0.1:${UNLAB_WEB_PORT}/" 180; then
  echo "error: Vite did not become ready. Last lines of logs/web.log:" >&2
  tail -n 40 "$ROOT/logs/web.log" >&2 || true
  bash "$ROOT/scripts/stop_linux.sh" || true
  exit 1
fi

echo "api  http://127.0.0.1:${UNLAB_API_PORT}/api/health"
echo "web  http://127.0.0.1:${UNLAB_WEB_PORT}/"
echo "logs $ROOT/logs/api.log $ROOT/logs/web.log"
echo "stop bash scripts/stop_linux.sh"
