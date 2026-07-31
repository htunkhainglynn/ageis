# AGENT.md — Aegis: API Security and Management System

This file gives AI coding agents (Windsurf, Cursor, etc.) persistent context on
this project so it doesn't need to be re-explained in every prompt.

## Project Overview

Aegis is a centralized API security and management system (university project).
It places a secure, high-performance reverse proxy in front of existing backend
services, with a control plane for configuration and a dashboard for monitoring.
No changes to existing backend services are required to adopt it.

## Architecture — Three Components

1. **Control Plane** (`/control-plane`) — Python 3 / FastAPI. Async REST API for
   configuration, key management, and rule management. This is where most
   current work happens.
2. **Reverse Proxy / Data Plane** (`/proxy`) — Go. High-throughput request
   validation layer: enforces rules the Control Plane defines. NOT YET STARTED.
3. **Dashboard** (`/dashboard`) — React + Vite. Admin UI for configuration and
   monitoring. NOT YET STARTED.

**Golden rule:** the Control Plane *defines* policy (rules, config, keys). The
Reverse Proxy *enforces* it. Never implement enforcement logic (rate limiting,
token validation, blocking) inside the Control Plane — that belongs to the Go
proxy and is out of scope for any Control Plane task unless explicitly stated.

## Tech Stack

| Layer | Technology |
|---|---|
| Control Plane | Python, FastAPI (async), SQLAlchemy, Alembic, Pydantic |
| Data Plane | Go, `net/http/httputil`, `go-redis/v9`, `google.golang.org/grpc` |
| Dashboard | React, Vite, shadcn/ui |
| Database | PostgreSQL |
| Cache / Rate Limiting store | Redis |
| Config Sync | gRPC (Control Plane ⇄ Proxy) |
| Testing | pytest (Python), `testing` package (Go), Vitest/Jest (React) |

## Current Build Status (update this section as work progresses)

**Done (Control Plane):**
- User APIs — registration, login/refresh/logout, JWT auth, Redis session/token
  revocation, user CRUD
- API Key Management — generate (bcrypt-hashed, shown once), list/get/update
  (metadata only, never re-exposes raw key or hash), soft-revoke, ownership +
  Admin checks
- Rate Limit Rule Configuration — CRUD for rules (scope: global/api_key/route),
  single-active-rule-per-scope constraint, Admin-only writes, general read access

**In progress / next:**
- JWT Configuration Management — encrypted signing key storage (Fernet), single
  active config, Admin-only on all endpoints (not just writes)

**Not started:**
- Go Reverse Proxy (proxy core, key validation, distributed rate limiter, JWT
  validation, threat pattern matcher, gRPC client)
- gRPC server (Control Plane side) for streaming config to the proxy
- Threat detection rule config, IP blocking rules
- React Dashboard (all pages)
- Metrics/analytics endpoints

## Conventions — Follow These Consistently

**API design:**
- All endpoints async, versioned under `/api/v1/`
- Every write endpoint enforces ownership or Admin-role checks explicitly —
  never rely on implicit filtering alone
- Soft delete by default (`status = revoked/disabled`), not hard deletes, so
  audit trails and in-flight proxy configs aren't broken mid-sync
- Pydantic response schemas must never leak secrets: raw API keys, key hashes,
  or JWT signing/public keys are shown once (creation) or masked, never again

**Data layer:**
- One Alembic migration per feature, `down_revision` chained correctly
- FK constraints declared explicitly (see `api_keys.owner_id -> users.id`)
- Index any column used in lookups or filters (`key_prefix`, `owner_id`, `status`)

**Security defaults:**
- Passwords: bcrypt. API keys: bcrypt. JWT signing keys: encrypted at rest
  (Fernet, key from env var, never hardcoded)
- Admin-only endpoints must check role at the dependency-injection level, not
  ad-hoc inside handlers

**Testing:**
- Every feature ships with pytest coverage for: happy path, ownership/Admin
  enforcement, and at least one edge case (duplicate/invalid state)

## Working With This Codebase

- **Ask before modifying existing files** outside the current task's scope —
  especially User APIs, API Key, and Rate Limit modules, which are stable.
- Match the folder structure, error handling, and auth dependency patterns of
  whichever existing module is most similar to the current task.
- When a task is Control-Plane-only (most tasks currently are), do not
  scaffold Go or React code unless explicitly asked.
