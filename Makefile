FRONTEND_DIR := aegis-frontend
BACKEND_DIR := aegis-backend
PROXY_DIR := reverse-proxy
ECHO_DIR := poc/echo-service
ATTACK_CONSOLE_DIR := poc/attack-console
NPM := npm --prefix $(FRONTEND_DIR)
PYTHON := $(BACKEND_DIR)/.venv/bin/python
COMPOSE := docker compose
SHELL := /bin/bash

.DEFAULT_GOAL := help

.PHONY: help init credentials dev run prepare ensure-backend-deps ensure-frontend-deps up services backend proxy frontend echo attack-console stop clean reset-dev \
	check backend-test proxy-test proxy-coverage frontend-install frontend-build frontend-lint \
	frontend-test poc-test e2e

help:
	@echo "Available commands:"
	@echo "  make init              Generate ignored local secrets in .env"
	@echo "  make run               Run every local project in one foreground session"
	@echo "  make dev               Alias for make run"
	@echo "  make prepare           Install missing deps, start infra, migrate, seed dev data"
	@echo "  make up                Build and run the full Docker Compose stack"
	@echo "  make services          Start only Postgres and Redis"
	@echo "  make credentials       Show the generated local Admin login"
	@echo "  make check             Run all Python, Go, and frontend checks"
	@echo "  make e2e               Run isolated Control Plane -> proxy -> upstream E2E"
	@echo "  make stop              Stop the Compose stack (preserve data)"
	@echo "  make clean             Stop the stack and remove its data volumes"
	@echo "  make reset-dev         Reset local Postgres/Redis volumes and regenerate .env"

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

dev: run

run: prepare
	@set -Eeuo pipefail; \
	set -a; . ./.env; set +a; \
	log_dir="$$(mktemp -d "$${TMPDIR:-/tmp}/aegis-run.XXXXXX")"; \
	pids=(); \
	cleanup() { \
		status="$$?"; \
		if [ "$${#pids[@]}" -gt 0 ]; then \
			kill "$${pids[@]}" >/dev/null 2>&1 || true; \
			wait "$${pids[@]}" >/dev/null 2>&1 || true; \
		fi; \
		if [ "$$status" != "0" ]; then \
			echo ""; \
			echo "Aegis stopped with an error. Logs are in $$log_dir"; \
		else \
			rm -rf "$$log_dir"; \
		fi; \
		exit "$$status"; \
	}; \
	trap cleanup EXIT INT TERM; \
	wait_for_http() { \
		name="$$1"; \
		url="$$2"; \
		for _ in $$(seq 1 60); do \
			if curl -fsS "$$url" >/dev/null 2>&1; then \
				echo "$$name is ready: $$url"; \
				return 0; \
			fi; \
			sleep 1; \
		done; \
		echo "$$name did not become ready. Check $$log_dir"; \
		return 1; \
	}; \
	echo "Starting Aegis locally. Logs: $$log_dir"; \
	export APP_ENV=development ENVIRONMENT=development APP_DEBUG=true; \
	export DATABASE_URL="postgresql+asyncpg://aegis:$$POSTGRES_PASSWORD@localhost:$${POSTGRES_PORT:-5432}/aegis"; \
	export REDIS_HOST=localhost REDIS_PORT="$${REDIS_PORT:-6379}" REDIS_PASSWORD="$${REDIS_PASSWORD:-}"; \
	export GRPC_HOST=0.0.0.0 GRPC_PORT=50051 GRPC_ENABLED=true; \
	export AUTO_IP_BLOCK_ENABLED=false; \
	export APP_CORS_ORIGINS="http://localhost:$${DASHBOARD_PORT:-3000},http://127.0.0.1:9100,http://localhost:9100"; \
	(cd $(BACKEND_DIR) && ../$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port "$${CONTROL_PLANE_PORT:-8000}" --reload) >"$$log_dir/control-plane.log" 2>&1 & \
	pids+=("$$!"); \
	wait_for_http "Control Plane" "http://localhost:$${CONTROL_PLANE_PORT:-8000}/health"; \
	($(PYTHON) $(ECHO_DIR)/server.py) >"$$log_dir/echo-service.log" 2>&1 & \
	pids+=("$$!"); \
	wait_for_http "Echo service" "http://localhost:$${UPSTREAM_PORT:-9000}/api/echo"; \
	export LISTEN_ADDR=":$${PROXY_PORT:-8080}"; \
	export BACKEND_URL="http://localhost:$${UPSTREAM_PORT:-9000}"; \
	export CONTROL_PLANE_URL="http://localhost:$${CONTROL_PLANE_PORT:-8000}"; \
	export REDIS_ADDR="localhost:$${REDIS_PORT:-6379}"; \
	export REDIS_DB=0; \
	export GRPC_POLICY_ADDR="localhost:50051"; \
	(cd $(PROXY_DIR) && go run ./cmd/proxy) >"$$log_dir/reverse-proxy.log" 2>&1 & \
	pids+=("$$!"); \
	sleep 1; \
	PORT="$${DASHBOARD_PORT:-3000}" HOST=0.0.0.0 $(NPM) run dev >"$$log_dir/dashboard.log" 2>&1 & \
	pids+=("$$!"); \
	ATTACK_CONSOLE_PORT=9100 $(PYTHON) $(ATTACK_CONSOLE_DIR)/serve.py >"$$log_dir/attack-console.log" 2>&1 & \
	pids+=("$$!"); \
	echo ""; \
	echo "Aegis is running."; \
	echo "Dashboard:      http://localhost:$${DASHBOARD_PORT:-3000}/login"; \
	echo "Control Plane:  http://localhost:$${CONTROL_PLANE_PORT:-8000}/docs"; \
	echo "Reverse Proxy:  http://localhost:$${PROXY_PORT:-8080}/api/echo"; \
	echo "Echo Service:   http://localhost:$${UPSTREAM_PORT:-9000}/api/echo"; \
	echo "Attack Console: http://127.0.0.1:9100"; \
	echo ""; \
	echo "Use Attack Console -> Prepare demo data to auto-load keys/JWT for proxy checks."; \
	echo "Press Ctrl-C to stop local app processes. Use 'make stop' to stop Postgres/Redis."; \
	while true; do \
		for pid in "$${pids[@]}"; do \
			if ! kill -0 "$$pid" >/dev/null 2>&1; then \
				wait "$$pid"; \
				exit "$$?"; \
			fi; \
		done; \
		sleep 1; \
	done

prepare: .env ensure-backend-deps ensure-frontend-deps services
	@set -a; . ./.env; set +a; \
	export APP_ENV=development ENVIRONMENT=development; \
	export DATABASE_URL="postgresql+asyncpg://aegis:$$POSTGRES_PASSWORD@localhost:$${POSTGRES_PORT:-5432}/aegis"; \
	export REDIS_HOST=localhost REDIS_PORT="$${REDIS_PORT:-6379}" REDIS_PASSWORD="$${REDIS_PASSWORD:-}"; \
	$(PYTHON) scripts/check_dev_db.py && \
	cd $(BACKEND_DIR) && ../$(PYTHON) -m alembic upgrade head
	@set -a; . ./.env; set +a; \
	export APP_ENV=development ENVIRONMENT=development; \
	export DATABASE_URL="postgresql+asyncpg://aegis:$$POSTGRES_PASSWORD@localhost:$${POSTGRES_PORT:-5432}/aegis"; \
	export REDIS_HOST=localhost REDIS_PORT="$${REDIS_PORT:-6379}" REDIS_PASSWORD="$${REDIS_PASSWORD:-}"; \
	$(PYTHON) scripts/seed_dev_data.py

ensure-backend-deps:
	@if [ ! -x "$(PYTHON)" ]; then \
		echo "Creating backend virtualenv and installing Python dependencies..."; \
		python3 -m venv $(BACKEND_DIR)/.venv; \
		$(PYTHON) -m pip install -r $(BACKEND_DIR)/requirements.txt; \
	fi

ensure-frontend-deps:
	@if [ ! -d "$(FRONTEND_DIR)/node_modules" ]; then \
		echo "Installing frontend dependencies from package-lock.json..."; \
		$(NPM) ci; \
	fi

services: .env
	$(COMPOSE) up --detach --wait postgres redis

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
	PORT=3000 HOST=0.0.0.0 $(NPM) run dev

echo:
	$(PYTHON) $(ECHO_DIR)/server.py

attack-console:
	$(PYTHON) $(ATTACK_CONSOLE_DIR)/serve.py

stop: .env
	$(COMPOSE) down

clean: .env
	$(COMPOSE) down --volumes --remove-orphans

reset-dev:
	$(COMPOSE) down --volumes --remove-orphans
	rm -f .env
	$(MAKE) init

backend-test:
	cd $(BACKEND_DIR) && ../$(PYTHON) -m coverage run -m pytest -q
	cd $(BACKEND_DIR) && ../$(PYTHON) -m coverage report

proxy-test:
	cd $(PROXY_DIR) && go test -race ./... && go vet ./... && test -z "$$(gofmt -l .)"

proxy-coverage:
	@cd $(PROXY_DIR) && \
	go test -coverprofile=.coverage.core.out ./internal/config ./internal/controlplane ./internal/middleware ./internal/proxy >/dev/null && \
	coverage=$$(go tool cover -func=.coverage.core.out | awk '/^total:/{gsub("%","",$$3); print $$3}'); \
	echo "Reverse proxy core coverage: $$coverage%"; \
	awk -v coverage="$$coverage" 'BEGIN { if (coverage < 70) exit 1 }'

frontend-install:
	$(NPM) ci

frontend-build:
	$(NPM) run build

frontend-lint:
	$(NPM) run lint

frontend-test:
	$(NPM) test

poc-test:
	$(PYTHON) -m pytest -q scripts/tests poc/echo-service/tests poc/attack-console/tests

check: backend-test proxy-test proxy-coverage frontend-lint frontend-test poc-test

e2e:
	./scripts/e2e.sh
