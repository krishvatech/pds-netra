#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/pds-netra-backend"

if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
  echo "Backend venv not found. Run scripts/bootstrap.sh first."
  exit 1
fi

echo "Running Alembic migrations..."
"$BACKEND_DIR/.venv/bin/python" -m alembic -c "$BACKEND_DIR/alembic.ini" upgrade head
echo "Migrations complete."
