#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

ensure_venv() {
  local dir="$1"
  if [[ ! -d "$dir/.venv" ]]; then
    echo "Creating venv in $dir/.venv"
    (cd "$dir" && "$PYTHON_BIN" -m venv .venv)
  fi
}

install_backend() {
  local dir="$ROOT_DIR/pds-netra-backend"
  ensure_venv "$dir"
  echo "Installing backend deps..."
  "$dir/.venv/bin/pip" install -U pip
  "$dir/.venv/bin/pip" install -e "$dir"
}

install_edge() {
  local dir="$ROOT_DIR/pds-netra-edge"
  ensure_venv "$dir"
  echo "Installing edge deps..."
  "$dir/.venv/bin/pip" install -U pip
  "$dir/.venv/bin/pip" install -r "$dir/requirements.txt"
}

install_dashboard() {
  local dir="$ROOT_DIR/pds-netra-dashboard"
  if [[ ! -d "$dir/node_modules" ]]; then
    echo "Installing dashboard deps..."
    (cd "$dir" && npm install)
  else
    echo "Dashboard deps already installed."
  fi
}

install_backend
install_edge
install_dashboard

echo "Bootstrap complete."
