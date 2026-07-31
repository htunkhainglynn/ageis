# Aegis Project Guide

This is the canonical working context for the Aegis monorepo. Keep the
Current Build Status and Key Decisions sections synchronized with verified
code and test results.

## Product Scope

Aegis is a centralized API security and management system comprising:

1. `aegis-backend`: FastAPI Control Plane that defines policy.
2. `reverse-proxy`: Go data plane that enforces policy before forwarding.
3. `aegis-frontend`: React dashboard for operators and API consumers.

The Project Proposal at
`/Users/htunkhainglynn/Documents/kmd/Htun_Khaing_Lynn_001557481_Project_Proposal.pdf`
is authoritative for the aim and objectives. `docs/requirements.md` is
authoritative for MoSCoW scope, `docs/domain-model.md` for domain constraints,
and `docs/api-reference.md` for the current HTTP contract.

## Architecture Rules

- The Control Plane defines policy; the reverse proxy enforces it.
- All Control Plane APIs are async and versioned under `/api/v1`.
- Prefer soft deletion for policy/security resources.
- Raw API keys are returned only at creation. Hashes are never returned.
- JWT key material is encrypted at rest and only masked values are returned.
- Admin-only routes enforce authorization through FastAPI dependencies and
  retain service-level checks for defense in depth.
- Never place secrets or encryption keys in source control.

## Current Build Status

Verified on 2026-07-31 against the actual monorepo:

### Implemented and tested

- Control Plane user registration, login, refresh, logout, Redis-backed token
  lifecycle, and user CRUD.
- Persisted `admin`, `viewer`, and `api_consumer` roles with a forward Alembic
  migration, dependency-level RBAC, role-bearing JWTs, and explicit bootstrap
  admin allowlisting.
- API key creation (one-time raw value, bcrypt persistence), metadata CRUD,
  owner/Admin authorization, admin all-key listing, and soft revocation.
- Rate-limit rule CRUD/config validation, one-active-rule-per-scope behavior,
  authenticated reads, and Admin-only writes.
- JWT configuration CRUD, Fernet-encrypted signing keys, masked responses,
  one-active-config behavior, and Admin-only access.
- Manual exact-address IP block CRUD with IPv4/IPv6 canonicalization,
  one-active-block-per-address behavior, soft deletion, Admin-only Control
  Plane access, an Admin-only dashboard page, active-policy distribution, and
  proxy-edge enforcement before credential validation.
- Admin-only threat-rule CRUD/dashboard, RE2-compatible pattern validation,
  active-rule policy distribution, and fail-closed proxy matching against the
  HTTP method plus request path/query before forwarding.
- Sanitized security-event persistence, authenticated internal ingestion,
  time-window analytics summary/history APIs for Admin and Viewer roles, and a
  live traffic/security analytics dashboard. The proxy reports every outcome
  through a bounded non-blocking queue and flushes it during graceful shutdown.
- Authenticated server-streaming gRPC policy synchronization from the Control
  Plane to the proxy, with immediate in-memory updates, REST bootstrap/fallback,
  reconnect backoff, and indefinite enforcement of the last valid snapshot.
- Automatic exact-IP blocking after a configurable number of recent threat or
  rate-limit violations, with system-authored audit metadata, database
  duplicate protection, gRPC distribution, dashboard visibility, and E2E
  enforcement.
- Authenticated internal policy snapshot returning only active JWT validation
  material and active rate-limit rules for the reverse proxy.
- Dashboard login and configuration pages for users, API keys, rate limits,
  JWT configuration, system health, and an analytics placeholder. Navigation
  and route visibility follow the role matrix.
- Go reverse-proxy forwarding core, Control Plane API-key validation client,
  authenticated Control Plane API-key validation contract, local validation
  cache, and API-key middleware unit/integration tests.
- Reverse-proxy JWT validation for HS256/RS256/ES256 with algorithm pinning,
  required expiration, optional issuer/audience enforcement, credential
  stripping, and stale-safe Control Plane policy caching.
- Redis-backed distributed rate limiting with atomic fixed-window,
  sliding-window, and token-bucket scripts, burst support, standard response
  headers, and cross-instance counter tests.
- Reproducible full-stack Docker Compose runtime with generated, ignored
  secrets; idempotent environment-driven Admin bootstrap; and an isolated E2E
  test that exercises Control Plane configuration, proxy API-key/JWT
  enforcement, Redis rate limiting, and forwarding to a real HTTP upstream.

Current checkpoint verification:

- Control Plane: 44 pytest tests pass, none skipped; all migrations apply
  successfully to PostgreSQL.
- Dashboard: lint, production build, and 6 Node tests pass, none skipped.
- Reverse proxy baseline: `go test -race ./...` and `go vet ./...` pass.
- Coverage gates: Control Plane application coverage is 77%; hand-written Go
  enforcement-core coverage is 83.2% (generated protobuf/process wiring
  excluded). Both fail `make check` below 70%.
- Full stack: the isolated `scripts/e2e.sh` test passes against fresh
  PostgreSQL and Redis volumes and real component containers, including
  manual block/unblock behavior for an actual Compose-network client and
  analytics verification for blocks, forwards, and rate limiting.

All Must Have, Should Have, and Could Have requirements in
`docs/requirements.md` are implemented and verified. Only the explicit Won't
Have scope below remains unbuilt.

### Explicitly out of scope

- Non-HTTP protocol support, offline/air-gapped deployment, and a native
  mobile app are Won't Have requirements and are intentionally not built.

## Key Decisions & Rationale

- **Canonical monorepo documentation:** source documents supplied outside the
  repository are mirrored under `docs/`, and this root file replaces the stale
  backend-only status file as the project-wide source of working context.
- **Persisted roles:** authorization roles are stored on `users` instead of
  inferred from transient Python attributes. This makes role checks consistent
  across HTTP requests and token refreshes.
- **Safe registration:** public registration always creates an API Consumer,
  except emails explicitly listed in `BOOTSTRAP_ADMIN_EMAILS`. Administrators
  can subsequently assign roles through protected user management.
- **Rate-limit reads:** the documented API permits any authenticated role to
  read rate-limit rules; create/update/disable operations remain Admin-only.
- **Dashboard runtime:** although early documents say React + Vite + shadcn/ui,
  the existing implementation is React 19 on Vinext/Vite with established
  local UI primitives. Preserve that working structure rather than replacing
  it during feature work.
- **Initial proxy synchronization:** complete and prove REST-backed cached
  policy enforcement first. gRPC remains a Should Have optimization after all
  Must Haves work end-to-end.
- **Authenticated internal contracts:** reverse-proxy REST calls use the
  `X-Aegis-Internal-Token` header with an environment-only shared secret. This
  prevents public use of key-validation and future raw policy-material APIs.
- **Rate-limit matching:** when multiple active scopes match, the proxy uses
  the most specific rule (`api_key`, then exact `route`, then `global`).
  API-key counters are isolated by key ID; route and global scopes represent
  shared traffic buckets as their names imply.
- **Local bootstrap without committed credentials:** Compose generates a
  git-ignored `.env` with cryptographically random secrets and an initial
  Admin password. Bootstrap creates the allowlisted Admin only when absent and
  never resets an existing account, preserving data and operator changes.
- **Isolated integration verification:** the E2E script uses random ports,
  credentials, Compose project names, and disposable volumes so it neither
  depends on nor mutates a developer's normal local stack.
- **IP block address semantics:** manual blocks target one canonical exact IPv4
  or IPv6 address. CIDR ranges are intentionally excluded from the baseline to
  avoid accidental broad lockouts; source is immutable and operator-created
  rows are always marked `manual`.
- **Trusted client address:** the proxy evaluates its direct network peer and
  deliberately ignores `X-Forwarded-For` for block decisions. This prevents a
  caller from evading a block by spoofing a forwarding header. Deployments
  behind another trusted load balancer can add an explicit trusted-proxy model
  later instead of trusting forwarded headers globally.
- **Threat matching surface:** active rules use Go RE2-compatible regular
  expressions over `METHOD path?query`. Bodies and arbitrary headers are not
  inspected, keeping streaming requests intact and avoiding accidental secret
  capture; RE2 provides linear-time matching without backtracking attacks.
- **Analytics data minimization:** security events persist outcome, direct
  source IP, optional API-key/rule IDs, method, path, and status only. They
  never contain raw API keys, JWTs, request bodies, or arbitrary headers.
- **Non-blocking event delivery:** proxy requests enqueue events into a bounded
  in-process channel; a single worker posts them to the authenticated internal
  API. A full queue drops events with a warning instead of delaying protected
  traffic, and graceful shutdown drains queued events.
- **gRPC compatibility and fallback:** protobuf defines a stable authenticated
  streaming RPC carrying the already-versioned policy snapshot as JSON bytes.
  This avoids duplicating every policy field across two serializers. REST
  supplies the initial/fallback snapshot; after the first stream update, a
  disconnect retains the last valid policy and reconnects with backoff.
- **Automatic-block signal:** only `threat_detected` and `rate_limited` events
  count toward the configurable per-source threshold/window. Authentication
  mistakes and upstream errors never trigger lockout. Automatic blocks have no
  human `created_by`, retain `source=auto`, and use the same soft-disable path
  as manual blocks.

## Testing and Checkpoints

- Python: add meaningful coverage and run the entire pytest suite after every
  backend checkpoint.
- Go: keep code gofmt-clean; run `go test -race ./...` and `go vet ./...`.
- Dashboard: run lint, production build, and the complete test suite.
- Coverage: `make check` enforces at least 70% for the Python application and
  hand-written Go core; generated protobuf code is excluded from the core
  metric.
- A checkpoint may be committed only when all relevant tests pass without
  failures or skips. Commit messages must name the feature and passing checks.
