#!/usr/bin/env bash
# Stop the API and Vite processes recorded under logs/.
# Signals only those pid files, and only when the command line is this app.
# Does not free a port by killing whatever else is listening.
#   bash scripts/stop_linux.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

descendants() {
  local pid="$1"
  local child
  [[ -r "/proc/${pid}/task/${pid}/children" ]] || return 0
  for child in $(<"/proc/${pid}/task/${pid}/children"); do
    descendants "$child"
    echo "$child"
  done
}

stop_one() {
  local name="$1"
  local pattern="$2"
  local pidfile="$ROOT/logs/${name}.pid"
  local pid cmd pgid self_pgid child

  if [[ ! -f "$pidfile" ]]; then
    echo "$name: no pid file"
    return 0
  fi
  pid="$(tr -cd '0-9' <"$pidfile" || true)"
  if [[ ! "$pid" =~ ^[0-9]+$ ]] || [[ "$pid" -le 1 ]]; then
    echo "error: $name pid file is invalid" >&2
    exit 1
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$pidfile"
    echo "$name: stale pid $pid removed"
    return 0
  fi
  cmd="$(tr '\0' ' ' <"/proc/${pid}/cmdline" 2>/dev/null || true)"
  if [[ ! "$cmd" =~ $pattern ]]; then
    echo "error: refusing to signal $name pid $pid; command line does not match this app" >&2
    echo "       $cmd" >&2
    exit 1
  fi

  self_pgid="$(ps -o pgid= -p $$ | tr -d '[:space:]' || true)"
  pgid="$(ps -o pgid= -p "$pid" | tr -d '[:space:]' || true)"
  if [[ -n "$pgid" && "$pgid" == "$pid" && "$pgid" != "$self_pgid" ]]; then
    kill -TERM -- "-$pgid" 2>/dev/null || true
  fi
  while IFS= read -r child; do
    [[ -n "$child" ]] || continue
    kill -TERM "$child" 2>/dev/null || true
  done < <(descendants "$pid" || true)
  kill -TERM "$pid" 2>/dev/null || true

  local i
  for i in $(seq 1 50); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.2
  done
  if kill -0 "$pid" 2>/dev/null; then
    if [[ -n "$pgid" && "$pgid" == "$pid" && "$pgid" != "$self_pgid" ]]; then
      kill -KILL -- "-$pgid" 2>/dev/null || true
    fi
    while IFS= read -r child; do
      [[ -n "$child" ]] || continue
      kill -KILL "$child" 2>/dev/null || true
    done < <(descendants "$pid" || true)
    kill -KILL "$pid" 2>/dev/null || true
    sleep 0.2
  fi
  if kill -0 "$pid" 2>/dev/null; then
    echo "error: $name pid $pid is still running" >&2
    exit 1
  fi
  rm -f "$pidfile"
  echo "$name: stopped $pid"
}

stop_one web 'vite|npm'
stop_one api 'urbannoise\.api:app'
echo "stop complete"
