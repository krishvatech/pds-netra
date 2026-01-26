#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/.pdsnetra.pids"

if [[ ! -f "$PID_FILE" ]]; then
  echo "No PID file found."
  exit 0
fi

while IFS= read -r line; do
  name="${line%%:*}"
  pid="${line##*:}"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "Stopping $name ($pid)..."
    kill "$pid" || true
  fi
done < "$PID_FILE"

rm -f "$PID_FILE"

echo "Stopping Mosquitto (docker compose)..."
(cd "$ROOT_DIR/pds-netra-edge" && docker compose down)

echo "Done."
