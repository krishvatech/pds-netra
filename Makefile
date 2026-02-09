SHELL := /bin/bash

PY_BACKEND := pds-netra-backend/.venv/bin/python
PY_EDGE := pds-netra-edge/.venv/bin/python

.PHONY: help setup-backend setup-edge setup-dashboard setup-local migrate docker-migrate

help:
	@echo "Targets:"
	@echo "  setup-backend    Create venv + install backend"
	@echo "  setup-edge       Create venv + install edge"
	@echo "  setup-dashboard  npm install in dashboard"
	@echo "  setup-local      Run all setup targets"
	@echo "  migrate          Run Alembic migrations (uses backend venv if present)"
	@echo "  docker-migrate   Run migrations via docker compose one-off service"

setup-backend:
	@if [ ! -x "$(PY_BACKEND)" ]; then \
		python3 -m venv pds-netra-backend/.venv; \
	fi
	@pds-netra-backend/.venv/bin/python -m pip install -U pip
	@pds-netra-backend/.venv/bin/python -m pip install -e pds-netra-backend

setup-edge:
	@if [ ! -x "$(PY_EDGE)" ]; then \
		python3 -m venv pds-netra-edge/.venv; \
	fi
	@pds-netra-edge/.venv/bin/python -m pip install -U pip
	@pds-netra-edge/.venv/bin/python -m pip install -r pds-netra-edge/requirements.txt

setup-dashboard:
	@cd pds-netra-dashboard && npm install

setup-local: setup-backend setup-edge setup-dashboard

migrate:
	@PYTHON_BIN="python3"; \
	if [ -x "$(PY_BACKEND)" ]; then PYTHON_BIN="$(PY_BACKEND)"; fi; \
	cd pds-netra-backend && $$PYTHON_BIN -m app.scripts.run_migrations

docker-migrate:
	@cd deployment && docker compose -f docker-compose.prod.yml --profile migrate run --rm migrate
