FRONTEND_DIR := aegis-frontend
BACKEND_DIR := aegis-backend
PROXY_DIR := reverse-proxy
NPM := npm --prefix $(FRONTEND_DIR)
PYTHON := $(BACKEND_DIR)/.venv/bin/python
COMPOSE := docker compose

.DEFAULT_GOAL := help

.PHONY: help init credentials dev up services backend proxy frontend stop clean \
	check backend-test proxy-test frontend-install frontend-build frontend-lint \
	frontend-test e2e

help:
	@echo "Available commands:"
	@echo "  make init              Generate ignored local secrets in .env"
	@echo "  make up                Build and run the full Docker Compose stack"
	@echo "  make dev               Run services plus local backend/proxy/frontend"
	@echo "  make credentials       Show the generated local Admin login"
	@echo "  make check             Run all Python, Go, and frontend checks"
	@echo "  make e2e               Run isolated Control Plane -> proxy -> upstream E2E"
	@echo "  make stop              Stop the Compose stack (preserve data)"
	@echo "  make clean             Stop the stack and remove its data volumes"

.env:
	@umask 077; python3 scripts/generate_env.py > .env.tmp
	@mv .env.tmp .env
	@echo "Generated .env with unique local secrets."

init: .env

credentials: .env
	@set -a; . ./.env; set +a; \
	echo "Email: $$BOOTSTRAP_ADMIN_EMAILS"; \
	echo "Password: $$BOOTSTRAP_ADMIN_PASSWORD"

up: .env
	$(COMPOSE) up --detach --build --wait
	@echo "Dashboard: http://localhost:$$(awk -F= '/^DASHBOARD_PORT=/{print $$2}' .env)/login"
	@echo "Proxy:     http://localhost:$$(awk -F= '/^PROXY_PORT=/{print $$2}' .env)"

dev: services
	$(MAKE) -j3 backend proxy frontend

services: .env
	$(COMPOSE) up --detach --wait postgres redis upstream

backend: .env
	@set -a; . ./.env; set +a; \
	export DATABASE_URL="postgresql+asyncpg://aegis:$$POSTGRES_PASSWORD@localhost:$$POSTGRES_PORT/aegis"; \
	export REDIS_HOST=localhost REDIS_PORT="$$REDIS_PORT"; \
	cd $(BACKEND_DIR) && ../$(PYTHON) -m alembic upgrade head && \
	exec ../$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port "$$CONTROL_PLANE_PORT" --reload

proxy: .env
	@set -a; . ./.env; set +a; \
	export BACKEND_URL="http://localhost:$$UPSTREAM_PORT"; \
	export CONTROL_PLANE_URL="http://localhost:$$CONTROL_PLANE_PORT"; \
	export REDIS_ADDR="localhost:$$REDIS_PORT"; \
	cd $(PROXY_DIR) && exec go run ./cmd/proxy

frontend:
	$(NPM) run dev

stop: .env
	$(COMPOSE) down

clean: .env
	$(COMPOSE) down --volumes --remove-orphans

backend-test:
	cd $(BACKEND_DIR) && ../$(PYTHON) -m pytest -q

proxy-test:
	cd $(PROXY_DIR) && go test -race ./... && go vet ./... && test -z "$$(gofmt -l .)"

frontend-install:
	$(NPM) ci

frontend-build:
	$(NPM) run build

frontend-lint:
	$(NPM) run lint

frontend-test:
	$(NPM) test

check: backend-test proxy-test frontend-lint frontend-test

e2e:
	./scripts/e2e.sh
