#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
PID_FILE="$ROOT_DIR/.pdsnetra.pids"

mkdir -p "$LOG_DIR"

start_cmd() {
  local name="$1"
  local cmd="$2"
  local log="$LOG_DIR/$name.log"
  echo "Starting $name..."
  nohup bash -lc "$cmd" >"$log" 2>&1 &
  echo "$name:$!" >>"$PID_FILE"
}

if [[ -f "$PID_FILE" ]]; then
  echo "PID file exists at $PID_FILE. Run scripts/stack-down.sh first."
  exit 1
fi

AUTO_BOOTSTRAP="${AUTO_BOOTSTRAP:-true}"
if [[ "$AUTO_BOOTSTRAP" != "false" ]]; then
  echo "Running bootstrap..."
  bash "$ROOT_DIR/scripts/bootstrap.sh"
fi

echo "Starting Mosquitto (docker compose)..."
(cd "$ROOT_DIR/pds-netra-edge" && docker compose up -d mosquitto)

AUTO_DB_MIGRATE="${AUTO_DB_MIGRATE:-true}"
if [[ "$AUTO_DB_MIGRATE" != "false" ]]; then
  bash "$ROOT_DIR/scripts/db-migrate.sh"
fi

start_cmd "backend" "cd \"$ROOT_DIR/pds-netra-backend\" && uvicorn app.main:app --reload --host 0.0.0.0 --port 8001"

echo "Running edge auto-setup..."
(cd "$ROOT_DIR/pds-netra-edge" && python tools/auto_setup.py --config config/pds_netra_config.yaml || true)

start_cmd "edge" "cd \"$ROOT_DIR/pds-netra-edge\" && EDGE_RULES_SOURCE=backend python -m app.main --config config/pds_netra_config.yaml --device cpu --log-level INFO"

start_cmd "dashboard" "cd \"$ROOT_DIR/pds-netra-dashboard\" && npm run dev"

echo "All services started."
echo "Logs: $LOG_DIR"
echo "PIDs: $PID_FILE"
