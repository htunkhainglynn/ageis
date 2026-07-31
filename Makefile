FRONTEND_DIR := aegis-frontend
BACKEND_DIR := aegis-backend
NPM := npm --prefix $(FRONTEND_DIR)
PYTHON := $(BACKEND_DIR)/.venv/bin/python
COMPOSE := docker compose

.DEFAULT_GOAL := help

.PHONY: help dev services backend frontend stop frontend-install frontend-build frontend-lint frontend-test

help:
	@echo "Available commands:"
	@echo "  make dev               Run the complete Aegis project"
	@echo "  make services          Start PostgreSQL and Redis"
	@echo "  make backend           Run the Control Plane at http://localhost:8000"
	@echo "  make frontend          Run aegis-frontend at http://localhost:3000"
	@echo "  make stop              Stop PostgreSQL and Redis"
	@echo "  make frontend-install  Reproduce dependencies from package-lock.json"
	@echo "  make frontend-build    Build aegis-frontend"
	@echo "  make frontend-lint     Lint aegis-frontend"
	@echo "  make frontend-test     Test aegis-frontend"

dev: services
	$(MAKE) -j2 backend frontend

services:
	$(COMPOSE) up -d --wait

backend:
	cd $(BACKEND_DIR) && ../$(PYTHON) -m alembic upgrade head
	cd $(BACKEND_DIR) && ../$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

frontend:
	$(NPM) run dev

stop:
	$(COMPOSE) down

frontend-install:
	$(NPM) ci

frontend-build:
	$(NPM) run build

frontend-lint:
	$(NPM) run lint

frontend-test:
	$(NPM) test
