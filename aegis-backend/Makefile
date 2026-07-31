PYTHON ?= python3
APP_MODULE ?= app.main:app
HOST ?= 0.0.0.0
PORT ?= 8000

.PHONY: help install run dev test test-api-keys migrate makemigration downgrade current history

help:
	@echo "Available commands:"
	@echo "  make install                         Install dependencies"
	@echo "  make run                             Run API (no reload)"
	@echo "  make dev                             Run API with reload"
	@echo "  make test                            Run all tests"
	@echo "  make test-api-keys                   Run API key tests only"
	@echo "  make migrate                         Apply all migrations"
	@echo "  make makemigration m=\"message\"      Create migration"
	@echo "  make downgrade rev=-1                Downgrade migration"
	@echo "  make current                         Show current revision"
	@echo "  make history                         Show migration history"

install:
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) -m uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT)

dev:
	$(PYTHON) -m uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT) --reload

test:
	$(PYTHON) -m pytest -q

test-api-keys:
	$(PYTHON) -m pytest -q tests/test_api_keys.py

migrate:
	$(PYTHON) -m alembic upgrade head

makemigration:
	@if [ -z "$(m)" ]; then echo "Usage: make makemigration m=\"your message\""; exit 1; fi
	$(PYTHON) -m alembic revision --autogenerate -m "$(m)"

downgrade:
	@if [ -z "$(rev)" ]; then echo "Usage: make downgrade rev=-1"; exit 1; fi
	$(PYTHON) -m alembic downgrade $(rev)

current:
	$(PYTHON) -m alembic current

history:
	$(PYTHON) -m alembic history
