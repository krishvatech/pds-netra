#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/.pdsnetra.pids"

if [[ ! -f "$PID_FILE" ]]; then
  echo "No PID file found."
  exit 0
fi

echo "Service status:"
while IFS= read -r line; do
  name="${line%%:*}"
  pid="${line##*:}"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "- $name: running (pid $pid)"
  else
    echo "- $name: stopped"
  fi
done < "$PID_FILE"
