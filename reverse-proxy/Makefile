GO ?= go

.DEFAULT_GOAL := help

.PHONY: help run fmt test race vet check

help:
	@echo "Available commands:"
	@echo "  make run    Run the reverse proxy"
	@echo "  make fmt    Format Go source"
	@echo "  make test   Run unit tests"
	@echo "  make race   Run tests with the race detector"
	@echo "  make vet    Run Go static analysis"
	@echo "  make check  Run formatting, race tests, and vet"

run:
	$(GO) run ./cmd/proxy

fmt:
	$(GO) fmt ./...

test:
	$(GO) test ./...

race:
	$(GO) test -race ./...

vet:
	$(GO) vet ./...

check: fmt race vet
